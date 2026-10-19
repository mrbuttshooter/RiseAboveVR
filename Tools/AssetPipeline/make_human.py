"""Builds one realistic CC0 MakeHuman (MPFB) pedestrian and exports it as FBX with textures.
Usage: blender -b --python make_human.py -- <out.fbx> '<json config>'"""
import bpy, json, math, os, sys

from bl_ext.blender_org.mpfb.services import HumanService, ObjectService

args = sys.argv[sys.argv.index("--") + 1:]
OUT = args[0]
CFG = json.loads(args[1])
DATA = os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "extensions", ".user", "blender_org", "mpfb", "data")


def asset(kind, name, ext):
    """Find <DATA>/<kind>/<name>/**/<file>.<ext> (first match)."""
    base = os.path.join(DATA, kind, name)
    for root, _, files in os.walk(base):
        for f in files:
            if f.endswith(ext):
                return os.path.join(root, f)
    raise FileNotFoundError(kind + "/" + name + " *" + ext)


bpy.ops.wm.read_factory_settings(use_empty=True)
male = CFG.get("gender", 1.0) > 0.5
macro = {"gender": CFG.get("gender", 1.0), "age": CFG.get("age", 0.5), "muscle": CFG.get("muscle", 0.5),
         "weight": CFG.get("weight", 0.5), "height": CFG.get("height", 0.5), "proportions": 0.5,
         "cupsize": 0.5, "firmness": 0.5, "race": CFG.get("race", {"african": 0.33, "asian": 0.33, "caucasian": 0.34})}
basemesh = HumanService.create_human(scale=0.1, macro_detail_dict=macro)
# Skeleton FIRST, so every part added afterwards is bound to it and follows the pose.
HumanService.add_builtin_rig(basemesh, "default")
rig = ObjectService.find_object_of_type_amongst_nearest_relatives(basemesh, "Skeleton")

# Low-poly body for the Quest, then skin and the other parts.
HumanService.add_mhclo_asset(asset("proxymeshes", "male1591" if male else "female1605", ".proxy"), basemesh,
                             asset_type="Proxymeshes", material_type="NONE")
HumanService.set_character_skin(asset("skins", CFG["skin"], ".mhmat"), basemesh, skin_type="GAMEENGINE")
HumanService.add_mhclo_asset(asset("eyes", "low-poly", ".mhclo"), basemesh, asset_type="Eyes", subdiv_levels=0)
HumanService.add_mhclo_asset(asset("eyebrows", CFG.get("eyebrows", "eyebrow001"), ".mhclo"), basemesh, asset_type="Eyebrows", subdiv_levels=0)
HumanService.add_mhclo_asset(asset("eyelashes", "eyelashes01", ".mhclo"), basemesh, asset_type="Eyelashes", subdiv_levels=0)
HumanService.add_mhclo_asset(asset("hair", CFG["hair"], ".mhclo"), basemesh, asset_type="Hair", subdiv_levels=0)
def mhclo_uuid(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("uuid"):
                return line.split()[1].strip()
    return None


for c in CFG.get("clothes", []):
    path = asset("clothes", c, ".mhclo")
    alt = CFG.get("alt", {}).get(c)  # e.g. "male_casualsuit01/toigo_..._khaki/toigo_..._khaki.mhmat"
    alts = {mhclo_uuid(path): alt} if alt else None
    HumanService.add_mhclo_asset(path, basemesh, asset_type="Clothes", subdiv_levels=0, alternative_materials=alts)

# Relax the arms down from the A-pose and bake the pose into the meshes.
if rig is not None:
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    for side, sign in (("L", 1.0), ("R", -1.0)):
        b = rig.pose.bones.get("upperarm01." + side)
        if b is not None:
            b.rotation_mode = "XYZ"
            # Z swings the arm down from the A-pose; X swings it back/forward (per-side sign keeps it symmetric).
            b.rotation_euler = (math.radians(CFG.get("arm_x", -18.0)), 0.0, math.radians(CFG.get("arm_down", -42.0)) * sign)
    bpy.ops.object.mode_set(mode="OBJECT")

meshes = [o for o in bpy.data.objects if o.type == "MESH" and o is not basemesh]
for o in meshes:
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except RuntimeError:
            o.modifiers.remove(m)
for o in [basemesh] + ([rig] if rig is not None else []):
    bpy.data.objects.remove(o, do_unlink=True)

tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
print("TRIS", tris)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, apply_unit_scale=True, axis_forward="-Z", axis_up="Y",
                         mesh_smooth_type="FACE", path_mode="COPY", embed_textures=False)

# Preview render.
scene = bpy.context.scene
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
scene.collection.objects.link(cam)
cam.location = (-1.8, -3.4, 1.4)
cam.rotation_euler = (math.radians(83), 0, math.radians(-28))
scene.camera = cam
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.data.energy = 3.5
sun.rotation_euler = (math.radians(50), 0, math.radians(-40))
scene.collection.objects.link(sun)
world = bpy.data.worlds.new("W")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[1].default_value = 0.6
scene.world = world
engines = scene.render.bl_rna.properties["engine"].enum_items.keys()
scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else engines[0]
scene.render.resolution_x = scene.render.resolution_y = 900
scene.render.filepath = os.path.splitext(OUT)[0] + ".png"
bpy.ops.render.render(write_still=True)
