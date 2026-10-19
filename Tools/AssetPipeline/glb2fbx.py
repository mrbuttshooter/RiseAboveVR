"""Convert a GLB into an FBX + texture PNGs for the Unity project.
Usage: blender -b -P glb2fbx.py -- in.glb out_dir Name [yaw_degrees] [decimate_ratio] [height_m]
Writes out_dir/Name.fbx and out_dir/Textures/*.png (textures renamed Name_<slot>.png)."""
import bpy, sys, os, math
from mathutils import Vector, Matrix
a = sys.argv[sys.argv.index("--") + 1:]
src, out_dir, name = a[0], a[1], a[2]
yaw = float(a[3]) if len(a) > 3 else 0.0
ratio = float(a[4]) if len(a) > 4 else 1.0
height = float(a[5]) if len(a) > 5 else 0.0
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
tex_dir = os.path.join(out_dir, "Textures"); os.makedirs(tex_dir, exist_ok=True)
# Name every image by its role so the Unity importer can pair them: <Name>_<m>_albedo / <Name>_<m>_normal (+ extras).
done = {}
for mi, mat in enumerate(list(bpy.data.materials)):
    if not mat.use_nodes: continue
    for node in mat.node_tree.nodes:
        if node.type != "TEX_IMAGE" or node.image is None or node.image.name in done: continue
        role = "extra"
        for link in mat.node_tree.links:
            if link.from_node == node:
                to = link.to_socket.name.lower(); tn = link.to_node.type
                if to == "base color": role = "albedo"
                elif tn == "NORMAL_MAP" or to == "normal": role = "normal"
        done[node.image.name] = (mi, role)
# FBX can only carry textures wired straight into the Principled BSDF: rewire albedo images directly.
for mat in bpy.data.materials:
    if not mat.use_nodes: continue
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        # glTF "unlit" materials have no Principled BSDF: build one and make it the surface.
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) or nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        for l in list(out.inputs["Surface"].links): nt.links.remove(l)
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    alb = next((n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image is not None and done.get(n.image.name, (0, ""))[1] == "albedo"), None)
    if alb is None:
        # fall back to the first image feeding anything that ends at Base Color
        alb = next((n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image is not None), None)
    if alb is not None:
        for l in list(bsdf.inputs["Base Color"].links): nt.links.remove(l)
        nt.links.new(alb.outputs["Color"], bsdf.inputs["Base Color"])
        done[alb.image.name] = (done.get(alb.image.name, (list(bpy.data.materials).index(mat), ""))[0], "albedo")
for img in list(bpy.data.images):
    if img.source != "FILE" and not img.packed_file: continue
    mi, role = done.get(img.name, (99, "extra"))
    fn = f"{name}_{mi}_{role}.png" if role != "extra" else f"{name}_{mi}_extra_{abs(hash(img.name)) % 10000}.png"
    img.filepath_raw = os.path.join(tex_dir, fn)
    img.file_format = "PNG"
    img.save()
    img.name = fn
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
if ratio < 0.999:
    for o in meshes:
        m = o.modifiers.new("Dec", "DECIMATE"); m.ratio = ratio
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier="Dec")
# Rotate everything about Z (so the animal's front points to -Y) and bake transforms.
root = bpy.data.objects.new(name, None); bpy.context.scene.collection.objects.link(root)
for o in bpy.data.objects:
    if o.parent is None and o is not root: o.parent = root
root.rotation_euler = (0, 0, math.radians(yaw))
if height > 0:
    bpy.context.view_layer.update()
    zs = [(o.matrix_world @ Vector(c)).z for o in meshes for c in o.bound_box]
    k = height / max(1e-6, max(zs) - min(zs))
    root.scale = (k, k, k)
bpy.ops.object.select_all(action="SELECT")
bpy.context.view_layer.objects.active = root
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
print("TRIS", tris)
bpy.ops.export_scene.fbx(filepath=os.path.join(out_dir, name + ".fbx"), use_selection=False, apply_unit_scale=True,
                         axis_forward="-Z", axis_up="Y", path_mode="STRIP", embed_textures=False, bake_anim=True)
