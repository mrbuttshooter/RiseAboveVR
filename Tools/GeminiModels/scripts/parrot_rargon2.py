import bpy
import bmesh
import math
import sys
import os
from mathutils import Vector, Matrix


def clamp(val, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(val)))


def safe_pow(base, exp):
    return math.pow(clamp(base, 0.0, 1.0), float(exp))


def safe_div(a, b, default=0.0):
    return float(a) / float(b) if abs(float(b)) > 1e-9 else float(default)


def clear_scene():
    if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for block_collection in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.lights,
        bpy.data.cameras,
        bpy.data.curves,
        bpy.data.images,
    ):
        for block in list(block_collection):
            block_collection.remove(block)


def make_material(name, color_rgba, roughness=0.5, specular=0.5, emission_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = color_rgba
    nodes = mat.node_tree.nodes
    bsdf = None
    for n in nodes:
        if n.type == 'BSDF_PRINCIPLED':
            bsdf = n
            break
    if bsdf is None:
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    if 'Base Color' in bsdf.inputs:
        bsdf.inputs['Base Color'].default_value = color_rgba
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = clamp(roughness, 0.0, 1.0)
    if 'IOR' in bsdf.inputs:
        bsdf.inputs['IOR'].default_value = 1.45
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = clamp(specular, 0.0, 1.0)
    elif 'Specular' in bsdf.inputs:
        bsdf.inputs['Specular'].default_value = clamp(specular, 0.0, 1.0)
    if emission_strength > 0.0:
        if 'Emission Color' in bsdf.inputs:
            bsdf.inputs['Emission Color'].default_value = color_rgba
        elif 'Emission' in bsdf.inputs:
            bsdf.inputs['Emission'].default_value = color_rgba
        if 'Emission Strength' in bsdf.inputs:
            bsdf.inputs['Emission Strength'].default_value = float(emission_strength)
    return mat


def cap_ring_quads(bm, ring_verts, mat_idx, flip=False):
    verts = list(reversed(ring_verts)) if flip else list(ring_verts)
    n = len(verts)
    if n == 4:
        try:
            f = bm.faces.new((verts[0], verts[1], verts[2], verts[3]))
            f.material_index = mat_idx
            f.smooth = True
        except ValueError:
            pass
    elif n == 6:
        pairs = ((0, 1, 2, 5), (5, 2, 3, 4))
        for a, b, c, d in pairs:
            try:
                f = bm.faces.new((verts[a], verts[b], verts[c], verts[d]))
                f.material_index = mat_idx
                f.smooth = True
            except ValueError:
                pass
    elif n == 8:
        triplets = ((0, 1, 2, 7), (7, 2, 3, 6), (6, 3, 4, 5))
        for a, b, c, d in triplets:
            try:
                f = bm.faces.new((verts[a], verts[b], verts[c], verts[d]))
                f.material_index = mat_idx
                f.smooth = True
            except ValueError:
                pass


def add_lofted_rings(bm, rings_coords, band_materials, cap_start=False, cap_end=True):
    ring_verts = []
    for r_coords in rings_coords:
        rv = [bm.verts.new(co) for co in r_coords]
        ring_verts.append(rv)
    num_bands = len(ring_verts) - 1
    m = len(ring_verts[0])
    for b_idx in range(num_bands):
        r0 = ring_verts[b_idx]
        r1 = ring_verts[b_idx + 1]
        mat_spec = band_materials[min(b_idx, len(band_materials) - 1)]
        for i in range(m):
            inext = (i + 1) % m
            if isinstance(mat_spec, (list, tuple)):
                m_idx = mat_spec[i % len(mat_spec)]
            else:
                m_idx = int(mat_spec)
            try:
                f = bm.faces.new((r0[i], r0[inext], r1[inext], r1[i]))
                f.material_index = m_idx
                f.smooth = True
            except ValueError:
                pass
    if cap_start:
        first_mat = band_materials[0][0] if isinstance(band_materials[0], (list, tuple)) else int(band_materials[0])
        cap_ring_quads(bm, ring_verts[0], first_mat, flip=True)
    if cap_end:
        last_spec = band_materials[-1]
        last_mat = last_spec[0] if isinstance(last_spec, (list, tuple)) else int(last_spec)
        cap_ring_quads(bm, ring_verts[-1], last_mat, flip=False)
    return ring_verts


def make_frame(forward_vec, up_hint=Vector((0.0, 0.0, 1.0))):
    fwd = forward_vec.normalized()
    if fwd.length < 1e-6:
        fwd = Vector((0.0, -1.0, 0.0))
    up = up_hint.normalized()
    if abs(fwd.dot(up)) > 0.96:
        up = Vector((0.0, 1.0, 0.0)) if abs(fwd.y) < 0.9 else Vector((1.0, 0.0, 0.0))
    right = fwd.cross(up).normalized()
    real_up = right.cross(fwd).normalized()
    return right, real_up, fwd


def build_body_neck_head(bm, mat_green, mat_red):
    # 9 rings: lowered body tilted ~20 degrees forward (belly toward -Y, rump/tail base low at +Y),
    # hiding the green thighs inside the plump lower belly directly over the feet, up to the head.
    # Each tuple: (center_y, center_z, rx, ry_front, ry_back, pitch_deg, face_flatten)
    profile = [
        (0.052, 0.056, 0.024, 0.024, 0.024, 22.0, 0.0),
        (0.026, 0.084, 0.068, 0.072, 0.056, 21.0, 0.0),
        (0.002, 0.122, 0.084, 0.090, 0.074, 20.0, 0.0),
        (-0.016, 0.162, 0.082, 0.088, 0.072, 18.0, 0.0),
        (-0.028, 0.198, 0.062, 0.066, 0.058, 12.0, 0.0),
        (-0.033, 0.224, 0.055, 0.056, 0.054, 5.0, 0.10),
        (-0.037, 0.260, 0.067, 0.058, 0.068, -2.0, 0.26),
        (-0.035, 0.302, 0.061, 0.053, 0.065, 0.0, 0.28),
        (-0.026, 0.332, 0.030, 0.028, 0.032, 0.0, 0.10),
    ]
    m = 8
    rings = []
    for cy, cz, rx, ry_f, ry_b, pitch_deg, flat in profile:
        pitch = math.radians(pitch_deg)
        cp = math.cos(pitch)
        sp = math.sin(pitch)
        ring = []
        for i in range(m):
            ang = safe_div(2.0 * math.pi * i, m)
            ca = math.cos(ang)
            sa = math.sin(ang)
            x_local = rx * sa
            if ca < 0.0:
                t_front = clamp(-ca, 0.0, 1.0)
                flatten_factor = 1.0 - flat * safe_pow(t_front, 1.5)
                y_local = ca * ry_f * flatten_factor
            else:
                y_local = ca * ry_b
            # Forward tilt around X: belly (y_local < 0) pitches forward/down, back (y_local > 0) pitches back/up
            wy = cy + y_local * cp
            wz = cz + y_local * sp
            ring.append(Vector((x_local, wy, wz)))
        rings.append(ring)

    # Band materials: 0..3 green body, 4 neck transition (red front, green nape), 5..7 red-orange head
    neck_band = [mat_red, mat_red, mat_green, mat_green, mat_green, mat_green, mat_red, mat_red]
    band_mats = [
        mat_green,
        mat_green,
        mat_green,
        mat_green,
        neck_band,
        mat_red,
        mat_red,
        mat_red,
    ]
    add_lofted_rings(bm, rings, band_mats, cap_start=True, cap_end=True)


def build_beaks(bm, mat_ivory, mat_tip):
    # Upper beak: 4-vertex cross-section (top culmen ridge, right tomium, bottom palate, left tomium)
    # Rooted deep inside the flattened face, curving forward (-Y) and hooking sharply downward (-Z)
    upper_specs = [
        # (y, z_top, z_mid, z_bot, half_w)
        (-0.072, 0.298, 0.276, 0.258, 0.032),
        (-0.096, 0.296, 0.273, 0.256, 0.029),
        (-0.124, 0.286, 0.264, 0.251, 0.021),
        (-0.144, 0.266, 0.248, 0.238, 0.011),
        (-0.150, 0.231, 0.227, 0.223, 0.0022),
    ]
    u_rings = []
    for y, zt, zm, zb, hw in upper_specs:
        u_rings.append([
            Vector((0.0, y, zt)),
            Vector((hw, y + 0.004, zm)),
            Vector((0.0, y + 0.008, zb)),
            Vector((-hw, y + 0.004, zm)),
        ])
    add_lofted_rings(
        bm,
        u_rings,
        [mat_ivory, mat_ivory, mat_ivory, mat_tip],
        cap_start=False,
        cap_end=True,
    )

    # Lower beak: smaller U-shaped scoop tucked neatly beneath the upper beak
    lower_specs = [
        (-0.070, 0.258, 0.246, 0.233, 0.025),
        (-0.095, 0.256, 0.245, 0.234, 0.022),
        (-0.120, 0.253, 0.248, 0.243, 0.009),
    ]
    l_rings = []
    for y, zt, zm, zb, hw in lower_specs:
        l_rings.append([
            Vector((0.0, y + 0.003, zt)),
            Vector((hw, y, zm)),
            Vector((0.0, y - 0.002, zb)),
            Vector((-hw, y, zm)),
        ])
    add_lofted_rings(
        bm,
        l_rings,
        [mat_ivory, mat_ivory],
        cap_start=False,
        cap_end=True,
    )


def build_face_details(bm, mat_ivory, mat_black, mat_spec, mat_cheek):
    for sx in (-1.0, 1.0):
        # Surface normal direction on the side-front of the head
        n_eye = Vector((sx * 0.84, -0.50, 0.16)).normalized()
        r_eye, u_eye, f_eye = make_frame(n_eye)
        eye_base = Vector((sx * 0.050, -0.058, 0.283))

        # 1. Pale eye-ring (6-sided cushion rim embedded into head around the eye)
        er_rings = []
        for depth, rad in ((-0.006, 0.023), (0.005, 0.021)):
            ring = []
            for i in range(6):
                ang = safe_div(2.0 * math.pi * i, 6)
                co = (
                    eye_base
                    + f_eye * depth
                    + r_eye * (math.cos(ang) * rad)
                    + u_eye * (math.sin(ang) * rad * 1.05)
                )
                ring.append(co)
            er_rings.append(ring)
        add_lofted_rings(bm, er_rings, [mat_ivory], cap_start=False, cap_end=True)

        # 2. Big glossy black eyeball (6-sided dome emerging out of the pale eye-ring)
        eb_rings = []
        for depth, rad in ((0.001, 0.0155), (0.012, 0.0115)):
            ring = []
            for i in range(6):
                ang = safe_div(2.0 * math.pi * i, 6)
                co = (
                    eye_base
                    + f_eye * depth
                    + r_eye * (math.cos(ang) * rad)
                    + u_eye * (math.sin(ang) * rad * 1.05)
                )
                ring.append(co)
            eb_rings.append(ring)
        add_lofted_rings(bm, eb_rings, [mat_black], cap_start=False, cap_end=True)

        # 3. White specular dot on upper-front-outer surface of the black eye
        spec_dir = Vector((sx * 0.72, -0.60, 0.35)).normalized()
        rs, us, fs = make_frame(spec_dir)
        spec_center = eye_base + f_eye * 0.0115 + Vector((sx * 0.002, -0.004, 0.0045))
        sp_rings = []
        for depth, rad in ((-0.001, 0.0048), (0.0022, 0.0032)):
            ring = []
            for i in range(4):
                ang = safe_div(2.0 * math.pi * i, 4) + math.pi * 0.25
                co = spec_center + fs * depth + rs * (math.cos(ang) * rad) + us * (math.sin(ang) * rad)
                ring.append(co)
            sp_rings.append(ring)
        add_lofted_rings(bm, sp_rings, [mat_spec], cap_start=False, cap_end=True)

        # 4. Small cheek patch embedded on lower cheek below eye-ring and beside beak
        n_cheek = Vector((sx * 0.86, -0.46, -0.12)).normalized()
        rc, uc, fc = make_frame(n_cheek)
        cheek_base = Vector((sx * 0.052, -0.062, 0.254))
        ck_rings = []
        for depth, rx_c, ry_c in ((-0.005, 0.018, 0.013), (0.005, 0.014, 0.010)):
            ring = []
            for i in range(4):
                ang = safe_div(2.0 * math.pi * i, 4) + math.pi * 0.25
                co = (
                    cheek_base
                    + fc * depth
                    + rc * (math.cos(ang) * rx_c)
                    + uc * (math.sin(ang) * ry_c)
                )
                ring.append(co)
            ck_rings.append(ring)
        add_lofted_rings(bm, ck_rings, [mat_cheek], cap_start=False, cap_end=True)


def add_feather_blade(bm, pts, widths, thicknesses, normal_hint, band_mats):
    rings = []
    n_pts = len(pts)
    for idx in range(n_pts):
        if idx == 0:
            tang = pts[1] - pts[0]
        elif idx == n_pts - 1:
            tang = pts[-1] - pts[-2]
        else:
            tang = pts[idx + 1] - pts[idx - 1]
        right, up, _ = make_frame(tang, normal_hint)
        w = widths[idx]
        th = thicknesses[idx]
        p = pts[idx]
        rings.append([
            p + up * th,
            p + right * w,
            p - up * th,
            p - right * w,
        ])
    add_lofted_rings(bm, rings, band_mats, cap_start=False, cap_end=True)


def build_head_tufts(bm, mat_red):
    # 3 curved feather tufts sprouting directly out of the crown of the head
    tuft_specs = [
        # Center tall tuft
        (
            [
                Vector((0.0, -0.028, 0.320)),
                Vector((0.0, -0.012, 0.346)),
                Vector((0.0, 0.018, 0.358)),
            ],
            [0.012, 0.010, 0.003],
            [0.007, 0.005, 0.002],
            Vector((0.0, -0.3, 1.0)),
        ),
        # Left tuft
        (
            [
                Vector((-0.010, -0.025, 0.318)),
                Vector((-0.020, -0.006, 0.341)),
                Vector((-0.028, 0.020, 0.350)),
            ],
            [0.010, 0.009, 0.003],
            [0.006, 0.004, 0.002],
            Vector((-0.3, -0.2, 1.0)),
        ),
        # Right tuft
        (
            [
                Vector((0.010, -0.025, 0.318)),
                Vector((0.020, -0.006, 0.341)),
                Vector((0.028, 0.020, 0.350)),
            ],
            [0.010, 0.009, 0.003],
            [0.006, 0.004, 0.002],
            Vector((0.3, -0.2, 1.0)),
        ),
    ]
    for pts, widths, thicknesses, nh in tuft_specs:
        add_feather_blade(bm, pts, widths, thicknesses, nh, [mat_red, mat_red])


def build_wings(bm, mat_green, mat_yellow, mat_blue):
    # 4 large overlapping feather plates per wing covering most of the body sides,
    # with primaries extending well past the tail base
    for sx in (-1.0, 1.0):
        out_n = Vector((sx * 0.96, 0.14, 0.22)).normalized()

        # Plate 1: Large Upper Scapular / Lesser Coverts shield (green, rooted into shoulder)
        p1_pts = [
            Vector((sx * 0.054, -0.036, 0.184)),
            Vector((sx * 0.088, -0.002, 0.150)),
            Vector((sx * 0.082, 0.052, 0.106)),
        ]
        add_feather_blade(
            bm,
            p1_pts,
            [0.048, 0.056, 0.028],
            [0.020, 0.022, 0.010],
            out_n,
            [mat_green, mat_green],
        )

        # Plate 2: Broad Greater Coverts layer (overlapping below Plate 1, green base with yellow band)
        p2_pts = [
            Vector((sx * 0.058, -0.018, 0.158)),
            Vector((sx * 0.090, 0.022, 0.118)),
            Vector((sx * 0.074, 0.084, 0.072)),
        ]
        add_feather_blade(
            bm,
            p2_pts,
            [0.046, 0.052, 0.024],
            [0.018, 0.020, 0.009],
            out_n,
            [mat_green, mat_yellow],
        )

        # Plate 3: Outer Secondary / Primary Feather Plate (green root, yellow band, blue tip past tail base)
        p3_pts = [
            Vector((sx * 0.056, -0.002, 0.134)),
            Vector((sx * 0.086, 0.040, 0.096)),
            Vector((sx * 0.068, 0.088, 0.062)),
            Vector((sx * 0.048, 0.130, 0.036)),
        ]
        add_feather_blade(
            bm,
            p3_pts,
            [0.040, 0.046, 0.032, 0.012],
            [0.016, 0.017, 0.012, 0.005],
            out_n,
            [mat_green, mat_yellow, mat_blue],
        )

        # Plate 4: Longest Primary Flight Feather (yellow edge band, long blue blade reaching far past tail base)
        p4_pts = [
            Vector((sx * 0.052, 0.014, 0.114)),
            Vector((sx * 0.080, 0.058, 0.078)),
            Vector((sx * 0.058, 0.108, 0.048)),
            Vector((sx * 0.036, 0.156, 0.024)),
        ]
        add_feather_blade(
            bm,
            p4_pts,
            [0.034, 0.040, 0.028, 0.010],
            [0.015, 0.016, 0.011, 0.004],
            out_n,
            [mat_yellow, mat_blue, mat_blue],
        )


def build_tail(bm, mat_blue):
    # 6 long tapered tail feathers fanning slightly and angling down and back from the tilted rump
    fan_vals = (-1.0, -0.6, -0.2, 0.2, 0.6, 1.0)
    for u in fan_vals:
        absu = abs(u)
        root_pt = Vector((u * 0.015, 0.045, 0.068 - absu * 0.003))
        mid_pt = Vector((u * 0.034, 0.120 - absu * 0.015, 0.038 + absu * 0.004))
        tip_pt = Vector((u * 0.058, 0.215 - absu * 0.040, 0.010 + absu * 0.014))
        nh = Vector((u * 0.25, 0.35, 0.90)).normalized()
        add_feather_blade(
            bm,
            [root_pt, mid_pt, tip_pt],
            [0.016, 0.018, 0.005],
            [0.007, 0.006, 0.0025],
            nh,
            [mat_blue, mat_blue],
        )


def build_legs_and_zygodactyl_feet(bm, mat_green, mat_grey, mat_claw):
    for sx in (-1.0, 1.0):
        # Green thigh tucked completely INSIDE the lower belly + very short visible grey tarsus + ankle hub
        leg_specs = [
            # (x, y, z, rx, ry)
            (sx * 0.026, 0.006, 0.106, 0.018, 0.020),
            (sx * 0.032, -0.002, 0.080, 0.015, 0.016),
            (sx * 0.036, -0.008, 0.058, 0.012, 0.013),
            (sx * 0.038, -0.011, 0.037, 0.011, 0.012),
            (sx * 0.038, -0.012, 0.020, 0.013, 0.015),
        ]
        leg_rings = []
        for lx, ly, lz, rx, ry in leg_specs:
            leg_rings.append([
                Vector((lx, ly - ry, lz)),
                Vector((lx + rx, ly, lz)),
                Vector((lx, ly + ry, lz)),
                Vector((lx - rx, ly, lz)),
            ])
        add_lofted_rings(
            bm,
            leg_rings,
            [mat_green, mat_green, mat_grey, mat_grey],
            cap_start=False,
            cap_end=True,
        )

        # Zygodactyl Toes (2 forward toward -Y, 2 back toward +Y) directly under the belly resting on Z=0
        ankle = Vector((sx * 0.038, -0.012, 0.020))
        # (dx_dir, dy_dir, length, is_front)
        toe_defs = [
            # Forward inner toe
            (-sx * 0.28, -0.96, 0.038, True),
            # Forward outer toe (longest)
            (sx * 0.24, -0.97, 0.044, True),
            # Backward inner toe
            (-sx * 0.30, 0.95, 0.030, False),
            # Backward outer toe
            (sx * 0.28, 0.96, 0.036, False),
        ]
        for dx, dy, tlen, is_front in toe_defs:
            horiz = Vector((dx, dy, 0.0)).normalized()
            side = Vector((-horiz.y, horiz.x, 0.0))
            if is_front:
                # 4 rings (2 grey toe bands + 1 curved dark claw band)
                p0 = ankle + horiz * 0.004 + Vector((0.0, 0.0, 0.001))
                p1 = ankle + horiz * (tlen * 0.52) + Vector((0.0, 0.0, -0.004))
                p2 = ankle + horiz * (tlen * 0.92) + Vector((0.0, 0.0, -0.012))
                p3 = ankle + horiz * (tlen * 1.08) + Vector((0.0, 0.0, -0.0185))
                pts = [p0, p1, p2, p3]
                rads = [(0.0065, 0.0065), (0.0058, 0.0058), (0.0042, 0.0045), (0.0015, 0.0015)]
                mats = [mat_grey, mat_grey, mat_claw]
            else:
                # 3 rings (1 grey toe band + 1 curved dark claw band)
                p0 = ankle + horiz * 0.004 + Vector((0.0, 0.0, 0.001))
                p1 = ankle + horiz * (tlen * 0.85) + Vector((0.0, 0.0, -0.011))
                p2 = ankle + horiz * (tlen * 1.05) + Vector((0.0, 0.0, -0.0185))
                pts = [p0, p1, p2]
                rads = [(0.0062, 0.0062), (0.0044, 0.0046), (0.0015, 0.0015)]
                mats = [mat_grey, mat_claw]

            t_rings = []
            for idx, pt in enumerate(pts):
                rw, rh = rads[idx]
                t_rings.append([
                    pt + Vector((0.0, 0.0, rh)),
                    pt + side * rw,
                    pt - Vector((0.0, 0.0, rh)),
                    pt - side * rw,
                ])
            add_lofted_rings(bm, t_rings, mats, cap_start=False, cap_end=True)


def create_kiwi_model():
    mats = [
        make_material("Mat_Green", (0.08, 0.55, 0.15, 1.0), roughness=0.48),
        make_material("Mat_RedOrange", (0.85, 0.25, 0.07, 1.0), roughness=0.48),
        make_material("Mat_Blue", (0.06, 0.28, 0.86, 1.0), roughness=0.46),
        make_material("Mat_Yellow", (0.96, 0.78, 0.05, 1.0), roughness=0.46),
        make_material("Mat_BeakIvory", (0.92, 0.87, 0.74, 1.0), roughness=0.42),
        make_material("Mat_BeakTip", (0.14, 0.12, 0.11, 1.0), roughness=0.40),
        make_material("Mat_LegGrey", (0.36, 0.37, 0.40, 1.0), roughness=0.55),
        make_material("Mat_EyeBlack", (0.015, 0.015, 0.02, 1.0), roughness=0.08, specular=0.9),
        make_material("Mat_EyeSpec", (1.0, 1.0, 1.0, 1.0), roughness=0.05, emission_strength=0.4),
    ]
    idx_green = 0
    idx_red = 1
    idx_blue = 2
    idx_yellow = 3
    idx_ivory = 4
    idx_tip = 5
    idx_grey = 6
    idx_black = 7
    idx_spec = 8

    bm = bmesh.new()
    build_body_neck_head(bm, idx_green, idx_red)
    build_beaks(bm, idx_ivory, idx_tip)
    build_face_details(bm, idx_ivory, idx_black, idx_spec, idx_red)
    build_head_tufts(bm, idx_red)
    build_wings(bm, idx_green, idx_yellow, idx_blue)
    build_tail(bm, idx_blue)
    build_legs_and_zygodactyl_feet(bm, idx_green, idx_grey, idx_tip)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new("Kiwi")
    bm.to_mesh(mesh)
    bm.free()

    for m in mats:
        mesh.materials.append(m)

    for poly in mesh.polygons:
        poly.use_smooth = True

    obj = bpy.data.objects.new("Kiwi", mesh)
    bpy.context.scene.collection.objects.link(obj)

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    sub = obj.modifiers.new("Subsurf", 'SUBSURF')
    sub.levels = 2
    sub.render_levels = 2
    sub.uv_smooth = 'PRESERVE_BOUNDARIES'
    bpy.ops.object.modifier_apply(modifier=sub.name)

    # Normalize exact height to 0.42 m and place origin at (0, 0, 0) at the bottom of the toes (Z=0)
    verts = obj.data.vertices
    if len(verts) > 0:
        min_z = min(v.co.z for v in verts)
        max_z = max(v.co.z for v in verts)
        span_z = max_z - min_z
        scale_f = safe_div(0.42, span_z, 1.0)
        foot_y = -0.012
        for v in verts:
            v.co.x = v.co.x * scale_f
            v.co.y = (v.co.y - foot_y) * scale_f
            v.co.z = (v.co.z - min_z) * scale_f
        obj.data.update()

    for poly in obj.data.polygons:
        poly.use_smooth = True

    obj.location = (0.0, 0.0, 0.0)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)
    return obj


