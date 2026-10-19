import math
import os
import sys
import bmesh
import bpy
from mathutils import Euler, Matrix, Vector


def clear_scene():
  bpy.ops.wm.read_factory_settings(use_empty=True)
  for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
  for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh, do_unlink=True)
  for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat, do_unlink=True)
  for img in list(bpy.data.images):
    bpy.data.images.remove(img, do_unlink=True)


def get_output_paths():
  argv = sys.argv
  if "--" in argv:
    idx = argv.index("--")
    if idx + 1 < len(argv):
      out_fbx = os.path.abspath(argv[idx + 1])
    else:
      out_fbx = os.path.abspath("Drone.fbx")
  else:
    out_fbx = os.path.abspath("Drone.fbx")
  if not out_fbx.lower().endswith(".fbx"):
    out_fbx = out_fbx + ".fbx"
  out_dir = os.path.dirname(out_fbx)
  if out_dir:
    os.makedirs(out_dir, exist_ok=True)
  else:
    out_dir = os.getcwd()
  out_png = os.path.splitext(out_fbx)[0] + ".png"
  return out_fbx, out_png, out_dir


def add_mix_color(
    nodes, links, fac_sock, col1, col2, blend_type="MIX", default_fac=0.5
):
  mix = nodes.new("ShaderNodeMix")
  mix.data_type = "RGBA"
  mix.blend_type = blend_type
  val_inputs = [s for s in mix.inputs if s.type == "VALUE"]
  rgba_inputs = [s for s in mix.inputs if s.type == "RGBA"]
  rgba_outputs = [s for s in mix.outputs if s.type == "RGBA"]
  f_in = val_inputs[0]
  a_in = rgba_inputs[0]
  b_in = rgba_inputs[1]
  c_out = rgba_outputs[0]
  f_in.default_value = default_fac
  if fac_sock is not None:
    links.new(fac_sock, f_in)
  if isinstance(col1, (tuple, list)):
    a_in.default_value = col1
  else:
    links.new(col1, a_in)
  if isinstance(col2, (tuple, list)):
    b_in.default_value = col2
  else:
    links.new(col2, b_in)
  return c_out


def create_weathered_material(
    name,
    base_color,
    roughness=0.45,
    metallic=0.0,
    scratch_strength=0.22,
    dirt_strength=0.35,
    rust_strength=0.18,
    bump_strength=0.14,
    alpha=1.0,
):
  mat = bpy.data.materials.new(name=name)
  mat.use_nodes = True
  nt = mat.node_tree
  nodes = nt.nodes
  links = nt.links
  nodes.clear()

  out = nodes.new("ShaderNodeOutputMaterial")
  out.location = (900, 0)

  bsdf = nodes.new("ShaderNodeBsdfPrincipled")
  bsdf.location = (600, 0)
  bsdf.inputs["Metallic"].default_value = metallic
  if "Alpha" in bsdf.inputs:
    bsdf.inputs["Alpha"].default_value = alpha
  links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

  tex_coord = nodes.new("ShaderNodeTexCoord")
  tex_coord.location = (-900, 0)

  sep_xyz = nodes.new("ShaderNodeSeparateXYZ")
  sep_xyz.location = (-680, -250)
  links.new(tex_coord.outputs["Object"], sep_xyz.inputs["Vector"])

  # Ground dirt gradient in Object Z + noise
  noise_dirt = nodes.new("ShaderNodeTexNoise")
  noise_dirt.location = (-680, -450)
  noise_dirt.inputs["Scale"].default_value = 35.0
  noise_dirt.inputs["Detail"].default_value = 6.0
  noise_dirt.inputs["Roughness"].default_value = 0.65
  links.new(tex_coord.outputs["Object"], noise_dirt.inputs["Vector"])

  math_z_scale = nodes.new("ShaderNodeMath")
  math_z_scale.operation = "MULTIPLY"
  math_z_scale.inputs[1].default_value = 14.0
  links.new(sep_xyz.outputs["Z"], math_z_scale.inputs[0])

  math_z_inv = nodes.new("ShaderNodeMath")
  math_z_inv.operation = "SUBTRACT"
  math_z_inv.use_clamp = True
  math_z_inv.inputs[0].default_value = 1.0
  links.new(math_z_scale.outputs["Value"], math_z_inv.inputs[1])

  math_dirt_mask = nodes.new("ShaderNodeMath")
  math_dirt_mask.operation = "MULTIPLY"
  math_dirt_mask.use_clamp = True
  links.new(math_z_inv.outputs["Value"], math_dirt_mask.inputs[0])
  links.new(noise_dirt.outputs["Fac"], math_dirt_mask.inputs[1])

  math_dirt_str = nodes.new("ShaderNodeMath")
  math_dirt_str.operation = "MULTIPLY"
  math_dirt_str.use_clamp = True
  math_dirt_str.inputs[1].default_value = dirt_strength
  links.new(math_dirt_mask.outputs["Value"], math_dirt_str.inputs[0])

  # Top dust gradient in Z + noise
  math_top_mask = nodes.new("ShaderNodeMath")
  math_top_mask.operation = "MULTIPLY"
  math_top_mask.use_clamp = True
  links.new(math_z_scale.outputs["Value"], math_top_mask.inputs[0])
  links.new(noise_dirt.outputs["Fac"], math_top_mask.inputs[1])

  math_dust_str = nodes.new("ShaderNodeMath")
  math_dust_str.operation = "MULTIPLY"
  math_dust_str.use_clamp = True
  math_dust_str.inputs[1].default_value = 0.18
  links.new(math_top_mask.outputs["Value"], math_dust_str.inputs[0])

  # Stretched vertical rust/grime streaks
  mapping_rust = nodes.new("ShaderNodeMapping")
  mapping_rust.location = (-680, 120)
  mapping_rust.inputs["Scale"].default_value = (45.0, 45.0, 9.0)
  links.new(tex_coord.outputs["Object"], mapping_rust.inputs["Vector"])

  noise_rust = nodes.new("ShaderNodeTexNoise")
  noise_rust.location = (-460, 120)
  noise_rust.inputs["Scale"].default_value = 3.2
  noise_rust.inputs["Detail"].default_value = 8.0
  noise_rust.inputs["Roughness"].default_value = 0.7
  links.new(mapping_rust.outputs["Vector"], noise_rust.inputs["Vector"])

  ramp_rust = nodes.new("ShaderNodeValToRGB")
  ramp_rust.location = (-240, 120)
  ramp_rust.color_ramp.elements[0].position = 0.62
  ramp_rust.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
  ramp_rust.color_ramp.elements[1].position = 0.82
  ramp_rust.color_ramp.elements[1].color = (
      rust_strength,
      rust_strength,
      rust_strength,
      1.0,
  )
  links.new(noise_rust.outputs["Fac"], ramp_rust.inputs["Fac"])

  # High-frequency scratches
  mapping_scr = nodes.new("ShaderNodeMapping")
  mapping_scr.location = (-680, 360)
  mapping_scr.inputs["Scale"].default_value = (85.0, 22.0, 85.0)
  links.new(tex_coord.outputs["Object"], mapping_scr.inputs["Vector"])

  noise_scr = nodes.new("ShaderNodeTexNoise")
  noise_scr.location = (-460, 360)
  noise_scr.inputs["Scale"].default_value = 4.5
  noise_scr.inputs["Detail"].default_value = 12.0
  noise_scr.inputs["Roughness"].default_value = 0.85
  links.new(mapping_scr.outputs["Vector"], noise_scr.inputs["Vector"])

  ramp_scr = nodes.new("ShaderNodeValToRGB")
  ramp_scr.location = (-240, 360)
  ramp_scr.color_ramp.elements[0].position = 0.70
  ramp_scr.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
  ramp_scr.color_ramp.elements[1].position = 0.84
  ramp_scr.color_ramp.elements[1].color = (
      scratch_strength,
      scratch_strength,
      scratch_strength,
      1.0,
  )
  links.new(noise_scr.outputs["Fac"], ramp_scr.inputs["Fac"])

  # Mix base color with scratches, rust streaks, dust, and ground dirt
  scr_col = (
      min(1.0, base_color[0] + 0.22),
      min(1.0, base_color[1] + 0.22),
      min(1.0, base_color[2] + 0.22),
      1.0,
  )
  rust_col = (0.32, 0.19, 0.11, 1.0)
  dust_col = (0.58, 0.56, 0.52, 1.0)
  dirt_col = (0.20, 0.17, 0.13, 1.0)

  c1 = add_mix_color(nodes, links, ramp_scr.outputs["Color"], base_color, scr_col)
  c2 = add_mix_color(nodes, links, ramp_rust.outputs["Color"], c1, rust_col)
  c3 = add_mix_color(nodes, links, math_dust_str.outputs["Value"], c2, dust_col)
  c4 = add_mix_color(nodes, links, math_dirt_str.outputs["Value"], c3, dirt_col)
  links.new(c4, bsdf.inputs["Base Color"])

  # Roughness variation
  math_r_add = nodes.new("ShaderNodeMath")
  math_r_add.operation = "ADD"
  math_r_add.use_clamp = True
  math_r_add.inputs[0].default_value = roughness
  links.new(math_dirt_str.outputs["Value"], math_r_add.inputs[1])
  links.new(math_r_add.outputs["Value"], bsdf.inputs["Roughness"])

  # Micro-bump & scratch normal
  math_bump_mix = nodes.new("ShaderNodeMath")
  math_bump_mix.operation = "ADD"
  links.new(noise_scr.outputs["Fac"], math_bump_mix.inputs[0])
  links.new(noise_dirt.outputs["Fac"], math_bump_mix.inputs[1])

  bump = nodes.new("ShaderNodeBump")
  bump.location = (340, -220)
  bump.inputs["Strength"].default_value = bump_strength
  bump.inputs["Distance"].default_value = 0.0015
  links.new(math_bump_mix.outputs["Value"], bump.inputs["Height"])
  links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

  return mat


