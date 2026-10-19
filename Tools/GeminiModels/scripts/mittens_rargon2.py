import bpy
import bmesh
import math
import sys
import os
from mathutils import Vector, Euler, Matrix


def clamp01(val):
    return max(0.0, min(1.0, float(val)))


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh, do_unlink=True)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat, do_unlink=True)
    for cam in list(bpy.data.cameras):
        bpy.data.cameras.remove(cam, do_unlink=True)
    for lgt in list(bpy.data.lights):
        bpy.data.lights.remove(lgt, do_unlink=True)


def make_material(name, rgba, roughness=0.45, metallic=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    if "Base Color" in bsdf.inputs:
        bsdf.inputs["Base Color"].default_value = rgba
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    mat.diffuse_color = rgba
    return mat


def build_loft_object(name, start_pole, rings, end_pole, materials, subsurf_levels=1, mat_fn=None):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    bm = bmesh.new()

    v_start = bm.verts.new(start_pole)
    bm_rings = []
    for ring in rings:
        bm_rings.append([bm.verts.new(co) for co in ring])
    v_end = bm.verts.new(end_pole)

    n_seg = len(bm_rings[0])
    for j in range(n_seg):
        jn = (j + 1) % n_seg
        f = bm.faces.new((v_start, bm_rings[0][jn], bm_rings[0][j]))
        f.smooth = True

    for r_idx in range(len(bm_rings) - 1):
        r0 = bm_rings[r_idx]
        r1 = bm_rings[r_idx + 1]
        for j in range(n_seg):
            jn = (j + 1) % n_seg
            f = bm.faces.new((r0[j], r0[jn], r1[jn], r1[j]))
            f.smooth = True

    last_ring = bm_rings[-1]
    for j in range(n_seg):
        jn = (j + 1) % n_seg
        f = bm.faces.new((v_end, last_ring[j], last_ring[jn]))
        f.smooth = True

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    for mat in materials:
        mesh.materials.append(mat)

    if subsurf_levels > 0:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="Subsurf", type='SUBSURF')
        mod.levels = subsurf_levels
        mod.render_levels = subsurf_levels
        bpy.ops.object.modifier_apply(modifier=mod.name)

    bm2 = bmesh.new()
    bm2.from_mesh(obj.data)
    bm2.faces.ensure_lookup_table()
    for f in bm2.faces:
        f.smooth = True
        if mat_fn is not None:
            center = f.calc_center_median()
            normal = f.normal
            f.material_index = mat_fn(center, normal)
        else:
            f.material_index = 0
    bm2.to_mesh(obj.data)
    bm2.free()

    return obj


HEAD_POS = Vector((0.0, -0.145, 0.220))
HEAD_ROT = Euler((math.radians(-20.0), 0.0, 0.0), 'XYZ').to_matrix()
HEAD_ROT_INV = HEAD_ROT.inverted()


def head_to_world(local_co):
    return HEAD_POS + (HEAD_ROT @ local_co)


def world_to_head(world_co):
    return HEAD_ROT_INV @ (world_co - HEAD_POS)


def create_torso(materials):
    y_front = -0.135
    y_back = 0.220
    n_rings = 9
    n_seg = 10

    start_pole = Vector((0.0, y_front, 0.134))
    end_pole = Vector((0.0, y_back, 0.142))

    rings = []
    for i in range(1, n_rings + 1):
        t = clamp01(i / (n_rings + 1))
        y = y_front + (y_back - y_front) * t
        envelope = math.sin(t * math.pi)
        env_pow = clamp01(envelope) ** 0.55

        chest_boost = 0.008 * math.exp(-((t - 0.22) / 0.18) ** 2)
        hip_boost = 0.009 * math.exp(-((t - 0.78) / 0.18) ** 2)

        rx = (0.062 * env_pow) + chest_boost + hip_boost
        rz = (0.054 * env_pow) + 0.6 * (chest_boost + hip_boost)
        cz = 0.132 + 0.010 * t - 0.005 * math.sin(t * math.pi)

        ring = []
        for j in range(n_seg):
            ang = (2.0 * math.pi * j) / n_seg
            ca = math.cos(ang)
            sa = math.sin(ang)
            x = rx * ca
            z_off = rz * sa
            if sa < 0.0:
                z_off *= 1.06
            z = cz + z_off
            ring.append(Vector((x, y, z)))
        rings.append(ring)

    def torso_mat_fn(co, normal):
        if co.y < -0.088 and co.z < 0.150 and abs(co.x) < 0.046:
            return 2
        if co.z > 0.118 and -0.075 < co.y < 0.185:
            if co.z > 0.160 and abs(co.x) < 0.014:
                return 1
            y_curved = co.y + 0.22 * (0.165 - co.z)
            band_centers = (-0.042, 0.016, 0.074, 0.132)
            for bc in band_centers:
                half_w = 0.014 * clamp01((co.z - 0.114) / 0.045)
                if abs(y_curved - bc) < half_w:
                    return 1
        return 0

    return build_loft_object(
        "Torso", start_pole, rings, end_pole, materials, subsurf_levels=2, mat_fn=torso_mat_fn
    )