def setup_render_and_camera(scene, target_obj):
    # Pick EEVEE from scene.render.bl_rna.properties['engine'].enum_items keys
    engine_keys = list(scene.render.bl_rna.properties['engine'].enum_items.keys())
    chosen_engine = None
    for candidate in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        if candidate in engine_keys:
            chosen_engine = candidate
            break
    if chosen_engine is None:
        for k in engine_keys:
            if 'EEVEE' in k.upper():
                chosen_engine = k
                break
    if chosen_engine is not None:
        scene.render.engine = chosen_engine

    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'

    # Grey studio world (strength 0.45)
    world = bpy.data.worlds.new("StudioWorld")
    scene.world = world
    world.use_nodes = True
    bg_node = None
    for n in world.node_tree.nodes:
        if n.type == 'BACKGROUND':
            bg_node = n
            break
    if bg_node is None:
        bg_node = world.node_tree.nodes.new('ShaderNodeBackground')
    if 'Color' in bg_node.inputs:
        bg_node.inputs['Color'].default_value = (0.82, 0.83, 0.85, 1.0)
    if 'Strength' in bg_node.inputs:
        bg_node.inputs['Strength'].default_value = 0.45

    # Key sun light (strength 3.0)
    key_data = bpy.data.lights.new("KeySun", 'SUN')
    key_data.energy = 3.0
    key_data.color = (1.0, 0.98, 0.94)
    if hasattr(key_data, 'angle'):
        key_data.angle = math.radians(12.0)
    key_obj = bpy.data.objects.new("KeySun", key_data)
    scene.collection.objects.link(key_obj)
    key_dir = Vector((-0.55, -0.65, 0.52)).normalized()
    kr, ku, kb = make_frame(key_dir)
    key_obj.matrix_world = Matrix.Translation(key_dir * 2.0) @ Matrix((kr, ku, kb)).transposed().to_4x4()

    # Soft fill light
    fill_data = bpy.data.lights.new("SoftFill", 'SUN')
    fill_data.energy = 1.25
    fill_data.color = (0.90, 0.95, 1.0)
    if hasattr(fill_data, 'angle'):
        fill_data.angle = math.radians(45.0)
    fill_obj = bpy.data.objects.new("SoftFill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_dir = Vector((0.68, -0.50, 0.30)).normalized()
    fr, fu, fb = make_frame(fill_dir)
    fill_obj.matrix_world = Matrix.Translation(fill_dir * 2.0) @ Matrix((fr, fu, fb)).transposed().to_4x4()

    # Camera at 3/4 front view (front-left, slightly above) framing the whole model with ~10% margin
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 55.0
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.05
    cam_data.clip_end = 50.0
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    view_dir = Vector((-0.60, -0.74, 0.24)).normalized()
    cam_right, cam_up, cam_back = make_frame(view_dir)

    world_verts = [target_obj.matrix_world @ v.co for v in target_obj.data.vertices]
    us = [v.dot(cam_right) for v in world_verts]
    ws = [v.dot(cam_up) for v in world_verts]
    ds = [v.dot(cam_back) for v in world_verts]

    u_mid = 0.5 * (min(us) + max(us))
    w_mid = 0.5 * (min(ws) + max(ws))
    d_mid = 0.5 * (min(ds) + max(ds))
    target_center = cam_right * u_mid + cam_up * w_mid + cam_back * d_mid

    half_tan = safe_div(0.5 * cam_data.sensor_width, cam_data.lens, 0.32)
    fill_ratio = 0.80  # 80% occupancy = 10% margin on each side
    req_dist = 0.5
    for v in world_verts:
        rel = v - target_center
        ru = abs(rel.dot(cam_right))
        rw = abs(rel.dot(cam_up))
        rd = rel.dot(cam_back)
        needed = rd + safe_div(max(ru, rw), fill_ratio * half_tan, 0.5)
        if needed > req_dist:
            req_dist = needed

    cam_pos = target_center + cam_back * req_dist
    rot_mat = Matrix((cam_right, cam_up, cam_back)).transposed()
    cam_obj.matrix_world = Matrix.Translation(cam_pos) @ rot_mat.to_4x4()


def main():
    out_fbx = "kiwi.fbx"
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if idx + 1 < len(sys.argv):
            out_fbx = sys.argv[idx + 1]
    out_fbx = os.path.abspath(out_fbx)
    out_dir = os.path.dirname(out_fbx)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    base_path, _ = os.path.splitext(out_fbx)
    out_png = base_path + ".png"

    clear_scene()
    kiwi_obj = create_kiwi_model()

    tri_count = sum(len(p.vertices) - 2 for p in kiwi_obj.data.polygons)
    print("TRIS", tri_count)

    bpy.ops.object.select_all(action='DESELECT')
    kiwi_obj.select_set(True)
    bpy.context.view_layer.objects.active = kiwi_obj

    bpy.ops.export_scene.fbx(
        filepath=out_fbx,
        use_selection=True,
        bake_space_transform=True,
        axis_forward='-Z',
        axis_up='Y',
        mesh_smooth_type='FACE',
        add_leaf_bones=False,
    )

    scene = bpy.context.scene
    setup_render_and_camera(scene, kiwi_obj)
    scene.render.filepath = out_png
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