def assign_faces_mat(faces, mat_idx, smooth=False):
  for f in faces:
    f.material_index = mat_idx
    f.smooth = smooth


def add_cylinder_part(
    bm,
    center,
    radius_bottom,
    radius_top,
    height,
    segments,
    mat_idx,
    rot_euler=None,
    smooth_sides=True,
    cap_bottom=True,
    cap_top=True,
):
  rings = []
  for r_idx, (z_off, rad) in enumerate(
      [(-height * 0.5, radius_bottom), (height * 0.5, radius_top)]
  ):
    ring = []
    for i in range(segments):
      ang = 2.0 * math.pi * i / segments
      p = Vector((math.cos(ang) * rad, math.sin(ang) * rad, z_off))
      if rot_euler is not None:
        p.rotate(rot_euler)
      p += center
      ring.append(bm.verts.new(p))
    rings.append(ring)

  side_faces = []
  for i in range(segments):
    ni = (i + 1) % segments
    f = bm.faces.new([rings[0][i], rings[0][ni], rings[1][ni], rings[1][i]])
    f.material_index = mat_idx
    f.smooth = smooth_sides
    side_faces.append(f)

  cap_faces = []
  if cap_bottom and radius_bottom > 1e-6:
    fb = bm.faces.new(list(reversed(rings[0])))
    fb.material_index = mat_idx
    fb.smooth = False
    cap_faces.append(fb)
  if cap_top and radius_top > 1e-6:
    ft = bm.faces.new(rings[1])
    ft.material_index = mat_idx
    ft.smooth = False
    cap_faces.append(ft)
  return side_faces, cap_faces, rings


def add_box_part(bm, center, size, mat_idx, rot_euler=None, bevel_top=0.0):
  hx, hy, hz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
  tx = max(0.0, hx - bevel_top)
  ty = max(0.0, hy - bevel_top)
  coords = [
      Vector((-hx, -hy, -hz)),
      Vector((hx, -hy, -hz)),
      Vector((hx, hy, -hz)),
      Vector((-hx, hy, -hz)),
      Vector((-tx, -ty, hz)),
      Vector((tx, -ty, hz)),
      Vector((tx, ty, hz)),
      Vector((-tx, ty, hz)),
  ]
  verts = []
  for c in coords:
    p = c.copy()
    if rot_euler is not None:
      p.rotate(rot_euler)
    p += center
    verts.append(bm.verts.new(p))
  quads = [
      (0, 3, 2, 1),
      (4, 5, 6, 7),
      (0, 1, 5, 4),
      (1, 2, 6, 5),
      (2, 3, 7, 6),
      (3, 0, 4, 7),
  ]
  faces = []
  for q in quads:
    f = bm.faces.new([verts[idx] for idx in q])
    f.material_index = mat_idx
    f.smooth = False
    faces.append(f)
  return faces, verts


def add_sensor_eye(
    bm,
    center,
    normal_dir,
    outer_radius,
    depth,
    mat_bezel,
    mat_metal,
    mat_lens,
    segments=16,
):
  z_axis = normal_dir.normalized()
  up_ref = (
      Vector((0.0, 0.0, 1.0))
      if abs(z_axis.z) < 0.95
      else Vector((0.0, 1.0, 0.0))
  )
  x_axis = up_ref.cross(z_axis).normalized()
  y_axis = z_axis.cross(x_axis).normalized()

  def to_world(r, ang, z_local):
    return (
        center
        + x_axis * (r * math.cos(ang))
        + y_axis * (r * math.sin(ang))
        + z_axis * z_local
    )

  # Rings from base to bezel lip, recessed metallic rim, and convex glass dome
  profile = [
      (outer_radius * 1.06, -depth * 0.5, mat_bezel, True),
      (outer_radius, depth * 0.45, mat_bezel, True),
      (outer_radius * 0.80, depth * 0.50, mat_bezel, False),
      (outer_radius * 0.72, depth * 0.15, mat_metal, False),
      (outer_radius * 0.64, depth * 0.18, mat_lens, True),
      (outer_radius * 0.34, depth * 0.40, mat_lens, True),
  ]
  rings = []
  for r, zl, _, _ in profile:
    ring = []
    for i in range(segments):
      ang = 2.0 * math.pi * i / segments
      ring.append(bm.verts.new(to_world(r, ang, zl)))
    rings.append(ring)

  for k in range(len(profile) - 1):
    mat_use = profile[k + 1][2]
    sm_use = profile[k + 1][3]
    for i in range(segments):
      ni = (i + 1) % segments
      f = bm.faces.new([rings[k][i], rings[k][ni], rings[k + 1][ni], rings[k + 1][i]])
      f.material_index = mat_use
      f.smooth = sm_use

  tip_v = bm.verts.new(center + z_axis * (depth * 0.48))
  for i in range(segments):
    ni = (i + 1) % segments
    f = bm.faces.new([rings[-1][i], rings[-1][ni], tip_v])
    f.material_index = mat_lens
    f.smooth = True

  back_f = bm.faces.new(list(reversed(rings[0])))
  back_f.material_index = mat_bezel
  back_f.smooth = False