def create_neck(materials):
    p0 = Vector((0.0, -0.105, 0.140))
    p1 = Vector((0.0, -0.142, 0.218))
    n_rings = 3
    n_seg = 8

    rings = []
    for i in range(1, n_rings + 1):
        t = clamp01(i / (n_rings + 1))
        center = p0.lerp(p1, t)
        rx = 0.045 * (1.0 - 0.12 * t)
        ry = 0.044 * (1.0 - 0.10 * t)
        ring = []
        for j in range(n_seg):
            ang = (2.0 * math.pi * j) / n_seg
            x = center.x + rx * math.cos(ang)
            y = center.y + ry * math.sin(ang)
            z = center.z + 0.008 * math.sin(ang)
            ring.append(Vector((x, y, z)))
        rings.append(ring)

    def neck_mat_fn(co, normal):
        if co.y < -0.125 and abs(co.x) < 0.032:
            return 2
        return 0

    return build_loft_object(
        "Neck", p0, rings, p1, materials, subsurf_levels=1, mat_fn=neck_mat_fn
    )


def create_chest_bib(materials):
    p_bot = Vector((0.0, -0.095, 0.082))
    p_top = Vector((0.0, -0.128, 0.182))
    n_rings = 4
    n_seg = 8

    rings = []
    for i in range(1, n_rings + 1):
        t = clamp01(i / (n_rings + 1))
        env = clamp01(math.sin(t * math.pi)) ** 0.65
        teardrop = 0.85 + 0.25 * math.sin((t - 0.15) * math.pi)
        rx = 0.044 * env * teardrop
        ry = 0.032 * env
        cy = -0.112 - 0.020 * math.sin(t * math.pi)
        cz = 0.082 + (0.182 - 0.082) * t
        ring = []
        for j in range(n_seg):
            ang = (2.0 * math.pi * j) / n_seg
            x = rx * math.cos(ang)
            y = cy + ry * math.sin(ang)
            z = cz
            ring.append(Vector((x, y, z)))
        rings.append(ring)

    return build_loft_object(
        "ChestBib", p_bot, rings, p_top, [materials[2]], subsurf_levels=1
    )


def create_head(materials):
    n_rings = 7
    n_seg = 10

    def deform_head_local(nx, ny, nz):
        rx = 0.078
        ry = 0.070
        rz = 0.066

        cheek_h = clamp01((0.18 - nz) / 0.72) * clamp01((nz + 0.75) / 0.65)
        cheek_f = clamp01((0.30 - ny) / 0.95)
        cheek_boost = 1.0 + 0.24 * cheek_h * cheek_f

        x = nx * rx * cheek_boost
        y = ny * ry
        z = nz * rz

        if ny < -0.45:
            y *= 0.92
        if nz < -0.55:
            z *= 0.90
        return Vector((x, y, z))

    start_pole = head_to_world(deform_head_local(0.0, 0.0, -1.0))
    end_pole = head_to_world(deform_head_local(0.0, 0.0, 1.0))

    rings = []
    for i in range(1, n_rings + 1):
        v = i / (n_rings + 1)
        phi = (v - 0.5) * math.pi
        cp = math.cos(phi)
        sp = math.sin(phi)
        ring = []
        for j in range(n_seg):
            theta = (2.0 * math.pi * j) / n_seg
            nx = cp * math.cos(theta)
            ny = cp * math.sin(theta)
            nz = sp
            lco = deform_head_local(nx, ny, nz)
            ring.append(head_to_world(lco))
        rings.append(ring)

    def head_mat_fn(co, normal):
        lco = world_to_head(co)
        lx, ly, lz = lco.x, lco.y, lco.z

        if ly < -0.025 and lz < -0.012 and abs(lx) < 0.050:
            return 2

        if lz > 0.016 and -0.062 < ly < 0.055:
            if abs(lx) < 0.0085:
                return 1
            spread = 0.019 + 0.08 * (lz - 0.016)
            if abs(abs(lx) - spread) < 0.0065:
                return 1
            if abs(abs(lx) - (spread + 0.018)) < 0.0060 and ly > -0.048:
                return 1

        if abs(lx) > 0.052 and -0.042 < ly < 0.022:
            if -0.006 < lz < 0.005 or -0.024 < lz < -0.013:
                return 1

        return 0

    return build_loft_object(
        "Head", start_pole, rings, end_pole, materials, subsurf_levels=2, mat_fn=head_mat_fn
    )


