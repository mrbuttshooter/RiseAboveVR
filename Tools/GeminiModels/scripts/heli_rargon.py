import bpy
import bmesh
import math
import sys
import os
from mathutils import Vector, Matrix


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh, do_unlink=True)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat, do_unlink=True)
    for light in list(bpy.data.lights):
        bpy.data.lights.remove(light, do_unlink=True)
    for cam in list(bpy.data.cameras):
        bpy.data.cameras.remove(cam, do_unlink=True)


def clamp01(val):
    return max(0.0, min(1.0, float(val)))


def make_material(name, color, roughness=0.45, metallic=0.0, coat=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = None
    for n in nodes:
        if n.type == 'BSDF_PRINCIPLED':
            bsdf = n
            break
    if bsdf is None:
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    if 'Base Color' in bsdf.inputs:
        bsdf.inputs['Base Color'].default_value = (color[0], color[1], color[2], 1.0)
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = roughness
    if 'Metallic' in bsdf.inputs:
        bsdf.inputs['Metallic'].default_value = metallic
    if coat > 0.0 and 'Coat Weight' in bsdf.inputs:
        bsdf.inputs['Coat Weight'].default_value = coat
    mat.diffuse_color = (color[0], color[1], color[2], 1.0)
    return mat


def get_crease_layer(bm):
    layer = bm.edges.layers.float.get("crease_edge")
    if layer is None:
        try:
            layer = bm.edges.layers.crease.verify()
        except AttributeError:
            layer = bm.edges.layers.float.new("crease_edge")
    return layer


def mark_region_boundary_crease(bm, faces, crease_val=0.75):
    crease_layer = get_crease_layer(bm)
    face_set = set(faces)
    for f in face_set:
        for e in f.edges:
            linked_in = sum(1 for lf in e.link_faces if lf in face_set)
            if linked_in == 1:
                e[crease_layer] = max(e[crease_layer], crease_val)


def add_lofted_tube(bm, rings_pts, mat_idx=0, cap_start=True, cap_end=True, crease_caps=False):
    n_seg = len(rings_pts[0])
    vert_rings = []
    for ring in rings_pts:
        v_ring = [bm.verts.new(co) for co in ring]
        vert_rings.append(v_ring)

    created_faces = []
    for r_idx in range(len(vert_rings) - 1):
        r0 = vert_rings[r_idx]
        r1 = vert_rings[r_idx + 1]
        for i in range(n_seg):
            ni = (i + 1) % n_seg
            try:
                f = bm.faces.new((r0[i], r0[ni], r1[ni], r1[i]))
                f.material_index = mat_idx
                f.smooth = True
                created_faces.append(f)
            except ValueError:
                pass

    crease_layer = get_crease_layer(bm)
    if cap_start:
        c0 = Vector((0.0, 0.0, 0.0))
        for v in vert_rings[0]:
            c0 += v.co
        c0 /= max(1, len(vert_rings[0]))
        vc0 = bm.verts.new(c0)
        for i in range(n_seg):
            ni = (i + 1) % n_seg
            try:
                f = bm.faces.new((vert_rings[0][ni], vert_rings[0][i], vc0))
                f.material_index = mat_idx
                f.smooth = True
                created_faces.append(f)
            except ValueError:
                pass
        if crease_caps:
            for i in range(n_seg):
                ni = (i + 1) % n_seg
                e = bm.edges.get((vert_rings[0][i], vert_rings[0][ni]))
                if e is not None:
                    e[crease_layer] = 0.65

    if cap_end:
        c1 = Vector((0.0, 0.0, 0.0))
        for v in vert_rings[-1]:
            c1 += v.co
        c1 /= max(1, len(vert_rings[-1]))
        vc1 = bm.verts.new(c1)
        for i in range(n_seg):
            ni = (i + 1) % n_seg
            try:
                f = bm.faces.new((vert_rings[-1][i], vert_rings[-1][ni], vc1))
                f.material_index = mat_idx
                f.smooth = True
                created_faces.append(f)
            except ValueError:
                pass
        if crease_caps:
            for i in range(n_seg):
                ni = (i + 1) % n_seg
                e = bm.edges.get((vert_rings[-1][i], vert_rings[-1][ni]))
                if e is not None:
                    e[crease_layer] = 0.65

    return vert_rings, created_faces


def build_fuselage_and_boom(bm, mat_map):
    idx_red = mat_map['red']
    idx_white = mat_map['white']
    idx_glass = mat_map['glass']
    idx_dark = mat_map['dark']

    # Stations: (y, z_bot, z_top, half_w, top_narrow, bot_flat)
    # Nose tip at Y = -3.90, tail boom end at Y = +5.80
    stations = [
        (-3.90, 0.96, 1.14, 0.14, 0.05, 0.05),  # 0: nose cap ring
        (-3.72, 0.80, 1.44, 0.48, 0.12, 0.12),  # 1: front nose wrap
        (-3.38, 0.68, 1.72, 0.80, 0.16, 0.18),  # 2: lower windshield / chin start
        (-2.92, 0.63, 1.95, 1.00, 0.18, 0.22),  # 3: mid windshield
        (-2.44, 0.60, 2.10, 1.12, 0.18, 0.25),  # 4: windshield rear edge
        (-2.26, 0.60, 2.13, 1.14, 0.17, 0.25),  # 5: A-pillar / front door start
        (-1.68, 0.59, 2.16, 1.18, 0.16, 0.26),  # 6: mid front door
        (-1.14, 0.59, 2.16, 1.18, 0.16, 0.26),  # 7: front door rear edge
        (-0.96, 0.60, 2.16, 1.16, 0.16, 0.25),  # 8: B-pillar / rear window start
        (-0.48, 0.61, 2.15, 1.13, 0.16, 0.24),  # 9: mid passenger cabin
        (-0.04, 0.64, 2.12, 1.05, 0.15, 0.22),  # 10: rear window rear edge
        (0.48,  0.76, 2.05, 0.86, 0.12, 0.16),  # 11: rear cabin taper
        (1.08,  1.06, 1.95, 0.54, 0.08, 0.08),  # 12: tail boom transition
        (1.75,  1.38, 1.91, 0.31, 0.03, 0.03),  # 13: tail boom root
        (2.75,  1.49, 1.92, 0.25, 0.02, 0.02),  # 14: tail boom mid-front
        (3.85,  1.59, 1.93, 0.20, 0.01, 0.01),  # 15: tail boom at horizontal stab
        (4.85,  1.67, 1.94, 0.16, 0.00, 0.00),  # 16: tail boom at vertical fin root
        (5.65,  1.73, 1.94, 0.12, 0.00, 0.00),  # 17: tail boom rear
        (5.82,  1.78, 1.88, 0.05, 0.00, 0.00),  # 18: tail cone tip
    ]

    n_ring = 20
    vert_rings = []
    for (y, z_bot, z_top, half_w, top_narrow, bot_flat) in stations:
        z_mid = 0.5 * (z_bot + z_top)
        half_h = 0.5 * (z_top - z_bot)
        ring = []
        for i in range(n_ring):
            theta = (i / float(n_ring)) * 2.0 * math.pi
            s_th = math.sin(theta)
            c_th = math.cos(theta)
            if c_th >= 0.0:
                w_scale = 1.0 - top_narrow * (clamp01(c_th) ** 1.25)
                z_norm = c_th
            else:
                w_scale = 1.0 + 0.06 * (1.0 - (clamp01(-c_th) ** 1.6))
                z_norm = -((clamp01(-c_th)) ** (1.0 - 0.32 * bot_flat))

            # Nudge center windshield post (i=1 and i=19) closer to X=0 on windshield stations
            if y < -2.35 and (i == 1 or i == n_ring - 1):
                s_th *= 0.42

            x = half_w * w_scale * s_th
            z = z_mid + half_h * z_norm
            ring.append(bm.verts.new((x, y, z)))
        vert_rings.append(ring)

    grid_faces = {}
    for s in range(len(stations) - 1):
        r0 = vert_rings[s]
        r1 = vert_rings[s + 1]
        for i in range(n_ring):
            ni = (i + 1) % n_ring
            f = bm.faces.new((r0[i], r0[ni], r1[ni], r1[i]))
            f.material_index = idx_red
            f.smooth = True
            grid_faces[(s, i)] = f

    # Nose cap and tail cone cap
    vc_nose = bm.verts.new((0.0, -3.95, 1.05))
    for i in range(n_ring):
        ni = (i + 1) % n_ring
        f = bm.faces.new((vert_rings[0][ni], vert_rings[0][i], vc_nose))
        f.material_index = idx_red
        f.smooth = True

    vc_tail = bm.verts.new((0.0, 5.88, 1.83))
    for i in range(n_ring):
        ni = (i + 1) % n_ring
        f = bm.faces.new((vert_rings[-1][i], vert_rings[-1][ni], vc_tail))
        f.material_index = idx_dark
        f.smooth = True

    # White livery stripe: wraps across the nose at s=1 (i=6..13) and runs down both sides s=2..16 (i=6 and i=13)
    stripe_faces = []
    for i in range(6, 14):
        stripe_faces.append(grid_faces[(1, i)])
    for s in range(2, 17):
        stripe_faces.append(grid_faces[(s, 6)])
        stripe_faces.append(grid_faces[(s, 13)])

    # Upper white roof crown on cabin/transition: s=4..12, i=0 and i=19
    crown_faces = []
    for s in range(4, 13):
        crown_faces.append(grid_faces[(s, 0)])
        crown_faces.append(grid_faces[(s, 19)])

    for f in stripe_faces + crown_faces:
        f.material_index = idx_white

    bmesh.ops.inset_region(
        bm,
        faces=stripe_faces,
        use_boundary=True,
        use_even_offset=True,
        thickness=0.012,
        depth=0.002
    )
    mark_region_boundary_crease(bm, stripe_faces, 0.75)

    bmesh.ops.inset_region(
        bm,
        faces=crown_faces,
        use_boundary=True,
        use_even_offset=True,
        thickness=0.012,
        depth=0.002
    )
    mark_region_boundary_crease(bm, crown_faces, 0.70)

    # 8 distinct window groups:
    # 1-2: Right & Left Panoramic Front Windshields (s=1..3, i=1..4 right, i=15..18 left)
    # 3-4: Right & Left Chin Bubble Windows (s=2..3, i=7..8 right, i=11..12 left)
    # 5-6: Right & Left Front Door Windows (s=5..6, i=1..4 right, i=15..18 left)
    # 7-8: Right & Left Rear Cabin Windows (s=8..9, i=1..4 right, i=15..18 left)
    window_groups = [
        [grid_faces[(s, i)] for s in (1, 2, 3) for i in (1, 2, 3, 4)],
        [grid_faces[(s, i)] for s in (1, 2, 3) for i in (15, 16, 17, 18)],
        [grid_faces[(s, i)] for s in (2, 3) for i in (7, 8)],
        [grid_faces[(s, i)] for s in (2, 3) for i in (11, 12)],
        [grid_faces[(s, i)] for s in (5, 6) for i in (1, 2, 3, 4)],
        [grid_faces[(s, i)] for s in (5, 6) for i in (15, 16, 17, 18)],
        [grid_faces[(s, i)] for s in (8, 9) for i in (1, 2, 3, 4)],
        [grid_faces[(s, i)] for s in (8, 9) for i in (15, 16, 17, 18)],
    ]

    for w_faces in window_groups:
        res = bmesh.ops.inset_region(
            bm,
            faces=w_faces,
            use_boundary=True,
            use_even_offset=True,
            thickness=0.026,
            depth=-0.012
        )
        for f in w_faces:
            f.material_index = idx_glass
        for f in res.get('faces', []):
            f.material_index = idx_dark
        mark_region_boundary_crease(bm, w_faces, 0.85)


def build_engine_and_mast(bm, mat_map):
    idx_red = mat_map['red']
    idx_white = mat_map['white']
    idx_dark = mat_map['dark']

    # Sculpted turboshaft engine housing on top of cabin roof (embedded down to Z=1.92 inside cabin)
    # Stations: (y, z_bot, z_top, half_w)
    eng_stations = [
        (-1.45, 1.92, 2.22, 0.28),
        (-1.25, 1.92, 2.52, 0.52),
        (-0.55, 1.92, 2.62, 0.58),
        (0.35,  1.90, 2.58, 0.52),
        (1.15,  1.86, 2.46, 0.38),
        (1.85,  1.78, 2.15, 0.20),
    ]
    n_seg = 12
    rings = []
    for (y, z_b, z_t, hw) in eng_stations:
        z_m = 0.5 * (z_b + z_t)
        hh = 0.5 * (z_t - z_b)
        ring = []
        for i in range(n_seg):
            th = (i / float(n_seg)) * 2.0 * math.pi
            x = hw * math.sin(th) * (0.85 if math.cos(th) > 0 else 1.0)
            z = z_m + hh * math.cos(th)
            ring.append(Vector((x, y, z)))
        rings.append(ring)

    v_rings, e_faces = add_lofted_tube(bm, rings, mat_idx=idx_white, cap_start=True, cap_end=True, crease_caps=True)

    # Paint top spine of engine cowling red and front air intake face dark metal
    for r_idx in range(len(v_rings) - 1):
        for i in (0, 1, 10, 11):
            # Upper top strips
            pass
    for f in e_faces:
        c = f.calc_center_median()
        if c.y < -1.36 and c.z > 2.05:
            f.material_index = idx_dark
        elif c.z > 2.42 and abs(c.x) < 0.32:
            f.material_index = idx_red

    # Exhaust pipe emerging from rear of engine cowling (embedded from Y=1.10 to Y=2.08)
    ex_stations = [
        (1.05, 2.24, 0.17),
        (1.55, 2.30, 0.18),
        (2.05, 2.36, 0.16),
        (2.05, 2.36, 0.12),
        (1.65, 2.31, 0.12),
    ]
    ex_rings = []
    for (y, z_c, rad) in ex_stations:
        ring = []
        for i in range(10):
            th = (i / 10.0) * 2.0 * math.pi
            ring.append(Vector((rad * 1.15 * math.sin(th), y, z_c + rad * math.cos(th))))
        ex_rings.append(ring)
    add_lofted_tube(bm, ex_rings, mat_idx=idx_dark, cap_start=False, cap_end=True, crease_caps=True)

    # Rotor mast housing and shaft centered at X=0.0, Y=-0.50
    # Embeds inside engine housing at Z=2.38 and reaches Z=3.06 (inside MainRotor hub at Z=3.02)
    mast_stations = [
        (2.38, 0.30),
        (2.68, 0.25),
        (2.74, 0.14),
        (2.96, 0.13),
        (3.06, 0.12),
    ]
    mast_rings = []
    for (z_h, rad) in mast_stations:
        ring = []
        for i in range(12):
            th = (i / 12.0) * 2.0 * math.pi
            ring.append(Vector((rad * math.cos(th), -0.50 + rad * math.sin(th), z_h)))
        mast_rings.append(ring)
    add_lofted_tube(bm, mast_rings, mat_idx=idx_dark, cap_start=False, cap_end=True, crease_caps=True)


def build_tail_surfaces(bm, mat_map):
    idx_red = mat_map['red']
    idx_white = mat_map['white']
    idx_dark = mat_map['dark']
    idx_yellow = mat_map['yellow']

    # Swept vertical fin (ventral fin Z=1.08 through tail boom Z=1.82 up to upper fin tip Z=3.12)
    # Stations: (z, y_lead, y_trail, half_thick)
    vfin_stations = [
        (1.08, 5.38, 5.76, 0.035),
        (1.42, 5.05, 5.72, 0.055),
        (1.80, 4.72, 5.75, 0.095),
        (2.15, 4.88, 5.84, 0.075),
        (2.55, 5.15, 5.96, 0.060),
        (2.85, 5.36, 6.04, 0.048),
        (3.12, 5.56, 6.10, 0.032),
    ]
    # Airfoil profile around 10 points
    prof_u = [0.0, 0.22, 0.55, 0.85, 1.0, 0.85, 0.55, 0.22]
    prof_x = [0.0, 0.78, 1.00, 0.62, 0.0, -0.62, -1.00, -0.78]

    vfin_rings = []
    for (z_h, y_l, y_t, ht) in vfin_stations:
        chord = y_t - y_l
        ring = []
        for u, sx in zip(prof_u, prof_x):
            ring.append(Vector((ht * sx, y_l + chord * u, z_h)))
        vfin_rings.append(ring)

    _, vf_faces = add_lofted_tube(bm, vfin_rings, mat_idx=idx_red, cap_start=True, cap_end=True, crease_caps=True)
    white_fin_faces = []
    for f in vf_faces:
        cz = f.calc_center_median().z
        if 2.30 <= cz <= 2.75:
            f.material_index = idx_white
            white_fin_faces.append(f)
        elif cz < 1.28:
            f.material_index = idx_yellow
    if white_fin_faces:
        mark_region_boundary_crease(bm, white_fin_faces, 0.75)

    # Tail rotor gearbox fairing & shaft on left side (-X) at Y=5.55, Z=2.02
    # Extends from X=+0.02 (inside fin) to X=-0.30 (embedded inside TailRotor hub at X=-0.26)
    gb_stations = [
        (0.02, 0.12),
        (-0.14, 0.10),
        (-0.20, 0.055),
        (-0.30, 0.050),
    ]
    gb_rings = []
    for (x_pos, rad) in gb_stations:
        ring = []
        for i in range(10):
            th = (i / 10.0) * 2.0 * math.pi
            ring.append(Vector((x_pos, 5.55 + rad * math.cos(th), 2.02 + rad * math.sin(th))))
        gb_rings.append(ring)
    add_lofted_tube(bm, gb_rings, mat_idx=idx_dark, cap_start=False, cap_end=True, crease_caps=True)

    # Horizontal stabilizer across tail boom at Y=3.85, Z=1.76 (spans X = -1.05 to +1.05)
    hstab_x = [-1.05, -0.65, -0.15, 0.15, 0.65, 1.05]
    hstab_rings = []
    for x_pos in hstab_x:
        taper = 1.0 - 0.25 * abs(x_pos) / 1.05
        y_l = 3.65 + 0.06 * abs(x_pos)
        chord = 0.46 * taper
        ht = 0.042 * taper
        ring = []
        for u, sz in zip(prof_u, prof_x):
            ring.append(Vector((x_pos, y_l + chord * u, 1.76 + ht * sz)))
        hstab_rings.append(ring)
    add_lofted_tube(bm, hstab_rings, mat_idx=idx_red, cap_start=True, cap_end=True, crease_caps=True)

    # Endplate finlets at X = -1.03 and X = +1.03 (embedded into horizontal stabilizer tips)
    for side in (-1.0, 1.0):
        x_base = side * 1.03
        ep_stations = [
            (1.56, 3.76, 4.10, 0.022),
            (1.76, 3.68, 4.14, 0.032),
            (2.02, 3.78, 4.12, 0.022),
        ]
        ep_rings = []
        for (z_h, y_l, y_t, ht) in ep_stations:
            chord = y_t - y_l
            ring = []
            for u, sx in zip(prof_u, prof_x):
                ring.append(Vector((x_base + ht * sx, y_l + chord * u, z_h)))
            ep_rings.append(ring)
        add_lofted_tube(bm, ep_rings, mat_idx=idx_white, cap_start=True, cap_end=True, crease_caps=True)


def build_skids_and_details(bm, mat_map):
    idx_dark = mat_map['dark']
    idx_white = mat_map['white']
    idx_glass = mat_map['glass']
    idx_red = mat_map['red']

    # Two longitudinal landing skids at X = ±1.05, bottom resting at Z = 0.00
    # Skid tube radius = 0.062 m, center Z = 0.062 m
    skid_pts = [
        (-3.48, 0.34, 0.042),
        (-3.32, 0.16, 0.055),
        (-3.08, 0.062, 0.062),
        (-2.05, 0.062, 0.064),
        (-1.15, 0.062, 0.062),
        (-0.25, 0.062, 0.064),
        (0.75,  0.062, 0.062),
        (0.92,  0.085, 0.048),
    ]
    for side in (-1.0, 1.0):
        x_skid = side * 1.05
        rings = []
        for (y_p, z_p, rad) in skid_pts:
            ring = []
            for i in range(8):
                th = (i / 8.0) * 2.0 * math.pi
                ring.append(Vector((x_skid + rad * math.sin(th), y_p, z_p + rad * math.cos(th))))
            rings.append(ring)
        add_lofted_tube(bm, rings, mat_idx=idx_dark, cap_start=True, cap_end=True, crease_caps=True)

    # Two continuous arched cross-tube struts at Y = -2.05 (front) and Y = -0.25 (rear)
    # Each starts embedded inside Left Skid (X=-1.05, Z=0.04), rises into belly (X=±0.54, Z=0.76), down to Right Skid
    arch_nodes = [
        (-1.05, 0.04, 0.072),
        (-1.05, 0.13, 0.065),
        (-0.94, 0.36, 0.052),
        (-0.75, 0.62, 0.056),
        (-0.52, 0.78, 0.072),
        (0.00,  0.82, 0.065),
        (0.52,  0.78, 0.072),
        (0.75,  0.62, 0.056),
        (0.94,  0.36, 0.052),
        (1.05,  0.13, 0.065),
        (1.05,  0.04, 0.072),
    ]
    for y_strut in (-2.05, -0.25):
        s_rings = []
        for idx_n, (x_p, z_p, rad) in enumerate(arch_nodes):
            if idx_n == 0:
                tx, tz = arch_nodes[1][0] - x_p, arch_nodes[1][1] - z_p
            elif idx_n == len(arch_nodes) - 1:
                tx, tz = x_p - arch_nodes[-2][0], z_p - arch_nodes[-2][1]
            else:
                tx = arch_nodes[idx_n + 1][0] - arch_nodes[idx_n - 1][0]
                tz = arch_nodes[idx_n + 1][1] - arch_nodes[idx_n - 1][1]
            t_len = max(1e-6, math.hypot(tx, tz))
            nx, nz = -tz / t_len, tx / t_len
            ring = []
            for i in range(8):
                th = (i / 8.0) * 2.0 * math.pi
                c_t, s_t = math.cos(th), math.sin(th)
                px = x_p + rad * c_t * nx
                py = y_strut + rad * s_t
                pz = z_p + rad * c_t * nz
                ring.append(Vector((px, py, pz)))
            s_rings.append(ring)
        add_lofted_tube(bm, s_rings, mat_idx=idx_dark, cap_start=True, cap_end=True, crease_caps=True)

    # Cabin entry step bars connecting between front and rear struts at X = ±0.93, Z = 0.36
    for side in (-1.0, 1.0):
        x_step = side * 0.93
        step_rings = []
        for y_p in (-2.08, -1.75, -0.55, -0.22):
            ring = []
            for i in range(6):
                th = (i / 6.0) * 2.0 * math.pi
                ring.append(Vector((x_step + 0.045 * math.sin(th), y_p, 0.36 + 0.025 * math.cos(th))))
            step_rings.append(ring)
        add_lofted_tube(bm, step_rings, mat_idx=idx_dark, cap_start=True, cap_end=True, crease_caps=True)

    # Stylized News ENG Chin Camera Gimbal (FLIR turret) under nose at X=0.0, Y=-3.38
    # Pylon embedded into nose belly at Z=0.76 down to gimbal sphere centered at Z=0.46
    flir_stations = [
        (-3.38, 0.78, 0.14),
        (-3.38, 0.62, 0.12),
        (-3.38, 0.56, 0.17),
        (-3.38, 0.45, 0.21),
        (-3.38, 0.34, 0.17),
        (-3.38, 0.27, 0.08),
    ]
    flir_rings = []
    for (y_c, z_h, rad) in flir_stations:
        ring = []
        for i in range(10):
            th = (i / 10.0) * 2.0 * math.pi
            ring.append(Vector((rad * math.sin(th), y_c - rad * math.cos(th), z_h)))
        flir_rings.append(ring)
    _, flir_faces = add_lofted_tube(bm, flir_rings, mat_idx=idx_white, cap_start=False, cap_end=True, crease_caps=True)
    for f in flir_faces:
        c = f.calc_center_median()
        if c.z > 0.57:
            f.material_index = idx_dark
        elif c.y < -3.50 and 0.36 <= c.z <= 0.55:
            f.material_index = idx_glass


def create_main_rotor(materials, mat_map, hub_loc):
    bm = bmesh.new()
    idx_dark = mat_map['dark']
    idx_blade = mat_map['blade']
    idx_yellow = mat_map['yellow']
    idx_white = mat_map['white']

    # Central rotor hub centered at local (0, 0, 0), rotation axis = local Z
    # Extends down to Z = -0.08 (embedding 12 cm into Body rotor mast) and up to Z = +0.16
    hub_stations = [
        (-0.08, 0.15),
        (-0.02, 0.28),
        (0.05,  0.30),
        (0.11,  0.22),
        (0.16,  0.09),
    ]
    hub_rings = []
    for (z_h, rad) in hub_stations:
        ring = []
        for i in range(12):
            th = (i / 12.0) * 2.0 * math.pi
            ring.append(Vector((rad * math.cos(th), rad * math.sin(th), z_h)))
        hub_rings.append(ring)
    add_lofted_tube(bm, hub_rings, mat_idx=idx_dark, cap_start=True, cap_end=True, crease_caps=True)

    # 4 long thin airfoil blades: 10.0 m diameter -> radius = 5.05 m pre-subsurf (~5.00 m post-subsurf)
    # Placed at 45, 135, 225, 315 degrees around Z so they frame compactly in 3/4 view
    prof_u = [-0.45, -0.20, 0.15, 0.55, 0.15, -0.20]
    prof_z = [0.00,   0.58, 0.45, 0.00, -0.32, -0.42]
    pitch_rad = math.radians(7.0)
    cp, sp = math.cos(pitch_rad), math.sin(pitch_rad)

    # Radial stations: (r, chord, thickness)
    blade_stations = [
        (0.18, 0.16, 0.095),  # Embedded inside central hub
        (0.55, 0.22, 0.080),  # Blade grip cuff
        (0.75, 0.34, 0.052),  # Blade root airfoil
        (2.45, 0.34, 0.046),  # Mid blade
        (4.38, 0.33, 0.042),  # Color border start
        (4.45, 0.33, 0.040),  # Yellow tip start
        (5.03, 0.26, 0.028),  # Blade tip (10 m total diameter)
    ]

    for b_idx in range(4):
        ang = math.radians(45.0 + b_idx * 90.0)
        ca, sa = math.cos(ang), math.sin(ang)
        b_rings = []
        for (r_dist, chord, thick) in blade_stations:
            ring = []
            for u, sz in zip(prof_u, prof_z):
                lx = u * chord
                lz = sz * thick
                # Apply collective pitch
                px = lx * cp - lz * sp
                pz = lx * sp + lz * cp + 0.015
                # Rotate blade radial axis (local Y -> angle ang)
                wx = r_dist * ca - px * sa
                wy = r_dist * sa + px * ca
                wz = pz
                ring.append(Vector((wx, wy, wz)))
            b_rings.append(ring)
        _, b_faces = add_lofted_tube(bm, b_rings, mat_idx=idx_blade, cap_start=True, cap_end=True, crease_caps=True)
        tip_faces = []
        for f in b_faces:
            c = f.calc_center_median()
            r_c = math.hypot(c.x, c.y)
            if r_c < 0.68:
                f.material_index = idx_dark
            elif r_c > 4.41:
                f.material_index = idx_yellow
                tip_faces.append(f)
        if tip_faces:
            mark_region_boundary_crease(bm, tip_faces, 0.80)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("MainRotor")
    bm.to_mesh(mesh)
    bm.free()

    for mat in materials:
        mesh.materials.append(mat)
    for p in mesh.polygons:
        p.use_smooth = True

    obj = bpy.data.objects.new("MainRotor", mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = hub_loc

    mod = obj.modifiers.new("Subsurf", 'SUBSURF')
    mod.levels = 1
    mod.render_levels = 1
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)

    for p in obj.data.polygons:
        p.use_smooth = True

    return obj


def create_tail_rotor(materials, mat_map, hub_loc):
    bm = bmesh.new()
    idx_dark = mat_map['dark']
    idx_blade = mat_map['blade']
    idx_yellow = mat_map['yellow']

    # Central tail rotor hub centered at local (0, 0, 0), rotation axis = local X
    # Spans X = -0.07 to X = +0.08 (overlapping gearbox shaft on Body)
    hub_stations = [
        (0.08,  0.075),
        (0.02,  0.105),
        (-0.04, 0.095),
        (-0.08, 0.055),
    ]
    hub_rings = []
    for (x_p, rad) in hub_stations:
        ring = []
        for i in range(10):
            th = (i / 10.0) * 2.0 * math.pi
            ring.append(Vector((x_p, rad * math.cos(th), rad * math.sin(th))))
        hub_rings.append(ring)
    add_lofted_tube(bm, hub_rings, mat_idx=idx_dark, cap_start=True, cap_end=True, crease_caps=True)

    # 2 opposing blades spinning in YZ plane around local X axis (1.4 m diameter -> radius = 0.71 m)
    prof_u = [-0.45, -0.15, 0.25, 0.55, 0.25, -0.15]
    prof_x = [0.00,   0.55, 0.42, 0.00, -0.35, -0.42]

    t_stations = [
        (0.06, 0.11, 0.040),
        (0.16, 0.15, 0.032),
        (0.50, 0.15, 0.028),
        (0.54, 0.15, 0.026),
        (0.71, 0.13, 0.020),
    ]

    for b_idx in range(2):
        ang = math.radians(25.0 + b_idx * 180.0)
        ca, sa = math.cos(ang), math.sin(ang)
        b_rings = []
        for (r_dist, chord, thick) in t_stations:
            ring = []
            for u, sx in zip(prof_u, prof_x):
                ly = u * chord
                lx = sx * thick
                wy = r_dist * ca - ly * sa
                wz = r_dist * sa + ly * ca
                ring.append(Vector((lx, wy, wz)))
            b_rings.append(ring)
        _, b_faces = add_lofted_tube(bm, b_rings, mat_idx=idx_blade, cap_start=True, cap_end=True, crease_caps=True)
        tip_faces = []
        for f in b_faces:
            c = f.calc_center_median()
            r_c = math.hypot(c.y, c.z)
            if r_c < 0.14:
                f.material_index = idx_dark
            elif r_c > 0.52:
                f.material_index = idx_yellow
                tip_faces.append(f)
        if tip_faces:
            mark_region_boundary_crease(bm, tip_faces, 0.80)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("TailRotor")
    bm.to_mesh(mesh)
    bm.free()

    for mat in materials:
        mesh.materials.append(mat)
    for p in mesh.polygons:
        p.use_smooth = True

    obj = bpy.data.objects.new("TailRotor", mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = hub_loc

    mod = obj.modifiers.new("Subsurf", 'SUBSURF')
    mod.levels = 1
    mod.render_levels = 1
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)

    for p in obj.data.polygons:
        p.use_smooth = True

    return obj


def build_helicopter():
    clear_scene()

    mat_red = make_material("Mat_Red", (0.84, 0.06, 0.06), roughness=0.42, metallic=0.05)
    mat_white = make_material("Mat_White", (0.95, 0.95, 0.96), roughness=0.42, metallic=0.05)
    mat_glass = make_material("Mat_Glass", (0.06, 0.12, 0.19), roughness=0.10, metallic=0.15, coat=0.60)
    mat_dark = make_material("Mat_DarkMetal", (0.14, 0.15, 0.17), roughness=0.45, metallic=0.55)
    mat_blade = make_material("Mat_Blade", (0.19, 0.21, 0.23), roughness=0.44, metallic=0.30)
    mat_yellow = make_material("Mat_Yellow", (0.96, 0.72, 0.04), roughness=0.42, metallic=0.05)

    materials = [mat_red, mat_white, mat_glass, mat_dark, mat_blade, mat_yellow]
    mat_map = {
        'red': 0,
        'white': 1,
        'glass': 2,
        'dark': 3,
        'blade': 4,
        'yellow': 5,
    }

    bm_body = bmesh.new()
    build_fuselage_and_boom(bm_body, mat_map)
    build_engine_and_mast(bm_body, mat_map)
    build_tail_surfaces(bm_body, mat_map)
    build_skids_and_details(bm_body, mat_map)
    bmesh.ops.recalc_face_normals(bm_body, faces=bm_body.faces)

    body_mesh = bpy.data.meshes.new("Body")
    bm_body.to_mesh(body_mesh)
    bm_body.free()

    for mat in materials:
        body_mesh.materials.append(mat)
    for p in body_mesh.polygons:
        p.use_smooth = True

    body_obj = bpy.data.objects.new("Body", body_mesh)
    bpy.context.collection.objects.link(body_obj)
    body_obj.location = (0.0, 0.0, 0.0)

    mod = body_obj.modifiers.new("Subsurf", 'SUBSURF')
    mod.levels = 1
    mod.render_levels = 1
    bpy.context.view_layer.objects.active = body_obj
    bpy.ops.object.modifier_apply(modifier=mod.name)

    # Ensure lowest point of Body (bottom of skids) is at exact Z = 0.0 and Body origin is at (0, 0, 0)
    min_z = min(v.co.z for v in body_obj.data.vertices)
    for v in body_obj.data.vertices:
        v.co.z -= min_z
    body_obj.data.update()
    for p in body_obj.data.polygons:
        p.use_smooth = True

    main_hub_loc = Vector((0.0, -0.50, 3.00 - min_z))
    tail_hub_loc = Vector((-0.26, 5.55, 2.02 - min_z))

    main_rotor_obj = create_main_rotor(materials, mat_map, main_hub_loc)
    tail_rotor_obj = create_tail_rotor(materials, mat_map, tail_hub_loc)

    # Parent MainRotor and TailRotor to Body (keep transforms)
    bpy.context.view_layer.update()
    for child in (main_rotor_obj, tail_rotor_obj):
        child.parent = body_obj
        child.matrix_parent_inverse = body_obj.matrix_world.inverted()

    bpy.context.view_layer.update()
    return body_obj, main_rotor_obj, tail_rotor_obj


def setup_render_and_camera(scene, objects, png_path):
    engine_keys = [item.identifier for item in scene.render.bl_rna.properties['engine'].enum_items]
    if 'BLENDER_EEVEE_NEXT' in engine_keys:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    elif 'BLENDER_EEVEE' in engine_keys:
        scene.render.engine = 'BLENDER_EEVEE'
    else:
        scene.render.engine = engine_keys[0]

    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = png_path

    # Grey world strength 0.45
    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg_node = None
    for n in world.node_tree.nodes:
        if n.type == 'BACKGROUND':
            bg_node = n
            break
    if bg_node is None:
        bg_node = world.node_tree.nodes.new('ShaderNodeBackground')
    bg_node.inputs[0].default_value = (0.5, 0.5, 0.5, 1.0)
    bg_node.inputs[1].default_value = 0.45

    # Key sun light (strength 3)
    sun_data = bpy.data.lights.new("SunKey", 'SUN')
    sun_data.energy = 3.0
    sun_data.color = (1.0, 0.98, 0.95)
    sun_obj = bpy.data.objects.new("SunKey", sun_data)
    scene.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = (math.radians(48.0), math.radians(18.0), math.radians(-38.0))

    # Soft fill light
    fill_data = bpy.data.lights.new("FillLight", 'AREA')
    fill_data.energy = 450.0
    fill_data.size = 8.0
    fill_data.color = (0.88, 0.94, 1.0)
    fill_obj = bpy.data.objects.new("FillLight", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.location = (7.5, -6.5, 4.5)
    fill_dir = Vector((0.0, 0.5, 1.5)) - fill_obj.location
    fill_obj.rotation_euler = fill_dir.to_track_quat('-Z', 'Y').to_euler()

    # Compute exact world-space vertices of all objects for framing with ~10% margin
    world_pts = []
    for obj in objects:
        mw = obj.matrix_world
        for v in obj.data.vertices:
            world_pts.append(mw @ v.co)

    min_v = Vector((
        min(p.x for p in world_pts),
        min(p.y for p in world_pts),
        min(p.z for p in world_pts),
    ))
    max_v = Vector((
        max(p.x for p in world_pts),
        max(p.y for p in world_pts),
        max(p.z for p in world_pts),
    ))
    center = 0.5 * (min_v + max_v)

    # 3/4 front view (front-left, slightly above; model faces -Y)
    view_dir = Vector((-0.68, -0.72, 0.34)).normalized()
    forward = (-view_dir).normalized()
    world_up = Vector((0.0, 0.0, 1.0))
    right = forward.cross(world_up).normalized()
    up = right.cross(forward).normalized()

    # Project bounding points onto camera plane to center and frame with ~10% margin
    u_vals = [(p - center).dot(right) for p in world_pts]
    v_vals = [(p - center).dot(up) for p in world_pts]
    u_mid = 0.5 * (min(u_vals) + max(u_vals))
    v_mid = 0.5 * (min(v_vals) + max(v_vals))
    target = center + right * u_mid + up * v_mid

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 50.0
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.1
    cam_data.clip_end = 200.0
    half_fov_tan = (cam_data.sensor_width * 0.5) / cam_data.lens

    req_dist = 1.0
    fill_ratio = 0.82  # ~10% margin on each side
    for p in world_pts:
        rel = p - target
        px = abs(rel.dot(right))
        py = abs(rel.dot(up))
        pz = rel.dot(view_dir)
        d_needed = pz + max(px, py) / (half_fov_tan * fill_ratio)
        if d_needed > req_dist:
            req_dist = d_needed

    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = target + view_dir * req_dist
    cam_obj.rotation_euler = (target - cam_obj.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam_obj


def main():
    out_path = "helicopter.fbx"
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if idx + 1 < len(sys.argv):
            out_path = sys.argv[idx + 1]

    out_path = os.path.abspath(out_path)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if out_path.lower().endswith(".fbx"):
        png_path = out_path[:-4] + ".png"
    else:
        png_path = out_path + ".png"

    body_obj, main_rotor_obj, tail_rotor_obj = build_helicopter()
    all_objs = [body_obj, main_rotor_obj, tail_rotor_obj]

    bpy.ops.object.select_all(action='DESELECT')
    for obj in all_objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = body_obj

    bpy.ops.export_scene.fbx(
        filepath=out_path,
        use_selection=True,
        bake_space_transform=True,
        axis_forward='-Z',
        axis_up='Y',
        mesh_smooth_type='FACE'
    )

    scene = bpy.context.scene
    setup_render_and_camera(scene, all_objs, png_path)
    bpy.ops.render.render(write_still=True)

    total_tris = sum(
        sum(len(p.vertices) - 2 for p in obj.data.polygons)
        for obj in all_objs
    )
    print("TRIS", total_tris)


if __name__ == "__main__":
    main()

