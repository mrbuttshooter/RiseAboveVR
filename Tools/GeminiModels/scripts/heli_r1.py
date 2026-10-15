import bpy
import bmesh
import mathutils
from mathutils import Vector, Matrix, Euler
import math
import sys
import os

# -----------------------------------------------------------------------------
# 1. SCENE CLEANUP
# -----------------------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

for block_col in [bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.curves]:
    for block in list(block_col):
        if block.users == 0:
            block_col.remove(block)

# -----------------------------------------------------------------------------
# 2. OUTPUT PATH HANDLING
# -----------------------------------------------------------------------------
output_path = "helicopter.fbx"
if "--" in sys.argv:
    argv_rest = sys.argv[sys.argv.index("--") + 1:]
    if len(argv_rest) > 0 and argv_rest[0].strip():
        output_path = argv_rest[0].strip()

output_path = os.path.abspath(output_path)
out_dir = os.path.dirname(output_path)
if out_dir:
    os.makedirs(out_dir, exist_ok=True)

# -----------------------------------------------------------------------------
# 3. MATERIALS SETUP (Principled BSDF, saturated cartoon palette)
# -----------------------------------------------------------------------------
def create_mat(name, color, roughness=0.45, metallic=0.0):
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

mat_red    = create_mat("Mat_Red",    (0.85, 0.05, 0.05, 1.0), roughness=0.40)
mat_white  = create_mat("Mat_White",  (0.92, 0.92, 0.94, 1.0), roughness=0.40)
mat_glass  = create_mat("Mat_Glass",  (0.04, 0.08, 0.15, 1.0), roughness=0.10, metallic=0.05)
mat_dark   = create_mat("Mat_Dark",   (0.12, 0.12, 0.14, 1.0), roughness=0.45)
mat_metal  = create_mat("Mat_Metal",  (0.55, 0.55, 0.58, 1.0), roughness=0.30, metallic=0.85)
mat_yellow = create_mat("Mat_Yellow", (0.95, 0.72, 0.05, 1.0), roughness=0.40)

# -----------------------------------------------------------------------------
# 4. HELPER FUNCTIONS FOR MESH CREATION
# -----------------------------------------------------------------------------
fuselage_parts = []