def create_ellipsoid_head_part(name, local_center, radii, local_euler, mat, n_rings=3, n_seg=8, subsurf_levels=1):
    rot = Euler(local_euler, 'XYZ').to_matrix()

    def pt(nx, ny, nz):
        local_p = local_center + (rot @ Vector((nx * radii[0], ny * radii[1], nz * radii[2])))
        return head_to_world(local_p)

    start_pole = pt(0.0, 0.0, -1.0)
    end_pole = pt(0.0, 0.0, 1.0)
    rings = []
    for i in range(1, n_rings + 1):
        phi = ((i / (n_rings + 1)) - 0.5) * math.pi
        cp = math.cos(phi)
        sp = math.sin(phi)
        ring = []
        for j in range(n_seg):
            ang = (2.0 * math.pi * j) / n_seg
            ring.append(pt(cp * math.cos(ang), cp * math.sin(ang), sp))
        rings.append(ring)

    return build_loft_object(name, start_pole, rings, end_pole, [mat], subsurf_levels=subsurf_levels)


def create_nose(mat_pink):
    n_rings = 3
    n_seg = 8
    y_back = -0.052
    y_front = -0.083

    start_pole = head_to_world(Vector((0.0, y_back, -0.007)))
    end_pole = head_to_world(Vector((0.0, y_front, -0.008)))

    rings = []
    for i in range(1, n_rings + 1):
        t = clamp01(i / (n_rings + 1))
        env = clamp01(math.sin(t * math.pi)) ** 0.55
        ly = y_back + (y_front - y_back) * t
        ring = []
        for j in range(n_seg):
            ang = (2.0 * math.pi * j) / n_seg
            ca = math.cos(ang)
            sa = math.sin(ang)
            top_widen = 1.0 + 0.38 * sa
            lx = 0.0115 * env * ca * max(0.35, top_widen)
            lz = -0.007 + 0.0085 * env * sa
            ring.append(head_to_world(Vector((lx, ly, lz))))
        rings.append(ring)

    return build_loft_object("Nose", start_pole, rings, end_pole, [mat_pink], subsurf_levels=1)


def create_mouth(mat_black):
    parts = []
    n_rings = 7
    n_seg = 4

    def mouth_center(s):
        lx = s * 0.022
        lz = -0.0245 + 0.0032 * math.cos(s * math.pi * 2.0) + 0.0012 * (s * s)
        ly = -0.0775 + 0.011 * (s * s)
        return Vector((lx, ly, lz))

    start_pole = head_to_world(mouth_center(-1.0) + Vector((0.0, 0.003, 0.0)))
    end_pole = head_to_world(mouth_center(1.0) + Vector((0.0, 0.003, 0.0)))

    rings = []
    for i in range(1, n_rings + 1):
        s = -1.0 + 2.0 * (i / (n_rings + 1))
        c = mouth_center(s)
        r_thick = 0.0020 * (1.0 - 0.35 * (s * s))
        ring = []
        for j in range(n_seg):
            ang = (2.0 * math.pi * j) / n_seg
            dy = r_thick * math.cos(ang)
            if dy > 0.0:
                dy += 0.0055
            dz = r_thick * math.sin(ang)
            ring.append(head_to_world(c + Vector((0.0, dy, dz))))
        rings.append(ring)

    parts.append(build_loft_object("MouthW", start_pole, rings, end_pole, [mat_black], subsurf_levels=1))

    p_top = head_to_world(Vector((0.0, -0.075, -0.011)))
    p_bot = head_to_world(Vector((0.0, -0.076, -0.024)))
    p_rings = []
    for i in range(1, 3):
        t = i / 3.0
        c = Vector((0.0, -0.0775, -0.011 - 0.013 * t))
        ring = []
        for j in range(4):
            ang = (2.0 * math.pi * j) / 4.0
            dx = 0.0016 * math.cos(ang)
            dy = 0.0018 * math.sin(ang)
            if dy > 0.0:
                dy += 0.005
            ring.append(head_to_world(c + Vector((dx, dy, 0.0))))
        p_rings.append(ring)

    parts.append(build_loft_object("Philtrum", p_top, p_rings, p_bot, [mat_black], subsurf_levels=1))
    return parts


