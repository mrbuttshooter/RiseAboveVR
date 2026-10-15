import bpy
import bmesh
import mathutils
from mathutils import Vector, Euler, Matrix, Quaternion
import math
import sys
import os

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh, do_unlink=True)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat, do_unlink=True)
for cam in list(bpy.data.cameras):
    bpy.data.cameras.remove(cam, do_unlink=True)
for light in list(bpy.data.lights):
    bpy.data.lights.remove(light, do_unlink=True)
for world in list(bpy.data.worlds):
    bpy.data.worlds.remove(world, do_unlink=True)

def create_mat(name, color, roughness=0.45):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = color
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
    return mat

mat_orange = create_mat("Mat_TabbyOrange", (0.88, 0.38, 0.06, 1.0), 0.45)
mat_dark_orange = create_mat("Mat_TabbyDarkOrange", (0.42, 0.12, 0.02, 1.0), 0.45)
mat_white = create_mat("Mat_MittensWhite", (0.95, 0.94, 0.92, 1.0), 0.45)
mat_pink = create_mat("Mat_NosePink", (0.92, 0.42, 0.50, 1.0), 0.45)
mat_green = create_mat("Mat_EyeGreen", (0.12, 0.78, 0.25, 1.0), 0.25)
mat_black = create_mat("Mat_PupilBlack", (0.015, 0.015, 0.015, 1.0), 0.2)
mat_highlight = create_mat("Mat_HighlightWhite", (1.0, 1.0, 1.0, 1.0), 0.1)

def make_sphere(name, loc, scale, rot=(0.0, 0.0, 0.0), mat=None, subsurf=1, segments=12, rings=8):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1.0, location=loc, rotation=rot)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    if subsurf > 0:
        mod = obj.modifiers.new(name="Subsurf", type='SUBSURF')
        mod.levels = subsurf
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj

def make_cylinder(name, loc, radius, depth, rot=(0.0, 0.0, 0.0), mat=None, subsurf=1, vertices=10, scale=(1.0, 1.0, 1.0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rot)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    if subsurf > 0:
        mod = obj.modifiers.new(name="Subsurf", type='SUBSURF')
        mod.levels = subsurf
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj

def make_cone(name, loc, radius1, radius2, depth, rot=(0.0, 0.0, 0.0), mat=None, subsurf=1, vertices=8, scale=(1.0, 1.0, 1.0)):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius1, radius2=radius2, depth=depth, location=loc, rotation=rot)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    if subsurf > 0:
        mod = obj.modifiers.new(name="Subsurf", type='SUBSURF')
        mod.levels = subsurf
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj

make_sphere("Body", (0.0, 0.04, 0.145), (0.095, 0.145, 0.10), rot=(math.radians(-6), 0.0, 0.0), mat=mat_orange, subsurf=1, segments=14, rings=10)
make_cylinder("Neck", (0.0, -0.09, 0.185), 0.065, 0.08, rot=(math.radians(25), 0.0, 0.0), mat=mat_orange, subsurf=1, vertices=10)
make_sphere("ChestTuft", (0.0, -0.095, 0.145), (0.075, 0.05, 0.075), rot=(math.radians(15), 0.0, 0.0), mat=mat_white, subsurf=1, segments=10, rings=8)

head_loc = Vector((0.0, -0.16, 0.225))
head_rot = Euler((math.radians(-22), 0.0, 0.0), 'XYZ')
head_mat = head_rot.to_matrix()

make_sphere("Head", head_loc, (0.082, 0.075, 0.072), rot=head_rot, mat=mat_orange, subsurf=1, segments=14, rings=10)

def head_to_world(local_p):
    return head_loc + head_mat @ local_p

def head_rot_combine(add_euler):
    q1 = head_rot.to_quaternion()
    q2 = add_euler.to_quaternion()
    return (q1 @ q2).to_euler('XYZ')

cheek_l1_loc = head_to_world(Vector((0.070, -0.015, -0.015)))
cheek_l1_rot = head_rot_combine(Euler((math.radians(-10), math.radians(65), math.radians(20)), 'XYZ'))
make_cone("Cheek_L1", cheek_l1_loc, 0.030, 0.005, 0.060, rot=cheek_l1_rot, mat=mat_orange, subsurf=1, vertices=8)