def apply_all_modifiers(obj):
    bpy.context.view_layer.objects.active = obj
    for mod in list(obj.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception:
            pass

def set_smooth(obj):
    for poly in obj.data.polygons:
        poly.use_smooth = True

# -----------------------------------------------------------------------------
# 5. FUSELAGE LOFT (Body shell with red top and white belly)
# -----------------------------------------------------------------------------
# Faces -Y, Z is up, X is lateral. 12 rings along Y, 16 verts each.
rings_def = [
    # (y, z_c, rx, rz_top, rz_bot)
    (-3.45, 1.35, 0.14, 0.15, 0.12),
    (-3.10, 1.42, 0.52, 0.44, 0.38),
    (-2.40, 1.58, 0.78, 0.72, 0.58),
    (-1.50, 1.68, 0.88, 0.80, 0.65),
    (-0.60, 1.70, 0.88, 0.80, 0.65),
    ( 0.30, 1.72, 0.78, 0.75, 0.62),
    ( 1.10, 1.80, 0.52, 0.55, 0.48),
    ( 1.90, 1.90, 0.32, 0.34, 0.30),
    ( 2.90, 2.00, 0.22, 0.24, 0.20),
    ( 3.90, 2.10, 0.16, 0.18, 0.16),
    ( 4.80, 2.16, 0.12, 0.14, 0.12),
    ( 5.25, 2.20, 0.06, 0.07, 0.06)
]

bm_hull = bmesh.new()
n_pts = 16
rings_verts = []

for y_c, z_c, rx, rz_top, rz_bot in rings_def:
    r_verts = []
    for j in range(n_pts):
        th = 2.0 * math.pi * j / n_pts
        sin_th = math.sin(th)
        cos_th = math.cos(th)
        vx = rx * sin_th
        vz = z_c + (rz_top * cos_th if cos_th >= 0.0 else rz_bot * cos_th)
        v = bm_hull.verts.new(Vector((vx, y_c, vz)))
        r_verts.append(v)
    rings_verts.append(r_verts)

bm_hull.verts.ensure_lookup_table()

# Faces between rings
for i in range(len(rings_def) - 1):
    z_ref = (rings_def[i][1] + rings_def[i+1][1]) * 0.5 - 0.05
    for j in range(n_pts):
        v0 = rings_verts[i][j]
        v1 = rings_verts[i][(j + 1) % n_pts]
        v2 = rings_verts[i + 1][(j + 1) % n_pts]
        v3 = rings_verts[i + 1][j]
        f = bm_hull.faces.new([v0, v1, v2, v3])
        # Lower belly is white (slot 1), upper hull is red (slot 0)
        f_center_z = (v0.co.z + v1.co.z + v2.co.z + v3.co.z) * 0.25
        f.material_index = 1 if f_center_z < z_ref else 0

# Front and rear caps
bm_hull.faces.new(list(reversed(rings_verts[0]))).material_index = 0
bm_hull.faces.new(rings_verts[-1]).material_index = 0

hull_mesh = bpy.data.meshes.new("HullMesh")
bm_hull.to_mesh(hull_mesh)
bm_hull.free()

obj_hull = bpy.data.objects.new("FuselageHull", hull_mesh)
bpy.context.collection.objects.link(obj_hull)
obj_hull.data.materials.append(mat_red)
obj_hull.data.materials.append(mat_white)
set_smooth(obj_hull)

sub_hull = obj_hull.modifiers.new("Subsurf", 'SUBSURF')
sub_hull.levels = 1
sub_hull.render_levels = 1
apply_all_modifiers(obj_hull)
fuselage_parts.append(obj_hull)

# -----------------------------------------------------------------------------
# 6. CANOPY & CABIN WINDOWS (Dark glossy tinted glass)
# -----------------------------------------------------------------------------
# Front panoramic windshield bubble
bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=14, radius=1.0, location=(0.0, -2.35, 1.72))
obj_canopy = bpy.context.active_object
obj_canopy.name = "CanopyGlass"
obj_canopy.scale = (0.79, 0.70, 0.50)
obj_canopy.rotation_euler = (math.radians(-12.0), 0.0, 0.0)
obj_canopy.data.materials.append(mat_glass)
set_smooth(obj_canopy)
apply_all_modifiers(obj_canopy)
fuselage_parts.append(obj_canopy)

# Side passenger cabin windows (Left & Right)
for side_x in [-0.82, 0.82]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.34, depth=0.14, vertices=16,
                                        location=(side_x, -0.95, 1.74),
                                        rotation=(0.0, math.pi * 0.5, 0.0))
    w_obj = bpy.context.active_object
    w_obj.name = f"Window_{side_x}"
    w_obj.scale = (0.75, 1.25, 1.0)
    w_obj.data.materials.append(mat_glass)
    set_smooth(w_obj)
    apply_all_modifiers(w_obj)
    fuselage_parts.append(w_obj)

# -----------------------------------------------------------------------------
# 7. ENGINE HOUSING & EXHAUST PORTS
# -----------------------------------------------------------------------------
# Top cowling / doghouse
bpy.ops.mesh.primitive_cylinder_add(radius=0.42, depth=1.95, vertices=16,
                                    location=(0.0, -0.55, 2.48),
                                    rotation=(math.pi * 0.5, 0.0, 0.0))
obj_cowling = bpy.context.active_object
obj_cowling.name = "EngineCowling"
obj_cowling.scale = (0.85, 0.62, 1.0)
obj_cowling.data.materials.append(mat_red)
set_smooth(obj_cowling)
apply_all_modifiers(obj_cowling)
fuselage_parts.append(obj_cowling)

# Twin turbine air intake scoops
for in_x in [-0.24, 0.24]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=0.22, vertices=12,
                                        location=(in_x, -1.52, 2.50),
                                        rotation=(math.pi * 0.5, 0.0, 0.0))
    in_obj = bpy.context.active_object
    in_obj.name = f"AirIntake_{in_x}"
    in_obj.data.materials.append(mat_dark)
    set_smooth(in_obj)
    apply_all_modifiers(in_obj)
    fuselage_parts.append(in_obj)

