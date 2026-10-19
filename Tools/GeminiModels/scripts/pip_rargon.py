import bpy
import bmesh
import mathutils
from mathutils import Vector, Matrix, Euler
import math
import sys
import os


def clamp01(val):
    return max(0.0, min(1.0, float(val)))


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for col in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.curves):
        for block in list(col):
            if block.users == 0:
                col.remove(block)


def make_material(name, base_color, roughness=0.45, metallic=0.0, emission_color=None, emission_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = None
    for n in nodes:
        if n.type == 'BSDF_PRINCIPLED':
            bsdf = n
            break
    if bsdf is None:
        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (base_color[0], base_color[1], base_color[2], 1.0)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.5
    elif 'Specular' in bsdf.inputs:
        bsdf.inputs['Specular'].default_value = 0.5
    if emission_color is not None and emission_strength > 0.0:
        if 'Emission Color' in bsdf.inputs:
            bsdf.inputs['Emission Color'].default_value = (emission_color[0], emission_color[1], emission_color[2], 1.0)
        elif 'Emission' in bsdf.inputs:
            bsdf.inputs['Emission'].default_value = (emission_color[0], emission_color[1], emission_color[2], 1.0)
        if 'Emission Strength' in bsdf.inputs:
            bsdf.inputs['Emission Strength'].default_value = emission_strength
    return mat


def add_uv_sphere(bm, segments, rings, mat_index, shape_fn=None, transform=None):
    verts_rings = []
    v_top = Vector((0.0, 0.0, 1.0))
    if shape_fn is not None:
        v_top = shape_fn(v_top.x, v_top.y, v_top.z)
    if transform is not None:
        v_top = transform @ v_top
    top_vert = bm.verts.new(v_top)

    for j in range(1, rings):
        phi = math.pi * float(j) / float(rings)
        sp = math.sin(phi)
        cp = math.cos(phi)
        ring = []
        for i in range(segments):
            theta = 2.0 * math.pi * float(i) / float(segments)
            x = sp * math.cos(theta)
            y = sp * math.sin(theta)
            z = cp
            p = Vector((x, y, z))
            if shape_fn is not None:
                p = shape_fn(p.x, p.y, p.z)
            if transform is not None:
                p = transform @ p
            ring.append(bm.verts.new(p))
        verts_rings.append(ring)

    v_bot = Vector((0.0, 0.0, -1.0))
    if shape_fn is not None:
        v_bot = shape_fn(v_bot.x, v_bot.y, v_bot.z)
    if transform is not None:
        v_bot = transform @ v_bot
    bot_vert = bm.verts.new(v_bot)

    created_faces = []
    for i in range(segments):
        i_next = (i + 1) % segments
        f = bm.faces.new((top_vert, verts_rings[0][i], verts_rings[0][i_next]))
        f.material_index = mat_index
        f.smooth = True
        created_faces.append(f)

    for j in range(rings - 2):
        r_curr = verts_rings[j]
        r_next = verts_rings[j + 1]
        for i in range(segments):
            i_next = (i + 1) % segments
            f = bm.faces.new((r_curr[i], r_next[i], r_next[i_next], r_curr[i_next]))
            f.material_index = mat_index
            f.smooth = True
            created_faces.append(f)

    last_ring = verts_rings[-1]
    for i in range(segments):
        i_next = (i + 1) % segments
        f = bm.faces.new((last_ring[i_next], last_ring[i], bot_vert))
        f.material_index = mat_index
        f.smooth = True
        created_faces.append(f)

    bmesh.ops.recalc_face_normals(bm, faces=created_faces)
    return created_faces


def add_swept_tube(bm, spine_points, radii, segments, mat_index, flatten_y=1.0):
    n_pts = len(spine_points)
    tangents = []
    for k in range(n_pts):
        if k == 0:
            d = spine_points[1] - spine_points[0]
        elif k == n_pts - 1:
            d = spine_points[-1] - spine_points[-2]
        else:
            d = spine_points[k + 1] - spine_points[k - 1]
        if d.length < 1e-6:
            d = Vector((0.0, 0.0, 1.0))
        else:
            d.normalize()
        tangents.append(d)

    ref = Vector((1.0, 0.0, 0.0))
    if abs(tangents[0].dot(ref)) > 0.9:
        ref = Vector((0.0, 1.0, 0.0))
    normal = (ref - tangents[0] * tangents[0].dot(ref)).normalized()

    rings_verts = []
    for k in range(n_pts):
        t_vec = tangents[k]
        normal = normal - t_vec * normal.dot(t_vec)
        if normal.length < 1e-6:
            normal = Vector((1.0, 0.0, 0.0))
        else:
            normal.normalize()
        binormal = t_vec.cross(normal).normalized()
        r = radii[k]
        ring = []
        for i in range(segments):
            ang = 2.0 * math.pi * float(i) / float(segments)
            ca = math.cos(ang) * r
            sa = math.sin(ang) * r * flatten_y
            pos = spine_points[k] + normal * ca + binormal * sa
            ring.append(bm.verts.new(pos))
        rings_verts.append(ring)

    start_cap_pos = spine_points[0] - tangents[0] * (radii[0] * 0.45)
    end_cap_pos = spine_points[-1] + tangents[-1] * (radii[-1] * 0.75)
    v_start = bm.verts.new(start_cap_pos)
    v_end = bm.verts.new(end_cap_pos)

    created_faces = []
    for i in range(segments):
        i_next = (i + 1) % segments
        f = bm.faces.new((v_start, rings_verts[0][i_next], rings_verts[0][i]))
        f.material_index = mat_index
        f.smooth = True
        created_faces.append(f)

    for k in range(n_pts - 1):
        r0 = rings_verts[k]
        r1 = rings_verts[k + 1]
        for i in range(segments):
            i_next = (i + 1) % segments
            f = bm.faces.new((r0[i], r0[i_next], r1[i_next], r1[i]))
            f.material_index = mat_index
            f.smooth = True
            created_faces.append(f)

    last_ring = rings_verts[-1]
    for i in range(segments):
        i_next = (i + 1) % segments
        f = bm.faces.new((last_ring[i], last_ring[i_next], v_end))
        f.material_index = mat_index
        f.smooth = True
        created_faces.append(f)

    bmesh.ops.recalc_face_normals(bm, faces=created_faces)
    return created_faces


def build_pip_and_wings():
    clear_scene()

    mat_sky_blue = make_material(
        "Mat_SkyBlue",
        (0.35, 0.8, 1.0),
        roughness=0.42,
        metallic=0.0,
        emission_color=(0.35, 0.8, 1.0),
        emission_strength=0.6,
    )
    mat_cream = make_material("Mat_Cream", (0.98, 0.94, 0.82), roughness=0.46)
    mat_orange = make_material("Mat_Orange", (1.0, 0.46, 0.06), roughness=0.42)
    mat_eye_black = make_material("Mat_EyeBlack", (0.015, 0.015, 0.022), roughness=0.12)
    mat_eye_white = make_material(
        "Mat_EyeWhite",
        (1.0, 1.0, 1.0),
        roughness=0.20,
        emission_color=(1.0, 1.0, 1.0),
        emission_strength=0.35,
    )
    mat_rosy = make_material("Mat_RosyCheek", (1.0, 0.36, 0.48), roughness=0.48)

    # Material indices on Pip:
    # 0: SkyBlue, 1: Cream, 2: Orange, 3: EyeBlack, 4: EyeWhite, 5: RosyCheek
    bm = bmesh.new()

    # 1. Main Chubby Songbird Body (centered at local (0, 0, 0))
    def body_shape(x, y, z):
        u_top = clamp01((z - 0.15) / 0.85)
        u_bot = clamp01((-z) / 1.0)
        chubby = 1.0 + 0.10 * clamp01(1.0 - z * z) - 0.12 * (u_top ** 1.6)
        sx = x * 0.070 * chubby * (1.0 + 0.06 * u_bot)
        sy = y * 0.072 * chubby
        sz = z * 0.068
        if y < 0.0:
            # Plump chest and face
            sy *= 1.0 + 0.06 * clamp01(-y) * clamp01(1.0 - 0.5 * z * z)
        else:
            # Cute songbird rump sweep
            rump = clamp01(y)
            sy += 0.010 * (rump ** 1.5)
            sz += 0.008 * (rump ** 1.8)
        if z < -0.55:
            # Gently flattened bottom
            flat = clamp01((-z - 0.55) / 0.45)
            sz += 0.006 * (flat ** 1.5)
        return Vector((sx, sy, sz))

    add_uv_sphere(bm, 16, 10, 0, shape_fn=body_shape)

    # 2. Cream Belly Patch (deeply embedded 3 cm into lower front chest/belly, smooth protrusion)
    def belly_shape(x, y, z):
        t_top = clamp01((z + 1.0) * 0.5)
        taper = 1.0 - 0.18 * (t_top ** 1.8)
        sx = x * 0.053 * taper
        sy = y * 0.056
        sz = z * 0.050
        return Vector((sx, sy, sz))

    belly_mat = Matrix.Translation(Vector((0.0, -0.025, -0.015))) @ Euler((math.radians(12.0), 0.0, 0.0), 'XYZ').to_matrix().to_4x4()
    add_uv_sphere(bm, 10, 7, 1, shape_fn=belly_shape, transform=belly_mat)

    # 3. Tail Feathers (3 rounded overlapping feathers embedded 2.5 cm into rear rump)
    def tail_feather_shape(x, y, z):
        t = clamp01((y + 1.0) * 0.5)
        width_env = 0.55 + 0.65 * math.sin(math.pi * (t ** 0.75))
        thick_env = 1.0 - 0.55 * (t ** 1.4)
        sx = x * 0.016 * width_env
        sy = -0.024 + 0.052 * t
        sz = z * 0.0075 * thick_env + 0.012 * (t ** 1.5)
        return Vector((sx, sy, sz))

    for idx, side in enumerate((-1.0, 0.0, 1.0)):
        yaw = math.radians(-side * 19.0)
        pitch = math.radians(22.0 + (3.0 if side == 0.0 else 0.0))
        roll = math.radians(side * 10.0)
        t_pos = Vector((side * 0.012, 0.062, 0.004 + (0.003 if side == 0.0 else 0.0)))
        t_mat = Matrix.Translation(t_pos) @ Euler((pitch, roll, yaw), 'XYZ').to_matrix().to_4x4()
        add_uv_sphere(bm, 6, 4, 0, shape_fn=tail_feather_shape, transform=t_mat)

    # 4. Head Feather Curl (2 swept curls rooted 2 cm inside top of head)
    curl1_pts = []
    curl1_rad = []
    for k in range(7):
        t = float(k) / 6.0
        ang = t * math.pi * 1.15
        px = 0.010 * (t ** 1.5)
        py = -0.004 - 0.020 * math.sin(ang * 0.85) + 0.008 * (t ** 2.2)
        pz = 0.048 + 0.052 * math.sin(ang * 0.62) + 0.010 * t * (1.0 - t)
        r = 0.0145 * (1.0 - 0.70 * (t ** 1.4)) + 0.002 * math.sin(math.pi * t)
        curl1_pts.append(Vector((px, py, pz)))
        curl1_rad.append(r)
    add_swept_tube(bm, curl1_pts, curl1_rad, 6, 0, flatten_y=0.82)

    curl2_pts = []
    curl2_rad = []
    for k in range(4):
        t = float(k) / 3.0
        px = -0.004 - 0.012 * (t ** 1.3)
        py = 0.005 - 0.010 * t
        pz = 0.048 + 0.038 * (t ** 0.85)
        r = 0.011 * (1.0 - 0.68 * (t ** 1.3))
        curl2_pts.append(Vector((px, py, pz)))
        curl2_rad.append(r)
    add_swept_tube(bm, curl2_pts, curl2_rad, 6, 0, flatten_y=0.82)

    # 5. Small Orange Beak (upper and lower mandibles embedded 2.5 cm into face)
    def upper_beak_shape(x, y, z):
        t = clamp01((-y + 1.0) * 0.5)
        taper = (1.0 - 0.78 * (t ** 1.35))
        sx = x * 0.0165 * taper
        sy = 0.022 - 0.048 * t
        sz = z * 0.0115 * taper - 0.0035 * (t ** 2.0)
        if z < 0.0:
            sz *= 0.65
        return Vector((sx, sy, sz))

    upper_beak_mat = Matrix.Translation(Vector((0.0, -0.064, 0.012)))
    add_uv_sphere(bm, 6, 4, 2, shape_fn=upper_beak_shape, transform=upper_beak_mat)

    def lower_beak_shape(x, y, z):
        t = clamp01((-y + 1.0) * 0.5)
        taper = (1.0 - 0.80 * (t ** 1.35))
        sx = x * 0.0135 * taper
        sy = 0.020 - 0.041 * t
        sz = z * 0.0085 * taper + 0.0015 * (t ** 1.6)
        return Vector((sx, sy, sz))

    lower_beak_mat = Matrix.Translation(Vector((0.0, -0.062, 0.006)))
    add_uv_sphere(bm, 6, 3, 2, shape_fn=lower_beak_shape, transform=lower_beak_mat)

    # 6. Big Shiny Black Eyes + Two White Highlights Each
    def eye_shape(x, y, z):
        return Vector((x * 0.019, y * 0.0155, z * 0.020))

    def hi_big_shape(x, y, z):
        return Vector((x * 0.0062, y * 0.0058, z * 0.0062))

    def hi_small_shape(x, y, z):
        return Vector((x * 0.0036, y * 0.0054, z * 0.0036))

    for side in (-1.0, 1.0):
        eye_pos = Vector((side * 0.031, -0.055, 0.022))
        eye_rot = Euler((math.radians(-12.0), 0.0, math.radians(-side * 24.0)), 'XYZ').to_matrix().to_4x4()
        eye_mat = Matrix.Translation(eye_pos) @ eye_rot
        add_uv_sphere(bm, 8, 5, 3, shape_fn=eye_shape, transform=eye_mat)

        # Two white highlights per eye (embedded into cornea and protruding forward)
        hi1_local = Matrix.Translation(Vector((-0.0052, -0.0132, 0.0062)))
        hi2_local = Matrix.Translation(Vector((0.0055, -0.0136, -0.0055)))
        add_uv_sphere(bm, 5, 3, 4, shape_fn=hi_big_shape, transform=eye_mat @ hi1_local)
        add_uv_sphere(bm, 5, 3, 4, shape_fn=hi_small_shape, transform=eye_mat @ hi2_local)

    # 7. Rosy Cheek Dots (embedded 2 cm into cheeks)
    def cheek_shape(x, y, z):
        return Vector((x * 0.0125, y * 0.0135, z * 0.0092))

    for side in (-1.0, 1.0):
        cheek_pos = Vector((side * 0.043, -0.049, 0.002))
        cheek_rot = Euler((math.radians(-4.0), 0.0, math.radians(-side * 34.0)), 'XYZ').to_matrix().to_4x4()
        cheek_mat = Matrix.Translation(cheek_pos) @ cheek_rot
        add_uv_sphere(bm, 6, 3, 5, shape_fn=cheek_shape, transform=cheek_mat)

    # 8. Tiny Feet Tucked Under (ankle base embedded 2.2 cm into lower body + 3 stubby toes each)
    def ankle_shape(x, y, z):
        return Vector((x * 0.013, y * 0.014, z * 0.018))

    def toe_shape(x, y, z):
        t = clamp01((-y + 1.0) * 0.5)
        bulb = 0.85 + 0.25 * math.sin(math.pi * t)
        sx = x * 0.0082 * bulb
        sy = 0.012 - 0.026 * t
        sz = z * 0.0078 * bulb
        if z < 0.0:
            sz *= 0.72
        return Vector((sx, sy, sz))

    for side in (-1.0, 1.0):
        foot_x = side * 0.026
        ankle_mat = Matrix.Translation(Vector((foot_x, -0.020, -0.056)))
        add_uv_sphere(bm, 5, 3, 2, shape_fn=ankle_shape, transform=ankle_mat)

        for toe_i in (-1, 0, 1):
            yaw = math.radians(-side * 8.0 - toe_i * 22.0)
            toe_pos = Vector((foot_x + toe_i * 0.005, -0.023, -0.068))
            toe_mat = Matrix.Translation(toe_pos) @ Euler((0.0, 0.0, yaw), 'XYZ').to_matrix().to_4x4()
            add_uv_sphere(bm, 5, 3, 2, shape_fn=toe_shape, transform=toe_mat)

    pip_mesh = bpy.data.meshes.new("Pip")
    bm.to_mesh(pip_mesh)
    bm.free()

    for poly in pip_mesh.polygons:
        poly.use_smooth = True

    pip_obj = bpy.data.objects.new("Pip", pip_mesh)
    bpy.context.collection.objects.link(pip_obj)

    for m in (mat_sky_blue, mat_cream, mat_orange, mat_eye_black, mat_eye_white, mat_rosy):
        pip_obj.data.materials.append(m)

    bpy.context.view_layer.objects.active = pip_obj
    pip_obj.select_set(True)
    sub_pip = pip_obj.modifiers.new(name="Subsurf", type='SUBSURF')
    sub_pip.levels = 1
    sub_pip.render_levels = 1
    bpy.ops.object.modifier_apply(modifier=sub_pip.name)

    # 9. Build Separate Wings ("WingL" and "WingR") with origin at each shoulder
    wings = []
    for wing_name, side in (("WingL", 1.0), ("WingR", -1.0)):
        bm_w = bmesh.new()

        def wing_shape(x, y, z, s=side):
            # Map z from [-1, 1] to span t in [0, 1] (0 = inner shoulder joint inside body, 1 = outer wingtip)
            t = clamp01((z + 1.0) * 0.5)
            chord_env = 0.65 + 0.50 * math.sin(math.pi * (t ** 0.8))
            thick_env = (1.0 - 0.55 * (t ** 1.3))
            # Local (0,0,0) is the shoulder pivot; t=0 reaches 1.8 cm inward into Pip's body
            lx = s * (-0.018 + 0.050 * t)
            ly = y * 0.025 * chord_env + 0.022 * (t ** 1.35)
            lz = x * 0.014 * thick_env - 0.024 * (t ** 1.2)
            # Subtle cupped airfoil curvature
            lx += s * 0.005 * clamp01(1.0 - y * y) * math.sin(math.pi * t)
            return Vector((lx, ly, lz))

        add_uv_sphere(bm_w, 10, 6, 0, shape_fn=wing_shape)
        w_mesh = bpy.data.meshes.new(wing_name)
        bm_w.to_mesh(w_mesh)
        bm_w.free()

        for poly in w_mesh.polygons:
            poly.use_smooth = True

        w_obj = bpy.data.objects.new(wing_name, w_mesh)
        bpy.context.collection.objects.link(w_obj)
        w_obj.data.materials.append(mat_sky_blue)

        w_obj.parent = pip_obj
        w_obj.location = Vector((side * 0.060, -0.004, 0.006))

        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = w_obj
        w_obj.select_set(True)
        sub_w = w_obj.modifiers.new(name="Subsurf", type='SUBSURF')
        sub_w.levels = 1
        sub_w.render_levels = 1
        bpy.ops.object.modifier_apply(modifier=sub_w.name)
        wings.append(w_obj)

    bpy.context.view_layer.update()

    # Position Pip so the lowest point of the entire model in world space is at Z = 0,
    # keeping Pip's origin at the centre of its body and each wing's origin at its shoulder.
    all_objs = [pip_obj] + wings
    min_z = min((obj.matrix_world @ v.co).z for obj in all_objs for v in obj.data.vertices)
    pip_obj.location = Vector((0.0, 0.0, -min_z))
    bpy.context.view_layer.update()

    bpy.ops.object.select_all(action='DESELECT')
    for obj in all_objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = pip_obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.context.view_layer.update()

    return pip_obj, wings


def count_triangles(objects):
    total = 0
    for obj in objects:
        if obj.type == 'MESH':
            obj.data.calc_loop_triangles()
            total += len(obj.data.loop_triangles)
    return total


def setup_camera_and_lights(objects):
    scene = bpy.context.scene

    # Pick EEVEE engine dynamically from enum_items keys
    engine_keys = list(scene.render.bl_rna.properties['engine'].enum_items.keys())
    eevee_engine = None
    for k in engine_keys:
        if 'EEVEE' in k.upper():
            eevee_engine = k
            break
    if eevee_engine is not None:
        scene.render.engine = eevee_engine

    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False

    # Grey world strength 0.45
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    bg_node = None
    for n in scene.world.node_tree.nodes:
        if n.type == 'BACKGROUND':
            bg_node = n
            break
    if bg_node is None:
        bg_node = scene.world.node_tree.nodes.new(type='ShaderNodeBackground')
    bg_node.inputs['Color'].default_value = (0.5, 0.5, 0.5, 1.0)
    bg_node.inputs['Strength'].default_value = 0.45

    # Sun light of strength 3
    sun_data = bpy.data.lights.new("KeySun", type='SUN')
    sun_data.energy = 3.0
    sun_data.color = (1.0, 0.98, 0.94)
    if hasattr(sun_data, "angle"):
        sun_data.angle = math.radians(15.0)
    sun_obj = bpy.data.objects.new("KeySun", sun_data)
    bpy.context.collection.objects.link(sun_obj)
    sun_dir = Vector((-0.55, -0.70, 0.65)).normalized()
    sun_obj.location = sun_dir * 2.0
    sun_obj.rotation_euler = sun_dir.to_track_quat('Z', 'Y').to_euler()

    # Soft fill light
    fill_data = bpy.data.lights.new("SoftFill", type='AREA')
    fill_data.energy = 12.0
    fill_data.color = (0.85, 0.93, 1.0)
    if hasattr(fill_data, "size"):
        fill_data.size = 0.8
    fill_obj = bpy.data.objects.new("SoftFill", fill_data)
    bpy.context.collection.objects.link(fill_obj)
    fill_pos = Vector((0.65, -0.55, 0.30))
    fill_obj.location = fill_pos
    fill_vec = (Vector((0.0, 0.0, 0.09)) - fill_pos).normalized()
    fill_obj.rotation_euler = (-fill_vec).to_track_quat('Z', 'Y').to_euler()

    # Camera at 3/4 front view (front-left, slightly above) framing whole model with ~10% margin
    world_verts = [obj.matrix_world @ v.co for obj in objects for v in obj.data.vertices]
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
    target = (min_v + max_v) * 0.5

    cam_dir = Vector((-0.62, -0.72, 0.32)).normalized()
    fwd = -cam_dir
    right = fwd.cross(Vector((0.0, 0.0, 1.0))).normalized()
    up = right.cross(fwd).normalized()

    # Center target in the camera view plane
    proj_x = [(p - target).dot(right) for p in world_verts]
    proj_y = [(p - target).dot(up) for p in world_verts]
    target = target + right * (0.5 * (min(proj_x) + max(proj_x))) + up * (0.5 * (min(proj_y) + max(proj_y)))

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 50.0
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.01
    cam_data.clip_end = 50.0
    tan_half_fov = (cam_data.sensor_width * 0.5) / cam_data.lens
    usable_tan = tan_half_fov * 0.80  # 10% margin on each side

    dist = 0.35
    for p in world_verts:
        rel = p - target
        px = abs(rel.dot(right))
        py = abs(rel.dot(up))
        pz = rel.dot(fwd)
        req_d = max(px, py) / max(usable_tan, 1e-5) - pz
        if req_d > dist:
            dist = req_d

    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = target + cam_dir * dist
    cam_obj.rotation_euler = cam_dir.to_track_quat('Z', 'Y').to_euler()
    scene.camera = cam_obj


def get_output_paths():
    argv = sys.argv
    out_arg = "pip.fbx"
    if "--" in argv:
        idx = argv.index("--")
        if idx + 1 < len(argv):
            out_arg = argv[idx + 1]
    out_arg = os.path.abspath(out_arg)
    out_dir = os.path.dirname(out_arg)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    base, ext = os.path.splitext(out_arg)
    fbx_path = out_arg if ext.lower() == ".fbx" else base + ".fbx"
    png_path = base + ".png"
    return fbx_path, png_path


def main():
    fbx_path, png_path = get_output_paths()
    pip_obj, wings = build_pip_and_wings()
    model_objs = [pip_obj] + wings

    tris = count_triangles(model_objs)

    bpy.ops.object.select_all(action='DESELECT')
    for obj in model_objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = pip_obj

    bpy.ops.export_scene.fbx(
        filepath=fbx_path,
        use_selection=True,
        bake_space_transform=True,
        axis_forward='-Z',
        axis_up='Y',
        mesh_smooth_type='FACE',
        add_leaf_bones=False,
    )

    setup_camera_and_lights(model_objs)
    bpy.context.scene.render.filepath = png_path
    bpy.ops.render.render(write_still=True)

    print("TRIS", tris)


if __name__ == "__main__":
    main()