def build_fuselage(bm, mat_body, mat_dark, mat_metal, mat_white):
  #Fuselage length: 0.15m (-0.075 to +0.075), width: 0.09m (-0.045 to +0.045), height: Z=0.014 to Z=0.064
  #Stations: (y, half_w, z_bot, z_top, nose_cut_depth, top_ridge_h, is_seam_ring, is_battery_bay)
  stations = [
      (-0.0750, 0.018, 0.036, 0.047, 0.008, 0.0000, False, False),
      (-0.0710, 0.029, 0.034, 0.053, 0.011, 0.0005, False, False),
      (-0.0640, 0.036, 0.032, 0.058, 0.012, 0.0012, False, False),
      (-0.0540, 0.040, 0.029, 0.061, 0.010, 0.0018, True, False),
      (-0.0440, 0.043, 0.020, 0.063, 0.003, 0.0022, False, False),
      (-0.0340, 0.045, 0.015, 0.064, 0.000, 0.0025, False, False),
      (-0.0200, 0.045, 0.014, 0.064, 0.000, 0.0026, True, False),
      (-0.0050, 0.045, 0.014, 0.064, 0.000, 0.0026, False, False),
      (0.0100, 0.044, 0.014, 0.063, 0.000, 0.0024, False, False),
      (0.0240, 0.043, 0.015, 0.062, 0.000, 0.0020, True, False),
      (0.0340, 0.041, 0.016, 0.060, 0.000, 0.0015, False, False),
      (0.0355, 0.039, 0.017, 0.059, 0.000, 0.0012, True, True),
      (0.0480, 0.039, 0.017, 0.058, 0.000, 0.0010, False, True),
      (0.0620, 0.037, 0.019, 0.055, 0.000, 0.0006, False, True),
      (0.0710, 0.033, 0.022, 0.051, 0.000, 0.0002, True, True),
      (0.0750, 0.026, 0.026, 0.046, 0.000, 0.0000, False, True),
  ]

  n_seg = 28
  ring_verts = []
  for y, hw, zb, zt, ncut, ridge, is_seam, is_batt in stations:
    zc = 0.5 * (zb + zt)
    hz = 0.5 * (zt - zb)
    ring = []
    for i in range(n_seg):
      ang = 2.0 * math.pi * i / n_seg
      ca = math.cos(ang)
      sa = math.sin(ang)
      # Superellipse cross-section for sleek DJI Mini 4 Pro fuselage
      sx = math.copysign(abs(ca) ** 0.78, ca) * hw
      sz = math.copysign(abs(sa) ** 0.82, sa) * hz
      z_val = zc + sz

      # Central upper ridge / canopy crown
      if sa > 0.25 and abs(ca) < 0.65:
        crown_fac = (1.0 - (abs(ca) / 0.65) ** 2) * ((sa - 0.25) / 0.75)
        z_val += ridge * crown_fac

      # Side aerodynamic character crease
      if abs(sa) < 0.32:
        crease = 1.0 - 0.055 * (1.0 - abs(sa) / 0.32)
        sx *= crease

      # Front underside gimbal recess cavity
      if ncut > 0.0 and sa < -0.15 and abs(ca) < 0.62:
        recess = (1.0 - (abs(ca) / 0.62) ** 2) * min(1.0, (-sa - 0.15) / 0.6)
        z_val += ncut * recess

      # Panel seam inset
      if is_seam:
        sx *= 0.985
        z_val = zc + (z_val - zc) * 0.985

      ring.append(bm.verts.new(Vector((sx, y, z_val))))
    ring_verts.append(ring)

  for s in range(len(stations) - 1):
    y0 = stations[s][0]
    y1 = stations[s + 1][0]
    seam_band = stations[s][6] and stations[s + 1][6]
    narrow_band = abs(y1 - y0) < 0.0025
    is_batt = stations[s][7] and stations[s + 1][7]
    for i in range(n_seg):
      ni = (i + 1) % n_seg
      ang_mid = 2.0 * math.pi * (i + 0.5) / n_seg
      sa = math.sin(ang_mid)
      ca = math.cos(ang_mid)
      f = bm.faces.new([
          ring_verts[s][i],
          ring_verts[s][ni],
          ring_verts[s + 1][ni],
          ring_verts[s + 1][i],
      ])
      # Assign dark grey to belly plate, side seam grooves, and battery latch zone
      if narrow_band or seam_band:
        f.material_index = mat_dark
        f.smooth = False
      elif sa < -0.58 and y0 > -0.040 and y1 < 0.065:
        f.material_index = mat_dark
        f.smooth = True
      elif is_batt and abs(ca) > 0.72 and abs(sa) < 0.42:
        f.material_index = mat_dark
        f.smooth = False
      else:
        f.material_index = mat_body
        f.smooth = True

  # Cap nose tip and tail end with quad fan around center vert
  nose_c = bm.verts.new(Vector((0.0, -0.0758, 0.0415)))
  for i in range(n_seg):
    ni = (i + 1) % n_seg
    f = bm.faces.new([ring_verts[0][ni], ring_verts[0][i], nose_c])
    f.material_index = mat_body
    f.smooth = True

  tail_c = bm.verts.new(Vector((0.0, 0.0756, 0.036)))
  for i in range(n_seg):
    ni = (i + 1) % n_seg
    f = bm.faces.new([ring_verts[-1][i], ring_verts[-1][ni], tail_c])
    f.material_index = mat_dark if abs(math.sin(2.0 * math.pi * i / n_seg)) < 0.45 else mat_body
    f.smooth = False

  # Rear battery power button (circular bezel + center button on top-rear)
  add_cylinder_part(
      bm,
      Vector((0.0, 0.044, 0.0595)),
      0.0055,
      0.0050,
      0.0022,
      16,
      mat_dark,
      smooth_sides=True,
  )
  add_cylinder_part(
      bm,
      Vector((0.0, 0.044, 0.0604)),
      0.0038,
      0.0036,
      0.0018,
      16,
      mat_body,
      smooth_sides=True,
  )

  # Rear USB-C port frame & recess
  add_box_part(
      bm,
      Vector((0.0, 0.0748, 0.035)),
      (0.011, 0.0025, 0.0045),
      mat_dark,
      bevel_top=0.0005,
  )
  add_box_part(
      bm,
      Vector((0.0, 0.0752, 0.035)),
      (0.0075, 0.0020, 0.0016),
      mat_metal,
  )

  # Side cooling intake vents (left & right shoulder louvers, 5 slats each side)
  for side in (-1.0, 1.0):
    add_box_part(
        bm,
        Vector((side * 0.0432, -0.028, 0.045)),
        (0.0035, 0.018, 0.0085),
        mat_dark,
        rot_euler=Euler((0.0, side * 0.18, side * 0.08)),
    )
    for k in range(5):
      yk = -0.034 + k * 0.0030
      add_box_part(
          bm,
          Vector((side * 0.0444, yk, 0.045)),
          (0.0022, 0.0010, 0.0072),
          mat_metal,
          rot_euler=Euler((0.25, side * 0.18, 0.0)),
      )

  # Belly heatsink cooling slot & 8 aluminum cooling fins
  add_box_part(
      bm,
      Vector((0.0, -0.012, 0.0142)),
      (0.026, 0.028, 0.0022),
      mat_dark,
  )
  for k in range(8):
    xk = -0.0105 + k * 0.0030
    add_box_part(
        bm,
        Vector((xk, -0.012, 0.0132)),
        (0.0009, 0.024, 0.0024),
        mat_metal,
    )

  # Top rear exhaust vents (left & right behind canopy arch)
  for side in (-1.0, 1.0):
    for k in range(4):
      yk = 0.024 + k * 0.0024
      add_box_part(
          bm,
          Vector((side * 0.022, yk, 0.0605 - k * 0.0004)),
          (0.010, 0.0010, 0.0018),
          mat_dark,
          rot_euler=Euler((-0.18, side * 0.22, 0.0)),
      )