# Twin turbine angled exhausts
for ex_x, ex_sign in [(-0.30, -1.0), (0.30, 1.0)]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.085, depth=0.42, vertices=12,
                                        location=(ex_x, 0.15, 2.55),
                                        rotation=(math.radians(-25.0), ex_sign * math.radians(28.0), 0.0))
    ex_obj = bpy.context.active_object
    ex_obj.name = f"Exhaust_{ex_x}"
    ex_obj.data.materials.append(mat_metal)
    set_smooth(ex_obj)
    apply_all_modifiers(ex_obj)
    fuselage_parts.append(ex_obj)

# Rotor mast base collar
bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=0.60, vertices=16,
                                    location=(0.0, -0.80, 2.85))
mast_base = bpy.context.active_object
mast_base.name = "MastBase"
mast_base.data.materials.append(mat_dark)
set_smooth(mast_base)
apply_all_modifiers(mast_base)
fuselage_parts.append(mast_base)

# -----------------------------------------------------------------------------
# 8. TAIL EMPENNAGE (Vertical fin & horizontal stabilizer)
# -----------------------------------------------------------------------------
# Swept vertical tail fin (extruded profile)
bm_fin = bmesh.new()
fin_pts_2d = [
    (4.75, 2.15),
    (5.08, 3.15),
    (5.38, 3.10),
    (5.32, 2.15),
    (5.40, 1.35),
    (5.20, 1.35)
]
fin_half_w = 0.04
v_left = [bm_fin.verts.new(Vector((-fin_half_w, y, z))) for y, z in fin_pts_2d]
v_right = [bm_fin.verts.new(Vector((fin_half_w, y, z))) for y, z in fin_pts_2d]
bm_fin.verts.ensure_lookup_table()

bm_fin.faces.new(list(reversed(v_left)))
bm_fin.faces.new(v_right)
for k in range(len(fin_pts_2d)):
    k_next = (k + 1) % len(fin_pts_2d)
    bm_fin.faces.new([v_left[k], v_left[k_next], v_right[k_next], v_right[k]])

fin_mesh = bpy.data.meshes.new("FinMesh")
bm_fin.to_mesh(fin_mesh)
bm_fin.free()

obj_fin = bpy.data.objects.new("VerticalFin", fin_mesh)
bpy.context.collection.objects.link(obj_fin)
obj_fin.data.materials.append(mat_red)
set_smooth(obj_fin)
apply_all_modifiers(obj_fin)
fuselage_parts.append(obj_fin)

# Horizontal stabilizer passing through tail boom
bpy.ops.mesh.primitive_cube_add(location=(0.0, 4.10, 2.08), scale=(0.85, 0.18, 0.025))
obj_stab = bpy.context.active_object
obj_stab.name = "HorizontalStabilizer"
obj_stab.data.materials.append(mat_white)
set_smooth(obj_stab)
apply_all_modifiers(obj_stab)
fuselage_parts.append(obj_stab)

# Stabilizer vertical endplates
for ep_x in [-0.85, 0.85]:
    bpy.ops.mesh.primitive_cube_add(location=(ep_x, 4.10, 2.08), scale=(0.02, 0.20, 0.14))
    ep_obj = bpy.context.active_object
    ep_obj.name = f"Endplate_{ep_x}"
    ep_obj.data.materials.append(mat_white)
    set_smooth(ep_obj)
    apply_all_modifiers(ep_obj)
    fuselage_parts.append(ep_obj)

# Tail bumper skid
bpy.ops.mesh.primitive_cylinder_add(radius=0.025, depth=0.35, vertices=10,
                                    location=(0.0, 5.32, 1.35),
                                    rotation=(math.radians(40.0), 0.0, 0.0))
tail_bumper = bpy.context.active_object
tail_bumper.name = "TailBumper"
tail_bumper.data.materials.append(mat_dark)
set_smooth(tail_bumper)
apply_all_modifiers(tail_bumper)
fuselage_parts.append(tail_bumper)