cheek_l2_loc = head_to_world(Vector((0.066, -0.005, -0.035)))
cheek_l2_rot = head_rot_combine(Euler((math.radians(-5), math.radians(75), math.radians(10)), 'XYZ'))
make_cone("Cheek_L2", cheek_l2_loc, 0.024, 0.004, 0.050, rot=cheek_l2_rot, mat=mat_orange, subsurf=1, vertices=8)

cheek_r1_loc = head_to_world(Vector((-0.070, -0.015, -0.015)))
cheek_r1_rot = head_rot_combine(Euler((math.radians(-10), math.radians(-65), math.radians(-20)), 'XYZ'))
make_cone("Cheek_R1", cheek_r1_loc, 0.030, 0.005, 0.060, rot=cheek_r1_rot, mat=mat_orange, subsurf=1, vertices=8)

cheek_r2_loc = head_to_world(Vector((-0.066, -0.005, -0.035)))
cheek_r2_rot = head_rot_combine(Euler((math.radians(-5), math.radians(-75), math.radians(-10)), 'XYZ'))
make_cone("Cheek_R2", cheek_r2_loc, 0.024, 0.004, 0.050, rot=cheek_r2_rot, mat=mat_orange, subsurf=1, vertices=8)

pad_l_loc = head_to_world(Vector((0.022, -0.062, -0.022)))
make_sphere("WhiskerPad_L", pad_l_loc, (0.026, 0.024, 0.020), rot=head_rot, mat=mat_white, subsurf=1, segments=10, rings=8)

pad_r_loc = head_to_world(Vector((-0.022, -0.062, -0.022)))
make_sphere("WhiskerPad_R", pad_r_loc, (0.026, 0.024, 0.020), rot=head_rot, mat=mat_white, subsurf=1, segments=10, rings=8)

chin_loc = head_to_world(Vector((0.0, -0.052, -0.045)))
make_sphere("Chin", chin_loc, (0.020, 0.018, 0.015), rot=head_rot, mat=mat_white, subsurf=1, segments=8, rings=6)

nose_loc = head_to_world(Vector((0.0, -0.072, -0.008)))
make_sphere("Nose", nose_loc, (0.015, 0.010, 0.011), rot=head_rot, mat=mat_pink, subsurf=1, segments=8, rings=6)

eye_l_loc = head_to_world(Vector((0.038, -0.058, 0.018)))
make_sphere("Eye_L", eye_l_loc, (0.022, 0.014, 0.024), rot=head_rot, mat=mat_green, subsurf=0, segments=12, rings=8)

eye_r_loc = head_to_world(Vector((-0.038, -0.058, 0.018)))
make_sphere("Eye_R", eye_r_loc, (0.022, 0.014, 0.024), rot=head_rot, mat=mat_green, subsurf=0, segments=12, rings=8)

pupil_l_loc = head_to_world(Vector((0.038, -0.070, 0.018)))
make_sphere("Pupil_L", pupil_l_loc, (0.0055, 0.003, 0.019), rot=head_rot, mat=mat_black, subsurf=0, segments=8, rings=6)

pupil_r_loc = head_to_world(Vector((-0.038, -0.070, 0.018)))
make_sphere("Pupil_R", pupil_r_loc, (0.0055, 0.003, 0.019), rot=head_rot, mat=mat_black, subsurf=0, segments=8, rings=6)

hl1_l_loc = head_to_world(Vector((0.046, -0.071, 0.025)))
make_sphere("Highlight1_L", hl1_l_loc, (0.0045, 0.003, 0.0045), rot=head_rot, mat=mat_highlight, subsurf=0, segments=6, rings=4)

hl2_l_loc = head_to_world(Vector((0.032, -0.071, 0.012)))
make_sphere("Highlight2_L", hl2_l_loc, (0.0028, 0.002, 0.0028), rot=head_rot, mat=mat_highlight, subsurf=0, segments=6, rings=4)

hl1_r_loc = head_to_world(Vector((-0.030, -0.071, 0.025)))
make_sphere("Highlight1_R", hl1_r_loc, (0.0045, 0.003, 0.0045), rot=head_rot, mat=mat_highlight, subsurf=0, segments=6, rings=4)

hl2_r_loc = head_to_world(Vector((-0.044, -0.071, 0.012)))
make_sphere("Highlight2_R", hl2_r_loc, (0.0028, 0.002, 0.0028), rot=head_rot, mat=mat_highlight, subsurf=0, segments=6, rings=4)

