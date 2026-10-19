import bpy
import bmesh
import math
import sys
import os
from mathutils import Vector, Matrix, Euler


def clamp01(val):
    return max(0.0, min(1.0, float(val)))


def safe_pow(base, exp):
    return math.pow(clamp01(base), exp)


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)
    for light in list(bpy.data.lights):
        bpy.data.lights.remove(light)
    for cam in list(bpy.data.cameras):
        bpy.data.cameras.remove(cam)
    for world in list(bpy.data.worlds):
        bpy.data.worlds.remove(world)


def make_material(name, color, roughness=0.45, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    if "Base Color" in bsdf.inputs:
        bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1.0)
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    mat.diffuse_color = (color[0], color[1], color[2], 1.0)
    return mat


def ensure_material_slot(obj, mat):
    for idx, slot in enumerate(obj.material_slots):
        if slot.material == mat:
            return idx
    obj.data.materials.append(mat)
    return len(obj.material_slots) - 1


def create_loft_object(name, rings, start_pole, end_pole, materials, strip_mat_fn, subsurf_levels=1):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    for mat in materials:
        ensure_material_slot(obj, mat)

    bm = bmesh.new()
    n_rings = len(rings)
    seg_count = len(rings[0])

    v_start = bm.verts.new(start_pole)
    v_rings = []
    for r_pts in rings:
        row = [bm.verts.new(pt) for pt in r_pts]
        v_rings.append(row)
    v_end = bm.verts.new(end_pole)

    bm.verts.ensure_lookup_table()

    for i in range(seg_count):
        i_next = (i + 1) % seg_count
        f = bm.faces.new((v_start, v_rings[0][i], v_rings[0][i_next]))
        f.smooth = True
        f.material_index = strip_mat_fn(-1, i, seg_count)

    for r in range(n_rings - 1):
        for i in range(seg_count):
            i_next = (i + 1) % seg_count
            f = bm.faces.new((
                v_rings[r][i],
                v_rings[r + 1][i],
                v_rings[r + 1][i_next],
                v_rings[r][i_next],
            ))
            f.smooth = True
            f.material_index = strip_mat_fn(r, i, seg_count)

    for i in range(seg_count):
        i_next = (i + 1) % seg_count
        f = bm.faces.new((v_rings[-1][i], v_end, v_rings[-1][i_next]))
        f.smooth = True
        f.material_index = strip_mat_fn(n_rings - 1, i, seg_count)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    if subsurf_levels > 0:
        mod = obj.modifiers.new("Subsurf", "SUBSURF")
        mod.levels = subsurf_levels
        mod.render_levels = subsurf_levels
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)

    bm2 = bmesh.new()
    bm2.from_mesh(obj.data)
    bmesh.ops.triangulate(bm2, faces=bm2.faces)
    for f in bm2.faces:
        f.smooth = True
    bmesh.ops.recalc_face_normals(bm2, faces=bm2.faces)
    bm2.to_mesh(obj.data)
    bm2.free()

    for poly in obj.data.polygons:
        poly.use_smooth = True

    return obj


def make_tilted_ring(center, rx, ry_neg, ry_pos, rz_bot, rz_top, pitch_deg, segs):
    rot = Euler((math.radians(pitch_deg), 0.0, 0.0), 'XYZ').to_matrix()
    pts = []
    for i in range(segs):
        ang = (2.0 * math.pi * i) / float(segs)
        ca = math.cos(ang)
        sa = math.sin(ang)
        x = ca * rx
        y = sa * (ry_pos if sa >= 0.0 else ry_neg)
        z = sa * (rz_top if sa >= 0.0 else rz_bot)
        local_pt = Vector((x, y, z))
        pts.append(center + (rot @ local_pt))
    return pts