# -----------------------------------------------------------------------------
# 9. LANDING SKIDS & STRUTS (Lowest point strictly Z=0)
# -----------------------------------------------------------------------------
# Skid tubes: Z_center = 0.045, radius = 0.045 -> lowest point = 0.000
def build_skid_tube(side_x):
    bm_skid = bmesh.new()
    path_pts = []
    # Front curved upturn
    for s in range(5):
        t = s / 4.0
        y_val = -2.40 - 0.75 * t
        z_val = 0.045 + 0.32 * (t ** 2)
        path_pts.append(Vector((side_x, y_val, z_val)))
    # Central straight section
    path_pts.append(Vector((side_x, -1.40, 0.045)))
    path_pts.append(Vector((side_x, -0.40, 0.045)))
    path_pts.append(Vector((side_x,  0.80, 0.045)))
    # Rear curved upturn
    for s in range(1, 4):
        t = s / 3.0
        y_val = 0.80 + 0.35 * t
        z_val = 0.045 + 0.14 * (t ** 2)
        path_pts.append(Vector((side_x, y_val, z_val)))

    tube_rad = 0.045
    n_seg = 12
    rings = []
    for pt_idx, pt in enumerate(path_pts):
        if pt_idx == 0:
            tangent = (path_pts[1] - pt).normalized()
        elif pt_idx == len(path_pts) - 1:
            tangent = (pt - path_pts[-2]).normalized()
        else:
            tangent = (path_pts[pt_idx + 1] - path_pts[pt_idx - 1]).normalized()
        norm_x = Vector((1.0, 0.0, 0.0))
        norm_y = tangent.cross(norm_x).normalized()
        norm_x = norm_y.cross(tangent).normalized()

        ring = []
        for j in range(n_seg):
            ang = 2.0 * math.pi * j / n_seg
            offset = (norm_x * math.cos(ang) + norm_y * math.sin(ang)) * tube_rad
            v = bm_skid.verts.new(pt + offset)
            ring.append(v)
        rings.append(ring)

    bm_skid.verts.ensure_lookup_table()
    for i in range(len(rings) - 1):
        for j in range(n_seg):
            bm_skid.faces.new([rings[i][j], rings[i][(j+1)%n_seg],
                              rings[i+1][(j+1)%n_seg], rings[i+1][j]])
    bm_skid.faces.new(list(reversed(rings[0])))
    bm_skid.faces.new(rings[-1])

    s_mesh = bpy.data.meshes.new(f"SkidMesh_{side_x}")
    bm_skid.to_mesh(s_mesh)
    bm_skid.free()
    s_obj = bpy.data.objects.new(f"SkidTube_{side_x}", s_mesh)
    bpy.context.collection.objects.link(s_obj)
    s_obj.data.materials.append(mat_dark)
    set_smooth(s_obj)
    return s_obj

fuselage_parts.append(build_skid_tube(-0.95))
fuselage_parts.append(build_skid_tube( 0.95))

# Arched tubular struts connecting skids into fuselage belly
def build_strut_arch(y_pos):
    bm_strut = bmesh.new()
    strut_pts = [
        Vector((-0.95, y_pos, 0.06)),
        Vector((-0.82, y_pos, 0.50)),
        Vector((-0.55, y_pos, 1.05)),
        Vector(( 0.00, y_pos, 1.15)),
        Vector(( 0.55, y_pos, 1.05)),
        Vector(( 0.82, y_pos, 0.50)),
        Vector(( 0.95, y_pos, 0.06))
    ]
    tube_rad = 0.038
    n_seg = 10
    rings = []
    for pt_idx, pt in enumerate(strut_pts):
        if pt_idx == 0:
            tangent = (strut_pts[1] - pt).normalized()
        elif pt_idx == len(strut_pts) - 1:
            tangent = (pt - strut_pts[-2]).normalized()
        else:
            tangent = (strut_pts[pt_idx + 1] - strut_pts[pt_idx - 1]).normalized()
        norm_y = Vector((0.0, 1.0, 0.0))
        norm_z = tangent.cross(norm_y).normalized()
        norm_y = norm_z.cross(tangent).normalized()

        ring = []
        for j in range(n_seg):
            ang = 2.0 * math.pi * j / n_seg
            offset = (norm_y * math.cos(ang) + norm_z * math.sin(ang)) * tube_rad
            v = bm_strut.verts.new(pt + offset)
            ring.append(v)
        rings.append(ring)

    bm_strut.verts.ensure_lookup_table()
    for i in range(len(rings) - 1):
        for j in range(n_seg):
            bm_strut.faces.new([rings[i][j], rings[i][(j+1)%n_seg],
                               rings[i+1][(j+1)%n_seg], rings[i+1][j]])
    bm_strut.faces.new(list(reversed(rings[0])))
    bm_strut.faces.new(rings[-1])

    st_mesh = bpy.data.meshes.new(f"StrutMesh_{y_pos}")
    bm_strut.to_mesh(st_mesh)
    bm_strut.free()
    st_obj = bpy.data.objects.new(f"SkidStrut_{y_pos}", st_mesh)
    bpy.context.collection.objects.link(st_obj)
    st_obj.data.materials.append(mat_white)
    set_smooth(st_obj)
    return st_obj