ear_l_loc = head_to_world(Vector((0.048, 0.010, 0.058)))
ear_l_rot = head_rot_combine(Euler((math.radians(-10), math.radians(22), math.radians(-15)), 'XYZ'))
make_cone("EarOuter_L", ear_l_loc, 0.034, 0.005, 0.070, rot=ear_l_rot, mat=mat_orange, subsurf=1, vertices=8, scale=(1.0, 0.55, 1.0))

ear_lin_loc = head_to_world(Vector((0.048, -0.002, 0.058)))
make_cone("EarInner_L", ear_lin_loc, 0.025, 0.003, 0.058, rot=ear_l_rot, mat=mat_pink, subsurf=1, vertices=8, scale=(1.0, 0.45, 1.0))

ear_r_loc = head_to_world(Vector((-0.048, 0.010, 0.058)))
ear_r_rot = head_rot_combine(Euler((math.radians(-10), math.radians(-22), math.radians(15)), 'XYZ'))
make_cone("EarOuter_R", ear_r_loc, 0.034, 0.005, 0.070, rot=ear_r_rot, mat=mat_orange, subsurf=1, vertices=8, scale=(1.0, 0.55, 1.0))

ear_rin_loc = head_to_world(Vector((-0.048, -0.002, 0.058)))
make_cone("EarInner_R", ear_rin_loc, 0.025, 0.003, 0.058, rot=ear_r_rot, mat=mat_pink, subsurf=1, vertices=8, scale=(1.0, 0.45, 1.0))

whisker_configs = [
    (1, Vector((0.022, -0.060, -0.018)), Euler((math.radians(10), math.radians(72), math.radians(15)), 'XYZ'), 1),
    (2, Vector((0.022, -0.060, -0.022)), Euler((math.radians(0), math.radians(80), math.radians(0)), 'XYZ'), 1),
    (3, Vector((0.022, -0.060, -0.026)), Euler((math.radians(-12), math.radians(82), math.radians(-15)), 'XYZ'), 1),
    (1, Vector((-0.022, -0.060, -0.018)), Euler((math.radians(10), math.radians(-72), math.radians(-15)), 'XYZ'), -1),
    (2, Vector((-0.022, -0.060, -0.022)), Euler((math.radians(0), math.radians(-80), math.radians(0)), 'XYZ'), -1),
    (3, Vector((-0.022, -0.060, -0.026)), Euler((math.radians(-12), math.radians(-82), math.radians(15)), 'XYZ'), -1),
]

for idx, loc_off, rot_off, side in whisker_configs:
    side_name = "L" if side == 1 else "R"
    w_root = head_to_world(loc_off)
    w_rot = head_rot_combine(rot_off)
    w_dir = (head_rot.to_quaternion() @ rot_off.to_quaternion()) @ Vector((0.0, 0.0, 1.0))
    w_center = w_root + w_dir * 0.035
    make_cone(f"Whisker_{side_name}{idx}", w_center, 0.0016, 0.0004, 0.075, rot=w_rot, mat=mat_white, subsurf=0, vertices=6)

stripe_head_c = head_to_world(Vector((0.0, -0.038, 0.067)))
make_sphere("StripeHead_C", stripe_head_c, (0.007, 0.022, 0.005), rot=head_rot, mat=mat_dark_orange, subsurf=0, segments=8, rings=6)

stripe_head_l = head_to_world(Vector((0.018, -0.034, 0.062)))
s_l_rot = head_rot_combine(Euler((0.0, 0.0, math.radians(-20)), 'XYZ'))
make_sphere("StripeHead_L", stripe_head_l, (0.006, 0.018, 0.005), rot=s_l_rot, mat=mat_dark_orange, subsurf=0, segments=8, rings=6)

stripe_head_r = head_to_world(Vector((-0.018, -0.034, 0.062)))
s_r_rot = head_rot_combine(Euler((0.0, 0.0, math.radians(20)), 'XYZ'))
make_sphere("StripeHead_R", stripe_head_r, (0.006, 0.018, 0.005), rot=s_r_rot, mat=mat_dark_orange, subsurf=0, segments=8, rings=6)

