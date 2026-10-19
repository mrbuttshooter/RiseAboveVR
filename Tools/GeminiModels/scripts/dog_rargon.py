import bpy
import bmesh
import math
import os
import sys
from mathutils import Matrix, Vector


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block_collection in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.lights,
        bpy.data.cameras,
        bpy.data.worlds,
    ):
        for block in list(block_collection):
            block_collection.remove(block)


def make_material(name, color, roughness=0.45, metallic=0.0):
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (
        color[0],
        color[1],
        color[2],
        1.0,
    )
    bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    return mat


def safe_normalize(vec, fallback):
    length = vec.length
    if length > 1e-7:
        return vec / length
    return fallback.copy()


def build_lofted_tube(name, stations, mat, segs=8, subsurf_levels=1, b0=None):
    if b0 is None:
        b0 = Vector((1.0, 0.0, 0.0))

    bm = bmesh.new()
    m_count = len(stations)
    centers = [Vector((s[0], s[1], s[2])) for s in stations]

    tangents = []
    for i in range(m_count):
        if i == 0:
            t_vec = centers[1] - centers[0]
        elif i == m_count - 1:
            t_vec = centers[m_count - 1] - centers[m_count - 2]
        else:
            d1 = safe_normalize(centers[i] - centers[i - 1], Vector((0.0, -1.0, 0.0)))
            d2 = safe_normalize(centers[i + 1] - centers[i], Vector((0.0, -1.0, 0.0)))
            t_vec = d1 + d2
        tangents.append(safe_normalize(t_vec, Vector((0.0, -1.0, 0.0))))

    b_vec = b0.copy()
    if abs(b_vec.dot(tangents[0])) > 0.95:
        b_vec = Vector((0.0, 1.0, 0.0))
    b_vec = safe_normalize(b_vec - tangents[0] * b_vec.dot(tangents[0]), Vector((1.0, 0.0, 0.0)))

    rings = []
    for i in range(m_count):
        t_cur = tangents[i]
        b_proj = b_vec - t_cur * b_vec.dot(t_cur)
        b_vec = safe_normalize(b_proj, Vector((1.0, 0.0, 0.0)))
        n_vec = safe_normalize(t_cur.cross(b_vec), Vector((0.0, 0.0, 1.0)))

        cx, cy, cz, rx, rn_pos, rn_neg = stations[i]
        c_pos = Vector((cx, cy, cz))
        ring_verts = []
        for k in range(segs):
            angle = (2.0 * math.pi * k) / float(segs)
            ca = math.cos(angle)
            sa = math.sin(angle)
            rn = rn_pos if sa >= 0.0 else rn_neg
            pt = c_pos + b_vec * (ca * rx) + n_vec * (sa * rn)
            ring_verts.append(bm.verts.new(pt))
        rings.append(ring_verts)

    for i in range(m_count - 1):
        r0 = rings[i]
        r1 = rings[i + 1]
        for k in range(segs):
            kn = (k + 1) % segs
            f = bm.faces.new((r0[k], r0[kn], r1[kn], r1[k]))
            f.smooth = True

    start_cap_pos = centers[0] - tangents[0] * (0.35 * stations[0][3])
    end_cap_pos = centers[-1] + tangents[-1] * (0.35 * stations[-1][3])
    v_start = bm.verts.new(start_cap_pos)
    v_end = bm.verts.new(end_cap_pos)

    for k in range(segs):
        kn = (k + 1) % segs
        f_start = bm.faces.new((v_start, rings[0][kn], rings[0][k]))
        f_start.smooth = True
        f_end = bm.faces.new((v_end, rings[-1][k], rings[-1][kn]))
        f_end.smooth = True

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new(name + "_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    if subsurf_levels > 0:
        mod = obj.modifiers.new(name="Subsurf", type="SUBSURF")
        mod.levels = subsurf_levels
        mod.render_levels = subsurf_levels
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)

    return obj