fuselage_parts.append(build_strut_arch(-2.15))
fuselage_parts.append(build_strut_arch(-0.35))

# Boarding footsteps on skids
for step_x in [-0.95, 0.95]:
    bpy.ops.mesh.primitive_cube_add(location=(step_x, -1.20, 0.09), scale=(0.06, 0.18, 0.015))
    step_obj = bpy.context.active_object
    step_obj.name = f"FootStep_{step_x}"
    step_obj.data.materials.append(mat_dark)
    set_smooth(step_obj)
    apply_all_modifiers(step_obj)
    fuselage_parts.append(step_obj)

# -----------------------------------------------------------------------------
# 10. NEWS CAMERA GIMBAL POD (Mounted under nose)
# -----------------------------------------------------------------------------
# Bracket mount
bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=0.35, vertices=12,
                                    location=(0.0, -2.85, 0.98))
bracket = bpy.context.active_object
bracket.name = "CameraBracket"
bracket.data.materials.append(mat_dark)
set_smooth(bracket)
apply_all_modifiers(bracket)
fuselage_parts.append(bracket)

# Spherical camera body
bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12, radius=0.20,
                                     location=(0.0, -2.85, 0.72))
cam_sphere = bpy.context.active_object
cam_sphere.name = "CameraSphere"
cam_sphere.data.materials.append(mat_white)
set_smooth(cam_sphere)
apply_all_modifiers(cam_sphere)
fuselage_parts.append(cam_sphere)

# Gimbal yoke ring
bpy.ops.mesh.primitive_cylinder_add(radius=0.21, depth=0.06, vertices=16,
                                    location=(0.0, -2.85, 0.72))
cam_ring = bpy.context.active_object
cam_ring.name = "CameraRing"
cam_ring.data.materials.append(mat_dark)
set_smooth(cam_ring)
apply_all_modifiers(cam_ring)
fuselage_parts.append(cam_ring)

# Camera optical lens
bpy.ops.mesh.primitive_cylinder_add(radius=0.075, depth=0.05, vertices=12,
                                    location=(-0.05, -3.02, 0.70),
                                    rotation=(math.radians(80.0), 0.0, math.radians(15.0)))
cam_lens = bpy.context.active_object
cam_lens.name = "CameraLens"
cam_lens.data.materials.append(mat_glass)
set_smooth(cam_lens)
apply_all_modifiers(cam_lens)
fuselage_parts.append(cam_lens)

# Roof blade antenna
bpy.ops.mesh.primitive_cube_add(location=(0.0, 1.20, 2.25), scale=(0.015, 0.12, 0.15))
ant_obj = bpy.context.active_object
ant_obj.name = "RoofAntenna"
ant_obj.data.materials.append(mat_dark)
set_smooth(ant_obj)
apply_all_modifiers(ant_obj)
fuselage_parts.append(ant_obj)

# -----------------------------------------------------------------------------
# 11. JOIN FUSELAGE INTO ONE OBJECT ("Body")
# -----------------------------------------------------------------------------
bpy.ops.object.select_all(action='DESELECT')
for p in fuselage_parts:
    p.select_set(True)

bpy.context.view_layer.objects.active = fuselage_parts[0]
bpy.ops.object.join()

body = bpy.context.view_layer.objects.active
body.name = "Body"
body.data.name = "BodyMesh"

# Ensure the lowest point is exactly Z=0.0 and origin is at bottom center of skids
min_z_val = min(v.co.z for v in body.data.vertices)
for v in body.data.vertices:
    v.co.z -= min_z_val
body.location = (0.0, 0.0, 0.0)
set_smooth(body)

# -----------------------------------------------------------------------------
# 12. MAIN ROTOR (SEPARATE object "MainRotor", Hub + 4 blades, 10 m diameter)
# -----------------------------------------------------------------------------
# Origin at hub centre: (0.0, -0.80, 3.40). Rotation axis = local Z through origin.
bm_main = bmesh.new()