body_stripe_y = [-0.015, 0.035, 0.085, 0.135]
for i, sy in enumerate(body_stripe_y):
    s_loc = (0.0, sy, 0.145)
    s_rot = (0.0, math.radians(90), 0.0)
    make_cylinder(f"BodyStripe_{i+1}", s_loc, 0.098, 0.016, rot=s_rot, mat=mat_dark_orange, subsurf=1, vertices=12, scale=(1.04, 1.0, 0.98))

def build_front_leg(side):
    sx = 0.055 * side
    prefix = "FrontLeg_L" if side == 1 else "FrontLeg_R"
    make_cylinder(f"{prefix}_Upper", (sx, -0.065, 0.090), 0.022, 0.13, rot=(math.radians(4), 0.0, 0.0), mat=mat_orange, subsurf=1, vertices=8)
    make_sphere(f"{prefix}_Paw", (sx, -0.075, 0.022), (0.028, 0.034, 0.020), mat=mat_white, subsurf=1, segments=10, rings=6)
    make_sphere(f"{prefix}_Toe1", (sx - 0.012 * side, -0.100, 0.014), (0.011, 0.014, 0.011), mat=mat_white, subsurf=0, segments=8, rings=5)
    make_sphere(f"{prefix}_Toe2", (sx, -0.104, 0.014), (0.012, 0.015, 0.012), mat=mat_white, subsurf=0, segments=8, rings=5)
    make_sphere(f"{prefix}_Toe3", (sx + 0.012 * side, -0.100, 0.014), (0.011, 0.014, 0.011), mat=mat_white, subsurf=0, segments=8, rings=5)

def build_rear_leg(side):
    sx = 0.075 * side
    prefix = "RearLeg_L" if side == 1 else "RearLeg_R"
    make_sphere(f"{prefix}_Thigh", (sx, 0.110, 0.130), (0.035, 0.055, 0.055), rot=(math.radians(-10), 0.0, 0.0), mat=mat_orange, subsurf=1, segments=10, rings=6)
    make_cylinder(f"{prefix}_Lower", (sx * 0.95, 0.125, 0.065), 0.020, 0.09, rot=(math.radians(-12), 0.0, 0.0), mat=mat_orange, subsurf=1, vertices=8)
    make_sphere(f"{prefix}_Paw", (sx * 0.92, 0.130, 0.022), (0.028, 0.034, 0.020), mat=mat_white, subsurf=1, segments=10, rings=6)
    make_sphere(f"{prefix}_Toe1", (sx * 0.92 - 0.012 * side, 0.102, 0.014), (0.011, 0.014, 0.011), mat=mat_white, subsurf=0, segments=8, rings=5)
    make_sphere(f"{prefix}_Toe2", (sx * 0.92, 0.098, 0.014), (0.012, 0.015, 0.012), mat=mat_white, subsurf=0, segments=8, rings=5)
    make_sphere(f"{prefix}_Toe3", (sx * 0.92 + 0.012 * side, 0.102, 0.014), (0.011, 0.014, 0.011), mat=mat_white, subsurf=0, segments=8, rings=5)

build_front_leg(1)
build_front_leg(-1)
build_rear_leg(1)
build_rear_leg(-1)

tail_points = [
    Vector((0.0, 0.145, 0.145)),
    Vector((0.0, 0.190, 0.175)),
    Vector((0.0, 0.225, 0.220)),
    Vector((0.0, 0.225, 0.275)),
    Vector((0.0, 0.190, 0.320)),
    Vector((0.0, 0.145, 0.345)),
    Vector((0.0, 0.110, 0.345)),
]

tail_radii = [0.019, 0.017, 0.016, 0.015, 0.014, 0.013, 0.012]

for i in range(len(tail_points) - 1):
    p1 = tail_points[i]
    p2 = tail_points[i + 1]
    seg_vec = p2 - p1
    seg_len = seg_vec.length
    seg_mid = (p1 + p2) * 0.5
    seg_quat = Vector((0.0, 0.0, 1.0)).rotation_difference(seg_vec)
    seg_rot = seg_quat.to_euler('XYZ')
    r_avg = (tail_radii[i] + tail_radii[i + 1]) * 0.5
    seg_mat = mat_orange
    make_cylinder(f"TailSeg_{i+1}", seg_mid, r_avg, seg_len + 0.018, rot=seg_rot, mat=seg_mat, subsurf=1, vertices=8)
    make_sphere(f"TailJoint_{i+1}", p2, (tail_radii[i+1], tail_radii[i+1], tail_radii[i+1]), mat=seg_mat, subsurf=0, segments=8, rings=6)