def make_yz_ring(center, rx, rz_bot, rz_top, pitch_deg, yaw_deg, segs):
    rot = Euler((math.radians(pitch_deg), 0.0, math.radians(yaw_deg)), 'XYZ').to_matrix()
    pts = []
    for i in range(segs):
        ang = (2.0 * math.pi * i) / float(segs)
        ca = math.cos(ang)
        sa = math.sin(ang)
        x = ca * rx
        z = sa * (rz_top if sa >= 0.0 else rz_bot)
        local_pt = Vector((x, 0.0, z))
        pts.append(center + (rot @ local_pt))
    return pts


def make_xy_ring(center, rx, ry_front, ry_back, pitch_deg, segs):
    rot = Euler((math.radians(pitch_deg), 0.0, 0.0), 'XYZ').to_matrix()
    pts = []
    for i in range(segs):
        ang = (2.0 * math.pi * i) / float(segs)
        ca = math.cos(ang)
        sa = math.sin(ang)
        x = ca * rx
        y = sa * (ry_back if sa >= 0.0 else ry_front)
        local_pt = Vector((x, y, 0.0))
        pts.append(center + (rot @ local_pt))
    return pts


def build_pigeon_parts(mats):
    parts = []
    mat_list = [
        mats["body_grey"],     # 0
        mats["wing_grey"],     # 1
        mats["head_grey"],     # 2
        mats["neck_green"],    # 3
        mats["neck_purple"],   # 4
        mats["dark_band"],     # 5
        mats["cere_white"],    # 6
        mats["eye_orange"],    # 7
        mats["leg_pink"],      # 8
    ]

    # 1. Plump Torso (S=10, N_rings=8 -> 680 tris)
    torso_segs = 10
    torso_specs = [
        (Vector((0.0, -0.075, 0.140)), 0.032, 0.030, 0.028, 18.0),
        (Vector((0.0, -0.056, 0.137)), 0.050, 0.048, 0.044, 15.0),
        (Vector((0.0, -0.028, 0.132)), 0.056, 0.052, 0.047, 12.0),
        (Vector((0.0,  0.004, 0.123)), 0.053, 0.050, 0.043, 10.0),
        (Vector((0.0,  0.035, 0.114)), 0.045, 0.042, 0.036,  8.0),
        (Vector((0.0,  0.062, 0.105)), 0.034, 0.030, 0.027,  6.0),
        (Vector((0.0,  0.086, 0.096)), 0.023, 0.019, 0.018,  4.0),
        (Vector((0.0,  0.104, 0.090)), 0.015, 0.012, 0.012,  2.0),
    ]
    torso_rings = [
        make_yz_ring(c, rx, rzb, rzt, pitch, 0.0, torso_segs)
        for (c, rx, rzb, rzt, pitch) in torso_specs
    ]
    torso_start = Vector((0.0, -0.084, 0.142))
    torso_end = Vector((0.0, 0.114, 0.087))

    def torso_mat_fn(r_idx, i_idx, s_cnt):
        if r_idx >= 5:
            return 1
        return 0

    parts.append(create_loft_object(
        "TorsoPart", torso_rings, torso_start, torso_end, mat_list, torso_mat_fn, 1
    ))

    # 2. Neck + Round Head with Iridescent Green & Purple Neck Patch (S=10, N_rings=8 -> 680 tris)
    neck_segs = 10
    neck_specs = [
        (Vector((0.0, -0.043, 0.130)), 0.045, 0.042, 0.043, -6.0),
        (Vector((0.0, -0.045, 0.152)), 0.041, 0.038, 0.039, -4.0),
        (Vector((0.0, -0.045, 0.171)), 0.035, 0.032, 0.035, -2.0),
        (Vector((0.0, -0.046, 0.189)), 0.031, 0.029, 0.031,  0.0),
        (Vector((0.0, -0.048, 0.205)), 0.032, 0.034, 0.032,  2.0),
        (Vector((0.0, -0.049, 0.221)), 0.031, 0.034, 0.031,  3.0),
        (Vector((0.0, -0.048, 0.237)), 0.024, 0.026, 0.025,  2.0),
        (Vector((0.0, -0.047, 0.246)), 0.012, 0.013, 0.013,  0.0),
    ]
    neck_rings = [
        make_xy_ring(c, rx, ryf, ryb, pitch, neck_segs)
        for (c, rx, ryf, ryb, pitch) in neck_specs
    ]
    neck_start = Vector((0.0, -0.042, 0.118))
    neck_end = Vector((0.0, -0.047, 0.251))

    def neck_mat_fn(r_idx, i_idx, s_cnt):
        ang = (2.0 * math.pi * (i_idx + 0.5)) / float(s_cnt)
        sa = math.sin(ang)
        if r_idx <= 0:
            return 0
        if r_idx == 1:
            return 4
        if r_idx == 2:
            return 3 if sa > -0.45 else 4
        if r_idx == 3:
            return 3 if sa > -0.15 else 2
        return 2

    parts.append(create_loft_object(
        "NeckHeadPart", neck_rings, neck_start, neck_end, mat_list, neck_mat_fn, 1
    ))

    # 3. Short Dark Upper Beak (S=6, N_rings=3 -> 168 tris)
    ubeak_segs = 6
    ubeak_rings = [
        make_yz_ring(Vector((0.0, -0.072, 0.215)), 0.011, 0.005, 0.009,  4.0, 0.0, ubeak_segs),
        make_yz_ring(Vector((0.0, -0.084, 0.214)), 0.008, 0.004, 0.007,  8.0, 0.0, ubeak_segs),
        make_yz_ring(Vector((0.0, -0.094, 0.211)), 0.004, 0.002, 0.004, 14.0, 0.0, ubeak_segs),
    ]
    ubeak_start = Vector((0.0, -0.065, 0.215))
    ubeak_end = Vector((0.0, -0.101, 0.208))
    parts.append(create_loft_object(
        "UpperBeakPart", ubeak_rings, ubeak_start, ubeak_end, mat_list, lambda r, i, s: 5, 1
    ))

    # 4. Short Dark Lower Beak (S=6, N_rings=2 -> 120 tris)
    lbeak_segs = 6
    lbeak_rings = [
        make_yz_ring(Vector((0.0, -0.072, 0.210)), 0.009, 0.005, 0.003, 0.0, 0.0, lbeak_segs),
        make_yz_ring(Vector((0.0, -0.086, 0.209)), 0.005, 0.003, 0.002, 4.0, 0.0, lbeak_segs),
    ]
    lbeak_start = Vector((0.0, -0.065, 0.210))
    lbeak_end = Vector((0.0, -0.095, 0.209))
    parts.append(create_loft_object(
        "LowerBeakPart", lbeak_rings, lbeak_start, lbeak_end, mat_list, lambda r, i, s: 5, 1
    ))

    # 5. White Cere across Base of Upper Beak (S=6, N_rings=3 -> 168 tris)
    cere_segs = 6
    cere_rings = []
    for x_pos, rad_yz, z_off in ((-0.006, 0.0065, 0.218), (0.0, 0.0052, 0.219), (0.006, 0.0065, 0.218)):
        ring_pts = []
        for i in range(cere_segs):
            ang = (2.0 * math.pi * i) / float(cere_segs)
            cy = -0.079 + math.cos(ang) * rad_yz
            cz = z_off + math.sin(ang) * (rad_yz * 0.85)
            ring_pts.append(Vector((x_pos, cy, cz)))
        cere_rings.append(ring_pts)
    cere_start = Vector((-0.011, -0.078, 0.217))
    cere_end = Vector((0.011, -0.078, 0.217))
    parts.append(create_loft_object(
        "CerePart", cere_rings, cere_start, cere_end, mat_list, lambda r, i, s: 6, 1
    ))

    # 6. Orange Eyes + Orbital Rings + Dark Pupils (L & R)
    for side_idx, side in enumerate((-1.0, 1.0)):
        suffix = "R" if side < 0.0 else "L"
        eye_base = Vector((side * 0.025, -0.060, 0.221))
        out_dir = Vector((side * 0.86, -0.50, 0.08)).normalized()
        up_dir = Vector((0.0, 0.08, 0.99)).normalized()
        tan_dir = out_dir.cross(up_dir).normalized()
        up_dir = tan_dir.cross(out_dir).normalized()

        # Pale Orbital Eye-Ring (S=6, N_rings=2 -> 120 tris each)
        orb_segs = 6
        orb_rings = []
        for d_along, r_rad in ((-0.003, 0.0078), (0.0035, 0.0068)):
            c_pt = eye_base + out_dir * d_along
            ring_pts = []
            for i in range(orb_segs):
                ang = (2.0 * math.pi * i) / float(orb_segs)
                pt = c_pt + (tan_dir * math.cos(ang) + up_dir * math.sin(ang)) * r_rad
                ring_pts.append(pt)
            orb_rings.append(ring_pts)
        orb_start = eye_base - out_dir * 0.006
        orb_end = eye_base + out_dir * 0.005
        parts.append(create_loft_object(
            f"OrbitalRing_{suffix}", orb_rings, orb_start, orb_end, mat_list, lambda r, i, s: 6, 1
        ))

        # Orange Eyeball with Black Pupil (S=6, N_rings=3 -> 168 tris each)
        eye_segs = 6
        eye_rings = []
        for d_along, r_rad in ((-0.002, 0.0062), (0.0042, 0.0055), (0.0062, 0.0028)):
            c_pt = eye_base + out_dir * d_along
            ring_pts = []
            for i in range(eye_segs):
                ang = (2.0 * math.pi * i) / float(eye_segs)
                pt = c_pt + (tan_dir * math.cos(ang) + up_dir * math.sin(ang)) * r_rad
                ring_pts.append(pt)
            eye_rings.append(ring_pts)
        eye_start = eye_base - out_dir * 0.005
        eye_end = eye_base + out_dir * 0.0072

        def eye_mat_fn(r_idx, i_idx, s_cnt):
            if r_idx >= 1:
                return 5
            return 7

        parts.append(create_loft_object(
            f"Eye_{suffix}", eye_rings, eye_start, eye_end, mat_list, eye_mat_fn, 1
        ))

    # 7. Tail Fan: 5 Overlapping Feathers with Dark Tail Band (5 * 144 = 720 tris)
    tail_segs = 4
    tail_root = Vector((0.0, 0.088, 0.095))
    for f_idx in range(-2, 3):
        yaw_deg = f_idx * 6.5
        roll_deg = f_idx * 4.0
        z_layer = -abs(f_idx) * 0.0018
        rot_mat = Euler((math.radians(-22.0), math.radians(roll_deg), math.radians(yaw_deg)), 'XYZ').to_matrix()

        f_specs = [
            (0.010, 0.013, 0.0040),
            (0.038, 0.017, 0.0038),
            (0.068, 0.019, 0.0035),
            (0.092, 0.015, 0.0028),
        ]
        f_rings = []
        for dist, w_half, t_half in f_specs:
            c_pt = tail_root + Vector((0.0, 0.0, z_layer)) + (rot_mat @ Vector((0.0, dist, 0.0)))
            ring_pts = []
            for i in range(tail_segs):
                ang = (2.0 * math.pi * i) / float(tail_segs)
                lx = math.cos(ang) * w_half
                lz = math.sin(ang) * t_half
                ring_pts.append(c_pt + (rot_mat @ Vector((lx, 0.0, lz))))
            f_rings.append(ring_pts)

        f_start = tail_root + Vector((0.0, 0.0, z_layer)) + (rot_mat @ Vector((0.0, -0.012, 0.0)))
        f_end = tail_root + Vector((0.0, 0.0, z_layer)) + (rot_mat @ Vector((0.0, 0.104, 0.0)))

        def tail_mat_fn(r_idx, i_idx, s_cnt):
            if r_idx == 1:
                return 5
            if r_idx == 2:
                return 5
            if r_idx >= 3:
                return 1
            return 0

        parts.append(create_loft_object(
            f"TailFeather_{f_idx + 2}", f_rings, f_start, f_end, mat_list, tail_mat_fn, 1
        ))

    # 8. Pink-Red Legs, Thigh Cuffs, Toes, and Claws (L & R)
    for side in (-1.0, 1.0):
        suffix = "R" if side < 0.0 else "L"
        hip_x = side * 0.030

        # Continuous Feathered Drumstick + Scaled Pink Tarsus + Foot Pad (S=6, N_rings=5 -> 264 tris each)
        leg_segs = 6
        leg_specs = [
            (Vector((hip_x,  0.012, 0.116)), 0.020, 0.022, 0.0),
            (Vector((hip_x,  0.018, 0.082)), 0.014, 0.016, 6.0),
            (Vector((hip_x,  0.023, 0.055)), 0.009, 0.010, 10.0),
            (Vector((hip_x,  0.008, 0.026)), 0.007, 0.008, -14.0),
            (Vector((hip_x, -0.005, 0.008)), 0.011, 0.013, 0.0),
        ]
        leg_rings = [
            make_xy_ring(c, rx, ry, ry, pitch, leg_segs)
            for (c, rx, ry, pitch) in leg_specs
        ]
        leg_start = Vector((hip_x, 0.010, 0.128))
        leg_end = Vector((hip_x, -0.005, 0.001))

        def leg_mat_fn(r_idx, i_idx, s_cnt):
            if r_idx <= 0:
                return 0
            return 8

        parts.append(create_loft_object(
            f"LegShaft_{suffix}", leg_rings, leg_start, leg_end, mat_list, leg_mat_fn, 1
        ))

        # 4 Toes per Foot (3 Forward + 1 Back Hallux) with Dark Claws (4 * 112 = 448 tris per foot)
        ankle_pt = Vector((hip_x, -0.005, 0.0055))
        toe_defs = [
            ("Mid",   0.0,           0.036, 0.0052),
            ("Inner", -side * 28.0,  0.029, 0.0046),
            ("Outer",  side * 28.0,  0.029, 0.0046),
            ("Back",  180.0,         0.019, 0.0044),
        ]
        toe_segs = 4
        for t_name, yaw_deg, t_len, t_rad in toe_defs:
            yaw_rad = math.radians(yaw_deg)
            fwd_vec = Vector((-math.sin(yaw_rad), -math.cos(yaw_rad), 0.0)).normalized()
            side_vec = Vector((math.cos(yaw_rad), -math.sin(yaw_rad), 0.0)).normalized()

            t_rings = []
            for frac, r_scale, z_c in ((0.12, 1.0, 0.0055), (0.55, 0.90, 0.0050), (0.84, 0.68, 0.0040)):
                c_pt = Vector((ankle_pt.x, ankle_pt.y, z_c)) + fwd_vec * (t_len * frac)
                r_w = t_rad * r_scale
                r_h = t_rad * r_scale * 0.80
                ring_pts = [
                    c_pt + side_vec * r_w,
                    c_pt + Vector((0.0, 0.0, r_h * 1.15)),
                    c_pt - side_vec * r_w,
                    Vector((c_pt.x, c_pt.y, 0.0005)),
                ]
                t_rings.append(ring_pts)

            t_start = ankle_pt - fwd_vec * 0.005
            t_end = Vector((ankle_pt.x, ankle_pt.y, 0.0012)) + fwd_vec * (t_len * 1.04)

            def toe_mat_fn(r_idx, i_idx, s_cnt):
                if r_idx >= 1:
                    return 5
                return 8

            parts.append(create_loft_object(
                f"Toe_{suffix}_{t_name}", t_rings, t_start, t_end, mat_list, toe_mat_fn, 1
            ))

    # Join all Pigeon parts into ONE object named "Pigeon"
    bpy.ops.object.select_all(action='DESELECT')
    for p_obj in parts:
        p_obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    pigeon_obj = bpy.context.view_layer.objects.active
    pigeon_obj.name = "Pigeon"
    pigeon_obj.data.name = "Pigeon_Mesh"

    for poly in pigeon_obj.data.polygons:
        poly.use_smooth = True

    return pigeon_obj