# Central Hub Cylinder
hub_r = 0.30
hub_h = 0.16
n_hub = 16
hub_bot = []
hub_top = []
for j in range(n_hub):
    ang = 2.0 * math.pi * j / n_hub
    vx = hub_r * math.cos(ang)
    vy = hub_r * math.sin(ang)
    hub_bot.append(bm_main.verts.new(Vector((vx, vy, -hub_h * 0.5))))
    hub_top.append(bm_main.verts.new(Vector((vx, vy,  hub_h * 0.5))))

bm_main.verts.ensure_lookup_table()
for j in range(n_hub):
    f = bm_main.faces.new([hub_bot[j], hub_bot[(j+1)%n_hub], hub_top[(j+1)%n_hub], hub_top[j]])
    f.material_index = 0
bm_main.faces.new(list(reversed(hub_bot))).material_index = 0
bm_main.faces.new(hub_top).material_index = 0

# Hub Top Dome Cap
cap_pts = []
for j in range(n_hub):
    ang = 2.0 * math.pi * j / n_hub
    cap_pts.append(bm_main.verts.new(Vector((hub_r * 0.75 * math.cos(ang),
                                             hub_r * 0.75 * math.sin(ang),
                                             hub_h * 0.5 + 0.08))))
cap_apex = bm_main.verts.new(Vector((0.0, 0.0, hub_h * 0.5 + 0.18)))
bm_main.verts.ensure_lookup_table()
for j in range(n_hub):
    f1 = bm_main.faces.new([hub_top[j], hub_top[(j+1)%n_hub], cap_pts[(j+1)%n_hub], cap_pts[j]])
    f1.material_index = 1
    f2 = bm_main.faces.new([cap_pts[j], cap_pts[(j+1)%n_hub], cap_apex])
    f2.material_index = 1

# 4 Blades (10 m diameter -> R = 5.0 m each)
# Spaced every 90 degrees. Dark inner blade + saturated yellow safety tip.
blade_chord = 0.22
blade_thick = 0.035
r_root = 0.30
r_grip = 0.65
r_trans = 4.45
r_tip = 5.00

def create_box_mesh(bm, p_min, p_max, mat_idx, rot_matrix):
    c = [
        Vector((p_min.x, p_min.y, p_min.z)),
        Vector((p_max.x, p_min.y, p_min.z)),
        Vector((p_max.x, p_max.y, p_min.z)),
        Vector((p_min.x, p_max.y, p_min.z)),
        Vector((p_min.x, p_min.y, p_max.z)),
        Vector((p_max.x, p_min.y, p_max.z)),
        Vector((p_max.x, p_max.y, p_max.z)),
        Vector((p_min.x, p_max.y, p_max.z))
    ]
    v = [bm.verts.new(rot_matrix @ pt) for pt in c]
    bm.verts.ensure_lookup_table()
    faces_idx = [
        (0, 1, 2, 3), (4, 7, 6, 5),
        (0, 4, 5, 1), (2, 6, 7, 3),
        (0, 3, 7, 4), (1, 5, 6, 2)
    ]
    for fi in faces_idx:
        f = bm.faces.new([v[i] for i in fi])
        f.material_index = mat_idx

for b_idx in range(4):
    b_ang = b_idx * (math.pi * 0.5)
    rot_m = Matrix.Rotation(b_ang, 3, 'Z')
    # Blade cuff / grip
    create_box_mesh(bm_main,
                    Vector((-0.05, r_root, -0.04)),
                    Vector(( 0.05, r_grip,  0.04)),
                    2, rot_m)
    # Main blade body (Dark)
    create_box_mesh(bm_main,
                    Vector((-blade_chord * 0.5, r_grip, -blade_thick * 0.5)),
                    Vector(( blade_chord * 0.5, r_trans, blade_thick * 0.5)),
                    2, rot_m)
    # Blade outer warning tip (Yellow)
    create_box_mesh(bm_main,
                    Vector((-blade_chord * 0.5, r_trans, -blade_thick * 0.5)),
                    Vector(( blade_chord * 0.5, r_tip,   blade_thick * 0.5)),
                    3, rot_m)

main_rotor_mesh = bpy.data.meshes.new("MainRotorMesh")
bm_main.to_mesh(main_rotor_mesh)
bm_main.free()