def build_biscuit():
    mat_gold = make_material("GoldFur", (0.88, 0.52, 0.12), roughness=0.46)
    mat_cream = make_material("CreamFur", (0.97, 0.84, 0.54), roughness=0.45)
    mat_ear = make_material("EarGold", (0.70, 0.34, 0.07), roughness=0.46)
    mat_nose = make_material("NoseBlack", (0.03, 0.03, 0.035), roughness=0.32)
    mat_eye = make_material("EyeBrown", (0.11, 0.04, 0.015), roughness=0.25)
    mat_white = make_material("EyeWhite", (0.98, 0.98, 0.98), roughness=0.20)
    mat_tongue = make_material("TonguePink", (0.92, 0.31, 0.41), roughness=0.40)
    mat_collar = make_material("CollarRed", (0.86, 0.07, 0.07), roughness=0.42)
    mat_tag = make_material("TagGold", (0.98, 0.76, 0.12), roughness=0.30, metallic=0.65)

    parts = []

    # 1. Torso and Neck (Golden Fur)
    torso_stations = [
        (0.0, 0.25, 0.34, 0.040, 0.040, 0.040),
        (0.0, 0.20, 0.35, 0.098, 0.088, 0.096),
        (0.0, 0.08, 0.34, 0.092, 0.082, 0.092),
        (0.0, -0.05, 0.34, 0.118, 0.098, 0.125),
        (0.0, -0.16, 0.36, 0.112, 0.095, 0.115),
        (0.0, -0.21, 0.43, 0.082, 0.080, 0.085),
        (0.0, -0.24, 0.50, 0.050, 0.050, 0.050),
    ]
    parts.append(
        build_lofted_tube("Torso", torso_stations, mat_gold, segs=6, subsurf_levels=2)
    )

    # 2. Lighter Cream Belly & Fluffy Chest Ruff
    belly_stations = [
        (0.0, 0.17, 0.29, 0.040, 0.035, 0.028),
        (0.0, 0.07, 0.26, 0.074, 0.058, 0.034),
        (0.0, -0.06, 0.24, 0.094, 0.072, 0.044),
        (0.0, -0.18, 0.28, 0.098, 0.078, 0.052),
        (0.0, -0.22, 0.35, 0.080, 0.062, 0.042),
        (0.0, -0.21, 0.40, 0.042, 0.040, 0.030),
    ]
    parts.append(
        build_lofted_tube("BellyRuff", belly_stations, mat_cream, segs=8, subsurf_levels=1)
    )

    # 3. Cranium / Head (Golden Fur)
    head_stations = [
        (0.0, -0.18, 0.50, 0.050, 0.048, 0.048),
        (0.0, -0.22, 0.51, 0.100, 0.092, 0.088),
        (0.0, -0.26, 0.51, 0.108, 0.098, 0.092),
        (0.0, -0.30, 0.49, 0.090, 0.082, 0.078),
        (0.0, -0.33, 0.47, 0.050, 0.045, 0.045),
    ]
    parts.append(
        build_lofted_tube("Head", head_stations, mat_gold, segs=6, subsurf_levels=2)
    )

    # 4. Upper Snout / Muzzle (Cream Fur)
    snout_stations = [
        (0.0, -0.28, 0.475, 0.048, 0.042, 0.042),
        (0.0, -0.32, 0.475, 0.070, 0.054, 0.048),
        (0.0, -0.37, 0.470, 0.065, 0.050, 0.045),
        (0.0, -0.415, 0.468, 0.055, 0.043, 0.040),
        (0.0, -0.435, 0.468, 0.030, 0.026, 0.026),
    ]
    parts.append(
        build_lofted_tube("Snout", snout_stations, mat_cream, segs=8, subsurf_levels=1)
    )

    # 5. Lower Jaw / Chin (Cream Fur)
    jaw_stations = [
        (0.0, -0.26, 0.435, 0.042, 0.032, 0.032),
        (0.0, -0.32, 0.425, 0.054, 0.030, 0.035),
        (0.0, -0.375, 0.418, 0.046, 0.025, 0.030),
        (0.0, -0.405, 0.418, 0.028, 0.018, 0.022),
    ]
    parts.append(
        build_lofted_tube("Jaw", jaw_stations, mat_cream, segs=8, subsurf_levels=1)
    )

    # 6. Cheek Tufts & Brow Ridges (Left and Right)
    for side_idx, sx in enumerate((-1.0, 1.0)):
        cheek_stations = [
            (sx * 0.055, -0.27, 0.47, 0.028, 0.028, 0.028),
            (sx * 0.088, -0.26, 0.455, 0.044, 0.038, 0.042),
            (sx * 0.112, -0.24, 0.440, 0.036, 0.030, 0.034),
            (sx * 0.122, -0.22, 0.430, 0.018, 0.016, 0.018),
        ]
        parts.append(
            build_lofted_tube(
                f"Cheek_{side_idx}",
                cheek_stations,
                mat_gold,
                segs=6,
                subsurf_levels=1,
                b0=Vector((0.0, 1.0, 0.0)),
            )
        )

        brow_stations = [
            (sx * 0.022, -0.312, 0.542, 0.018, 0.016, 0.016),
            (sx * 0.048, -0.318, 0.548, 0.024, 0.020, 0.018),
            (sx * 0.072, -0.305, 0.535, 0.016, 0.014, 0.014),
        ]
        parts.append(
            build_lofted_tube(
                f"Brow_{side_idx}",
                brow_stations,
                mat_gold,
                segs=6,
                subsurf_levels=1,
                b0=Vector((0.0, 1.0, 0.0)),
            )
        )

    # 7. Black Nose
    nose_stations = [
        (0.0, -0.412, 0.482, 0.020, 0.016, 0.016),
        (0.0, -0.432, 0.486, 0.034, 0.024, 0.026),
        (0.0, -0.448, 0.484, 0.028, 0.020, 0.022),
        (0.0, -0.456, 0.480, 0.014, 0.012, 0.012),
    ]
    parts.append(
        build_lofted_tube("Nose", nose_stations, mat_nose, segs=8, subsurf_levels=1)
    )

    # 8. Pink Tongue (slightly out, rooted inside mouth)
    tongue_stations = [
        (0.0, -0.330, 0.440, 0.022, 0.012, 0.012),
        (0.004, -0.375, 0.435, 0.026, 0.012, 0.013),
        (0.009, -0.412, 0.420, 0.024, 0.011, 0.012),
        (0.012, -0.430, 0.402, 0.016, 0.009, 0.010),
    ]
    parts.append(
        build_lofted_tube("Tongue", tongue_stations, mat_tongue, segs=6, subsurf_levels=1)
    )

    # 9. Dark Brown Eyes with White Highlights
    for side_idx, sx in enumerate((-1.0, 1.0)):
        eye_stations = [
            (sx * 0.048, -0.295, 0.512, 0.015, 0.015, 0.015),
            (sx * 0.052, -0.312, 0.512, 0.023, 0.024, 0.024),
            (sx * 0.055, -0.324, 0.512, 0.013, 0.013, 0.013),
        ]
        parts.append(
            build_lofted_tube(
                f"Eye_{side_idx}", eye_stations, mat_eye, segs=8, subsurf_levels=1
            )
        )

        hi_stations = [
            (sx * 0.056, -0.316, 0.520, 0.006, 0.006, 0.006),
            (sx * 0.059, -0.324, 0.521, 0.009, 0.009, 0.009),
            (sx * 0.061, -0.330, 0.522, 0.005, 0.005, 0.005),
        ]
        parts.append(
            build_lofted_tube(
                f"EyeHi_{side_idx}", hi_stations, mat_white, segs=6, subsurf_levels=1
            )
        )

    # 10. Floppy Ears (Left and Right)
    for side_idx, sx in enumerate((-1.0, 1.0)):
        ear_stations = [
            (sx * 0.068, -0.23, 0.545, 0.032, 0.020, 0.020),
            (sx * 0.105, -0.23, 0.540, 0.048, 0.024, 0.022),
            (sx * 0.128, -0.225, 0.495, 0.058, 0.026, 0.022),
            (sx * 0.136, -0.220, 0.440, 0.062, 0.026, 0.022),
            (sx * 0.132, -0.215, 0.395, 0.048, 0.022, 0.020),
            (sx * 0.124, -0.212, 0.372, 0.024, 0.015, 0.015),
        ]
        parts.append(
            build_lofted_tube(
                f"Ear_{side_idx}",
                ear_stations,
                mat_ear,
                segs=8,
                subsurf_levels=1,
                b0=Vector((0.0, -1.0, 0.0)),
            )
        )

    # 11. Red Collar & Small Gold Tag
    collar_stations = [
        (0.0, -0.192, 0.395, 0.062, 0.062, 0.065),
        (0.0, -0.198, 0.405, 0.098, 0.095, 0.100),
        (0.0, -0.208, 0.420, 0.098, 0.095, 0.100),
        (0.0, -0.215, 0.432, 0.094, 0.090, 0.095),
        (0.0, -0.220, 0.440, 0.060, 0.058, 0.060),
    ]
    parts.append(
        build_lofted_tube("Collar", collar_stations, mat_collar, segs=12, subsurf_levels=1)
    )

    loop_stations = [
        (0.0, -0.275, 0.392, 0.012, 0.012, 0.012),
        (0.0, -0.292, 0.376, 0.016, 0.014, 0.014),
        (0.0, -0.298, 0.360, 0.012, 0.012, 0.012),
    ]
    parts.append(
        build_lofted_tube("TagLoop", loop_stations, mat_tag, segs=6, subsurf_levels=1)
    )

    tag_stations = [
        (0.0, -0.288, 0.354, 0.016, 0.016, 0.016),
        (0.0, -0.298, 0.348, 0.028, 0.028, 0.028),
        (0.0, -0.308, 0.344, 0.026, 0.026, 0.026),
        (0.0, -0.314, 0.341, 0.012, 0.012, 0.012),
    ]
    parts.append(
        build_lofted_tube("GoldTag", tag_stations, mat_tag, segs=8, subsurf_levels=1)
    )

    # 12. Feathery Tail Raised & Curved (Golden Fur + Cream Plume)
    tail_stations = [
        (0.0, 0.20, 0.34, 0.036, 0.036, 0.038),
        (0.010, 0.27, 0.37, 0.044, 0.040, 0.058),
        (0.025, 0.34, 0.42, 0.042, 0.038, 0.064),
        (0.042, 0.40, 0.48, 0.036, 0.032, 0.056),
        (0.052, 0.44, 0.54, 0.028, 0.025, 0.040),
        (0.056, 0.46, 0.57, 0.016, 0.016, 0.020),
    ]
    parts.append(
        build_lofted_tube("Tail", tail_stations, mat_gold, segs=8, subsurf_levels=1)
    )

    plume_stations = [
        (0.008, 0.25, 0.34, 0.022, 0.022, 0.025),
        (0.020, 0.32, 0.37, 0.034, 0.028, 0.048),
        (0.036, 0.39, 0.42, 0.036, 0.028, 0.052),
        (0.048, 0.44, 0.48, 0.028, 0.022, 0.038),
        (0.054, 0.46, 0.53, 0.015, 0.015, 0.020),
    ]
    parts.append(
        build_lofted_tube("TailPlume", plume_stations, mat_cream, segs=6, subsurf_levels=1)
    )

    # 13. Four Legs in Walking Stride (Front-Left Lifted Mid-Step, 3 Planted)
    leg_fl_stations = [
        (0.068, -0.15, 0.35, 0.042, 0.042, 0.042),
        (0.078, -0.18, 0.28, 0.048, 0.046, 0.058),
        (0.080, -0.22, 0.20, 0.038, 0.036, 0.050),
        (0.080, -0.30, 0.15, 0.034, 0.032, 0.042),
        (0.080, -0.35, 0.12, 0.038, 0.032, 0.030),
        (0.080, -0.38, 0.09, 0.026, 0.022, 0.020),
    ]
    parts.append(
        build_lofted_tube("Leg_FL", leg_fl_stations, mat_gold, segs=8, subsurf_levels=1)
    )

    leg_fr_stations = [
        (-0.068, -0.14, 0.35, 0.042, 0.042, 0.042),
        (-0.078, -0.14, 0.27, 0.048, 0.046, 0.058),
        (-0.080, -0.13, 0.17, 0.038, 0.035, 0.050),
        (-0.080, -0.14, 0.07, 0.034, 0.032, 0.038),
        (-0.080, -0.18, 0.026, 0.042, 0.032, 0.026),
        (-0.080, -0.22, 0.024, 0.028, 0.022, 0.020),
    ]
    parts.append(
        build_lofted_tube("Leg_FR", leg_fr_stations, mat_gold, segs=8, subsurf_levels=1)
    )

    leg_bl_stations = [
        (0.068, 0.17, 0.35, 0.046, 0.046, 0.046),
        (0.080, 0.19, 0.27, 0.056, 0.052, 0.064),
        (0.080, 0.17, 0.18, 0.042, 0.040, 0.052),
        (0.080, 0.23, 0.09, 0.035, 0.032, 0.042),
        (0.080, 0.20, 0.026, 0.042, 0.032, 0.026),
        (0.080, 0.16, 0.024, 0.028, 0.022, 0.020),
    ]
    parts.append(
        build_lofted_tube("Leg_BL", leg_bl_stations, mat_gold, segs=8, subsurf_levels=1)
    )

    leg_br_stations = [
        (-0.068, 0.16, 0.35, 0.046, 0.046, 0.046),
        (-0.080, 0.15, 0.26, 0.056, 0.052, 0.064),
        (-0.080, 0.09, 0.17, 0.042, 0.040, 0.050),
        (-0.080, 0.12, 0.08, 0.035, 0.032, 0.040),
        (-0.080, 0.09, 0.026, 0.042, 0.032, 0.026),
        (-0.080, 0.05, 0.024, 0.028, 0.022, 0.020),
    ]
    parts.append(
        build_lofted_tube("Leg_BR", leg_br_stations, mat_gold, segs=8, subsurf_levels=1)
    )

    # 14. Side Toes Embedded on Each Paw
    paw_configs = [
        ("FL", 0.080, -0.365, 0.095),
        ("FR", -0.080, -0.205, 0.024),
        ("BL", 0.080, 0.175, 0.024),
        ("BR", -0.080, 0.065, 0.024),
    ]
    for paw_name, px, py, pz in paw_configs:
        for t_idx, dx in enumerate((-0.022, 0.022)):
            toe_stations = [
                (px + dx * 0.7, py + 0.022, pz + 0.004, 0.015, 0.015, 0.014),
                (px + dx, py, pz, 0.018, 0.018, 0.016),
                (px + dx, py - 0.020, pz - 0.002, 0.011, 0.011, 0.010),
            ]
            parts.append(
                build_lofted_tube(
                    f"Toe_{paw_name}_{t_idx}",
                    toe_stations,
                    mat_gold,
                    segs=4,
                    subsurf_levels=1,
                )
            )

    # Join all parts into ONE object named "Biscuit"
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()

    biscuit = bpy.context.view_layer.objects.active
    biscuit.name = "Biscuit"
    biscuit.data.name = "Biscuit_Mesh"

    # Normalize dimensions so Biscuit is ~0.60 m tall at the head, ~0.90 m long,
    # centered in X/Y with lowest point exactly at Z = 0.0.
    verts = biscuit.data.vertices
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)

    cur_len = max(max_y - min_y, 1e-5)
    cur_h = max(max_z - min_z, 1e-5)
    scale_y = 0.90 / cur_len
    scale_z = 0.60 / cur_h
    scale_x = 0.5 * (scale_y + scale_z)

    cx = 0.5 * (min_x + max_x)
    cy = 0.5 * (min_y + max_y)

    for v in verts:
        v.co.x = (v.co.x - cx) * scale_x
        v.co.y = (v.co.y - cy) * scale_y
        v.co.z = (v.co.z - min_z) * scale_z

    for poly in biscuit.data.polygons:
        poly.use_smooth = True

    biscuit.location = (0.0, 0.0, 0.0)
    biscuit.rotation_euler = (0.0, 0.0, 0.0)
    biscuit.scale = (1.0, 1.0, 1.0)
    biscuit.data.update()

    return biscuit