def build_wing_object(name, side, mats):
    # side: +1.0 for WingL (+X), -1.0 for WingR (-X)
    # Shoulder joint origin in world space:
    shoulder_origin = Vector((side * 0.046, -0.032, 0.146))

    mat_list = [
        mats["wing_grey"],   # 0: light blue-grey wing shield
        mats["dark_band"],   # 1: two dark wing bars + dark primary tips
        mats["body_grey"],   # 2: scapular/inner blend
    ]

    # Main Contoured Wing Blade in local space relative to shoulder_origin (S=8, N_rings=9 -> 608 tris)
    wing_segs = 8
    # (local_center, half_thickness_x, half_height_z, pitch_deg, is_bar)
    wing_specs = [
        (Vector((-side * 0.006, -0.012,  0.002)), 0.015, 0.024, 15.0, False),
        (Vector(( side * 0.005,  0.004, -0.001)), 0.018, 0.034, 14.0, False),
        (Vector(( side * 0.008,  0.024, -0.006)), 0.018, 0.038, 12.0, False),
        (Vector(( side * 0.009,  0.044, -0.012)), 0.019, 0.037, 10.0, True),   # Bar 1 start
        (Vector(( side * 0.007,  0.062, -0.018)), 0.017, 0.034,  9.0, False),  # Bar 1 end / mid grey
        (Vector(( side * 0.005,  0.080, -0.024)), 0.017, 0.030,  8.0, True),   # Bar 2 start
        (Vector(( side * 0.001,  0.097, -0.030)), 0.014, 0.025,  6.0, False),  # Bar 2 end / outer grey
        (Vector((-side * 0.006,  0.114, -0.036)), 0.011, 0.018,  5.0, False),  # Primary feathers
        (Vector((-side * 0.014,  0.128, -0.041)), 0.007, 0.010,  4.0, False),  # Primary tip ring
    ]

    wing_rings = []
    for c_loc, rx, rz, pitch_deg, is_bar in wing_specs:
        rot = Euler((math.radians(pitch_deg), 0.0, 0.0), 'XYZ').to_matrix()
        ring_pts = []
        for i in range(wing_segs):
            ang = (2.0 * math.pi * i) / float(wing_segs)
            ca = math.cos(ang)
            sa = math.sin(ang)
            # Outer side bulges convexly; inner side hugs body closely
            outer_boost = 1.15 if (ca * side > 0.0 and is_bar) else 1.0
            inward_tuck = 0.72 if (ca * side < 0.0) else outer_boost
            lx = ca * rx * inward_tuck
            lz = sa * rz
            ring_pts.append(c_loc + (rot @ Vector((lx, 0.0, lz))))
        wing_rings.append(ring_pts)

    wing_start = Vector((-side * 0.016, -0.022, 0.005))
    wing_end = Vector((-side * 0.020, 0.140, -0.045))

    def wing_mat_fn(r_idx, i_idx, s_cnt):
        if r_idx == 2 or r_idx == 4:
            return 1
        if r_idx >= 6:
            return 1
        if r_idx <= -1:
            return 2
        return 0

    main_wing = create_loft_object(
        name + "_Main", wing_rings, wing_start, wing_end, mat_list, wing_mat_fn, 1
    )

    # Secondary Covert Feather Ridge embedded into upper-rear of Wing (S=4, N_rings=3 -> 112 tris)
    sec_segs = 4
    sec_rings = []
    for y_off, z_off, rx, rz in (
        (0.050, -0.004, 0.009, 0.014),
        (0.082, -0.014, 0.008, 0.012),
        (0.108, -0.024, 0.005, 0.008),
    ):
        c_loc = Vector((side * 0.004, y_off, z_off))
        ring_pts = []
        for i in range(sec_segs):
            ang = (2.0 * math.pi * i) / float(sec_segs)
            ring_pts.append(c_loc + Vector((math.cos(ang) * rx, 0.0, math.sin(ang) * rz)))
        sec_rings.append(ring_pts)
    sec_start = Vector((0.0, 0.032, 0.002))
    sec_end = Vector((-side * 0.008, 0.122, -0.030))

    sec_feather = create_loft_object(
        name + "_Secondary", sec_rings, sec_start, sec_end, mat_list, lambda r, i, s: (1 if r >= 1 else 0), 1
    )

    bpy.ops.object.select_all(action='DESELECT')
    main_wing.select_set(True)
    sec_feather.select_set(True)
    bpy.context.view_layer.objects.active = main_wing
    bpy.ops.object.join()
    wing_obj = bpy.context.view_layer.objects.active
    wing_obj.name = name
    wing_obj.data.name = name + "_Mesh"
    wing_obj.location = shoulder_origin

    for poly in wing_obj.data.polygons:
        poly.use_smooth = True

    return wing_obj