main_rotor = bpy.data.objects.new("MainRotor", main_rotor_mesh)
bpy.context.collection.objects.link(main_rotor)
main_rotor.data.materials.append(mat_metal)   # 0
main_rotor.data.materials.append(mat_red)     # 1
main_rotor.data.materials.append(mat_dark)    # 2
main_rotor.data.materials.append(mat_yellow)  # 3
main_rotor.location = (0.0, -0.80, 3.40)
set_smooth(main_rotor)

# -----------------------------------------------------------------------------
# 13. TAIL ROTOR (SEPARATE object "TailRotor", Hub + 2 blades, 1.4 m diameter)
# -----------------------------------------------------------------------------
# Origin at hub centre: (0.16, 5.25, 2.45). Rotation axis = local X through origin.
bm_tail = bmesh.new()

# Hub cylinder along local X axis
t_hub_r = 0.08
t_hub_w = 0.12
n_thub = 14
thub_in = []
thub_out = []
for j in range(n_thub):
    ang = 2.0 * math.pi * j / n_thub
    vy = t_hub_r * math.cos(ang)
    vz = t_hub_r * math.sin(ang)
    thub_in.append(bm_tail.verts.new(Vector((-t_hub_w * 0.5, vy, vz))))
    thub_out.append(bm_tail.verts.new(Vector(( t_hub_w * 0.5, vy, vz))))

bm_tail.verts.ensure_lookup_table()
for j in range(n_thub):
    f = bm_tail.faces.new([thub_in[j], thub_in[(j+1)%n_thub], thub_out[(j+1)%n_thub], thub_out[j]])
    f.material_index = 0
bm_tail.faces.new(list(reversed(thub_in))).material_index = 0
bm_tail.faces.new(thub_out).material_index = 0

# 2 Blades (1.4 m diameter -> R = 0.70 m each along local Z)
tb_chord = 0.09
tb_thick = 0.018
tb_root = 0.07
tb_trans = 0.55
tb_tip = 0.70

# Blade +Z
create_box_mesh(bm_tail,
                Vector((-tb_thick * 0.5, -tb_chord * 0.5, tb_root)),
                Vector(( tb_thick * 0.5,  tb_chord * 0.5, tb_trans)),
                1, Matrix.Identity(3))
create_box_mesh(bm_tail,
                Vector((-tb_thick * 0.5, -tb_chord * 0.5, tb_trans)),
                Vector(( tb_thick * 0.5,  tb_chord * 0.5, tb_tip)),
                2, Matrix.Identity(3))

# Blade -Z
create_box_mesh(bm_tail,
                Vector((-tb_thick * 0.5, -tb_chord * 0.5, -tb_trans)),
                Vector(( tb_thick * 0.5,  tb_chord * 0.5, -tb_root)),
                1, Matrix.Identity(3))
create_box_mesh(bm_tail,
                Vector((-tb_thick * 0.5, -tb_chord * 0.5, -tb_tip)),
                Vector(( tb_thick * 0.5,  tb_chord * 0.5, -tb_trans)),
                2, Matrix.Identity(3))

tail_rotor_mesh = bpy.data.meshes.new("TailRotorMesh")
bm_tail.to_mesh(tail_rotor_mesh)
bm_tail.free()

tail_rotor = bpy.data.objects.new("TailRotor", tail_rotor_mesh)
bpy.context.collection.objects.link(tail_rotor)
tail_rotor.data.materials.append(mat_metal)   # 0
tail_rotor.data.materials.append(mat_dark)    # 1
tail_rotor.data.materials.append(mat_yellow)  # 2
tail_rotor.location = (0.16, 5.25, 2.45)
set_smooth(tail_rotor)

# -----------------------------------------------------------------------------
# 14. PARENTING (MainRotor and TailRotor to Body, keep transforms)
# -----------------------------------------------------------------------------
bpy.context.view_layer.update()

main_rotor.parent = body
main_rotor.matrix_parent_inverse = body.matrix_world.inverted()

tail_rotor.parent = body
tail_rotor.matrix_parent_inverse = body.matrix_world.inverted()

bpy.context.view_layer.update()

# -----------------------------------------------------------------------------
# 15. TRIANGLE COUNT CHECK
# -----------------------------------------------------------------------------
total_tris = 0
for obj in [body, main_rotor, tail_rotor]:
    me = obj.data
    me.calc_loop_triangles()
    total_tris += len(me.loop_triangles)

print("TRIS", total_tris)