for stripe_idx, p_idx in enumerate([1, 3]):
    st_p = (tail_points[p_idx] + tail_points[p_idx + 1]) * 0.5
    st_vec = tail_points[p_idx + 1] - tail_points[p_idx]
    st_quat = Vector((0.0, 0.0, 1.0)).rotation_difference(st_vec)
    st_rot = st_quat.to_euler('XYZ')
    st_r = tail_radii[p_idx] * 1.08
    make_cylinder(f"TailStripe_{stripe_idx+1}", st_p, st_r, 0.018, rot=st_rot, mat=mat_dark_orange, subsurf=1, vertices=8)

tail_tip = tail_points[-1]
make_sphere("TailTip", tail_tip, (0.013, 0.013, 0.013), mat=mat_white, subsurf=0, segments=8, rings=6)

if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

all_mesh_objs = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
bpy.ops.object.select_all(action='DESELECT')
for obj in all_mesh_objs:
    obj.select_set(True)

bpy.context.view_layer.objects.active = all_mesh_objs[0]
bpy.ops.object.join()
mittens = bpy.context.active_object
mittens.name = "Mittens"

bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

min_z = min(v.co.z for v in mittens.data.vertices)
for v in mittens.data.vertices:
    v.co.z -= min_z
mittens.data.update()

bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')

mittens.data.calc_loop_triangles()
tri_count = len(mittens.data.loop_triangles)
if tri_count == 0:
    tri_count = sum(len(p.vertices) - 2 for p in mittens.data.polygons)
print("TRIS", tri_count)

output_path = "Mittens.fbx"
if "--" in sys.argv:
    args = sys.argv[sys.argv.index("--") + 1:]
    if args:
        output_path = args[0]
out_dir = os.path.dirname(output_path)
if out_dir:
    os.makedirs(out_dir, exist_ok=True)

bpy.ops.object.select_all(action='DESELECT')
mittens.select_set(True)
bpy.context.view_layer.objects.active = mittens

try:
    bpy.ops.export_scene.fbx(
        filepath=output_path,
        use_selection=True,
        bake_space_transform=True,
        axis_forward='-Z',
        axis_up='Y',
        mesh_smooth_type='FACE'
    )
except TypeError:
    bpy.ops.export_scene.fbx(
        filepath=output_path,
        use_selection=True,
        axis_forward='-Z',
        axis_up='Y',
        mesh_smooth_type='FACE'
    )

preview_path = os.path.splitext(output_path)[0] + ".png"

scene = bpy.context.scene
avail_engines = [item.identifier for item in scene.render.bl_rna.properties['engine'].enum_items]
eevee_engine = next((e for e in ['BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'] if e in avail_engines), avail_engines[0])
scene.render.engine = eevee_engine
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.filepath = preview_path
scene.render.image_settings.file_format = 'PNG'

world = bpy.data.worlds.new(name="GreyWorld")
scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.45, 0.45, 0.45, 1.0)
    bg_node.inputs["Strength"].default_value = 0.45

sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.0
sun_data.color = (1.0, 0.98, 0.95)
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(48), math.radians(16), math.radians(-32))

fill_data = bpy.data.lights.new(name="FillLight", type='AREA')
fill_data.energy = 14.0
fill_data.size = 0.65
fill_data.color = (0.86, 0.92, 1.0)
fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_data)
scene.collection.objects.link(fill_obj)
fill_obj.location = (0.40, -0.65, 0.35)
fill_obj.rotation_euler = (math.radians(65), 0.0, math.radians(30))

bbox_corners = [mittens.matrix_world @ Vector(corner) for corner in mittens.bound_box]
center = sum(bbox_corners, Vector((0.0, 0.0, 0.0))) / 8.0
max_dist = max((v - center).length for v in bbox_corners)

cam_data = bpy.data.cameras.new(name="PreviewCam")
cam_data.lens = 50
cam_obj = bpy.data.objects.new(name="PreviewCam", object_data=cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

cam_dir = Vector((-0.65, -0.85, 0.48)).normalized()
fov = 2.0 * math.atan(18.0 / 50.0)
dist = (max_dist * 1.12) / math.sin(fov / 2.0)
cam_obj.location = center + cam_dir * dist
direction = center - cam_obj.location
cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

bpy.ops.render.render(write_still=True)