def build_pip_lettering(bm, mat_white):
  # White "PIP" printed on top shell: crisp 3D block strokes conforming to top shell Z
  # Viewed from top/front: X from left (-X) to right (+X), Y around -0.006, Z on top shell (~0.0666)
  def top_z_at(x, y):
    # Match fuselage top crown contour at (x, y)
    base_z = 0.0665 - 0.14 * (x * x) - 0.08 * ((y + 0.008) ** 2)
    return base_z

  def add_stroke_quad(x0, y0, x1, y1, thickness=0.00045):
    v_coords = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    bot_v = [bm.verts.new(Vector((vx, vy, top_z_at(vx, vy) - 0.0001))) for vx, vy in v_coords]
    top_v = [bm.verts.new(Vector((vx, vy, top_z_at(vx, vy) + thickness))) for vx, vy in v_coords]
    ft = bm.faces.new(top_v)
    ft.material_index = mat_white
    ft.smooth = False
    for i in range(4):
      ni = (i + 1) % 4
      fs = bm.faces.new([bot_v[i], bot_v[ni], top_v[ni], top_v[i]])
      fs.material_index = mat_white
      fs.smooth = False

  # Letter P (left, X around -0.0145 to -0.0055), I (center, X around -0.0018 to +0.0018), P (right, X around +0.0055 to +0.0145)
  # Note: Front is -Y, so top of letters is towards +Y (away from nose) and bottom of letters is towards -Y (towards nose)
  y_bot = -0.0120
  y_mid = -0.0055
  y_top = 0.0010
  sw = 0.0022

  for x_base in (-0.0145, 0.0055):
    # Vertical stem of P
    add_stroke_quad(x_base, y_bot, x_base + sw, y_top)
    # Top horizontal bar of P
    add_stroke_quad(x_base + sw, y_top - sw, x_base + 0.0072, y_top)
    # Middle horizontal bar of P
    add_stroke_quad(x_base + sw, y_mid, x_base + 0.0072, y_mid + sw)
    # Right bowl vertical bar of P
    add_stroke_quad(x_base + 0.0065, y_mid + sw * 0.5, x_base + 0.0087, y_top - sw * 0.5)

  # Letter I in the middle
  add_stroke_quad(-0.0012, y_bot, 0.0012, y_top)
  add_stroke_quad(-0.0032, y_top - sw, 0.0032, y_top)
  add_stroke_quad(-0.0032, y_bot, 0.0032, y_bot + sw)


def build_obstacle_sensors(bm, mat_body, mat_dark, mat_metal, mat_lens):
  # Front obstacle-sensor eyes (binocular angled pods on nose upper corners)
  for side in (-1.0, 1.0):
    pod_c = Vector((side * 0.023, -0.066, 0.048))
    add_cylinder_part(
        bm,
        pod_c,
        0.0082,
        0.0074,
        0.010,
        16,
        mat_body,
        rot_euler=Euler((math.radians(72), 0.0, side * math.radians(-22))),
        smooth_sides=True,
    )
    eye_pos = Vector((side * 0.0245, -0.0702, 0.0492))
    eye_dir = Vector((side * 0.34, -0.90, 0.24)).normalized()
    add_sensor_eye(bm, eye_pos, eye_dir, 0.0068, 0.0032, mat_dark, mat_metal, mat_lens, segments=16)

  # Rear obstacle-sensor eyes (facing backward-outward on upper tail corners)
  for side in (-1.0, 1.0):
    eye_pos = Vector((side * 0.022, 0.0725, 0.0455))
    eye_dir = Vector((side * 0.28, 0.93, 0.18)).normalized()
    add_sensor_eye(bm, eye_pos, eye_dir, 0.0062, 0.0030, mat_dark, mat_metal, mat_lens, segments=16)

  # Downward optical flow & ToF vision sensors on belly
  for side in (-1.0, 1.0):
    eye_pos = Vector((side * 0.0115, 0.012, 0.0140))
    eye_dir = Vector((0.0, 0.0, -1.0))
    add_sensor_eye(bm, eye_pos, eye_dir, 0.0052, 0.0024, mat_dark, mat_metal, mat_lens, segments=14)