# -----------------------------------------------------------------------------
# 16. EXPORT FBX
# -----------------------------------------------------------------------------
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
main_rotor.select_set(True)
tail_rotor.select_set(True)
bpy.context.view_layer.objects.active = body

bpy.ops.export_scene.fbx(
    filepath=output_path,
    use_selection=True,
    bake_space_transform=True,
    axis_forward='-Z',
    axis_up='Y',
    mesh_smooth_type='FACE'
)

# -----------------------------------------------------------------------------
# 17. LIGHTING & CAMERA SETUP FOR PREVIEW RENDER
# -----------------------------------------------------------------------------
scene = bpy.context.scene

# Pick EEVEE engine dynamically from enum items
engine_keys = list(scene.render.bl_rna.properties['engine'].enum_items.keys())
if 'BLENDER_EEVEE_NEXT' in engine_keys:
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
elif 'BLENDER_EEVEE' in engine_keys:
    scene.render.engine = 'BLENDER_EEVEE'
else:
    eevee_cands = [k for k in engine_keys if 'EEVEE' in k]
    scene.render.engine = eevee_cands[0] if eevee_cands else engine_keys[0]

# Render settings (900x900 PNG)
png_path = os.path.splitext(output_path)[0] + ".png"
scene.render.filepath = png_path
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'

# World setup: grey strength 0.45
world = bpy.data.worlds.new("World_Preview")
scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.50, 0.50, 0.53, 1.0)
    bg_node.inputs["Strength"].default_value = 0.45

# Key Sun Light (strength 3.0)
sun_data = bpy.data.lights.new(name="Sun_Key", type='SUN')
sun_data.energy = 3.0
sun_data.color = (1.0, 0.98, 0.95)
sun_obj = bpy.data.objects.new("Sun_Key", sun_data)
scene.collection.objects.link(sun_obj)
sun_obj.location = (-8.0, -12.0, 10.0)
sun_dir = Vector((0.0, -0.6, 2.0)) - sun_obj.location
sun_obj.rotation_euler = sun_dir.to_track_quat('-Z', 'Y').to_euler()

# Soft Fill Light
fill_data = bpy.data.lights.new(name="Light_Fill", type='AREA')
fill_data.energy = 380.0
fill_data.size = 7.0
fill_data.color = (0.86, 0.92, 1.0)
fill_obj = bpy.data.objects.new("Light_Fill", fill_data)
scene.collection.objects.link(fill_obj)
fill_obj.location = (9.0, 6.0, 5.0)
fill_dir = Vector((0.0, -0.6, 2.0)) - fill_obj.location
fill_obj.rotation_euler = fill_dir.to_track_quat('-Z', 'Y').to_euler()

# Camera framing: 3/4 front view (front-left, slightly above) framing whole model with ~10% margin
cam_data = bpy.data.cameras.new("Camera_Preview")
cam_data.lens = 42.0
cam_obj = bpy.data.objects.new("Camera_Preview", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# Calculate bounding sphere of all objects
min_co = Vector(( 1e9,  1e9,  1e9))
max_co = Vector((-1e9, -1e9, -1e9))
for obj in [body, main_rotor, tail_rotor]:
    for corner in obj.bound_box:
        world_pt = obj.matrix_world @ Vector(corner)
        min_co.x = min(min_co.x, world_pt.x)
        min_co.y = min(min_co.y, world_pt.y)
        min_co.z = min(min_co.z, world_pt.z)
        max_co.x = max(max_co.x, world_pt.x)
        max_co.y = max(max_co.y, world_pt.y)
        max_co.z = max(max_co.z, world_pt.z)

bbox_center = (min_co + max_co) * 0.5
bbox_extents = (max_co - min_co) * 0.5
radius = bbox_extents.length

# Direction from center to camera: front is -Y, left is -X, above is +Z
view_dir = Vector((-0.72, -1.0, 0.44)).normalized()
fov = 2.0 * math.atan((cam_data.sensor_width * 0.5) / cam_data.lens)
dist = (radius / math.sin(fov * 0.5)) * 1.10

cam_obj.location = bbox_center + view_dir * dist
cam_dir = bbox_center - cam_obj.location
cam_obj.rotation_euler = cam_dir.to_track_quat('-Z', 'Y').to_euler()

# Render preview image
bpy.ops.render.render(write_still=True)