def setup_lighting_and_camera(biscuit):
    scene = bpy.context.scene

    engine_keys = [
        item.identifier
        for item in scene.render.bl_rna.properties["engine"].enum_items
    ]
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if candidate in engine_keys:
            scene.render.engine = candidate
            break

    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg is None:
        bg = world.node_tree.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (0.5, 0.5, 0.5, 1.0)
    bg.inputs[1].default_value = 0.45

    sun_data = bpy.data.lights.new(name="SunLight", type="SUN")
    sun_data.energy = 3.0
    sun_data.color = (1.0, 0.97, 0.90)
    if hasattr(sun_data, "angle"):
        sun_data.angle = math.radians(12.0)
    sun_obj = bpy.data.objects.new("SunLight", sun_data)
    bpy.context.collection.objects.link(sun_obj)
    sun_obj.location = (-2.0, -2.5, 3.2)
    sun_dir = Vector((0.0, 0.0, 0.3)) - sun_obj.location
    sun_obj.rotation_euler = sun_dir.to_track_quat("-Z", "Y").to_euler()

    fill_data = bpy.data.lights.new(name="FillLight", type="AREA")
    fill_data.energy = 35.0
    fill_data.color = (0.88, 0.94, 1.0)
    if hasattr(fill_data, "size"):
        fill_data.size = 2.5
    fill_obj = bpy.data.objects.new("FillLight", fill_data)
    bpy.context.collection.objects.link(fill_obj)
    fill_obj.location = (2.2, -1.8, 1.6)
    fill_dir = Vector((0.0, 0.0, 0.3)) - fill_obj.location
    fill_obj.rotation_euler = fill_dir.to_track_quat("-Z", "Y").to_euler()

    # Camera at 3/4 front view (front-left, slightly above) with ~10% margin
    cam_data = bpy.data.cameras.new(name="Camera")
    cam_data.lens = 50.0
    cam_data.sensor_width = 36.0
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    view_dir_from_target = safe_normalize(
        Vector((-1.05, -1.25, 0.68)), Vector((-0.6, -0.7, 0.38))
    )
    forward = -view_dir_from_target
    right = safe_normalize(forward.cross(Vector((0.0, 0.0, 1.0))), Vector((1.0, 0.0, 0.0)))
    up = safe_normalize(right.cross(forward), Vector((0.0, 0.0, 1.0)))

    verts = [v.co.copy() for v in biscuit.data.vertices]
    target = Vector((0.0, 0.0, 0.30))
    tan_half_fov = 0.5 * cam_data.sensor_width / cam_data.lens
    fill_ratio = 0.80  # leaves ~10% margin on each side

    dist = 1.65
    for _ in range(6):
        cam_pos = target - forward * dist
        u_vals = []
        v_vals = []
        for pt in verts:
            rel = pt - cam_pos
            depth = max(rel.dot(forward), 0.1)
            u_vals.append(rel.dot(right) / (depth * tan_half_fov))
            v_vals.append(rel.dot(up) / (depth * tan_half_fov))
        u_mid = 0.5 * (min(u_vals) + max(u_vals))
        v_mid = 0.5 * (min(v_vals) + max(v_vals))
        target = target + (right * u_mid + up * v_mid) * (dist * tan_half_fov * 0.6)
        span = max(max(u_vals) - min(u_vals), max(v_vals) - min(v_vals), 1e-4)
        dist = dist * (span / (2.0 * fill_ratio))

    cam_obj.location = target - forward * dist
    cam_obj.rotation_euler = forward.to_track_quat("-Z", "Y").to_euler()


def main():
    out_path = "Biscuit.fbx"
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if idx + 1 < len(sys.argv):
            out_path = sys.argv[idx + 1]
    out_path = os.path.abspath(out_path)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    clear_scene()
    biscuit = build_biscuit()
    setup_lighting_and_camera(biscuit)

    bpy.ops.object.select_all(action="DESELECT")
    biscuit.select_set(True)
    bpy.context.view_layer.objects.active = biscuit
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    bpy.ops.export_scene.fbx(
        filepath=out_path,
        use_selection=True,
        bake_space_transform=True,
        axis_forward="-Z",
        axis_up="Y",
        mesh_smooth_type="FACE",
    )

    png_path = os.path.splitext(out_path)[0] + ".png"
    bpy.context.scene.render.filepath = png_path
    bpy.ops.render.render(write_still=True)

    n_tris = sum(len(p.vertices) - 2 for p in biscuit.data.polygons)
    print("TRIS", n_tris)


if __name__ == "__main__":
    main()