def build_gimbal_and_camera(bm, mat_body, mat_dark, mat_metal, mat_lens):
  # 3-Axis Gimbal under the nose (-Y is front):
  # 1. Vibration-damping upper gimbal plate under nose roof
  add_box_part(
      bm,
      Vector((0.0, -0.050, 0.039)),
      (0.026, 0.024, 0.004),
      mat_dark,
      bevel_top=0.001,
  )
  for sx in (-0.010, 0.010):
    for sy in (-0.058, -0.042):
      add_cylinder_part(
          bm,
          Vector((sx, sy, 0.037)),
          0.0026,
          0.0022,
          0.004,
          10,
          mat_dark,
      )

  # 2. Axis 1 (Yaw): Vertical pivot hub & L-shaped yaw arm
  add_cylinder_part(
      bm,
      Vector((0.0, -0.045, 0.0355)),
      0.0065,
      0.0065,
      0.0045,
      16,
      mat_metal,
  )
  for i in range(6):
    t = i / 5.0
    ang = t * math.pi * 0.5
    pos = Vector((0.013 * math.sin(ang), -0.044, 0.034 - 0.011 * (1.0 - math.cos(ang))))
    add_box_part(
        bm,
        pos,
        (0.0042, 0.0055, 0.0042),
        mat_metal,
        rot_euler=Euler((0.0, ang * 0.6, 0.0)),
    )

  # 3. Axis 2 (Roll): Rear roll motor drum + curved yoke cross-arm
  add_cylinder_part(
      bm,
      Vector((0.0, -0.043, 0.0235)),
      0.0072,
      0.0072,
      0.0055,
      16,
      mat_metal,
      rot_euler=Euler((math.radians(90), 0.0, 0.0)),
  )
  add_box_part(
      bm,
      Vector((0.0, -0.046, 0.0235)),
      (0.034, 0.0045, 0.0065),
      mat_metal,
      bevel_top=0.0008,
  )

  # 4. Axis 3 (Pitch): Left & right pitch arms extending forward to camera pivot hubs
  for side in (-1.0, 1.0):
    add_box_part(
        bm,
        Vector((side * 0.0158, -0.0535, 0.0235)),
        (0.0036, 0.017, 0.0062),
        mat_metal,
        bevel_top=0.0006,
    )
    add_cylinder_part(
        bm,
        Vector((side * 0.0162, -0.0595, 0.0235)),
        0.0048,
        0.0048,
        0.0032,
        14,
        mat_dark,
        rot_euler=Euler((0.0, math.radians(90), 0.0)),
    )

  # 5. Camera Body Housing (0.026m wide x 0.021m deep x 0.021m tall)
  cam_c = Vector((0.0, -0.0595, 0.0235))
  add_box_part(
      bm,
      cam_c,
      (0.026, 0.020, 0.020),
      mat_metal,
      bevel_top=0.0022,
  )
  # Camera top heatsink fins
  for k in range(5):
    xk = -0.008 + k * 0.004
    add_box_part(
        bm,
        Vector((xk, -0.0585, 0.0342)),
        (0.0012, 0.013, 0.0016),
        mat_dark,
    )

  # Front rectangular optical bezel frame
  add_box_part(
      bm,
      Vector((0.0, -0.0702, 0.0235)),
      (0.023, 0.0030, 0.018),
      mat_dark,
      bevel_top=0.0012,
  )

  # Protruding cylindrical lens barrel & convex glossy dark glass lens facing -Y
  lens_pos = Vector((0.0, -0.0715, 0.0235))
  lens_dir = Vector((0.0, -1.0, 0.0))
  add_sensor_eye(
      bm,
      lens_pos,
      lens_dir,
      0.0082,
      0.0048,
      mat_dark,
      mat_metal,
      mat_lens,
      segments=24,
  )


def build_arms_feet_and_motors(
    bm, rotor_hubs, mat_body, mat_dark, mat_metal, mat_led
):
  # Four folding arms reaching to rotor hubs on 0.25m diagonal (radius = 0.125m)
  # rotor_hubs: list of (name, hx, hy, hz, is_front)
  for idx, (rname, hx, hy, hz, is_front) in enumerate(rotor_hubs):
    sx = -1.0 if hx < 0 else 1.0
    sy = -1.0 if hy < 0 else 1.0

    # Arm attachment hinge on fuselage
    root = Vector((sx * 0.036, sy * (0.030 if is_front else 0.032), hz - 0.004))
    tip = Vector((hx, hy, hz - 0.006))
    arm_vec = tip - root
    arm_len = arm_vec.length
    arm_dir = arm_vec.normalized()
    up_vec = Vector((0.0, 0.0, 1.0))
    side_vec = arm_dir.cross(up_vec).normalized()
    perp_up = side_vec.cross(arm_dir).normalized()

    # Dark grey folding hinge collar at fuselage root
    hinge_pos = root + arm_dir * 0.006
    yaw_ang = math.atan2(arm_dir.y, arm_dir.x) - math.pi * 0.5
    add_cylinder_part(
        bm,
        hinge_pos,
        0.0085,
        0.0080,
        0.013,
        14,
        mat_dark,
        rot_euler=Euler((0.0, 0.0, yaw_ang)),
    )

    # Multi-station sculpted aero-tube arm (10 stations x 12 cross-section verts)
    n_arm_stations = 10
    n_arm_seg = 12
    arm_rings = []
    for s in range(n_arm_stations):
      t = s / (n_arm_stations - 1)
      center_pt = root.lerp(tip, t)
      # Slight upward arch in middle of arm
      center_pt.z += math.sin(t * math.pi) * 0.0032
      # Taper width and height along arm
      rx = 0.0078 * (1.0 - 0.28 * t) + (0.0022 if t > 0.85 else 0.0)
      rz = 0.0095 * (1.0 - 0.22 * t)
      ring = []
      for i in range(n_arm_seg):
        ang = 2.0 * math.pi * i / n_arm_seg
        ca = math.cos(ang)
        sa = math.sin(ang)
        # Aerodynamic teardrop-oval cross section
        pt = (
            center_pt
            + side_vec * (ca * rx)
            + perp_up * (sa * rz * (1.05 if sa > 0 else 0.85))
        )
        ring.append(bm.verts.new(pt))
      arm_rings.append(ring)

    for s in range(n_arm_stations - 1):
      is_hinge_seam = s == 1
      for i in range(n_arm_seg):
        ni = (i + 1) % n_arm_seg
        sa = math.sin(2.0 * math.pi * (i + 0.5) / n_arm_seg)
        f = bm.faces.new([
            arm_rings[s][i],
            arm_rings[s][ni],
            arm_rings[s + 1][ni],
            arm_rings[s + 1][i],
        ])
        if is_hinge_seam or sa < -0.65:
          f.material_index = mat_dark
          f.smooth = False
        else:
          f.material_index = mat_body
          f.smooth = True

    # Motor pod outer cup at arm tip (hx, hy)
    pod_base_z = hz - 0.015
    pod_top_z = hz - 0.002
    pod_h = pod_top_z - pod_base_z
    pod_c = Vector((hx, hy, 0.5 * (pod_base_z + pod_top_z)))
    side_faces, _, _ = add_cylinder_part(
        bm,
        pod_c,
        0.0112,
        0.0124,
        pod_h,
        20,
        mat_body,
        smooth_sides=True,
    )

    # Small green status LED window on outer face of the motor pod tip
    out_ang = math.atan2(hy, hx)
    led_c = Vector((
        hx + math.cos(out_ang) * 0.0118,
        hy + math.sin(out_ang) * 0.0118,
        pod_c.z,
    ))
    add_box_part(
        bm,
        led_c,
        (0.0022, 0.0055, pod_h * 0.68),
        mat_led,
        rot_euler=Euler((0.0, 0.0, out_ang)),
        bevel_top=0.0004,
    )
    # Dark bezel trim around LED
    add_box_part(
        bm,
        Vector((
            hx + math.cos(out_ang) * 0.0113,
            hy + math.sin(out_ang) * 0.0113,
            pod_c.z,
        )),
        (0.0020, 0.0068, pod_h * 0.78),
        mat_dark,
        rot_euler=Euler((0.0, 0.0, out_ang)),
    )

    # Brushless motor rotor bell & shaft collar rising to hub Z
    add_cylinder_part(
        bm,
        Vector((hx, hy, hz - 0.0012)),
        0.0102,
        0.0094,
        0.0042,
        20,
        mat_metal,
        smooth_sides=True,
    )
    add_cylinder_part(
        bm,
        Vector((hx, hy, hz + 0.0005)),
        0.0042,
        0.0038,
        0.0022,
        14,
        mat_dark,
        smooth_sides=True,
    )

    # Landing leg under each arm reaching down cleanly to Z = 0.000
    # Front landing struts descend from under the motor pods; rear struts descend from under rear arm/elbow
    if is_front:
      leg_top = Vector((hx * 0.96, hy * 0.96, pod_base_z + 0.002))
      leg_bot = Vector((hx * 0.96, hy * 0.96, 0.0025))
    else:
      leg_top = Vector((hx * 0.84, hy * 0.84, pod_base_z + 0.004))
      leg_bot = Vector((hx * 0.84, hy * 0.84, 0.0025))

    leg_h = leg_top.z - leg_bot.z
    leg_mid = 0.5 * (leg_top + leg_bot)
    add_cylinder_part(
        bm,
        leg_mid,
        0.0034,
        0.0056,
        leg_h,
        12,
        mat_body,
        smooth_sides=True,
    )
    # Rubberized dark grey landing foot pad touching Z = 0.000
    foot_c = Vector((leg_bot.x, leg_bot.y, 0.0014))
    add_cylinder_part(
        bm,
        foot_c,
        0.0036,
        0.0038,
        0.0028,
        12,
        mat_dark,
        smooth_sides=True,
    )