def create_whiskers(mat_white):
    whiskers = []
    for side in (-1.0, 1.0):
        for idx in range(3):
            offset_z = (idx - 1) * 0.0055
            offset_y = (idx - 1) * 0.0035
            n_rings = 4
            n_seg = 5

            def w_pt(t):
                lx = side * (0.016 + 0.076 * t)
                ly = -0.062 - 0.006 * math.sin(t * math.pi) + offset_y * (1.0 + 0.8 * t)
                lz = -0.019 + offset_z + (idx - 1.2) * 0.009 * t - 0.007 * (t * t)
                return Vector((lx, ly, lz))

            start_pole = head_to_world(w_pt(0.0))
            end_pole = head_to_world(w_pt(1.0))
            rings = []
            for i in range(1, n_rings + 1):
                t = clamp01(i / (n_rings + 1))
                c = w_pt(t)
                rad = 0.0017 * (1.0 - 0.72 * t)
                ring = []
                for j in range(n_seg):
                    ang = (2.0 * math.pi * j) / n_seg
                    dy = rad * math.cos(ang)
                    dz = rad * math.sin(ang)
                    ring.append(head_to_world(c + Vector((0.0, dy, dz))))
                rings.append(ring)

            w_obj = build_loft_object(
                f"Whisker_{int(side)}_{idx}", start_pole, rings, end_pole, [mat_white], subsurf_levels=0
            )
            whiskers.append(w_obj)
    return whiskers


def create_eyes(mat_white, mat_green, mat_black):
    eye_objs = []
    for side in (-1.0, 1.0):
        eye_center = Vector((side * 0.031, -0.053, 0.012))
        eye_rot = Euler((math.radians(-6.0), 0.0, side * math.radians(-12.0)), 'XYZ').to_matrix()
        rx, ry, rz = 0.021, 0.016, 0.021

        def e_world(local_e):
            return head_to_world(eye_center + (eye_rot @ local_e))

        start_pole = e_world(Vector((0.0, ry, 0.0)))
        end_pole = e_world(Vector((0.0, -ry, 0.0)))

        n_rings = 4
        n_seg = 10
        rings = []
        for i in range(1, n_rings + 1):
            t = clamp01(i / (n_rings + 1))
            phi = (0.5 - t) * math.pi
            cp = math.cos(phi)
            sp = math.sin(phi)
            ring = []
            for j in range(n_seg):
                ang = (2.0 * math.pi * j) / n_seg
                ex = rx * cp * math.cos(ang)
                ey = ry * sp
                ez = rz * cp * math.sin(ang)
                ring.append(e_world(Vector((ex, ey, ez))))
            rings.append(ring)

        eye_front_world = (HEAD_ROT @ (eye_rot @ Vector((0.0, -1.0, 0.0)))).normalized()
        eye_center_world = head_to_world(eye_center)

        def eye_mat_fn(co, normal):
            rel = (co - eye_center_world).normalized()
            if rel.dot(eye_front_world) > 0.32:
                return 0
            return 1

        eyeball = build_loft_object(
            f"Eyeball_{int(side)}",
            start_pole,
            rings,
            end_pole,
            [mat_green, mat_white],
            subsurf_levels=1,
            mat_fn=eye_mat_fn,
        )
        eye_objs.append(eyeball)

        pupil_offset = Vector((-side * 0.0012, -ry + 0.0020, 0.0022))
        p_bot = e_world(pupil_offset + Vector((0.0, 0.003, -0.0125)))
        p_top = e_world(pupil_offset + Vector((0.0, 0.003, 0.0125)))
        p_rings = []
        for i in range(1, 4):
            t = clamp01(i / 4.0)
            env = math.sin(t * math.pi)
            pz = -0.0125 + 0.0250 * t
            ring = []
            for j in range(8):
                ang = (2.0 * math.pi * j) / 8.0
                px = 0.0040 * env * math.cos(ang)
                py = 0.0038 * math.sin(ang)
                if py > 0.0:
                    py += 0.0045
                ring.append(e_world(pupil_offset + Vector((px, py, pz))))
            p_rings.append(ring)

        pupil = build_loft_object(
            f"Pupil_{int(side)}", p_bot, p_rings, p_top, [mat_black], subsurf_levels=1
        )
        eye_objs.append(pupil)

        highlights = [
            ("HiBig", Vector((-0.0052, -ry + 0.0012, 0.0062)), 0.0044),
            ("HiSmall", Vector((0.0050, -ry + 0.0015, -0.0052)), 0.0023),
        ]
        for h_name, h_pos, h_rad in highlights:
            h_back = e_world(h_pos + Vector((0.0, 0.006, 0.0)))
            h_front = e_world(h_pos + Vector((0.0, -0.0028, 0.0)))
            h_rings = []
            for i in range(1, 3):
                t = i / 3.0
                env = math.sin(t * math.pi)
                hy = 0.006 - 0.0088 * t
                ring = []
                for j in range(6):
                    ang = (2.0 * math.pi * j) / 6.0
                    hx = h_rad * env * math.cos(ang)
                    hz = h_rad * env * math.sin(ang)
                    ring.append(e_world(h_pos + Vector((hx, hy, hz))))
                h_rings.append(ring)
            h_obj = build_loft_object(
                f"{h_name}_{int(side)}", h_back, h_rings, h_front, [mat_white], subsurf_levels=1
            )
            eye_objs.append(h_obj)

    return eye_objs


