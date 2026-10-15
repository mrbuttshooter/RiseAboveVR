import bpy
import bmesh
import mathutils
from mathutils import Vector, Matrix
import math
import sys
import os

# ---------------------------------------------------------------------------
# 1. Clean the default scene completely
# ---------------------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

for block in list(bpy.data.meshes):
    bpy.data.meshes.remove(block)
for block in list(bpy.data.materials):
    bpy.data.materials.remove(block)
for block in list(bpy.data.cameras):
    bpy.data.cameras.remove(block)
for block in list(bpy.data.lights):
    bpy.data.lights.remove(block)

# ---------------------------------------------------------------------------
# 2. Material Helper & Definitions
# ---------------------------------------------------------------------------
def create_material(name, color, roughness=0.45, metallic=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = color
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
    return mat

mat_golden = create_material("Mat_Golden", (0.85, 0.55, 0.20, 1.0), roughness=0.45)
mat_cream  = create_material("Mat_Cream",  (0.95, 0.85, 0.65, 1.0), roughness=0.45)
mat_nose   = create_material("Mat_Nose",   (0.02, 0.02, 0.02, 1.0), roughness=0.30)
mat_eyes   = create_material("Mat_Eyes",   (0.04, 0.02, 0.01, 1.0), roughness=0.15)
mat_white  = create_material("Mat_White",  (1.00, 1.00, 1.00, 1.0), roughness=0.10)
mat_collar = create_material("Mat_Collar", (0.82, 0.06, 0.06, 1.0), roughness=0.40)
mat_gold   = create_material("Mat_GoldTag",(0.95, 0.75, 0.12, 1.0), roughness=0.25, metallic=0.85)
mat_tongue = create_material("Mat_Tongue", (0.92, 0.25, 0.38, 1.0), roughness=0.40)

materials_palette = [
    mat_golden,  # 0
    mat_cream,   # 1
    mat_nose,    # 2
    mat_eyes,    # 3
    mat_white,   # 4
    mat_collar,  # 5
    mat_gold,    # 6
    mat_tongue   # 7
]

MAT_GOLDEN_IDX = 0
MAT_CREAM_IDX  = 1
MAT_NOSE_IDX   = 2
MAT_EYES_IDX   = 3
MAT_WHITE_IDX  = 4
MAT_COLLAR_IDX = 5
MAT_GOLD_IDX   = 6
MAT_TONGUE_IDX = 7

# ---------------------------------------------------------------------------
# 3. Geometry Helpers (watertight BMesh builders)
# ---------------------------------------------------------------------------
def build_tube_bmesh(bm, points, radii_x, radii_z=None, num_sides=8,
                     cap_start=True, cap_end=True, mat_index=0,
                     feather_ventral=False):
    if radii_z is None:
        radii_z = list(radii_x)
    pts = [Vector(p) for p in points]
    n_pts = len(pts)
    if n_pts < 2:
        return []

    rings = []
    for i in range(n_pts):
        p = pts[i]
        rx = max(radii_x[i], 0.001)
        rz = max(radii_z[i], 0.001)

        if i == 0:
            tangent = (pts[1] - pts[0]).normalized()
        elif i == n_pts - 1:
            tangent = (pts[-1] - pts[-2]).normalized()
        else:
            tangent = (pts[i+1] - pts[i-1]).normalized()

        if tangent.length < 1e-5:
            tangent = Vector((0.0, 1.0, 0.0))

        up = Vector((0.0, 0.0, 1.0))
        if abs(tangent.dot(up)) > 0.95:
            up = Vector((1.0, 0.0, 0.0))
        side = tangent.cross(up).normalized()
        normal = side.cross(tangent).normalized()

        ring_verts = []
        for k in range(num_sides):
            angle = 2.0 * math.pi * k / num_sides
            ca = math.cos(angle)
            sa = math.sin(angle)

            cur_rz = rz
            if feather_ventral and sa < 0.0:
                cur_rz = rz * (1.0 - 0.55 * sa)

            offset = side * (rx * ca) + normal * (cur_rz * sa)
            v = bm.verts.new(p + offset)
            ring_verts.append(v)
        rings.append(ring_verts)

    for i in range(n_pts - 1):
        r0 = rings[i]
        r1 = rings[i+1]
        for k in range(num_sides):
            k_next = (k + 1) % num_sides
            f = bm.faces.new([r0[k], r0[k_next], r1[k_next], r1[k]])
            f.material_index = mat_index

    if cap_start:
        f0 = bm.faces.new([rings[0][k] for k in reversed(range(num_sides))])
        f0.material_index = mat_index
    if cap_end:
        f1 = bm.faces.new([rings[-1][k] for k in range(num_sides)])
        f1.material_index = mat_index

    return rings

def add_sphere_bmesh(bm, center, radius, mat_idx, u_seg=10, v_seg=8):
    res = bmesh.ops.create_uvsphere(
        bm,
        u_segments=u_seg,
        v_segments=v_seg,
        radius=radius
    )
    trans = Matrix.Translation(Vector(center))
    bmesh.ops.transform(bm, matrix=trans, verts=res['verts'])
    faces = set()
    for v in res['verts']:
        for f in v.link_faces:
            faces.add(f)
    for f in faces:
        f.material_index = mat_idx
    return res['verts']

# ---------------------------------------------------------------------------
# 4. Build "Biscuit" components in a single BMesh
# ---------------------------------------------------------------------------
bm = bmesh.new()

# --- A. Torso (Body) ---
torso_pts = [
    Vector((0.0, -0.23, 0.37)),
    Vector((0.0, -0.11, 0.39)),
    Vector((0.0,  0.05, 0.39)),
    Vector((0.0,  0.18, 0.38)),
    Vector((0.0,  0.28, 0.36))
]
torso_rx = [0.125, 0.145, 0.125, 0.130, 0.110]
torso_rz = [0.140, 0.155, 0.130, 0.135, 0.115]
torso_rings = build_tube_bmesh(
    bm, torso_pts, torso_rx, torso_rz,
    num_sides=12, cap_start=True, cap_end=True,
    mat_index=MAT_GOLDEN_IDX
)

for r_idx in range(len(torso_rings) - 1):
    r0 = torso_rings[r_idx]
    r1 = torso_rings[r_idx + 1]
    for k in range(12):
        k_next = (k + 1) % 12
        f_verts = {r0[k], r0[k_next], r1[k_next], r1[k]}
        avg_z = sum(v.co.z for v in f_verts) / 4.0
        avg_y = sum(v.co.y for v in f_verts) / 4.0
        if avg_z < 0.37 and avg_y < 0.15:
            for f in r0[k].link_faces:
                if set(f.verts) == f_verts:
                    f.material_index = MAT_CREAM_IDX
                    break

# --- B. Neck ---
neck_pts = [
    Vector((0.0, -0.16, 0.38)),
    Vector((0.0, -0.23, 0.43)),
    Vector((0.0, -0.30, 0.49)),
    Vector((0.0, -0.36, 0.53))
]
neck_rx = [0.095, 0.085, 0.075, 0.070]
neck_rz = [0.105, 0.095, 0.085, 0.080]
neck_rings = build_tube_bmesh(
    bm, neck_pts, neck_rx, neck_rz,
    num_sides=10, cap_start=True, cap_end=True,
    mat_index=MAT_GOLDEN_IDX
)

for r_idx in range(len(neck_rings) - 1):
    r0 = neck_rings[r_idx]
    r1 = neck_rings[r_idx + 1]
    for k in range(10):
        k_next = (k + 1) % 10
        f_verts = {r0[k], r0[k_next], r1[k_next], r1[k]}
        avg_z = sum(v.co.z for v in f_verts) / 4.0
        avg_y = sum(v.co.y for v in f_verts) / 4.0
        if avg_y < -0.20 and avg_z < 0.47:
            for f in r0[k].link_faces:
                if set(f.verts) == f_verts:
                    f.material_index = MAT_CREAM_IDX
                    break

# --- C. Head (Cranium) ---
head_pts = [
    Vector((0.0, -0.29, 0.53)),
    Vector((0.0, -0.35, 0.545)),
    Vector((0.0, -0.41, 0.540)),
    Vector((0.0, -0.46, 0.525))
]
head_rx = [0.065, 0.105, 0.095, 0.075]
head_rz = [0.075, 0.110, 0.100, 0.080]
build_tube_bmesh(
    bm, head_pts, head_rx, head_rz,
    num_sides=12, cap_start=True, cap_end=True,
    mat_index=MAT_GOLDEN_IDX
)

# --- D. Muzzle (Retriever profile) ---
muzzle_pts = [
    Vector((0.0, -0.42, 0.505)),
    Vector((0.0, -0.48, 0.495)),
    Vector((0.0, -0.54, 0.485)),
    Vector((0.0, -0.59, 0.480))
]
muzzle_rx = [0.060, 0.052, 0.044, 0.035]
muzzle_rz = [0.062, 0.054, 0.046, 0.036]
build_tube_bmesh(
    bm, muzzle_pts, muzzle_rx, muzzle_rz,
    num_sides=10, cap_start=True, cap_end=True,
    mat_index=MAT_CREAM_IDX
)

# --- E. Nose ---
nose_pts = [
    Vector((0.0, -0.585, 0.498)),
    Vector((0.0, -0.603, 0.496))
]
nose_rx = [0.024, 0.018]
nose_rz = [0.018, 0.013]
build_tube_bmesh(
    bm, nose_pts, nose_rx, nose_rz,
    num_sides=8, cap_start=True, cap_end=True,
    mat_index=MAT_NOSE_IDX
)

# --- F. Tongue ---
tongue_pts = [
    Vector((0.010, -0.50, 0.465)),
    Vector((0.013, -0.53, 0.450)),
    Vector((0.016, -0.56, 0.430)),
    Vector((0.018, -0.58, 0.415))
]
tongue_rx = [0.018, 0.018, 0.016, 0.012]
tongue_rz = [0.005, 0.005, 0.004, 0.003]
build_tube_bmesh(
    bm, tongue_pts, tongue_rx, tongue_rz,
    num_sides=8, cap_start=True, cap_end=True,
    mat_index=MAT_TONGUE_IDX
)

# --- G. Floppy Retriever Ears ---
left_ear_pts = [
    Vector(( 0.070, -0.36, 0.565)),
    Vector(( 0.102, -0.37, 0.550)),
    Vector(( 0.110, -0.37, 0.490)),
    Vector(( 0.100, -0.38, 0.420)),
    Vector(( 0.090, -0.39, 0.360))
]
ear_rx = [0.020, 0.032, 0.038, 0.032, 0.022]
ear_rz = [0.012, 0.010, 0.009, 0.008, 0.006]
build_tube_bmesh(
    bm, left_ear_pts, ear_rx, ear_rz,
    num_sides=8, cap_start=True, cap_end=True,
    mat_index=MAT_GOLDEN_IDX
)

right_ear_pts = [
    Vector((-0.070, -0.36, 0.565)),
    Vector((-0.102, -0.37, 0.550)),
    Vector((-0.110, -0.37, 0.490)),
    Vector((-0.100, -0.38, 0.420)),
    Vector((-0.090, -0.39, 0.360))
]
build_tube_bmesh(
    bm, right_ear_pts, ear_rx, ear_rz,
    num_sides=8, cap_start=True, cap_end=True,
    mat_index=MAT_GOLDEN_IDX
)

# --- H. Eyes & Highlights ---
add_sphere_bmesh(bm, ( 0.062, -0.440, 0.535), 0.022, MAT_EYES_IDX,  u_seg=10, v_seg=8)
add_sphere_bmesh(bm, (-0.062, -0.440, 0.535), 0.022, MAT_EYES_IDX,  u_seg=10, v_seg=8)

add_sphere_bmesh(bm, ( 0.068, -0.455, 0.545), 0.007,  MAT_WHITE_IDX, u_seg=8,  v_seg=6)
add_sphere_bmesh(bm, (-0.056, -0.455, 0.545), 0.007,  MAT_WHITE_IDX, u_seg=8,  v_seg=6)
add_sphere_bmesh(bm, ( 0.072, -0.450, 0.532), 0.0035, MAT_WHITE_IDX, u_seg=6,  v_seg=4)
add_sphere_bmesh(bm, (-0.052, -0.450, 0.532), 0.0035, MAT_WHITE_IDX, u_seg=6,  v_seg=4)

# --- I. Collar & Gold Tag ---
collar_pts = []
center = Vector((0.0, -0.27, 0.46))
v_x = Vector((1.0, 0.0, 0.0))
v_yz = Vector((0.0, 0.7071, 0.7071))
for k in range(12):
    ang = 2.0 * math.pi * k / 12
    p = center + v_x * (0.086 * math.cos(ang)) + v_yz * (0.092 * math.sin(ang))
    collar_pts.append(p)
collar_pts.append(collar_pts[0])
build_tube_bmesh(
    bm, collar_pts, [0.010]*13,
    num_sides=6, cap_start=False, cap_end=False,
    mat_index=MAT_COLLAR_IDX
)

tag_pts = [
    Vector((0.0, -0.315, 0.41)),
    Vector((0.0, -0.325, 0.41))
]
build_tube_bmesh(
    bm, tag_pts, [0.022, 0.022],
    num_sides=10, cap_start=True, cap_end=True,
    mat_index=MAT_GOLD_IDX
)

tag_link_pts = [
    Vector((0.0, -0.305, 0.43)),
    Vector((0.0, -0.315, 0.415))
]
build_tube_bmesh(
    bm, tag_link_pts, [0.004, 0.004],
    num_sides=6, cap_start=True, cap_end=True,
    mat_index=MAT_GOLD_IDX
)

# --- J. Tail (Curved & Feathery) ---
tail_pts = [
    Vector((0.0, 0.27, 0.36)),
    Vector((0.0, 0.35, 0.42)),
    Vector((0.0, 0.43, 0.50)),
    Vector((0.0, 0.47, 0.60)),
    Vector((0.0, 0.45, 0.69)),
    Vector((0.0, 0.39, 0.74)),
    Vector((0.0, 0.31, 0.75))
]
tail_rx = [0.045, 0.040, 0.035, 0.028, 0.022, 0.016, 0.008]
tail_rz = [0.045, 0.042, 0.038, 0.032, 0.026, 0.018, 0.008]
build_tube_bmesh(
    bm, tail_pts, tail_rx, tail_rz,
    num_sides=8, cap_start=True, cap_end=True,
    mat_index=MAT_GOLDEN_IDX, feather_ventral=True
)

# --- K. Four Tapered Limbs & Paws (Walking Pose, Front Right Lifted) ---
# Front Left Leg (Planted firmly)
fl_pts = [
    Vector(( 0.12, -0.12, 0.38)),
    Vector(( 0.12, -0.13, 0.28)),
    Vector(( 0.12, -0.14, 0.18)),
    Vector(( 0.12, -0.15, 0.08)),
    Vector(( 0.12, -0.16, 0.04)),
    Vector(( 0.12, -0.19, 0.02)),
    Vector(( 0.12, -0.22, 0.01))
]
fl_rx = [0.060, 0.046, 0.036, 0.032, 0.034, 0.044, 0.040]
fl_rz = [0.065, 0.048, 0.038, 0.032, 0.026, 0.022, 0.014]
build_tube_bmesh(
    bm, fl_pts, fl_rx, fl_rz,
    num_sides=10, cap_start=True, cap_end=True,
    mat_index=MAT_GOLDEN_IDX
)

# Front Right Leg (LIFTED mid-step)
fr_pts = [
    Vector((-0.12, -0.12, 0.38)),
    Vector((-0.12, -0.16, 0.28)),
    Vector((-0.12, -0.19, 0.20)),
    Vector((-0.12, -0.22, 0.14)),
    Vector((-0.12, -0.24, 0.10)),
    Vector((-0.12, -0.26, 0.08)),
    Vector((-0.12, -0.28, 0.07))
]
fr_rx = [0.060, 0.046, 0.038, 0.033, 0.034, 0.044, 0.038]
fr_rz = [0.065, 0.048, 0.040, 0.032, 0.026, 0.022, 0.016]
build_tube_bmesh(
    bm, fr_pts, fr_rx, fr_rz,
    num_sides=10, cap_start=True, cap_end=True,
    mat_index=MAT_GOLDEN_IDX
)

# Rear Left Leg (Trailing stride)
rl_pts = [
    Vector(( 0.12,  0.22, 0.37)),
    Vector(( 0.12,  0.18, 0.26)),
    Vector(( 0.12,  0.20, 0.18)),
    Vector(( 0.12,  0.27, 0.12)),
    Vector(( 0.12,  0.27, 0.05)),
    Vector(( 0.12,  0.25, 0.02)),
    Vector(( 0.12,  0.22, 0.01))
]
rl_rx = [0.070, 0.055, 0.042, 0.035, 0.032, 0.042, 0.038]
rl_rz = [0.075, 0.058, 0.044, 0.036, 0.028, 0.022, 0.014]
build_tube_bmesh(
    bm, rl_pts, rl_rx, rl_rz,
    num_sides=10, cap_start=True, cap_end=True,
    mat_index=MAT_GOLDEN_IDX
)

# Rear Right Leg (Stepping forward)
rr_pts = [
    Vector((-0.12,  0.22, 0.37)),
    Vector((-0.12,  0.14, 0.26)),
    Vector((-0.12,  0.12, 0.18)),
    Vector((-0.12,  0.19, 0.12)),
    Vector((-0.12,  0.19, 0.05)),
    Vector((-0.12,  0.17, 0.02)),
    Vector((-0.12,  0.14, 0.01))
]
rr_rx = [0.070, 0.055, 0.042, 0.035, 0.032, 0.042, 0.038]
rr_rz = [0.075, 0.058, 0.044, 0.036, 0.028, 0.022, 0.014]
build_tube_bmesh(
    bm, rr_pts, rr_rx, rr_rz,
    num_sides=10, cap_start=True, cap_end=True,
    mat_index=MAT_GOLDEN_IDX
)

# ---------------------------------------------------------------------------
# 5. Ground alignment: Lowest point at exactly Z = 0
# ---------------------------------------------------------------------------
min_z = min(v.co.z for v in bm.verts)
for v in bm.verts:
    v.co.z -= min_z

# ---------------------------------------------------------------------------
# 6. Instantiate Object "Biscuit" & Assign Materials
# ---------------------------------------------------------------------------
dog_mesh = bpy.data.meshes.new(name="Biscuit")
bm.to_mesh(dog_mesh)
bm.free()

dog_obj = bpy.data.objects.new(name="Biscuit", object_data=dog_mesh)
bpy.context.scene.collection.objects.link(dog_obj)

for mat in materials_palette:
    dog_obj.data.materials.append(mat)

# ---------------------------------------------------------------------------
# 7. Modifiers & Smooth Shading
# ---------------------------------------------------------------------------
subsurf = dog_obj.modifiers.new(name="Subdivision", type='SUBSURF')
subsurf.levels = 1
subsurf.render_levels = 1

bpy.context.view_layer.objects.active = dog_obj
dog_obj.select_set(True)
bpy.ops.object.modifier_apply(modifier="Subdivision")

for poly in dog_obj.data.polygons:
    poly.use_smooth = True

# ---------------------------------------------------------------------------
# 8. Print Triangle Count
# ---------------------------------------------------------------------------
dog_obj.data.calc_loop_triangles()
tri_count = len(dog_obj.data.loop_triangles)
print("TRIS", tri_count)

# ---------------------------------------------------------------------------
# 9. Output Path parsing
# ---------------------------------------------------------------------------
output_path = "Biscuit.fbx"
if "--" in sys.argv:
    idx = sys.argv.index("--")
    if idx + 1 < len(sys.argv):
        output_path = sys.argv[idx + 1]

out_dir = os.path.dirname(output_path)
if out_dir and not os.path.exists(out_dir):
    os.makedirs(out_dir, exist_ok=True)

# ---------------------------------------------------------------------------
# 10. FBX Export
# ---------------------------------------------------------------------------
bpy.ops.object.select_all(action='DESELECT')
dog_obj.select_set(True)
bpy.context.view_layer.objects.active = dog_obj
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bpy.ops.export_scene.fbx(
    filepath=output_path,
    use_selection=True,
    axis_forward='-Z',
    axis_up='Y',
    mesh_smooth_type='FACE'
)

# ---------------------------------------------------------------------------
# 11. Lighting, World & Camera Preview Setup
# ---------------------------------------------------------------------------
scene = bpy.context.scene
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100

# EEVEE engine selection across Blender versions
engine_keys = scene.render.bl_rna.properties['engine'].enum_items.keys()
if 'BLENDER_EEVEE_NEXT' in engine_keys:
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
elif 'BLENDER_EEVEE' in engine_keys:
    scene.render.engine = 'BLENDER_EEVEE'

# Grey World
world = scene.world
if not world:
    world = bpy.data.worlds.new(name="World")
    scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs['Color'].default_value = (0.5, 0.5, 0.5, 1.0)
    bg_node.inputs['Strength'].default_value = 0.45

# Sun Light (strength 3)
sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.0
sun_data.color = (1.0, 0.98, 0.95)
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(52), math.radians(15), math.radians(-35))

# Soft Fill Light
fill_data = bpy.data.lights.new(name="FillLight", type='POINT')
fill_data.energy = 120.0
fill_data.shadow_soft_size = 0.35
fill_data.color = (0.9, 0.95, 1.0)
fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_data)
scene.collection.objects.link(fill_obj)
fill_obj.location = (-0.9, -1.2, 0.7)

# Camera (3/4 front view: front-left, slightly above, framing dog with ~10% margin)
cam_data = bpy.data.cameras.new(name="Camera")
cam_data.lens = 50.0
cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

cam_pos = Vector((-1.15, -1.35, 0.75))
target_pos = Vector((0.0, -0.05, 0.32))
cam_obj.location = cam_pos

direction = target_pos - cam_pos
rot_quat = direction.to_track_quat('-Z', 'Y')
cam_obj.rotation_euler = rot_quat.to_euler()

# ---------------------------------------------------------------------------
# 12. Render Preview PNG
# ---------------------------------------------------------------------------
png_path = os.path.splitext(output_path)[0] + ".png"
scene.render.filepath = png_path
scene.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