def build_screws(bm, rotor_hubs, mat_metal, mat_dark):
  # Exposed miniature Torx screws on arm hinges, belly plate, and motor mounts
  screw_locs = [
      (Vector((-0.032, -0.028, 0.0155)), Euler((math.pi, 0.0, 0.0))),
      (Vector((0.032, -0.028, 0.0155)), Euler((math.pi, 0.0, 0.0))),
      (Vector((-0.030, 0.028, 0.0160)), Euler((math.pi, 0.0, 0.0))),
      (Vector((0.030, 0.028, 0.0160)), Euler((math.pi, 0.0, 0.0))),
      (Vector((-0.018, -0.032, 0.0145)), Euler((math.pi, 0.0, 0.0))),
      (Vector((0.018, -0.032, 0.0145)), Euler((math.pi, 0.0, 0.0))),
      (Vector((-0.018, 0.018, 0.0145)), Euler((math.pi, 0.0, 0.0))),
      (Vector((0.018, 0.018, 0.0145)), Euler((math.pi, 0.0, 0.0))),
      (Vector((-0.036, -0.030, 0.0545)), Euler((0.0, 0.0, 0.0))),
      (Vector((0.036, -0.030, 0.0545)), Euler((0.0, 0.0, 0.0))),
      (Vector((-0.036, 0.032, 0.0465)), Euler((0.0, 0.0, 0.0))),
      (Vector((0.036, 0.032, 0.0465)), Euler((0.0, 0.0, 0.0))),
  ]
  for _, hx, hy, hz, _ in rotor_hubs:
    screw_locs.append((Vector((hx, hy, hz - 0.0152)), Euler((math.pi, 0.0, 0.0))))

  for pos, rot in screw_locs:
    add_cylinder_part(
        bm,
        pos,
        0.0018,
        0.0016,
        0.0010,
        8,
        mat_metal,
        rot_euler=rot,
        smooth_sides=False,
    )
    add_cylinder_part(
        bm,
        pos + Vector((0.0, 0.0, 0.0004 if rot.x == 0.0 else -0.0004)),
        0.0009,
        0.0009,
        0.0005,
        6,
        mat_dark,
        rot_euler=rot,
        smooth_sides=False,
    )


def create_rotor_object(
    name, hub_location, yaw_offset, spin_dir, materials_list, mat_rotor, mat_dark, mat_metal
):
  # Each propeller: 2 blades, 0.15 m tip to tip (radius 0.075 m), origin at its hub, spinning about local Z
  mesh = bpy.data.meshes.new(name + "_Mesh")
  obj = bpy.data.objects.new(name, mesh)
  bpy.context.collection.objects.link(obj)
  for m in materials_list:
    obj.data.materials.append(m)

  bm = bmesh.new()

  # Central spinner hub cap & blade root clamps at local (0, 0, 0)
  add_cylinder_part(
      bm,
      Vector((0.0, 0.0, 0.0022)),
      0.0068,
      0.0056,
      0.0044,
      16,
      mat_dark,
      smooth_sides=True,
  )
  add_cylinder_part(
      bm,
      Vector((0.0, 0.0, 0.0046)),
      0.0028,
      0.0022,
      0.0012,
      12,
      mat_metal,
      smooth_sides=True,
  )

  # Two opposite blades reaching r = 0.075m (0.15m tip to tip)
  n_stations = 13
  # Airfoil cross-section loop (10 points around chord from -0.5 to +0.5)
  foil_pts = [
      (-0.50, 0.000),
      (-0.35, 0.065),
      (-0.10, 0.095),
      (0.18, 0.080),
      (0.42, 0.035),
      (0.50, 0.000),
      (0.38, -0.025),
      (0.12, -0.035),
      (-0.15, -0.030),
      (-0.38, -0.018),
  ]

  for blade_side in (-1.0, 1.0):
    base_ang = yaw_offset + (0.0 if blade_side > 0 else math.pi)
    dir_x = math.cos(base_ang)
    dir_y = math.sin(base_ang)
    perp_x = -dir_y * spin_dir
    perp_y = dir_x * spin_dir

    # Blade root hinge pin
    pin_pos = Vector((dir_x * 0.0062, dir_y * 0.0062, 0.0025))
    add_cylinder_part(
        bm,
        pin_pos,
        0.0016,
        0.0015,
        0.0048,
        10,
        mat_metal,
        smooth_sides=True,
    )

    blade_rings = []
    for s in range(n_stations):
      t = s / (n_stations - 1)
      # Span from r = 0.0055m to exact r = 0.0750m (so 2 * 0.0750 = 0.150m tip to tip)
      r = 0.0055 + t * (0.0750 - 0.0055)
      # Scimitar chord shape (wider mid-blade, tapered root and tip)
      if t < 0.25:
        chord = 0.0075 + (t / 0.25) * 0.0090
      elif t < 0.75:
        chord = 0.0165 - ((t - 0.25) / 0.50) * 0.0025
      else:
        chord = 0.0140 * (1.0 - 0.58 * ((t - 0.75) / 0.25) ** 1.3)

      # Twist pitch angle from 22 deg at root to 7 deg at tip
      pitch = math.radians(22.0 * (1.0 - 0.68 * t))
      sweep = 0.0022 * math.sin(t * math.pi) - (0.0018 * ((t - 0.7) / 0.3) ** 2 if t > 0.7 else 0.0)
      z_camber = 0.0024 + 0.0012 * t
      thick_scale = 1.35 * (1.0 - 0.55 * t)

      cp = math.cos(pitch)
      sp = math.sin(pitch)
      ring = []
      for u_c, v_t in foil_pts:
        local_c = u_c * chord + sweep
        local_z = v_t * chord * thick_scale
        rot_c = local_c * cp - local_z * sp
        rot_z = local_c * sp + local_z * cp + z_camber
        wx = dir_x * r + perp_x * rot_c
        wy = dir_y * r + perp_y * rot_c
        wz = rot_z
        ring.append(bm.verts.new(Vector((wx, wy, wz))))
      blade_rings.append(ring)

    n_foil = len(foil_pts)
    for s in range(n_stations - 1):
      for i in range(n_foil):
        ni = (i + 1) % n_foil
        f = bm.faces.new([
            blade_rings[s][i],
            blade_rings[s][ni],
            blade_rings[s + 1][ni],
            blade_rings[s + 1][i],
        ])
        f.material_index = mat_rotor
        f.smooth = True

    # Cap blade root and tip cleanly
    f_root = bm.faces.new(list(reversed(blade_rings[0])))
    f_root.material_index = mat_rotor
    f_root.smooth = False
    f_tip = bm.faces.new(blade_rings[-1])
    f_tip.material_index = mat_rotor
    f_tip.smooth = False

  bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
  bm.to_mesh(mesh)
  bm.free()
  mesh.update()

  obj.location = hub_location
  return obj