def create_ears(mat_orange, mat_dark_orange, mat_pink):
    ear_objs = []
    for side in (-1.0, 1.0):
        p_base = Vector((side * 0.044, -0.004, 0.034))
        p_tip = Vector((side * 0.074, -0.012, 0.106))
        n_rings = 5
        n_seg = 10

        ear_rot = Euler((math.radians(8.0), side * math.radians(18.0), side * math.radians(-10.0)), 'XYZ').to_matrix()

        rings = []
        for i in range(1, n_rings + 1):
            t = clamp01(i / (n_rings + 1))
            taper = (1.0 - (t ** 1.15)) * (0.35 + 0.65 * math.sin(clamp01(t * 0.85 + 0.15) * math.pi))
            c = p_base.lerp(p_tip, t)
            rx = 0.028 * max(0.12, taper)
            ry = 0.016 * max(0.15, taper)
            ring = []
            for j in range(n_seg):
                ang = (2.0 * math.pi * j) / n_seg
                ca = math.cos(ang)
                sa = math.sin(ang)
                ly = ry * sa
                if sa < -0.15 and 0.15 < t < 0.82 and abs(ca) < 0.72:
                    ly *= 0.42
                offset = ear_rot @ Vector((rx * ca, ly, 0.0))
                ring.append(head_to_world(c + offset))
            rings.append(ring)

        start_pole = head_to_world(p_base)
        end_pole = head_to_world(p_tip)
        ear_front_dir = (HEAD_ROT @ (ear_rot @ Vector((0.0, -1.0, 0.0)))).normalized()

        def ear_mat_fn(co, normal):
            lco = world_to_head(co)
            rel_h = clamp01((lco.z - 0.042) / 0.062)
            if normal.dot(ear_front_dir) > 0.38 and 0.16 < rel_h < 0.82:
                if abs(lco.x) > 0.036 and abs(lco.x) < 0.070:
                    return 2
            if rel_h > 0.76:
                return 1
            return 0

        ear = build_loft_object(
            f"Ear_{int(side)}",
            start_pole,
            rings,
            end_pole,
            [mat_orange, mat_dark_orange, mat_pink],
            subsurf_levels=1,
            mat_fn=ear_mat_fn,
        )
        ear_objs.append(ear)

    return ear_objs