def setup_scene_and_render(objects, png_path):
    scene = bpy.context.scene

    # Choose EEVEE engine dynamically from enum_items keys
    engine_keys = list(scene.render.bl_rna.properties['engine'].enum_items.keys())
    if 'BLENDER_EEVEE_NEXT' in engine_keys:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    elif 'BLENDER_EEVEE' in engine_keys:
        scene.render.engine = 'BLENDER_EEVEE'
    else:
        scene.render.engine = engine_keys[0]

    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = False

    # Grey World of strength 0.45
    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    w_nodes = world.node_tree.nodes
    bg = w_nodes.get("Background")
    if bg is None:
        bg = w_nodes.new(type="ShaderNodeBackground")
    bg.inputs[0].default_value = (0.50, 0.50, 0.52, 1.0)
    bg.inputs[1].default_value = 0.45

    # Sun light of strength 3.0
    sun_data = bpy.data.lights.new("KeySun", 'SUN')
    sun_data.energy = 3.0
    sun_data.color = (1.0, 0.98, 0.94)
    sun_obj = bpy.data.objects.new("KeySun", sun_data)
    scene.collection.objects.link(sun_obj)
    sun_obj.location = Vector((-1.2, -1.5, 2.2))
    sun_dir = Vector((0.0, 0.0, 0.12)) - sun_obj.location
    sun_obj.rotation_euler = sun_dir.to_track_quat('-Z', 'Y').to_euler()

    # Soft Fill Light
    fill_data = bpy.data.lights.new("FillLight", 'AREA')
    fill_data.energy = 12.0
    fill_data.size = 1.2
    fill_data.color = (0.88, 0.94, 1.0)
    fill_obj = bpy.data.objects.new("FillLight", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.location = Vector((1.1, -0.9, 0.8))
    fill_dir = Vector((0.0, 0.02, 0.12)) - fill_obj.location
    fill_obj.rotation_euler = fill_dir.to_track_quat('-Z', 'Y').to_euler()

    # Compute exact world-space vertices of all mesh objects for framing
    bpy.context.view_layer.update()
    world_verts = []
    for obj in objects:
        if obj.type == 'MESH':
            mw = obj.matrix_world
            for v in obj.data.vertices:
                world_verts.append(mw @ v.co)

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
    center = 0.5 * (min_v + max_v)

    # 3/4 front-left view (model faces -Y, left side is +X), slightly above
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 50.0
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.01
    cam_data.clip_end = 50.0
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    view_offset_dir = Vector((0.66, -0.70, 0.30)).normalized()
    look_dir = -view_offset_dir
    cam_rot = look_dir.to_track_quat('-Z', 'Y')
    cam_right = cam_rot @ Vector((1.0, 0.0, 0.0))
    cam_up = cam_rot @ Vector((0.0, 1.0, 0.0))

    half_fov = 0.5 * cam_data.angle
    tan_fov = max(0.001, math.tan(half_fov))
    margin_factor = 1.12  # ~10% margin on each side

    req_dist = 0.25
    for p in world_verts:
        rel = p - center
        px = abs(rel.dot(cam_right))
        py = abs(rel.dot(cam_up))
        pz = rel.dot(view_offset_dir)
        d_x = (px * margin_factor) / tan_fov + pz
        d_y = (py * margin_factor) / tan_fov + pz
        req_dist = max(req_dist, d_x, d_y)

    cam_obj.location = center + view_offset_dir * req_dist
    cam_obj.rotation_euler = cam_rot.to_euler()

    scene.render.filepath = png_path
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv
    if "--" in argv:
        custom_args = argv[argv.index("--") + 1:]
    else:
        custom_args = []

    out_fbx = custom_args[0] if len(custom_args) > 0 else os.path.abspath("pigeon.fbx")
    out_dir = os.path.dirname(os.path.abspath(out_fbx))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    clear_scene()

    mats = {
        "body_grey":   make_material("Mat_BodyGrey",   (0.35, 0.42, 0.52), roughness=0.45),
        "wing_grey":   make_material("Mat_WingGrey",   (0.49, 0.56, 0.66), roughness=0.45),
        "head_grey":   make_material("Mat_HeadGrey",   (0.22, 0.27, 0.35), roughness=0.45),
        "neck_green":  make_material("Mat_NeckGreen",  (0.08, 0.64, 0.38), roughness=0.35, metallic=0.30),
        "neck_purple": make_material("Mat_NeckPurple", (0.58, 0.16, 0.64), roughness=0.35, metallic=0.30),
        "dark_band":   make_material("Mat_DarkBand",   (0.06, 0.07, 0.09), roughness=0.45),
        "cere_white":  make_material("Mat_CereWhite",  (0.92, 0.91, 0.88), roughness=0.48),
        "eye_orange":  make_material("Mat_EyeOrange",  (0.96, 0.32, 0.05), roughness=0.25),
        "leg_pink":    make_material("Mat_LegPink",    (0.84, 0.20, 0.28), roughness=0.45),
    }

    pigeon = build_pigeon_parts(mats)
    wing_l = build_wing_object("WingL", 1.0, mats)
    wing_r = build_wing_object("WingR", -1.0, mats)

    # Shift vertically so the lowest point rests exactly at Z = 0, and Pigeon origin is at (0, 0, 0)
    bpy.context.view_layer.update()
    min_z = min(v.co.z for v in pigeon.data.vertices)
    if abs(min_z) > 1e-6:
        for v in pigeon.data.vertices:
            v.co.z -= min_z
        pigeon.data.update()
        wing_l.location.z -= min_z
        wing_r.location.z -= min_z

    pigeon.location = Vector((0.0, 0.0, 0.0))

    # Parent WingL and WingR to Pigeon (keep transforms)
    bpy.context.view_layer.update()
    for w_obj in (wing_l, wing_r):
        world_mat = w_obj.matrix_world.copy()
        w_obj.parent = pigeon
        w_obj.matrix_parent_inverse = pigeon.matrix_world.inverted()
        w_obj.matrix_world = world_mat

    export_objs = [pigeon, wing_l, wing_r]
    bpy.ops.object.select_all(action='DESELECT')
    for obj in export_objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = pigeon

    bpy.ops.export_scene.fbx(
        filepath=out_fbx,
        use_selection=True,
        bake_space_transform=True,
        axis_forward='-Z',
        axis_up='Y',
        mesh_smooth_type='FACE',
        add_leaf_bones=False,
    )

    base_no_ext = os.path.splitext(out_fbx)[0]
    png_path_primary = base_no_ext + ".png"
    png_path_alt = out_fbx + ".png"
    setup_scene_and_render(export_objs, png_path_primary)
    if os.path.abspath(png_path_primary) != os.path.abspath(png_path_alt) and os.path.exists(png_path_primary):
        with open(png_path_primary, "rb") as f_src:
            data_bytes = f_src.read()
        with open(png_path_alt, "wb") as f_dst:
            f_dst.write(data_bytes)

    total_tris = 0
    for obj in export_objs:
        obj.data.calc_loop_triangles()
        total_tris += len(obj.data.loop_triangles)

    print("TRIS", total_tris)


if __name__ == "__main__":
    main()