def main():
  clear_scene()
  out_fbx, out_png, out_dir = get_output_paths()

  # Create procedural Principled materials with wear (scratches, rust streaks, dust, Z-gradient dirt)
  mat_body_grey = create_weathered_material(
      "Drone_Body_LightGrey",
      base_color=(0.70, 0.72, 0.74, 1.0),
      roughness=0.42,
      metallic=0.0,
      scratch_strength=0.22,
      dirt_strength=0.38,
      rust_strength=0.16,
      bump_strength=0.14,
  )
  mat_accent_dark = create_weathered_material(
      "Drone_Accent_DarkGrey",
      base_color=(0.14, 0.15, 0.17, 1.0),
      roughness=0.55,
      metallic=0.05,
      scratch_strength=0.25,
      dirt_strength=0.45,
      rust_strength=0.18,
      bump_strength=0.18,
  )
  mat_gimbal_metal = create_weathered_material(
      "Drone_Gimbal_Metal",
      base_color=(0.20, 0.22, 0.25, 1.0),
      roughness=0.32,
      metallic=0.85,
      scratch_strength=0.30,
      dirt_strength=0.28,
      rust_strength=0.24,
      bump_strength=0.12,
  )
  mat_lens_glass = create_weathered_material(
      "Drone_Lens_Glass",
      base_color=(0.03, 0.05, 0.09, 1.0),
      roughness=0.08,
      metallic=0.15,
      scratch_strength=0.10,
      dirt_strength=0.12,
      rust_strength=0.04,
      bump_strength=0.04,
  )
  mat_led_green = create_weathered_material(
      "Drone_LED_Green",
      base_color=(0.08, 0.92, 0.24, 1.0),
      roughness=0.22,
      metallic=0.0,
      scratch_strength=0.08,
      dirt_strength=0.10,
      rust_strength=0.02,
      bump_strength=0.05,
  )
  mat_white_print = create_weathered_material(
      "Drone_White_Print",
      base_color=(0.95, 0.95, 0.96, 1.0),
      roughness=0.36,
      metallic=0.0,
      scratch_strength=0.18,
      dirt_strength=0.20,
      rust_strength=0.10,
      bump_strength=0.08,
  )
  mat_rotor_plastic = create_weathered_material(
      "Drone_Rotor_Plastic",
      base_color=(0.32, 0.34, 0.37, 1.0),
      roughness=0.28,
      metallic=0.0,
      scratch_strength=0.26,
      dirt_strength=0.22,
      rust_strength=0.12,
      bump_strength=0.12,
      alpha=0.88,
  )

  all_materials = [
      mat_body_grey,
      mat_accent_dark,
      mat_gimbal_metal,
      mat_lens_glass,
      mat_led_green,
      mat_white_print,
      mat_rotor_plastic,
  ]
  idx_body = 0
  idx_dark = 1
  idx_metal = 2
  idx_lens = 3
  idx_led = 4
  idx_white = 5
  idx_rotor = 6

  # Rotor hub coordinates on a 0.25m diagonal (distance from (0,0) = 0.125m -> X = +-0.08839m, Y = +-0.08839m)
  d_xy = 0.125 / math.sqrt(2.0)  # 0.088388 m
  rotor_hubs = [
      ("Rotor1", -d_xy, -d_xy, 0.055, True),
      ("Rotor2", d_xy, -d_xy, 0.055, True),
      ("Rotor3", -d_xy, d_xy, 0.047, False),
      ("Rotor4", d_xy, d_xy, 0.047, False),
  ]

  # Build "Body" (body + folding arms + gimbal + sensors + feet + LEDs + PIP print)
  body_mesh = bpy.data.meshes.new("Body_Mesh")
  body_obj = bpy.data.objects.new("Body", body_mesh)
  bpy.context.collection.objects.link(body_obj)
  for m in all_materials:
    body_obj.data.materials.append(m)

  bm = bmesh.new()
  build_fuselage(bm, idx_body, idx_dark, idx_metal, idx_white)
  build_pip_lettering(bm, idx_white)
  build_obstacle_sensors(bm, idx_body, idx_dark, idx_metal, idx_lens)
  build_gimbal_and_camera(bm, idx_body, idx_dark, idx_metal, idx_lens)
  build_arms_feet_and_motors(
      bm, rotor_hubs, idx_body, idx_dark, idx_metal, idx_led
  )
  build_screws(bm, rotor_hubs, idx_metal, idx_dark)

  bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
  bm.to_mesh(body_mesh)
  bm.free()
  body_mesh.update()

  # Build 4 separate propeller objects ("Rotor1" .. "Rotor4") parented to Body
  rotor_objs = []
  yaw_angles = [0.35, -0.42, -0.28, 0.50]
  spin_dirs = [1.0, -1.0, -1.0, 1.0]
  for i, (rname, hx, hy, hz, _) in enumerate(rotor_hubs):
    r_obj = create_rotor_object(
        rname,
        Vector((hx, hy, hz)),
        yaw_angles[i],
        spin_dirs[i],
        all_materials,
        idx_rotor,
        idx_dark,
        idx_metal,
    )
    r_obj.parent = body_obj
    rotor_objs.append(r_obj)

  all_objs = [body_obj] + rotor_objs

  # Select all 5 objects and UV unwrap into shared non-overlapping UV space
  bpy.ops.object.select_all(action="DESELECT")
  for o in all_objs:
    o.select_set(True)
  bpy.context.view_layer.objects.active = body_obj

  bpy.ops.object.mode_set(mode="EDIT")
  bpy.ops.mesh.select_all(action="SELECT")
  bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.01)
  bpy.ops.uv.average_islands_scale()
  bpy.ops.uv.pack_islands(margin=0.01)
  bpy.ops.object.mode_set(mode="OBJECT")

  # Create 2048x2048 bake images: "Drone_albedo" and "Drone_normal" (Non-Color)
  img_albedo = bpy.data.images.new(
      "Drone_albedo", width=2048, height=2048, alpha=False
  )
  img_normal = bpy.data.images.new(
      "Drone_normal", width=2048, height=2048, alpha=False
  )
  img_normal.colorspace_settings.name = "Non-Color"

  # Add Image Texture node to EVERY material
  mat_tex_nodes = {}
  for mat in all_materials:
    nt = mat.node_tree
    tex_node = nt.nodes.new("ShaderNodeTexImage")
    tex_node.location = (600, 320)
    mat_tex_nodes[mat.name] = tex_node

  scene = bpy.context.scene
  scene.render.engine = "CYCLES"
  scene.cycles.device = "CPU"
  scene.cycles.samples = 16
  scene.render.bake.margin = 8
  scene.render.bake.use_selected_to_active = False
  scene.render.bake.use_clear = True

  # Ensure all 5 objects are selected for baking
  bpy.ops.object.select_all(action="DESELECT")
  for o in all_objs:
    o.select_set(True)
  bpy.context.view_layer.objects.active = body_obj

  # 1. Bake DIFFUSE (pass_filter {'COLOR'}) into Drone_albedo
  for mat in all_materials:
    nt = mat.node_tree
    tn = mat_tex_nodes[mat.name]
    tn.image = img_albedo
    for n in nt.nodes:
      n.select = False
    tn.select = True
    nt.nodes.active = tn

  scene.render.bake.use_pass_direct = False
  scene.render.bake.use_pass_indirect = False
  scene.render.bake.use_pass_color = True
  bpy.ops.object.bake(
      type="DIFFUSE", pass_filter={"COLOR"}, margin=8, use_clear=True
  )

  albedo_path = os.path.join(out_dir, "Drone_albedo.png")
  img_albedo.filepath_raw = albedo_path
  img_albedo.file_format = "PNG"
  img_albedo.save()

  # 2. Bake NORMAL (tangent) into Drone_normal
  for mat in all_materials:
    nt = mat.node_tree
    tn = mat_tex_nodes[mat.name]
    tn.image = img_normal
    for n in nt.nodes:
      n.select = False
    tn.select = True
    nt.nodes.active = tn

  scene.render.bake.normal_space = "TANGENT"
  bpy.ops.object.bake(
      type="NORMAL", normal_space="TANGENT", margin=8, use_clear=True
  )

  normal_path = os.path.join(out_dir, "Drone_normal.png")
  img_normal.filepath_raw = normal_path
  img_normal.file_format = "PNG"
  img_normal.save()

  # Replace all slots with ONE material "Drone_Mat"
  drone_mat = bpy.data.materials.new(name="Drone_Mat")
  drone_mat.use_nodes = True
  d_nt = drone_mat.node_tree
  d_nodes = d_nt.nodes
  d_links = d_nt.links
  d_nodes.clear()

  d_out = d_nodes.new("ShaderNodeOutputMaterial")
  d_out.location = (400, 0)

  d_bsdf = d_nodes.new("ShaderNodeBsdfPrincipled")
  d_bsdf.location = (100, 0)
  d_bsdf.inputs["Roughness"].default_value = 0.6
  d_links.new(d_bsdf.outputs["BSDF"], d_out.inputs["Surface"])

  d_tex_alb = d_nodes.new("ShaderNodeTexImage")
  d_tex_alb.location = (-350, 150)
  d_tex_alb.image = img_albedo
  d_links.new(d_tex_alb.outputs["Color"], d_bsdf.inputs["Base Color"])

  d_tex_nrm = d_nodes.new("ShaderNodeTexImage")
  d_tex_nrm.location = (-550, -180)
  d_tex_nrm.image = img_normal
  img_normal.colorspace_settings.name = "Non-Color"

  d_nrm_map = d_nodes.new("ShaderNodeNormalMap")
  d_nrm_map.location = (-200, -180)
  d_links.new(d_tex_nrm.outputs["Color"], d_nrm_map.inputs["Color"])
  d_links.new(d_nrm_map.outputs["Normal"], d_bsdf.inputs["Normal"])

  for o in all_objs:
    o.data.materials.clear()
    o.data.materials.append(drone_mat)
    for poly in o.data.polygons:
      poly.material_index = 0

  # Calculate and print total triangle count
  total_tris = 0
  for o in all_objs:
    o.data.calc_loop_triangles()
    total_tris += len(o.data.loop_triangles)
  print("TRIS", total_tris)

  # Export FBX: selected only, apply transforms, axis_forward='-Z', axis_up='Y', path_mode='COPY', embed_textures=True
  bpy.ops.object.select_all(action="DESELECT")
  for o in all_objs:
    o.select_set(True)
  bpy.context.view_layer.objects.active = body_obj
  bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

  bpy.ops.export_scene.fbx(
      filepath=out_fbx,
      use_selection=True,
      bake_space_transform=True,
      axis_forward="-Z",
      axis_up="Y",
      path_mode="COPY",
      embed_textures=True,
  )

  # Set up Preview Render: 900x900, EEVEE, grey sky strength 0.6, sun strength 3 from front-left-above, camera 0.6 m away
  engine_keys = list(
      scene.render.bl_rna.properties["engine"].enum_items.keys()
  )
  eevee_engines = [k for k in engine_keys if "EEVEE" in k]
  if eevee_engines:
    scene.render.engine = eevee_engines[0]

  world = bpy.data.worlds.new("PreviewWorld")
  scene.world = world
  world.use_nodes = True
  w_nodes = world.node_tree.nodes
  w_links = world.node_tree.links
  w_nodes.clear()
  w_out = w_nodes.new("ShaderNodeOutputWorld")
  w_bg = w_nodes.new("ShaderNodeBackground")
  w_bg.inputs["Color"].default_value = (0.52, 0.54, 0.57, 1.0)
  w_bg.inputs["Strength"].default_value = 0.6
  w_links.new(w_bg.outputs["Background"], w_out.inputs["Surface"])

  # Sun light strength 3 from front-left-above (-X, -Y, +Z pointing at drone)
  sun_data = bpy.data.lights.new(name="SunLight", type="SUN")
  sun_data.energy = 3.0
  sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
  bpy.context.collection.objects.link(sun_obj)
  sun_obj.location = Vector((-1.5, -2.0, 2.5))
  sun_dir = Vector((0.0, 0.0, 0.03)) - sun_obj.location
  sun_obj.rotation_euler = sun_dir.to_track_quat("-Z", "Y").to_euler()

  # Camera 0.6 m away in a front 3/4 view framing the whole drone
  target_pt = Vector((0.0, 0.0, 0.035))
  cam_dir = Vector((-0.58, -0.68, 0.45)).normalized()
  cam_pos = target_pt + cam_dir * 0.60

  cam_data = bpy.data.cameras.new(name="PreviewCamera")
  cam_data.lens = 85.0
  cam_data.clip_start = 0.01
  cam_data.clip_end = 50.0
  cam_obj = bpy.data.objects.new(name="PreviewCamera", object_data=cam_data)
  bpy.context.collection.objects.link(cam_obj)
  cam_obj.location = cam_pos
  look_vec = target_pt - cam_pos
  cam_obj.rotation_euler = look_vec.to_track_quat("-Z", "Y").to_euler()
  scene.camera = cam_obj

  scene.render.resolution_x = 900
  scene.render.resolution_y = 900
  scene.render.resolution_percentage = 100
  scene.render.image_settings.file_format = "PNG"
  scene.render.filepath = out_png
  bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
  main()