def create_legs_and_paws(mat_orange, mat_white):
    objs = []
    leg_specs = [
        ("FrontLeg", -0.088, True),
        ("BackLeg", 0.132, False),
    ]

    for base_name, y_base, is_front in leg_specs:
        for side in (-1.0, 1.0):
            x_base = side * (0.044 if is_front else 0.050)
            z_top = 0.146 if is_front else 0.154

            if is_front:
                profile = [
                    (0.125, x_base, y_base, 0.028, 0.030),
                    (0.082, x_base, y_base - 0.003, 0.023, 0.024),
                    (0.038, x_base, y_base - 0.005, 0.021, 0.022),
                    (0.018, x_base, y_base - 0.015, 0.026, 0.031),
                    (0.003, x_base, y_base - 0.016, 0.025, 0.030),
                ]
                paw_center = Vector((x_base, y_base - 0.015, 0.0))
            else:
                profile = [
                    (0.128, x_base, y_base - 0.004, 0.034, 0.042),
                    (0.085, x_base, y_base + 0.006, 0.026, 0.030),
                    (0.040, x_base, y_base - 0.002, 0.021, 0.023),
                    (0.018, x_base, y_base - 0.014, 0.027, 0.032),
                    (0.003, x_base, y_base - 0.015, 0.026, 0.031),
                ]
                paw_center = Vector((x_base, y_base - 0.014, 0.0))

            start_pole = Vector((x_base, y_base, z_top))
            end_pole = Vector((paw_center.x, paw_center.y, 0.0))

            n_seg = 8
            rings = []
            for z_val, cx, cy, rx, ry in profile:
                ring = []
                for j in range(n_seg):
                    ang = (2.0 * math.pi * j) / n_seg
                    px = cx + rx * math.cos(ang)
                    py = cy + ry * math.sin(ang)
                    pz = max(0.0, z_val)
                    ring.append(Vector((px, py, pz)))
                rings.append(ring)

            def leg_mat_fn(co, normal):
                if co.z < 0.042:
                    return 1
                return 0

            leg_obj = build_loft_object(
                f"{base_name}_{int(side)}",
                start_pole,
                rings,
                end_pole,
                [mat_orange, mat_white],
                subsurf_levels=1,
                mat_fn=leg_mat_fn,
            )
            for v in leg_obj.data.vertices:
                if v.co.z < 0.002:
                    v.co.z = 0.0
            objs.append(leg_obj)

            for t_idx in (-1, 0, 1):
                ang_toe = t_idx * 0.42
                tx = paw_center.x + math.sin(ang_toe) * 0.018
                ty = paw_center.y - math.cos(ang_toe) * 0.025
                t_back = Vector((paw_center.x, paw_center.y - 0.006, 0.010))
                t_front = Vector((tx, ty - 0.010, 0.008))
                t_rings = []
                for r_i in range(1, 3):
                    s = r_i / 3.0
                    env = math.sin(s * math.pi)
                    tc = t_back.lerp(t_front, s)
                    ring = []
                    for j in range(6):
                        a = (2.0 * math.pi * j) / 6.0
                        vx = tc.x + 0.0085 * env * math.cos(a)
                        vy = tc.y + 0.0050 * env * math.cos(a)
                        vz = max(0.0, tc.z + 0.0095 * env * math.sin(a))
                        ring.append(Vector((vx, vy, vz)))
                    t_rings.append(ring)

                toe_obj = build_loft_object(
                    f"Toe_{base_name}_{int(side)}_{t_idx}",
                    t_back,
                    t_rings,
                    t_front,
                    [mat_white],
                    subsurf_levels=0,
                )
                for v in toe_obj.data.vertices:
                    if v.co.z < 0.0015:
                        v.co.z = 0.0
                objs.append(toe_obj)

    return objs


def create_tail(mat_orange, mat_dark_orange, mat_white):
    n_rings = 13
    n_seg = 8

    def tail_curve(t):
        t = clamp01(t)
        x = 0.015 * math.sin(t * math.pi)
        y = 0.180 + 0.068 * math.sin(t * math.pi * 0.65) + 0.036 * t - 0.024 * math.sin(t * math.pi * 1.85)
        z = 0.140 + 0.155 * t - 0.016 * math.sin(t * math.pi * 1.5)
        return Vector((x, y, z))

    start_pole = tail_curve(0.0)
    end_pole = tail_curve(1.0)

    rings = []
    for i in range(1, n_rings + 1):
        t = clamp01(i / (n_rings + 1))
        c = tail_curve(t)
        dt = 0.01
        tang = (tail_curve(min(1.0, t + dt)) - tail_curve(max(0.0, t - dt))).normalized()
        up_ref = Vector((1.0, 0.0, 0.0))
        binorm = tang.cross(up_ref).normalized()
        norm_v = binorm.cross(tang).normalized()

        taper = (1.0 - 0.42 * (t ** 1.6)) * (0.45 + 0.55 * math.sin(clamp01(0.15 + 0.80 * t) * math.pi))
        rad = 0.023 * max(0.25, taper)

        ring = []
        for j in range(n_seg):
            ang = (2.0 * math.pi * j) / n_seg
            offset = (norm_v * math.cos(ang) + binorm * math.sin(ang)) * rad
            ring.append(c + offset)
        rings.append(ring)

    def tail_mat_fn(co, normal):
        if co.z > 0.278 and co.y > 0.255:
            return 2
        if normal.z > 0.05 or normal.y < -0.15:
            s_approx = clamp01((co.z - 0.145) / 0.150)
            for sc in (0.24, 0.48, 0.70):
                if abs(s_approx - sc) < 0.065:
                    return 1
        return 0

    return build_loft_object(
        "Tail",
        start_pole,
        rings,
        end_pole,
        [mat_orange, mat_dark_orange, mat_white],
        subsurf_levels=1,
        mat_fn=tail_mat_fn,
    )


