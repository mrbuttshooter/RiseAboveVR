import math
import os
import sys
import bmesh
import bpy
from mathutils import Euler, Matrix, Vector


def clear_scene():
  bpy.ops.object.select_all(action='SELECT')
  bpy.ops.object.delete(use_global=False)
  for block_col in (
      bpy.data.meshes,
      bpy.data.materials,
      bpy.data.lights,
      bpy.data.cameras,
      bpy.data.worlds,
  ):
    for block in list(block_col):
      block_col.remove(block)


def make_material(name, rgb, roughness=0.45):
  mat = bpy.data.materials.new(name)
  mat.use_nodes = True
  bsdf = mat.node_tree.nodes.get('Principled BSDF')
  if bsdf is None:
    bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
  r = max(0.0, min(1.0, float(rgb[0])))
  g = max(0.0, min(1.0, float(rgb[1])))
  b = max(0.0, min(1.0, float(rgb[2])))
  bsdf.inputs['Base Color'].default_value = (r, g, b, 1.0)
  bsdf.inputs['Roughness'].default_value = max(0.0, min(1.0, float(roughness)))
  return mat


def build_loft_object(
    name, rings, segments, mat, subsurf_level=1, flatten_z_below=None
):
  bm = bmesh.new()
  ring_vert_lists = []

  for r_info in rings:
    cx, cy, cz = r_info[0], r_info[1], r_info[2]
    rx, ry_front, ry_back = r_info[3], r_info[4], r_info[5]
    pitch_deg = r_info[6] if len(r_info) > 6 else 0.0
    roll_deg = r_info[7] if len(r_info) > 7 else 0.0
    yaw_deg = r_info[8] if len(r_info) > 8 else 0.0
    boxiness = r_info[9] if len(r_info) > 9 else 0.0

    rot_mat = Euler(
        (
            math.radians(pitch_deg),
            math.radians(roll_deg),
            math.radians(yaw_deg),
        ),
        'XYZ',
    ).to_matrix()
    center = Vector((cx, cy, cz))

    verts = []
    for i in range(segments):
      theta = (2.0 * math.pi * i) / max(1, segments)
      ca = math.cos(theta)
      sa = math.sin(theta)

      shape_mod = 1.0 + boxiness * (0.12 * (1.0 - math.cos(4.0 * theta)))
      lx = rx * ca * shape_mod
      ry = ry_front if sa < 0.0 else ry_back
      ly = ry * sa * shape_mod
      lz = 0.0

      pt = center + (rot_mat @ Vector((lx, ly, lz)))
      if flatten_z_below is not None and pt.z < flatten_z_below:
        pt.z = flatten_z_below + (pt.z - flatten_z_below) * 0.15
      verts.append(bm.verts.new(pt))
    ring_vert_lists.append(verts)

  bm.verts.ensure_lookup_table()

  for r_idx in range(len(ring_vert_lists) - 1):
    r0 = ring_vert_lists[r_idx]
    r1 = ring_vert_lists[r_idx + 1]
    for i in range(segments):
      ni = (i + 1) % segments
      f = bm.faces.new((r0[i], r0[ni], r1[ni], r1[i]))
      f.smooth = True

  cap_bottom = bm.faces.new(list(reversed(ring_vert_lists[0])))
  cap_bottom.smooth = True
  cap_top = bm.faces.new(ring_vert_lists[-1])
  cap_top.smooth = True

  bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

  mesh = bpy.data.meshes.new(name)
  bm.to_mesh(mesh)
  bm.free()

  for poly in mesh.polygons:
    poly.use_smooth = True

  obj = bpy.data.objects.new(name, mesh)
  bpy.context.scene.collection.objects.link(obj)
  obj.data.materials.append(mat)

  if subsurf_level > 0:
    mod = obj.modifiers.new('Subsurf', 'SUBSURF')
    mod.levels = subsurf_level
    mod.render_levels = subsurf_level
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)

  for poly in obj.data.polygons:
    poly.use_smooth = True

  return obj


