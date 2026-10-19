"""Render a preview of a GLB (and report its size / triangle count / animations). Usage: blender -b -P render_glb.py -- in.glb out.png"""
import bpy, sys, math
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=a[0])
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
size = hi - lo; centre = (hi + lo) / 2
tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
print("SIZE", tuple(round(v, 3) for v in size), "TRIS", tris, "ANIMS", [ac.name for ac in bpy.data.actions], "ARMATURES", len([o for o in bpy.data.objects if o.type == "ARMATURE"]))
scene = bpy.context.scene
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); scene.collection.objects.link(cam)
r = max(size) * 1.6
cam.location = centre + Vector((r * 0.8, -r, r * 0.45))
cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam
cam.data.clip_start = max(0.001, r * 0.01); cam.data.clip_end = r * 20
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sun.data.energy = 3.5
sun.rotation_euler = (math.radians(50), 0, math.radians(30)); scene.collection.objects.link(sun)
w = bpy.data.worlds.new("W"); w.use_nodes = True; w.node_tree.nodes["Background"].inputs[1].default_value = 0.7; scene.world = w
engines = scene.render.bl_rna.properties["engine"].enum_items.keys()
scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else engines[0]
scene.render.resolution_x = scene.render.resolution_y = 600
scene.render.filepath = a[1]
bpy.ops.render.render(write_still=True)