def build_mittens():
    mat_orange = make_material("Mat_Orange", (0.92, 0.36, 0.07, 1.0), roughness=0.45)
    mat_dark_orange = make_material("Mat_DarkOrange", (0.55, 0.14, 0.02, 1.0), roughness=0.46)
    mat_white = make_material("Mat_White", (0.96, 0.94, 0.90, 1.0), roughness=0.44)
    mat_pink = make_material("Mat_Pink", (0.94, 0.42, 0.48, 1.0), roughness=0.42)
    mat_green = make_material("Mat_Green", (0.14, 0.72, 0.22, 1.0), roughness=0.35)
    mat_black = make_material("Mat_Black", (0.03, 0.03, 0.04, 1.0), roughness=0.35)

    body_mats = [mat_orange, mat_dark_orange, mat_white]

    all_parts = []
    all_parts.append(create_torso(body_mats))
    all_parts.append(create_neck(body_mats))
    all_parts.append(create_chest_bib(body_mats))
    all_parts.append(create_head(body_mats))

    for side in (-1.0, 1.0):
        puff = create_ellipsoid_head_part(
            f"MuzzlePuff_{int(side)}",
            Vector((side * 0.017, -0.058, -0.020)),
            (0.024, 0.022, 0.018),
            (0.0, side * math.radians(10.0), side * math.radians(-8.0)),
            mat_white,
            n_rings=3,
            n_seg=8,
            subsurf_levels=1,
        )
        all_parts.append(puff)

    chin = create_ellipsoid_head_part(
        "Chin",
        Vector((0.0, -0.054, -0.034)),
        (0.022, 0.020, 0.013),
        (math.radians(10.0), 0.0, 0.0),
        mat_white,
        n_rings=3,
        n_seg=8,
        subsurf_levels=1,
    )
    all_parts.append(chin)

    all_parts.append(create_nose(mat_pink))
    all_parts.extend(create_mouth(mat_black))
    all_parts.extend(create_whiskers(mat_white))
    all_parts.extend(create_eyes(mat_white, mat_green, mat_black))
    all_parts.extend(create_ears(mat_orange, mat_dark_orange, mat_pink))
    all_parts.extend(create_legs_and_paws(mat_orange, mat_white))
    all_parts.append(create_tail(mat_orange, mat_dark_orange, mat_white))

    bpy.ops.object.select_all(action='DESELECT')
    for part in all_parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = all_parts[0]
    bpy.ops.object.join()

    mittens = bpy.context.view_layer.objects.active
    mittens.name = "Mittens"
    mittens.data.name = "Mittens_Mesh"

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    verts = mittens.data.vertices
    min_x = min(v.co.x for v in verts)
    max_x = max(v.co.x for v in verts)
    min_y = min(v.co.y for v in verts)
    max_y = max(v.co.y for v in verts)
    min_z = min(v.co.z for v in verts)

    cx = 0.5 * (min_x + max_x)
    cy = 0.5 * (min_y + max_y)
    offset = Vector((-cx, -cy, -min_z))
    for v in verts:
        v.co += offset
        if v.co.z < 0.0005:
            v.co.z = 0.0

    mittens.location = (0.0, 0.0, 0.0)
    mittens.data.update()

    bm = bmesh.new()
    bm.from_mesh(mittens.data)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(mittens.data)
    bm.free()

    return mittens