def create_pedestrian():
  mat_jacket = make_material('Mat_Jacket', (0.2, 0.45, 0.75), 0.45)
  mat_jeans = make_material('Mat_Jeans', (0.12, 0.17, 0.28), 0.48)
  mat_sneakers = make_material('Mat_Sneakers', (0.93, 0.94, 0.96), 0.42)
  mat_skin = make_material('Mat_Skin', (0.89, 0.64, 0.49), 0.45)
  mat_hair = make_material('Mat_Hair', (0.24, 0.13, 0.07), 0.46)
  mat_eyes = make_material('Mat_Eyes', (0.06, 0.06, 0.08), 0.35)
  mat_shirt = make_material('Mat_Shirt', (0.91, 0.87, 0.79), 0.45)

  parts = []

  # 1. Jacket Torso (R=6, S=8)
  torso_rings = [
      (0.0, 0.000, 0.855, 0.226, 0.148, 0.158, 2.0, 0.0, -2.0, 0.25),
      (0.0, 0.002, 0.985, 0.202, 0.136, 0.142, 1.0, 0.0, -2.5, 0.20),
      (0.0, -0.004, 1.145, 0.228, 0.156, 0.154, 0.0, 0.0, -3.0, 0.20),
      (0.0, -0.005, 1.305, 0.250, 0.152, 0.152, -1.0, 0.0, -3.5, 0.25),
      (0.0, 0.000, 1.395, 0.202, 0.122, 0.128, -1.0, 0.0, -3.0, 0.15),
      (0.0, 0.005, 1.445, 0.112, 0.092, 0.098, 0.0, 0.0, -2.0, 0.0),
  ]
  parts.append(build_loft_object('Torso', torso_rings, 8, mat_jacket, 1))

  # 2. Inner Shirt V-Neck Insert (R=3, S=6)
  shirt_rings = [
      (0.0, -0.065, 1.235, 0.092, 0.082, 0.065, -8.0, 0.0, -3.0, 0.0),
      (0.0, -0.045, 1.355, 0.105, 0.096, 0.075, -5.0, 0.0, -3.0, 0.0),
      (0.0, -0.015, 1.450, 0.082, 0.078, 0.072, 0.0, 0.0, -2.0, 0.0),
  ]
  parts.append(build_loft_object('InnerShirt', shirt_rings, 6, mat_shirt, 1))

  # 3. Jacket Collar / Lapels wrapping around neck (R=5, S=6)
  collar_rings = [
      (0.082, -0.118, 1.305, 0.042, 0.046, 0.046, 55.0, -20.0, -25.0, 0.2),
      (0.116, -0.020, 1.425, 0.048, 0.052, 0.052, 75.0, -10.0, 5.0, 0.2),
      (0.000, 0.092, 1.460, 0.052, 0.054, 0.054, 0.0, 85.0, 0.0, 0.2),
      (-0.116, -0.020, 1.425, 0.048, 0.052, 0.052, -75.0, -10.0, -5.0, 0.2),
      (-0.082, -0.118, 1.305, 0.042, 0.046, 0.046, -55.0, -20.0, 25.0, 0.2),
  ]
  parts.append(build_loft_object('Collar', collar_rings, 6, mat_jacket, 1))

  # 4. Pelvis / Jeans Hips (R=3, S=8)
  pelvis_rings = [
      (0.0, 0.000, 0.815, 0.186, 0.116, 0.132, 0.0, 0.0, 3.0, 0.15),
      (0.0, 0.002, 0.890, 0.204, 0.128, 0.145, 1.0, 0.0, 2.5, 0.15),
      (0.0, 0.000, 0.975, 0.182, 0.115, 0.125, 1.0, 0.0, 1.5, 0.10),
  ]
  parts.append(build_loft_object('Pelvis', pelvis_rings, 8, mat_jeans, 1))

  # 5. Left Jeans Leg (stepping forward toward -Y) (R=5, S=6)
  left_leg_rings = [
      (0.105, -0.115, 0.095, 0.072, 0.076, 0.076, -8.0, 0.0, 0.0, 0.15),
      (0.105, -0.105, 0.275, 0.078, 0.078, 0.088, -10.0, 0.0, 0.0, 0.10),
      (0.105, -0.085, 0.490, 0.085, 0.090, 0.082, -4.0, 0.0, 0.0, 0.10),
      (0.105, -0.045, 0.690, 0.098, 0.098, 0.104, 6.0, 0.0, 2.0, 0.10),
      (0.102, -0.012, 0.895, 0.108, 0.104, 0.110, 8.0, 0.0, 3.0, 0.10),
  ]
  parts.append(build_loft_object('Leg_L', left_leg_rings, 6, mat_jeans, 1))

  # 6. Right Jeans Leg (trailing slightly toward +Y) (R=5, S=6)
  right_leg_rings = [
      (-0.105, 0.125, 0.105, 0.072, 0.076, 0.076, 12.0, 0.0, 0.0, 0.15),
      (-0.105, 0.095, 0.285, 0.078, 0.078, 0.088, 10.0, 0.0, 0.0, 0.10),
      (-0.105, 0.048, 0.490, 0.085, 0.088, 0.082, 8.0, 0.0, 0.0, 0.10),
      (-0.105, 0.025, 0.690, 0.098, 0.098, 0.104, 4.0, 0.0, 2.0, 0.10),
      (-0.102, 0.010, 0.895, 0.108, 0.104, 0.110, 2.0, 0.0, 3.0, 0.10),
  ]
  parts.append(build_loft_object('Leg_R', right_leg_rings, 6, mat_jeans, 1))

  # 7. Left Sneaker + Ankle Shaft (R=5, S=6 and R=2, S=6)
  left_shoe_rings = [
      (0.105, -0.045, 0.052, 0.056, 0.048, 0.058, 90.0, 0.0, 0.0, 0.35),
      (0.105, -0.105, 0.058, 0.068, 0.054, 0.072, 90.0, 0.0, 0.0, 0.35),
      (0.105, -0.175, 0.052, 0.072, 0.048, 0.064, 90.0, 0.0, 0.0, 0.35),
      (0.105, -0.245, 0.044, 0.070, 0.040, 0.052, 90.0, 0.0, 0.0, 0.35),
      (0.105, -0.298, 0.036, 0.050, 0.030, 0.036, 90.0, 0.0, 0.0, 0.25),
  ]
  parts.append(
      build_loft_object(
          'Sneaker_L',
          left_shoe_rings,
          6,
          mat_sneakers,
          1,
          flatten_z_below=0.008,
      )
  )

  left_ankle_rings = [
      (0.105, -0.110, 0.045, 0.058, 0.064, 0.062, -6.0, 0.0, 0.0, 0.15),
      (0.105, -0.114, 0.150, 0.056, 0.060, 0.060, -8.0, 0.0, 0.0, 0.15),
  ]
  parts.append(
      build_loft_object('Ankle_L', left_ankle_rings, 6, mat_sneakers, 1)
  )

  # 8. Right Sneaker + Ankle Shaft (R=5, S=6 and R=2, S=6)
  right_shoe_rings = [
      (-0.105, 0.195, 0.060, 0.056, 0.048, 0.058, 84.0, 0.0, 0.0, 0.35),
      (-0.105, 0.135, 0.064, 0.068, 0.054, 0.072, 84.0, 0.0, 0.0, 0.35),
      (-0.105, 0.065, 0.054, 0.072, 0.048, 0.064, 86.0, 0.0, 0.0, 0.35),
      (-0.105, -0.005, 0.044, 0.070, 0.040, 0.052, 88.0, 0.0, 0.0, 0.35),
      (-0.105, -0.058, 0.036, 0.050, 0.030, 0.036, 90.0, 0.0, 0.0, 0.25),
  ]
  parts.append(
      build_loft_object(
          'Sneaker_R',
          right_shoe_rings,
          6,
          mat_sneakers,
          1,
          flatten_z_below=0.008,
      )
  )

  right_ankle_rings = [
      (-0.105, 0.130, 0.050, 0.058, 0.064, 0.062, 10.0, 0.0, 0.0, 0.15),
      (-0.105, 0.125, 0.155, 0.056, 0.060, 0.060, 12.0, 0.0, 0.0, 0.15),
  ]
  parts.append(
      build_loft_object('Ankle_R', right_ankle_rings, 6, mat_sneakers, 1)
  )

  # 9. Left Jacket Arm (swinging slightly back) (R=5, S=6)
  left_arm_rings = [
      (0.192, 0.005, 1.355, 0.082, 0.082, 0.082, 6.0, -26.0, 0.0, 0.15),
      (0.244, 0.025, 1.245, 0.072, 0.072, 0.074, 10.0, -15.0, 0.0, 0.15),
      (0.264, 0.062, 1.115, 0.066, 0.066, 0.068, 6.0, -8.0, 0.0, 0.15),
      (0.258, 0.082, 0.995, 0.062, 0.062, 0.062, -4.0, -5.0, 0.0, 0.15),
      (0.250, 0.090, 0.895, 0.058, 0.060, 0.060, -6.0, -4.0, 0.0, 0.20),
  ]
  parts.append(build_loft_object('Arm_L', left_arm_rings, 6, mat_jacket, 1))

  # 10. Right Jacket Arm (swinging forward) (R=5, S=6)
  right_arm_rings = [
      (-0.192, -0.005, 1.355, 0.082, 0.082, 0.082, -8.0, 26.0, 0.0, 0.15),
      (-0.244, -0.022, 1.245, 0.072, 0.072, 0.074, -12.0, 15.0, 0.0, 0.15),
      (-0.262, -0.038, 1.115, 0.066, 0.066, 0.068, -22.0, 8.0, 0.0, 0.15),
      (-0.250, -0.096, 1.005, 0.062, 0.062, 0.062, -30.0, 5.0, 0.0, 0.15),
      (-0.238, -0.155, 0.915, 0.058, 0.060, 0.060, -32.0, 4.0, 0.0, 0.20),
  ]
  parts.append(build_loft_object('Arm_R', right_arm_rings, 6, mat_jacket, 1))

  # 11. Left Mitten Hand + Thumb (R=3, S=6 and R=2, S=5)
  left_hand_rings = [
      (0.252, 0.088, 0.935, 0.044, 0.046, 0.046, -6.0, -4.0, 0.0, 0.15),
      (0.246, 0.082, 0.845, 0.042, 0.058, 0.052, -8.0, -4.0, 0.0, 0.25),
      (0.240, 0.076, 0.780, 0.032, 0.046, 0.042, -8.0, -4.0, 0.0, 0.20),
  ]
  parts.append(build_loft_object('Hand_L', left_hand_rings, 6, mat_skin, 1))

  left_thumb_rings = [
      (0.235, 0.055, 0.865, 0.024, 0.024, 0.024, -35.0, 18.0, 0.0, 0.10),
      (0.215, 0.015, 0.825, 0.020, 0.020, 0.020, -40.0, 22.0, 0.0, 0.10),
  ]
  parts.append(build_loft_object('Thumb_L', left_thumb_rings, 5, mat_skin, 1))

  # 12. Right Mitten Hand + Thumb (R=3, S=6 and R=2, S=5)
  right_hand_rings = [
      (-0.242, -0.135, 0.948, 0.044, 0.046, 0.046, -32.0, 4.0, 0.0, 0.15),
      (-0.230, -0.185, 0.870, 0.042, 0.058, 0.052, -34.0, 4.0, 0.0, 0.25),
      (-0.222, -0.222, 0.812, 0.032, 0.046, 0.042, -34.0, 4.0, 0.0, 0.20),
  ]
  parts.append(build_loft_object('Hand_R', right_hand_rings, 6, mat_skin, 1))

  right_thumb_rings = [
      (-0.218, -0.195, 0.890, 0.024, 0.024, 0.024, -55.0, -18.0, 0.0, 0.10),
      (-0.196, -0.238, 0.865, 0.020, 0.020, 0.020, -60.0, -22.0, 0.0, 0.10),
  ]
  parts.append(build_loft_object('Thumb_R', right_thumb_rings, 5, mat_skin, 1))

  # 13. Neck (R=2, S=6)
  neck_rings = [
      (0.0, -0.005, 1.385, 0.062, 0.062, 0.065, -4.0, 0.0, 0.0, 0.0),
      (0.0, -0.015, 1.535, 0.056, 0.056, 0.058, -4.0, 0.0, 0.0, 0.0),
  ]
  parts.append(build_loft_object('Neck', neck_rings, 6, mat_skin, 1))

  # 14. Head (R=5, S=8)
  head_rings = [
      (0.0, -0.032, 1.485, 0.058, 0.068, 0.058, 2.0, 0.0, 0.0, 0.10),
      (0.0, -0.020, 1.535, 0.088, 0.096, 0.086, 1.0, 0.0, 0.0, 0.10),
      (0.0, -0.012, 1.598, 0.098, 0.102, 0.098, 0.0, 0.0, 0.0, 0.10),
      (0.0, -0.008, 1.658, 0.094, 0.096, 0.098, 0.0, 0.0, 0.0, 0.08),
      (0.0, -0.004, 1.710, 0.072, 0.074, 0.080, 0.0, 0.0, 0.0, 0.0),
  ]
  parts.append(build_loft_object('Head', head_rings, 8, mat_skin, 1))

  # 15. Nose & Ears (R=2, S=5 each)
  nose_rings = [
      (0.0, -0.082, 1.592, 0.022, 0.022, 0.020, 82.0, 0.0, 0.0, 0.0),
      (0.0, -0.126, 1.584, 0.018, 0.018, 0.016, 82.0, 0.0, 0.0, 0.0),
  ]
  parts.append(build_loft_object('Nose', nose_rings, 5, mat_skin, 1))

  ear_l_rings = [
      (0.078, -0.005, 1.590, 0.018, 0.028, 0.028, 0.0, 75.0, -12.0, 0.10),
      (0.114, 0.002, 1.594, 0.016, 0.026, 0.026, 0.0, 75.0, -12.0, 0.10),
  ]
  parts.append(build_loft_object('Ear_L', ear_l_rings, 5, mat_skin, 1))

  ear_r_rings = [
      (-0.078, -0.005, 1.590, 0.018, 0.028, 0.028, 0.0, -75.0, 12.0, 0.10),
      (-0.114, 0.002, 1.594, 0.016, 0.026, 0.026, 0.0, -75.0, 12.0, 0.10),
  ]
  parts.append(build_loft_object('Ear_R', ear_r_rings, 5, mat_skin, 1))

  # 16. Simple Eyes & Eyebrows (R=2, S=6 and R=2, S=4)
  eye_l_rings = [
      (0.038, -0.084, 1.606, 0.017, 0.020, 0.020, 90.0, 0.0, -10.0, 0.0),
      (0.039, -0.114, 1.606, 0.015, 0.018, 0.018, 90.0, 0.0, -10.0, 0.0),
  ]
  parts.append(build_loft_object('Eye_L', eye_l_rings, 6, mat_eyes, 1))

  eye_r_rings = [
      (-0.038, -0.084, 1.606, 0.017, 0.020, 0.020, 90.0, 0.0, 10.0, 0.0),
      (-0.039, -0.114, 1.606, 0.015, 0.018, 0.018, 90.0, 0.0, 10.0, 0.0),
  ]
  parts.append(build_loft_object('Eye_R', eye_r_rings, 6, mat_eyes, 1))

  brow_l_rings = [
      (0.020, -0.098, 1.634, 0.009, 0.011, 0.011, 0.0, 85.0, -12.0, 0.2),
      (0.058, -0.090, 1.636, 0.008, 0.010, 0.010, 0.0, 85.0, -18.0, 0.2),
  ]
  parts.append(build_loft_object('Brow_L', brow_l_rings, 4, mat_hair, 1))

  brow_r_rings = [
      (-0.020, -0.098, 1.634, 0.009, 0.011, 0.011, 0.0, -85.0, 12.0, 0.2),
      (-0.058, -0.090, 1.636, 0.008, 0.010, 0.010, 0.0, -85.0, 18.0, 0.2),
  ]
  parts.append(build_loft_object('Brow_R', brow_r_rings, 4, mat_hair, 1))

  # 17. Short Brown Hair Cap + Front Quiff (R=5, S=8 and R=3, S=6)
  hair_cap_rings = [
      (0.0, 0.036, 1.542, 0.086, 0.038, 0.072, 10.0, 0.0, 0.0, 0.15),
      (0.0, 0.026, 1.595, 0.106, 0.052, 0.085, 6.0, 0.0, 0.0, 0.15),
      (0.0, 0.010, 1.652, 0.108, 0.084, 0.100, 2.0, 0.0, 0.0, 0.15),
      (0.0, -0.006, 1.698, 0.102, 0.104, 0.098, -2.0, 0.0, 0.0, 0.15),
      (0.0, -0.005, 1.742, 0.072, 0.078, 0.074, 0.0, 0.0, 0.0, 0.10),
  ]
  parts.append(build_loft_object('HairCap', hair_cap_rings, 8, mat_hair, 1))

  hair_quiff_rings = [
      (-0.045, -0.055, 1.685, 0.042, 0.045, 0.042, -15.0, 65.0, 18.0, 0.20),
      (0.005, -0.085, 1.715, 0.048, 0.052, 0.045, -10.0, 72.0, 12.0, 0.20),
      (0.055, -0.068, 1.700, 0.036, 0.038, 0.036, -5.0, 78.0, -10.0, 0.15),
  ]
  parts.append(build_loft_object('HairQuiff', hair_quiff_rings, 6, mat_hair, 1))

  bpy.ops.object.select_all(action='DESELECT')
  for p in parts:
    p.select_set(True)
  bpy.context.view_layer.objects.active = parts[0]
  bpy.ops.object.join()

  ped = bpy.context.view_layer.objects.active
  ped.name = 'Pedestrian'
  ped.data.name = 'Pedestrian'

  # Fit exact height 1.75 m and bottom-centre origin (lowest point at Z=0)
  verts = ped.data.vertices
  if len(verts) > 0:
    min_z = min(v.co.z for v in verts)
    max_z = max(v.co.z for v in verts)
    cur_h = max(1e-6, max_z - min_z)
    scale_f = 1.75 / cur_h

    min_x = min(v.co.x for v in verts)
    max_x = max(v.co.x for v in verts)
    min_y = min(v.co.y for v in verts)
    max_y = max(v.co.y for v in verts)
    cx = 0.5 * (min_x + max_x)
    cy = 0.5 * (min_y + max_y)

    for v in verts:
      v.co.x = (v.co.x - cx) * scale_f
      v.co.y = (v.co.y - cy) * scale_f
      v.co.z = (v.co.z - min_z) * scale_f

    ped.data.update()

  for poly in ped.data.polygons:
    poly.use_smooth = True

  ped.location = (0.0, 0.0, 0.0)
  ped.rotation_euler = (0.0, 0.0, 0.0)
  ped.scale = (1.0, 1.0, 1.0)
  bpy.ops.object.select_all(action='DESELECT')
  ped.select_set(True)
  bpy.context.view_layer.objects.active = ped
  bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

  return ped


def setup_lighting_and_camera(scene):
  enum_keys = [
      item.identifier
      for item in scene.render.bl_rna.properties['engine'].enum_items
  ]
  for candidate in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    if candidate in enum_keys:
      scene.render.engine = candidate
      break
  else:
    for key in enum_keys:
      if 'EEVEE' in key:
        scene.render.engine = key
        break

  world = bpy.data.worlds.new('World')
  scene.world = world
  world.use_nodes = True
  bg = world.node_tree.nodes.get('Background')
  if bg is None:
    bg = world.node_tree.nodes.new('ShaderNodeBackground')
  bg.inputs['Color'].default_value = (0.5, 0.5, 0.5, 1.0)
  bg.inputs['Strength'].default_value = 0.45

  sun_data = bpy.data.lights.new('Sun', 'SUN')
  sun_data.energy = 3.0
  sun_data.color = (1.0, 0.98, 0.95)
  sun_obj = bpy.data.objects.new('Sun', sun_data)
  scene.collection.objects.link(sun_obj)
  sun_pos = Vector((2.4, -3.2, 4.2))
  sun_target = Vector((0.0, 0.0, 0.9))
  sun_obj.location = sun_pos
  sun_obj.rotation_euler = (
      (sun_target - sun_pos).normalized().to_track_quat('-Z', 'Y').to_euler()
  )

  fill_data = bpy.data.lights.new('Fill', 'AREA')
  fill_data.energy = 35.0
  fill_data.size = 2.5
  fill_data.color = (0.90, 0.95, 1.0)
  fill_obj = bpy.data.objects.new('Fill', fill_data)
  scene.collection.objects.link(fill_obj)
  fill_pos = Vector((-2.6, -2.0, 2.1))
  fill_obj.location = fill_pos
  fill_obj.rotation_euler = (
      (sun_target - fill_pos).normalized().to_track_quat('-Z', 'Y').to_euler()
  )

  cam_data = bpy.data.cameras.new('Camera')
  cam_data.lens = 50.0
  cam_data.sensor_width = 36.0
  cam_obj = bpy.data.objects.new('Camera', cam_data)
  scene.collection.objects.link(cam_obj)
  cam_pos = Vector((-1.58, -2.38, 1.34))
  cam_target = Vector((0.0, -0.02, 0.875))
  cam_obj.location = cam_pos
  cam_obj.rotation_euler = (
      (cam_target - cam_pos).normalized().to_track_quat('-Z', 'Y').to_euler()
  )
  scene.camera = cam_obj

  scene.render.resolution_x = 900
  scene.render.resolution_y = 900
  scene.render.resolution_percentage = 100
  scene.render.image_settings.file_format = 'PNG'


def main():
  out_path = 'pedestrian.fbx'
  if '--' in sys.argv:
    idx = sys.argv.index('--')
    if idx + 1 < len(sys.argv):
      out_path = sys.argv[idx + 1]
  out_path = os.path.abspath(out_path)
  out_dir = os.path.dirname(out_path)
  if out_dir:
    os.makedirs(out_dir, exist_ok=True)
  png_path = os.path.splitext(out_path)[0] + '.png'

  clear_scene()
  ped = create_pedestrian()

  bpy.ops.object.select_all(action='DESELECT')
  ped.select_set(True)
  bpy.context.view_layer.objects.active = ped

  bpy.ops.export_scene.fbx(
      filepath=out_path,
      use_selection=True,
      bake_space_transform=True,
      axis_forward='-Z',
      axis_up='Y',
      mesh_smooth_type='FACE',
  )

  scene = bpy.context.scene
  setup_lighting_and_camera(scene)
  scene.render.filepath = png_path
  bpy.ops.render.render(write_still=True)

  tris = sum(len(p.vertices) - 2 for p in ped.data.polygons)
  print('TRIS', tris)


if __name__ == '__main__':
  main()