def setup_render_and_camera(mittens, png_path):
    scene = bpy.context.scene

    engine_keys = [item.identifier for item in scene.render.bl_rna.properties['engine'].enum_items]
    for candidate in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        if candidate in engine_keys:
            scene.render.engine = candidate
            break
    else:
        for k in engine_keys:
            if 'EEVEE' in k:
                scene.render.engine = k
                break

    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = png_path

    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    w_nodes = scene.world.node_tree.nodes
    bg = w_nodes.get("Background")
    if bg is None:
        bg = w_nodes.new(type="ShaderNodeBackground")
    if "Color" in bg.inputs:
        bg.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1.0)
    if "Strength" in bg.inputs:
        bg.inputs["Strength"].default_value = 0.45

    sun_data = bpy.data.lights.new(name="KeySun", type='SUN')
    sun_data.energy = 3.0
    sun_data.angle = math.radians(12.0)
    sun_obj = bpy.data.objects.new("KeySun", sun_data)
    bpy.context.collection.objects.link(sun_obj)
    sun_obj.location = (-1.5, -2.0, 2.5)
    sun_dir = Vector((0.45, 0.65, -0.60)).normalized()
    sun_obj.rotation_mode = 'QUATERNION'
    sun_obj.rotation_quaternion = sun_dir.to_track_quat('-Z', 'Y')

    fill_data = bpy.data.lights.new(name="FillLight", type='AREA')
    fill_data.energy = 15.0
    fill_data.size = 1.6
    fill_obj = bpy.data.objects.new("FillLight", fill_data)
    bpy.context.collection.objects.link(fill_obj)
    fill_obj.location = (1.1, -1.2, 0.85)
    fill_dir = (Vector((0.0, 0.0, 0.16)) - fill_obj.location).normalized()
    fill_obj.rotation_mode = 'QUATERNION'
    fill_obj.rotation_quaternion = fill_dir.to_track_quat('-Z', 'Y')

    cam_data = bpy.data.cameras.new(name="PreviewCam")
    cam_data.lens = 50.0
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.05
    cam_data.clip_end = 50.0
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    world_verts = [mittens.matrix_world @ v.co for v in mittens.data.vertices]
    min_v = Vector((
        min(p.x for p in world_verts),
        min(p.y for p in world_verts),
        min(p.z for p in world_verts),
    ))
    max_v = Vector((
        max(p.x for p in world_verts),
        max(p.y for p in world_verts),
        max(p.z for p in world_verts),
    ))
    target = 0.5 * (min_v + max_v)

    cam_offset_dir = Vector((-0.62, -0.74, 0.34)).normalized()
    forward = -cam_offset_dir
    right = forward.cross(Vector((0.0, 0.0, 1.0))).normalized()
    up = right.cross(forward).normalized()
    half_tan = (0.5 * cam_data.sensor_width) / cam_data.lens
    fill_ratio = 0.80

    dist = 0.85
    for _ in range(4):
        cam_pos = target + cam_offset_dir * dist
        min_sx, max_sx = 1e9, -1e9
        min_sy, max_sy = 1e9, -1e9
        req_dist = 0.2
        for p in world_verts:
            rel = p - target
            du = rel.dot(right)
            dv = rel.dot(up)
            dz = rel.dot(cam_offset_dir)
            depth = max(0.05, dist - dz)
            sx = du / (depth * half_tan)
            sy = dv / (depth * half_tan)
            min_sx = min(min_sx, sx)
            max_sx = max(max_sx, sx)
            min_sy = min(min_sy, sy)
            max_sy = max(max_sy, sy)
            d_need = dz + max(abs(du), abs(dv)) / (fill_ratio * half_tan)
            req_dist = max(req_dist, d_need)

        shift_u = 0.5 * (min_sx + max_sx) * dist * half_tan
        shift_v = 0.5 * (min_sy + max_sy) * dist * half_tan
        target += right * shift_u + up * shift_v
        dist = req_dist

    cam_obj.location = target + cam_offset_dir * dist
    cam_obj.rotation_mode = 'QUATERNION'
    cam_obj.rotation_quaternion = forward.to_track_quat('-Z', 'Y')

    bpy.ops.render.render(write_still=True)


def main():
    out_fbx = "Mittens.fbx"
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if idx + 1 < len(sys.argv):
            out_fbx = sys.argv[idx + 1]

    out_fbx = os.path.abspath(out_fbx)
    out_dir = os.path.dirname(out_fbx)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    out_png = os.path.splitext(out_fbx)[0] + ".png"

    clear_scene()
    mittens = build_mittens()

    bpy.ops.object.select_all(action='DESELECT')
    mittens.select_set(True)
    bpy.context.view_layer.objects.active = mittens

    bpy.ops.export_scene.fbx(
        filepath=out_fbx,
        use_selection=True,
        bake_space_transform=True,
        axis_forward='-Z',
        axis_up='Y',
        mesh_smooth_type='FACE',
    )

    setup_render_and_camera(mittens, out_png)

    n_tris = sum(len(p.vertices) - 2 for p in mittens.data.polygons)
    print("TRIS", n_tris)


if __name__ == "__main__":
    main()
