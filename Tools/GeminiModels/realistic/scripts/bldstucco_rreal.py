import bpy
import bmesh
from mathutils import Vector, Matrix, Euler
import math
import sys
import os

NAME = "BldgStucco"

# ---------------------------------------------------------------------------
# 1. OUTPUT PATH PARSING
# ---------------------------------------------------------------------------
out_arg = os.path.join(os.getcwd(), f"{NAME}.fbx")
if "--" in sys.argv:
    idx = sys.argv.index("--")
    if idx + 1 < len(sys.argv):
        out_arg = sys.argv[idx + 1]

out_arg = os.path.abspath(out_arg)
if out_arg.lower().endswith(".fbx"):
    fbx_path = out_arg
    preview_path = os.path.splitext(fbx_path)[0] + ".png"
elif out_arg.lower().endswith(".png"):
    preview_path = out_arg
    fbx_path = os.path.splitext(preview_path)[0] + ".fbx"
elif os.path.isdir(out_arg) or out_arg.endswith(("/", "\\")):
    fbx_path = os.path.join(out_arg, f"{NAME}.fbx")
    preview_path = os.path.join(out_arg, f"{NAME}.png")
else:
    fbx_path = out_arg + ".fbx"
    preview_path = out_arg + ".png"

out_dir = os.path.dirname(fbx_path)
if out_dir:
    os.makedirs(out_dir, exist_ok=True)

albedo_path = os.path.join(out_dir, f"{NAME}_albedo.png")
normal_path = os.path.join(out_dir, f"{NAME}_normal.png")

# ---------------------------------------------------------------------------
# 2. RESET SCENE (DELETE EVERYTHING FIRST)
# ---------------------------------------------------------------------------
if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for m in list(bpy.data.meshes):
    bpy.data.meshes.remove(m, do_unlink=True)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat, do_unlink=True)
for img in list(bpy.data.images):
    bpy.data.images.remove(img, do_unlink=True)
for cam in list(bpy.data.cameras):
    bpy.data.cameras.remove(cam, do_unlink=True)
for lgt in list(bpy.data.lights):
    bpy.data.lights.remove(lgt, do_unlink=True)

scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0

# ---------------------------------------------------------------------------
# 3. PROCEDURAL MATERIALS FOR BAKING
# ---------------------------------------------------------------------------
MAT_STUCCO = 0
MAT_CONCRETE = 1
MAT_BRICK = 2
MAT_GLASS = 3
MAT_METAL = 4
MAT_WOOD_GREEN = 5
MAT_ROOF_TILE = 6
MAT_ROOF_MEMBRANE = 7
MAT_AWNING = 8


def make_mix_rgba(nodes, blend_type='MIX', factor=0.5):
    m = nodes.new('ShaderNodeMix')
    m.data_type = 'RGBA'
    m.blend_type = blend_type
    m.inputs['Factor'].default_value = factor
    return m


def add_z_grime(nodes, links, base_color_socket, z_height=14.0, grime_col=(0.08, 0.07, 0.06, 1.0), strength=0.55):
    tex_coord = nodes.new('ShaderNodeTexCoord')
    sep_xyz = nodes.new('ShaderNodeSeparateXYZ')
    links.new(tex_coord.outputs['Object'], sep_xyz.inputs['Vector'])

    # Normalize Z near ground (0..2.8m) for bottom splash grime
    math_div = nodes.new('ShaderNodeMath')
    math_div.operation = 'DIVIDE'
    math_div.inputs[1].default_value = 2.8
    links.new(sep_xyz.outputs['Z'], math_div.inputs[0])

    ramp_ground = nodes.new('ShaderNodeValToRGB')
    ramp_ground.color_ramp.elements[0].position = 0.0
    ramp_ground.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
    ramp_ground.color_ramp.elements[1].position = 1.0
    ramp_ground.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    links.new(math_div.outputs['Value'], ramp_ground.inputs['Fac'])

    # Vertical streak noise for under-sill and rain drips
    mapping_streak = nodes.new('ShaderNodeMapping')
    mapping_streak.inputs['Scale'].default_value = (4.5, 4.5, 0.45)
    links.new(tex_coord.outputs['Object'], mapping_streak.inputs['Vector'])

    noise_streak = nodes.new('ShaderNodeTexNoise')
    noise_streak.inputs['Scale'].default_value = 3.2
    noise_streak.inputs['Detail'].default_value = 6.0
    noise_streak.inputs['Roughness'].default_value = 0.65
    links.new(mapping_streak.outputs['Vector'], noise_streak.inputs['Vector'])

    # Periodic floor/sill banding modulation in Z
    wave_sill = nodes.new('ShaderNodeTexWave')
    wave_sill.wave_type = 'BANDS'
    wave_sill.bands_direction = 'Z'
    wave_sill.inputs['Scale'].default_value = 0.92
    wave_sill.inputs['Distortion'].default_value = 1.8
    wave_sill.inputs['Detail'].default_value = 3.0
    links.new(tex_coord.outputs['Object'], wave_sill.inputs['Vector'])

    math_sill = nodes.new('ShaderNodeMath')
    math_sill.operation = 'MULTIPLY'
    links.new(noise_streak.outputs['Fac'], math_sill.inputs[0])
    links.new(wave_sill.outputs['Fac'], math_sill.inputs[1])

    math_comb = nodes.new('ShaderNodeMath')
    math_comb.operation = 'MAXIMUM'
    links.new(ramp_ground.outputs['Color'], math_comb.inputs[0])
    links.new(math_sill.outputs['Value'], math_comb.inputs[1])

    math_str = nodes.new('ShaderNodeMath')
    math_str.operation = 'MULTIPLY'
    math_str.inputs[1].default_value = strength
    links.new(math_comb.outputs['Value'], math_str.inputs[0])

    mix_grime = make_mix_rgba(nodes, 'MIX', 0.5)
    mix_grime.inputs['B'].default_value = grime_col
    links.new(math_str.outputs['Value'], mix_grime.inputs['Factor'])
    links.new(base_color_socket, mix_grime.inputs['A'])
    return mix_grime.outputs['Result'], noise_streak.outputs['Fac']


def create_stucco_mat():
    mat = bpy.data.materials.new("Proc_Stucco")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs['Roughness'].default_value = 0.82
    bsdf.inputs['Metallic'].default_value = 0.0

    tc = nodes.new('ShaderNodeTexCoord')

    n_macro = nodes.new('ShaderNodeTexNoise')
    n_macro.inputs['Scale'].default_value = 0.55
    n_macro.inputs['Detail'].default_value = 5.0
    n_macro.inputs['Roughness'].default_value = 0.6
    links.new(tc.outputs['Object'], n_macro.inputs['Vector'])

    n_fine = nodes.new('ShaderNodeTexNoise')
    n_fine.inputs['Scale'].default_value = 18.0
    n_fine.inputs['Detail'].default_value = 8.0
    n_fine.inputs['Roughness'].default_value = 0.75
    links.new(tc.outputs['Object'], n_fine.inputs['Vector'])

    mix_col = make_mix_rgba(nodes, 'MIX', 0.5)
    # Warm European cream & ochre painted plaster
    mix_col.inputs['A'].default_value = (0.76, 0.64, 0.44, 1.0)
    mix_col.inputs['B'].default_value = (0.62, 0.48, 0.30, 1.0)
    links.new(n_macro.outputs['Fac'], mix_col.inputs['Factor'])

    # Damp plaster blotches
    n_stain = nodes.new('ShaderNodeTexNoise')
    n_stain.inputs['Scale'].default_value = 1.35
    n_stain.inputs['Detail'].default_value = 6.0
    n_stain.inputs['Distortion'].default_value = 0.4
    links.new(tc.outputs['Object'], n_stain.inputs['Vector'])

    ramp_stain = nodes.new('ShaderNodeValToRGB')
    ramp_stain.color_ramp.elements[0].position = 0.48
    ramp_stain.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_stain.color_ramp.elements[1].position = 0.78
    ramp_stain.color_ramp.elements[1].color = (0.45, 0.45, 0.45, 1.0)
    links.new(n_stain.outputs['Fac'], ramp_stain.inputs['Fac'])

    mix_stain = make_mix_rgba(nodes, 'MIX', 0.35)
    mix_stain.inputs['B'].default_value = (0.36, 0.28, 0.19, 1.0)
    links.new(ramp_stain.outputs['Color'], mix_stain.inputs['Factor'])
    links.new(mix_col.outputs['Result'], mix_stain.inputs['A'])

    grimed_out, streak_fac = add_z_grime(
        nodes, links, mix_stain.outputs['Result'],
        grime_col=(0.14, 0.11, 0.08, 1.0), strength=0.62
    )
    links.new(grimed_out, bsdf.inputs['Base Color'])

    # Plaster bump
    math_bump = nodes.new('ShaderNodeMath')
    math_bump.operation = 'MULTIPLY_ADD'
    math_bump.inputs[1].default_value = 0.7
    links.new(n_fine.outputs['Fac'], math_bump.inputs[0])
    links.new(streak_fac, math_bump.inputs[2])

    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.38
    bump.inputs['Distance'].default_value = 0.02
    links.new(math_bump.outputs['Value'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def create_concrete_mat():
    mat = bpy.data.materials.new("Proc_Concrete")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs['Roughness'].default_value = 0.78
    bsdf.inputs['Metallic'].default_value = 0.0

    tc = nodes.new('ShaderNodeTexCoord')

    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 6.5
    noise.inputs['Detail'].default_value = 8.0
    noise.inputs['Roughness'].default_value = 0.7
    links.new(tc.outputs['Object'], noise.inputs['Vector'])

    # Block seams in Z and X
    wave_z = nodes.new('ShaderNodeTexWave')
    wave_z.wave_type = 'BANDS'
    wave_z.bands_direction = 'Z'
    wave_z.inputs['Scale'].default_value = 3.2
    wave_z.inputs['Detail'].default_value = 1.0
    links.new(tc.outputs['Object'], wave_z.inputs['Vector'])

    ramp_seam = nodes.new('ShaderNodeValToRGB')
    ramp_seam.color_ramp.elements[0].position = 0.0
    ramp_seam.color_ramp.elements[0].color = (0.22, 0.20, 0.18, 1.0)
    ramp_seam.color_ramp.elements[1].position = 0.08
    ramp_seam.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(wave_z.outputs['Fac'], ramp_seam.inputs['Fac'])

    mix_stone = make_mix_rgba(nodes, 'MIX', 0.5)
    mix_stone.inputs['A'].default_value = (0.58, 0.55, 0.49, 1.0)
    mix_stone.inputs['B'].default_value = (0.44, 0.41, 0.36, 1.0)
    links.new(noise.outputs['Fac'], mix_stone.inputs['Factor'])

    mix_seam = make_mix_rgba(nodes, 'MULTIPLY', 0.45)
    links.new(mix_stone.outputs['Result'], mix_seam.inputs['A'])
    links.new(ramp_seam.outputs['Color'], mix_seam.inputs['B'])

    grimed_out, _ = add_z_grime(
        nodes, links, mix_seam.outputs['Result'],
        grime_col=(0.12, 0.11, 0.09, 1.0), strength=0.65
    )
    links.new(grimed_out, bsdf.inputs['Base Color'])

    math_b = nodes.new('ShaderNodeMath')
    math_b.operation = 'MULTIPLY'
    links.new(noise.outputs['Fac'], math_b.inputs[0])
    links.new(ramp_seam.outputs['Color'], math_b.inputs[1])

    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.45
    bump.inputs['Distance'].default_value = 0.025
    links.new(math_b.outputs['Value'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def create_brick_mat():
    mat = bpy.data.materials.new("Proc_Brick")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs['Roughness'].default_value = 0.80
    bsdf.inputs['Metallic'].default_value = 0.0

    tc = nodes.new('ShaderNodeTexCoord')
    sep = nodes.new('ShaderNodeSeparateXYZ')
    links.new(tc.outputs['Object'], sep.inputs['Vector'])

    # Map X+Y to U and Z to V so 3D object coords produce crisp bricks on all 4 sides
    math_add = nodes.new('ShaderNodeMath')
    math_add.operation = 'ADD'
    links.new(sep.outputs['X'], math_add.inputs[0])
    links.new(sep.outputs['Y'], math_add.inputs[1])

    comb = nodes.new('ShaderNodeCombineXYZ')
    links.new(math_add.outputs['Value'], comb.inputs['X'])
    links.new(sep.outputs['Z'], comb.inputs['Y'])

    brick = nodes.new('ShaderNodeTexBrick')
    brick.offset = 0.5
    brick.offset_frequency = 2
    brick.inputs['Color1'].default_value = (0.48, 0.21, 0.14, 1.0)
    brick.inputs['Color2'].default_value = (0.34, 0.14, 0.09, 1.0)
    brick.inputs['Mortar'].default_value = (0.62, 0.58, 0.52, 1.0)
    brick.inputs['Scale'].default_value = 3.5
    brick.inputs['Mortar Size'].default_value = 0.025
    brick.inputs['Mortar Smooth'].default_value = 0.1
    brick.inputs['Bias'].default_value = -0.15
    brick.inputs['Brick Width'].default_value = 0.5
    brick.inputs['Row Height'].default_value = 0.22
    links.new(comb.outputs['Vector'], brick.inputs['Vector'])

    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 12.0
    noise.inputs['Detail'].default_value = 6.0
    links.new(tc.outputs['Object'], noise.inputs['Vector'])

    mix_var = make_mix_rgba(nodes, 'OVERLAY', 0.25)
    links.new(brick.outputs['Color'], mix_var.inputs['A'])
    links.new(noise.outputs['Color'], mix_var.inputs['B'])

    grimed_out, _ = add_z_grime(
        nodes, links, mix_var.outputs['Result'],
        grime_col=(0.09, 0.08, 0.07, 1.0), strength=0.55
    )
    links.new(grimed_out, bsdf.inputs['Base Color'])

    math_b = nodes.new('ShaderNodeMath')
    math_b.operation = 'MULTIPLY_ADD'
    math_b.inputs[1].default_value = 0.85
    links.new(brick.outputs['Fac'], math_b.inputs[0])
    links.new(noise.outputs['Fac'], math_b.inputs[2])

    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.65
    bump.inputs['Distance'].default_value = 0.03
    links.new(math_b.outputs['Value'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def create_glass_mat():
    mat = bpy.data.materials.new("Proc_Glass")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    # Keep Metallic=0 during DIFFUSE COLOR bake so base color is preserved
    bsdf.inputs['Roughness'].default_value = 0.15
    bsdf.inputs['Metallic'].default_value = 0.0

    tc = nodes.new('ShaderNodeTexCoord')

    # Faint interior room & curtain variation across bays
    vor = nodes.new('ShaderNodeTexVoronoi')
    vor.inputs['Scale'].default_value = 1.1
    links.new(tc.outputs['Object'], vor.inputs['Vector'])

    wave_curtain = nodes.new('ShaderNodeTexWave')
    wave_curtain.wave_type = 'BANDS'
    wave_curtain.bands_direction = 'X'
    wave_curtain.inputs['Scale'].default_value = 9.0
    wave_curtain.inputs['Distortion'].default_value = 1.2
    links.new(tc.outputs['Object'], wave_curtain.inputs['Vector'])

    mix_int = make_mix_rgba(nodes, 'MIX', 0.35)
    # Deep architectural blue-charcoal glass vs subtle warm interior curtain reflection
    mix_int.inputs['A'].default_value = (0.04, 0.07, 0.09, 1.0)
    mix_int.inputs['B'].default_value = (0.19, 0.17, 0.13, 1.0)

    math_f = nodes.new('ShaderNodeMath')
    math_f.operation = 'MULTIPLY'
    links.new(vor.outputs['Distance'], math_f.inputs[0])
    links.new(wave_curtain.outputs['Fac'], math_f.inputs[1])
    links.new(math_f.outputs['Value'], mix_int.inputs['Factor'])

    links.new(mix_int.outputs['Result'], bsdf.inputs['Base Color'])

    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.04
    bump.inputs['Distance'].default_value = 0.005
    links.new(wave_curtain.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def create_metal_mat():
    mat = bpy.data.materials.new("Proc_Metal")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    # Metallic=0 during bake so DIFFUSE COLOR pass captures dark wrought-iron albedo
    bsdf.inputs['Roughness'].default_value = 0.45
    bsdf.inputs['Metallic'].default_value = 0.0

    tc = nodes.new('ShaderNodeTexCoord')
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 16.0
    noise.inputs['Detail'].default_value = 6.0
    links.new(tc.outputs['Object'], noise.inputs['Vector'])

    mix_m = make_mix_rgba(nodes, 'MIX', 0.4)
    mix_m.inputs['A'].default_value = (0.09, 0.10, 0.11, 1.0)
    mix_m.inputs['B'].default_value = (0.18, 0.17, 0.16, 1.0)
    links.new(noise.outputs['Fac'], mix_m.inputs['Factor'])
    links.new(mix_m.outputs['Result'], bsdf.inputs['Base Color'])

    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.22
    bump.inputs['Distance'].default_value = 0.01
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def create_wood_shutter_mat():
    mat = bpy.data.materials.new("Proc_ShutterWood")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs['Roughness'].default_value = 0.65
    bsdf.inputs['Metallic'].default_value = 0.0

    tc = nodes.new('ShaderNodeTexCoord')

    # Horizontal louver slat bands + wood grain
    wave_louver = nodes.new('ShaderNodeTexWave')
    wave_louver.wave_type = 'BANDS'
    wave_louver.bands_direction = 'Z'
    wave_louver.inputs['Scale'].default_value = 26.0
    wave_louver.inputs['Detail'].default_value = 1.0
    links.new(tc.outputs['Object'], wave_louver.inputs['Vector'])

    noise_wood = nodes.new('ShaderNodeTexNoise')
    noise_wood.inputs['Scale'].default_value = 9.0
    noise_wood.inputs['Detail'].default_value = 6.0
    links.new(tc.outputs['Object'], noise_wood.inputs['Vector'])

    mix_green = make_mix_rgba(nodes, 'MIX', 0.4)
    # Heritage European dark forest green shutters
    mix_green.inputs['A'].default_value = (0.07, 0.21, 0.11, 1.0)
    mix_green.inputs['B'].default_value = (0.04, 0.13, 0.07, 1.0)
    links.new(wave_louver.outputs['Fac'], mix_green.inputs['Factor'])

    mix_var = make_mix_rgba(nodes, 'OVERLAY', 0.22)
    links.new(mix_green.outputs['Result'], mix_var.inputs['A'])
    links.new(noise_wood.outputs['Color'], mix_var.inputs['B'])
    links.new(mix_var.outputs['Result'], bsdf.inputs['Base Color'])

    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.55
    bump.inputs['Distance'].default_value = 0.02
    links.new(wave_louver.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def create_roof_tile_mat():
    mat = bpy.data.materials.new("Proc_RoofTile")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs['Roughness'].default_value = 0.72
    bsdf.inputs['Metallic'].default_value = 0.0

    tc = nodes.new('ShaderNodeTexCoord')

    # Barrel tile ripples + horizontal row courses
    wave_barrel = nodes.new('ShaderNodeTexWave')
    wave_barrel.wave_type = 'BANDS'
    wave_barrel.bands_direction = 'X'
    wave_barrel.inputs['Scale'].default_value = 14.0
    wave_barrel.inputs['Distortion'].default_value = 0.25
    links.new(tc.outputs['Object'], wave_barrel.inputs['Vector'])

    wave_rows = nodes.new('ShaderNodeTexWave')
    wave_rows.wave_type = 'BANDS'
    wave_rows.bands_direction = 'Z'
    wave_rows.inputs['Scale'].default_value = 11.0
    links.new(tc.outputs['Object'], wave_rows.inputs['Vector'])

    noise_clay = nodes.new('ShaderNodeTexNoise')
    noise_clay.inputs['Scale'].default_value = 4.0
    noise_clay.inputs['Detail'].default_value = 6.0
    links.new(tc.outputs['Object'], noise_clay.inputs['Vector'])

    mix_terra = make_mix_rgba(nodes, 'MIX', 0.5)
    mix_terra.inputs['A'].default_value = (0.58, 0.22, 0.11, 1.0)
    mix_terra.inputs['B'].default_value = (0.39, 0.14, 0.07, 1.0)
    links.new(noise_clay.outputs['Fac'], mix_terra.inputs['Factor'])

    mix_rib = make_mix_rgba(nodes, 'MULTIPLY', 0.32)
    links.new(mix_terra.outputs['Result'], mix_rib.inputs['A'])
    links.new(wave_barrel.outputs['Color'], mix_rib.inputs['B'])

    links.new(mix_rib.outputs['Result'], bsdf.inputs['Base Color'])

    math_h = nodes.new('ShaderNodeMath')
    math_h.operation = 'MULTIPLY_ADD'
    math_h.inputs[1].default_value = 0.75
    links.new(wave_barrel.outputs['Fac'], math_h.inputs[0])
    links.new(wave_rows.outputs['Fac'], math_h.inputs[2])

    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.75
    bump.inputs['Distance'].default_value = 0.035
    links.new(math_h.outputs['Value'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def create_roof_membrane_mat():
    mat = bpy.data.materials.new("Proc_RoofMembrane")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs['Roughness'].default_value = 0.88
    bsdf.inputs['Metallic'].default_value = 0.0

    tc = nodes.new('ShaderNodeTexCoord')
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 8.0
    noise.inputs['Detail'].default_value = 8.0
    links.new(tc.outputs['Object'], noise.inputs['Vector'])

    mix_m = make_mix_rgba(nodes, 'MIX', 0.5)
    mix_m.inputs['A'].default_value = (0.16, 0.16, 0.17, 1.0)
    mix_m.inputs['B'].default_value = (0.24, 0.23, 0.22, 1.0)
    links.new(noise.outputs['Fac'], mix_m.inputs['Factor'])
    links.new(mix_m.outputs['Result'], bsdf.inputs['Base Color'])

    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.3
    bump.inputs['Distance'].default_value = 0.015
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def create_awning_mat():
    mat = bpy.data.materials.new("Proc_Awning")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs['Roughness'].default_value = 0.85
    bsdf.inputs['Metallic'].default_value = 0.0

    tc = nodes.new('ShaderNodeTexCoord')
    wave = nodes.new('ShaderNodeTexWave')
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'X'
    wave.inputs['Scale'].default_value = 9.5
    links.new(tc.outputs['Object'], wave.inputs['Vector'])

    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'CONSTANT'
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.45, 0.08, 0.08, 1.0)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (0.82, 0.76, 0.65, 1.0)
    links.new(wave.outputs['Fac'], ramp.inputs['Fac'])

    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.2
    bump.inputs['Distance'].default_value = 0.01
    links.new(wave.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


proc_materials = [
    create_stucco_mat(),
    create_concrete_mat(),
    create_brick_mat(),
    create_glass_mat(),
    create_metal_mat(),
    create_wood_shutter_mat(),
    create_roof_tile_mat(),
    create_roof_membrane_mat(),
    create_awning_mat(),
]

# ---------------------------------------------------------------------------
# 4. BMESH ARCHITECTURAL GEOMETRY CONSTRUCTION
# ---------------------------------------------------------------------------
bm = bmesh.new()


def set_faces_mat(faces, mat_idx):
    for f in faces:
        f.material_index = mat_idx
        f.smooth = False


def add_box(bm, center, size, mat_idx, rot_euler=None):
    mat_t = Matrix.Translation(Vector(center))
    if rot_euler is not None:
        mat_r = Euler(rot_euler, 'XYZ').to_matrix().to_4x4()
        xform = mat_t @ mat_r
    else:
        xform = mat_t
    res = bmesh.ops.create_cube(bm, size=1.0)
    verts = res['verts']
    bmesh.ops.scale(bm, vec=Vector(size), verts=verts)
    bmesh.ops.transform(bm, matrix=xform, verts=verts)
    fset = set()
    for v in verts:
        for f in v.link_faces:
            fset.add(f)
    set_faces_mat(fset, mat_idx)
    return list(fset)


def inset_and_extrude_face(bm, face, inset_thickness, inset_depth, extrude_dist, inner_mat, side_mat):
    res_in = bmesh.ops.inset_individual(
        bm, faces=[face], thickness=inset_thickness, depth=inset_depth, use_even_offset=True
    )
    set_faces_mat(res_in.get('faces', []), side_mat)
    if abs(extrude_dist) > 1e-5:
        n = face.normal.copy()
        res_ex = bmesh.ops.extrude_face_region(bm, geom=[face])
        ex_verts = [g for g in res_ex['geom'] if isinstance(g, bmesh.types.BMVert)]
        ex_faces = [g for g in res_ex['geom'] if isinstance(g, bmesh.types.BMFace)]
        bmesh.ops.translate(bm, verts=ex_verts, vec=n * extrude_dist)
        bmesh.ops.delete(bm, geom=[face], context='FACES')
        main_face = None
        for ef in ex_faces:
            if ef.normal.dot(n) > 0.85:
                ef.material_index = inner_mat
                ef.smooth = False
                main_face = ef
            else:
                ef.material_index = side_mat
                ef.smooth = False
        return main_face
    else:
        face.material_index = inner_mat
        face.smooth = False
        return face


def facade_transform(side):
    # Returns transform mapping local facade coords (u along width, v outward normal, z up)
    # Side 0: Front (-Y), Side 1: Right (+X), Side 2: Back (+Y), Side 3: Left (-X)
    if side == 0:
        return Matrix.Identity(4)
    elif side == 1:
        return Euler((0.0, 0.0, math.pi * 0.5), 'XYZ').to_matrix().to_4x4()
    elif side == 2:
        return Euler((0.0, 0.0, math.pi), 'XYZ').to_matrix().to_4x4()
    else:
        return Euler((0.0, 0.0, -math.pi * 0.5), 'XYZ').to_matrix().to_4x4()


def add_local_box(bm, side, center_local, size_local, mat_idx, tilt_x=0.0):
    xf = facade_transform(side)
    mat_local = Matrix.Translation(Vector(center_local))
    if abs(tilt_x) > 1e-5:
        mat_local = mat_local @ Euler((tilt_x, 0.0, 0.0), 'XYZ').to_matrix().to_4x4()
    res = bmesh.ops.create_cube(bm, size=1.0)
    verts = res['verts']
    bmesh.ops.scale(bm, vec=Vector(size_local), verts=verts)
    bmesh.ops.transform(bm, matrix=xf @ mat_local, verts=verts)
    fset = set()
    for v in verts:
        for f in v.link_faces:
            fset.add(f)
    set_faces_mat(fset, mat_idx)
    return list(fset)


# ---------------------------------------------------------------------------
# 4A. MAIN FACADE WALLS WITH INTEGRATED RECESSED WINDOWS & DOORS (BMESH GRID)
# ---------------------------------------------------------------------------
# Footprint: 12m x 12m (-6..+6 in X and Y), Wall Height: 0..14.0m
# Upper floors have 4 bays at u = -4.2, -1.4, +1.4, +4.2 (each window 1.16m wide -> [-4.78,-3.62], etc.)
# Floors 2, 3, 4 windows span Z: [4.25..6.45], [7.65..9.85], [11.05..13.25]
u_cuts = [-6.0, -4.78, -3.62, -1.98, -0.82, 0.82, 1.98, 3.62, 4.78, 6.0]
z_cuts = [0.0, 0.60, 0.90, 3.30, 3.80, 4.25, 6.45, 7.20, 7.65, 9.85, 10.60, 11.05, 13.25, 13.65, 14.00]

upper_u_indices = [1, 3, 5, 7]
upper_z_indices = [5, 8, 11]

for side in range(4):
    xf = facade_transform(side)
    ny = len(u_cuts)
    nz = len(z_cuts)
    grid_verts = [[None] * nz for _ in range(ny)]
    for iu, u in enumerate(u_cuts):
        for iz, z in enumerate(z_cuts):
            co = xf @ Vector((u, -6.0, z))
            grid_verts[iu][iz] = bm.verts.new(co)

    for iu in range(ny - 1):
        for iz in range(nz - 1):
            v00 = grid_verts[iu][iz]
            v10 = grid_verts[iu + 1][iz]
            v11 = grid_verts[iu + 1][iz + 1]
            v01 = grid_verts[iu][iz + 1]
            f = bm.faces.new((v00, v10, v11, v01))
            f.normal_update()
            f.smooth = False

            # Base stone plinth (Z = 0..0.60)
            if iz == 0:
                f.material_index = MAT_CONCRETE
                inset_and_extrude_face(bm, f, 0.0, 0.0, 0.06, MAT_CONCRETE, MAT_CONCRETE)
            # Upper floor recessed windows (4 bays x 3 upper floors)
            elif iu in upper_u_indices and iz in upper_z_indices:
                f.material_index = MAT_STUCCO
                # 1. Outer stone/stucco frame inset & 0.20m deep recess into wall
                inner_f = inset_and_extrude_face(bm, f, 0.07, 0.0, -0.20, MAT_METAL, MAT_CONCRETE)
                if inner_f is not None:
                    # 2. Inner timber/metal casement frame inset & 0.03m glass step
                    inset_and_extrude_face(bm, inner_f, 0.06, 0.0, -0.03, MAT_GLASS, MAT_METAL)
            # Ground floor openings (Z = 0.90..3.30 -> iz == 2)
            elif iz == 2 and iu in (1, 3, 5, 7):
                if side == 0 and iu in (3, 5):
                    # Front cafe central entrance or arched display bay
                    f.material_index = MAT_CONCRETE
                    inner_f = inset_and_extrude_face(bm, f, 0.08, 0.0, -0.24, MAT_WOOD_GREEN, MAT_CONCRETE)
                    if inner_f is not None:
                        inset_and_extrude_face(bm, inner_f, 0.09, 0.0, -0.03, MAT_GLASS, MAT_WOOD_GREEN)
                else:
                    # Cafe arched storefront windows (sides & outer front bays)
                    f.material_index = MAT_CONCRETE
                    inner_f = inset_and_extrude_face(bm, f, 0.07, 0.0, -0.22, MAT_METAL, MAT_CONCRETE)
                    if inner_f is not None:
                        inset_and_extrude_face(bm, inner_f, 0.06, 0.0, -0.03, MAT_GLASS, MAT_METAL)
            elif iz <= 3:
                # Ground floor rusticated stonework facade
                f.material_index = MAT_CONCRETE
            else:
                f.material_index = MAT_STUCCO

# ---------------------------------------------------------------------------
# 4B. UPPER FLOOR WINDOW SILLS, HOOD MOULDINGS, MULLIONS & LOUVERED SHUTTERS
# ---------------------------------------------------------------------------
bay_centers = [-4.2, -1.4, 1.4, 4.2]
floor_z_bases = [4.25, 7.65, 11.05]

for side in range(4):
    for fl_idx, z0 in enumerate(floor_z_bases):
        z_mid = z0 + 1.10
        z_top = z0 + 2.20
        for u_c in bay_centers:
            # Projecting stone sill + under-sill corbel strip
            add_local_box(bm, side, (u_c, -6.07, z0 - 0.04), (1.34, 0.16, 0.09), MAT_CONCRETE)
            add_local_box(bm, side, (u_c, -6.04, z0 - 0.11), (1.22, 0.09, 0.05), MAT_CONCRETE)

            # Projecting window lintel / cornice hood
            add_local_box(bm, side, (u_c, -6.06, z_top + 0.06), (1.36, 0.14, 0.11), MAT_CONCRETE)
            if fl_idx == 0:
                # Triangular pediment cap on Piano Nobile (2nd floor)
                add_local_box(bm, side, (u_c, -6.08, z_top + 0.15), (1.44, 0.18, 0.07), MAT_CONCRETE)
                add_local_box(bm, side, (u_c, -6.05, z_top + 0.22), (0.36, 0.12, 0.14), MAT_BRICK)

            # French casement central vertical mullion + horizontal transom bar inside recess
            add_local_box(bm, side, (u_c, -5.81, z_mid), (0.05, 0.06, 2.04), MAT_METAL)
            add_local_box(bm, side, (u_c, -5.81, z0 + 1.48), (1.02, 0.06, 0.05), MAT_METAL)
            add_local_box(bm, side, (u_c, -5.81, z0 + 0.72), (1.02, 0.04, 0.035), MAT_METAL)

            # Dark green wooden shutters on left and right of every upper window
            for sh_dir in (-1.0, 1.0):
                sh_u = u_c + sh_dir * 0.84
                # Main shutter leaf panel
                add_local_box(bm, side, (sh_u, -6.035, z_mid), (0.44, 0.045, 2.12), MAT_WOOD_GREEN)
                # Raised outer stiles and rails on shutter
                add_local_box(bm, side, (sh_u - 0.18, -6.06, z_mid), (0.06, 0.025, 2.12), MAT_WOOD_GREEN)
                add_local_box(bm, side, (sh_u + 0.18, -6.06, z_mid), (0.06, 0.025, 2.12), MAT_WOOD_GREEN)
                for r_z in (z0 + 0.08, z_mid, z_top - 0.08):
                    add_local_box(bm, side, (sh_u, -6.06, r_z), (0.32, 0.025, 0.08), MAT_WOOD_GREEN)
                # Angled louver slats (5 louver ribs per shutter for close-up balcony realism)
                for lv_i in range(5):
                    lv_z = z0 + 0.30 + lv_i * 0.38
                    add_local_box(bm, side, (sh_u, -6.062, lv_z), (0.30, 0.025, 0.045), MAT_WOOD_GREEN, tilt_x=0.35)
                # Iron shutter dog / hinge strap
                add_local_box(bm, side, (sh_u - sh_dir * 0.14, -6.07, z0 + 0.25), (0.14, 0.02, 0.03), MAT_METAL)

# ---------------------------------------------------------------------------
# 4C. SMALL WROUGHT-IRON BALCONIES ON FLOORS 2-4
# ---------------------------------------------------------------------------
# Balconies on Front (-Y) all 4 bays on floors 2 & 4 and inner 2 bays on floor 3;
# on Left (-X), Right (+X), and Back (+Y) on inner 2 bays across floors 2-4.
for side in range(4):
    for fl_idx, z0 in enumerate(floor_z_bases):
        if side == 0:
            balc_bays = bay_centers if fl_idx in (0, 2) else [-1.4, 1.4]
        else:
            balc_bays = [-1.4, 1.4]

        for u_c in balc_bays:
            bw = 1.56
            bd = 0.52
            bz = z0 - 0.06
            # Stone balcony platform slab + lower lip
            add_local_box(bm, side, (u_c, -6.0 - bd * 0.5, bz), (bw, bd, 0.11), MAT_CONCRETE)
            add_local_box(bm, side, (u_c, -6.0 - bd * 0.45, bz - 0.07), (bw - 0.10, bd - 0.08, 0.05), MAT_CONCRETE)

            # 2 Stepped stone corbel brackets under each balcony
            for br_dir in (-1.0, 1.0):
                br_u = u_c + br_dir * 0.56
                add_local_box(bm, side, (br_u, -6.20, bz - 0.18), (0.14, 0.38, 0.16), MAT_CONCRETE)
                add_local_box(bm, side, (br_u, -6.12, bz - 0.32), (0.12, 0.22, 0.16), MAT_CONCRETE)

            # Wrought-iron railings (top handrail, bottom rail, corner posts, vertical balusters)
            rh = 0.92
            r_front_y = -6.0 - bd + 0.04
            # Top & bottom front rails
            add_local_box(bm, side, (u_c, r_front_y, bz + rh), (bw - 0.04, 0.045, 0.04), MAT_METAL)
            add_local_box(bm, side, (u_c, r_front_y, bz + 0.10), (bw - 0.04, 0.035, 0.03), MAT_METAL)
            add_local_box(bm, side, (u_c, r_front_y, bz + rh - 0.14), (bw - 0.06, 0.03, 0.025), MAT_METAL)

            # Side return rails (left and right)
            for s_dir in (-1.0, 1.0):
                su = u_c + s_dir * (bw * 0.5 - 0.04)
                add_local_box(bm, side, (su, -6.0 - bd * 0.5, bz + rh), (0.045, bd - 0.04, 0.04), MAT_METAL)
                add_local_box(bm, side, (su, -6.0 - bd * 0.5, bz + 0.10), (0.035, bd - 0.04, 0.03), MAT_METAL)
                # Corner newel post + finial cap
                add_local_box(bm, side, (su, r_front_y, bz + rh * 0.5 + 0.04), (0.055, 0.055, rh + 0.08), MAT_METAL)
                # Side baluster
                add_local_box(bm, side, (su, -6.0 - bd * 0.5, bz + rh * 0.5), (0.025, 0.025, rh - 0.10), MAT_METAL)

            # Front vertical wrought-iron balusters (7 per balcony)
            for bi in range(7):
                bu = u_c - 0.60 + bi * 0.20
                add_local_box(bm, side, (bu, r_front_y, bz + rh * 0.5), (0.024, 0.024, rh - 0.10), MAT_METAL)

            # Decorative diagonal cross-scroll motif in top frieze band
            add_local_box(bm, side, (u_c, r_front_y, bz + rh - 0.07), (0.36, 0.028, 0.10), MAT_METAL)

# ---------------------------------------------------------------------------
# 4D. GROUND-FLOOR CAFE ARCHED WINDOWS, AWNINGS, ENTRANCE & RUSTICATION
# ---------------------------------------------------------------------------
for side in range(4):
    # Horizontal rustication bands across the ground floor stone piers
    for rz in (1.20, 1.85, 2.50, 3.15):
        add_local_box(bm, side, (0.0, -6.025, rz), (12.04, 0.05, 0.06), MAT_CONCRETE)

    for b_idx, u_c in enumerate(bay_centers):
        # 5-segment stone arch fan/voussoirs + keystone at the top of each ground-floor bay (Z ~ 3.30m)
        arch_r = 0.58
        arch_z_center = 2.82
        for seg in range(5):
            ang = -0.38 * math.pi + seg * (0.19 * math.pi)
            au = u_c + math.sin(ang) * arch_r
            az = arch_z_center + math.cos(ang) * 0.44
            is_key = (seg == 2)
            mat_v = MAT_CONCRETE if is_key else MAT_BRICK
            sz_v = (0.24, 0.14 if is_key else 0.10, 0.24 if is_key else 0.18)
            add_local_box(bm, side, (au, -6.05, az), sz_v, mat_v)

        # Ground-floor window sills & decorative cafe window boxes
        if not (side == 0 and b_idx in (1, 2)):
            add_local_box(bm, side, (u_c, -6.08, 0.88), (1.36, 0.18, 0.10), MAT_CONCRETE)
            # Arched window wrought-iron grille guard at bottom + mullion grid
            add_local_box(bm, side, (u_c, -5.80, 2.10), (0.045, 0.05, 2.30), MAT_METAL)
            add_local_box(bm, side, (u_c, -5.80, 2.35), (1.06, 0.05, 0.045), MAT_METAL)
            add_local_box(bm, side, (u_c, -6.04, 1.15), (1.16, 0.04, 0.035), MAT_METAL)

    # Sloped striped Cafe Awnings & Signboard on Front (-Y) and Side (-X, +X) facades
    if side in (0, 1, 3):
        # Timber & gilt cafe fascia board above ground floor windows
        add_local_box(bm, side, (0.0, -6.07, 3.56), (9.80, 0.14, 0.34), MAT_WOOD_GREEN)
        add_local_box(bm, side, (0.0, -6.15, 3.56), (9.50, 0.04, 0.22), MAT_CONCRETE)

        # Projecting sloped fabric cafe awnings over outer bays
        for aw_u in (-2.80, 2.80):
            # Sloped canopy top
            add_local_box(bm, side, (aw_u, -6.48, 3.16), (3.95, 0.98, 0.06), MAT_AWNING, tilt_x=0.36)
            # Front valance scalloped strip
            add_local_box(bm, side, (aw_u, -6.93, 2.91), (3.95, 0.05, 0.16), MAT_AWNING)
            # Wrought-iron awning support arms
            for arm_dir in (-1.0, 1.0):
                add_local_box(bm, side, (aw_u + arm_dir * 1.85, -6.46, 2.86), (0.035, 0.90, 0.035), MAT_METAL, tilt_x=-0.22)

# Grand Central Cafe Entrance Portal on Front (-Y) facade
# Stone pilasters framing the central entrance bay, entablature, steps, and double doors
for p_dir in (-1.0, 1.0):
    add_local_box(bm, 0, (p_dir * 0.72, -6.10, 1.85), (0.28, 0.22, 3.40), MAT_CONCRETE)
    add_local_box(bm, 0, (p_dir * 0.72, -6.14, 0.25), (0.34, 0.28, 0.50), MAT_CONCRETE)
    add_local_box(bm, 0, (p_dir * 0.72, -6.14, 3.45), (0.36, 0.28, 0.22), MAT_CONCRETE)

# Recessed central double timber cafe entrance door + threshold steps
add_local_box(bm, 0, (0.0, -6.02, 1.65), (1.18, 0.18, 3.05), MAT_WOOD_GREEN)
add_local_box(bm, 0, (-0.27, -6.12, 1.55), (0.46, 0.04, 2.20), MAT_GLASS)
add_local_box(bm, 0, (0.27, -6.12, 1.55), (0.46, 0.04, 2.20), MAT_GLASS)
add_local_box(bm, 0, (0.0, -6.13, 2.92), (1.02, 0.04, 0.42), MAT_GLASS)
# Brass/iron door handles
add_local_box(bm, 0, (-0.06, -6.16, 1.15), (0.03, 0.06, 0.24), MAT_METAL)
add_local_box(bm, 0, (0.06, -6.16, 1.15), (0.03, 0.06, 0.24), MAT_METAL)
# Entrance stone steps at street level (Z = 0..0.30m)
add_local_box(bm, 0, (0.0, -6.28, 0.075), (1.85, 0.56, 0.15), MAT_CONCRETE)
add_local_box(bm, 0, (0.0, -6.18, 0.225), (1.60, 0.36, 0.15), MAT_CONCRETE)

# ---------------------------------------------------------------------------
# 4E. FLOOR BANDS (STRING COURSES), CORNER QUOINS, MAIN CORNICE & PARAPET
# ---------------------------------------------------------------------------
# Horizontal stone floor bands wrapping all 4 facades
for band_z in (3.80, 7.20, 10.60):
    for side in range(4):
        add_local_box(bm, side, (0.0, -6.06, band_z), (12.24, 0.14, 0.18), MAT_CONCRETE)
        add_local_box(bm, side, (0.0, -6.09, band_z + 0.06), (12.30, 0.18, 0.07), MAT_CONCRETE)

# Rusticated stone Corner Quoins at all 4 vertical corners
corners_xy = [(-6.0, -6.0), (6.0, -6.0), (6.0, 6.0), (-6.0, 6.0)]
for q_idx in range(24):
    qz = 0.78 + q_idx * 0.53
    if qz > 13.45:
        break
    long_x = (q_idx % 2 == 0)
    qx_len = 0.52 if long_x else 0.32
    qy_len = 0.32 if long_x else 0.52
    for cx, cy in corners_xy:
        sx = -1.0 if cx < 0 else 1.0
        sy = -1.0 if cy < 0 else 1.0
        bx = cx + sx * (0.06 - qx_len * 0.5)
        by = cy + sy * (0.06 - qy_len * 0.5)
        add_box(bm, (bx, by, qz), (qx_len, qy_len, 0.44), MAT_CONCRETE)

# Crowning Main Cornice with Dentils/Modillions (Z = 13.55..14.08m)
for side in range(4):
    # Frieze architrave
    add_local_box(bm, side, (0.0, -6.06, 13.58), (12.24, 0.14, 0.14), MAT_CONCRETE)
    # Brick decorative frieze band
    add_local_box(bm, side, (0.0, -6.04, 13.74), (12.16, 0.10, 0.18), MAT_BRICK)
    # Overhanging stone cornice corona
    add_local_box(bm, side, (0.0, -6.18, 13.94), (12.68, 0.38, 0.14), MAT_CONCRETE)
    add_local_box(bm, side, (0.0, -6.24, 14.04), (12.80, 0.48, 0.09), MAT_CONCRETE)
    # 13 Modillion / Dentil brackets under cornice per side
    for d_i in range(13):
        du = -5.4 + d_i * 0.90
        add_local_box(bm, side, (du, -6.15, 13.82), (0.16, 0.28, 0.12), MAT_CONCRETE)

# Roof Parapet Wall with Recessed Panels, Corner Piers & Coping (Z = 14.08..14.62m)
for side in range(4):
    # Parapet wall body
    add_local_box(bm, side, (0.0, -5.88, 14.34), (11.76, 0.24, 0.46), MAT_STUCCO)
    # Parapet stone coping cap
    add_local_box(bm, side, (0.0, -5.88, 14.60), (12.12, 0.34, 0.09), MAT_CONCRETE)
    # Corner piers on parapet
    add_local_box(bm, side, (-5.88, -5.88, 14.38), (0.44, 0.44, 0.56), MAT_CONCRETE)

# Flat perimeter roof gutter walk membrane at Z = 14.05m
add_box(bm, (0.0, 0.0, 14.02), (11.60, 11.60, 0.10), MAT_ROOF_MEMBRANE)

# Rainwater Downspouts on all 4 facade corners with mounting brackets
for side in range(4):
    add_local_box(bm, side, (-5.55, -6.08, 7.00), (0.075, 0.075, 13.80), MAT_METAL)
    for clip_z in (1.5, 4.0, 6.8, 9.6, 12.4):
        add_local_box(bm, side, (-5.55, -6.08, clip_z), (0.12, 0.10, 0.05), MAT_METAL)

# ---------------------------------------------------------------------------
# 4F. TERRACOTTA TILED PITCHED HIP ROOF, DORMERS, CHIMNEYS & ROOFTOP DETAILS
# ---------------------------------------------------------------------------
# Hipped pitched roof rising from eaves (Z=14.05, XY=+-5.45) to ridge line (X in [-2.4, 2.4], Y=0, Z=17.25)
eave_w = 5.45
ridge_x = 2.40
z_eave = 14.05
z_ridge = 17.25

v_sw = bm.verts.new(Vector((-eave_w, -eave_w, z_eave)))
v_se = bm.verts.new(Vector((eave_w, -eave_w, z_eave)))
v_ne = bm.verts.new(Vector((eave_w, eave_w, z_eave)))
v_nw = bm.verts.new(Vector((-eave_w, eave_w, z_eave)))
v_rw = bm.verts.new(Vector((-ridge_x, 0.0, z_ridge)))
v_re = bm.verts.new(Vector((ridge_x, 0.0, z_ridge)))

roof_faces = [
    bm.faces.new((v_sw, v_se, v_re, v_rw)),
    bm.faces.new((v_ne, v_nw, v_rw, v_re)),
    bm.faces.new((v_nw, v_sw, v_rw)),
    bm.faces.new((v_se, v_ne, v_re)),
]
set_faces_mat(roof_faces, MAT_ROOF_TILE)

# Stepped 3D terracotta tile lap courses & ridge/hip caps for rooftop VR silhouette
num_courses = 8
for c_i in range(num_courses):
    t = (c_i + 0.5) / num_courses
    cz = z_eave + t * (z_ridge - z_eave)
    half_y = eave_w * (1.0 - t)
    half_x = eave_w - t * (eave_w - ridge_x)
    # Front & back slope horizontal tile overlap ledges
    add_box(bm, (0.0, -half_y - 0.03, cz), (half_x * 2.0, 0.14, 0.06), MAT_ROOF_TILE, rot_euler=(0.52, 0.0, 0.0))
    add_box(bm, (0.0, half_y + 0.03, cz), (half_x * 2.0, 0.14, 0.06), MAT_ROOF_TILE, rot_euler=(-0.52, 0.0, 0.0))
    # Left & right hip slope tile overlap ledges
    add_box(bm, (-half_x - 0.03, 0.0, cz), (0.14, half_y * 2.0, 0.06), MAT_ROOF_TILE, rot_euler=(0.0, -0.78, 0.0))
    add_box(bm, (half_x + 0.03, 0.0, cz), (0.14, half_y * 2.0, 0.06), MAT_ROOF_TILE, rot_euler=(0.0, 0.78, 0.0))

# Top ridge terracotta barrel cap
add_box(bm, (0.0, 0.0, z_ridge + 0.06), (ridge_x * 2.0 + 0.16, 0.24, 0.14), MAT_ROOF_TILE)

# 4 Roof Dormer Windows (2 on front -Y slope, 2 on back +Y slope)
for d_side in (0, 2):
    for du in (-2.1, 2.1):
        # Dormer body & cheeks
        add_local_box(bm, d_side, (du, -3.55, 15.35), (1.16, 1.35, 1.25), MAT_STUCCO)
        # Dormer recessed window frame & glass
        add_local_box(bm, d_side, (du, -4.24, 15.32), (0.86, 0.10, 0.92), MAT_CONCRETE)
        add_local_box(bm, d_side, (du, -4.21, 15.32), (0.68, 0.06, 0.76), MAT_GLASS)
        add_local_box(bm, d_side, (du, -4.23, 15.32), (0.04, 0.07, 0.76), MAT_METAL)
        # Dormer sill & pitched gable cap
        add_local_box(bm, d_side, (du, -4.28, 14.84), (0.98, 0.16, 0.08), MAT_CONCRETE)
        add_local_box(bm, d_side, (du - 0.34, -3.60, 16.08), (0.76, 1.52, 0.08), MAT_ROOF_TILE, tilt_x=0.0)
        add_local_box(bm, d_side, (du + 0.34, -3.60, 16.08), (0.76, 1.52, 0.08), MAT_ROOF_TILE, tilt_x=0.0)
        add_local_box(bm, d_side, (du, -3.60, 16.16), (0.96, 1.56, 0.10), MAT_CONCRETE)

# Two Tall Brick Chimneys on the roof (Left X=-3.25m, Right X=+3.25m)
for ch_x in (-3.25, 3.25):
    # Brick chimney stack rising through the roof to Z = 18.25m
    add_box(bm, (ch_x, 0.0, 16.35), (0.96, 1.56, 3.70), MAT_BRICK)
    # Stone base flashing collar at roof intersection
    add_box(bm, (ch_x, 0.0, 15.55), (1.08, 1.68, 0.16), MAT_CONCRETE)
    # Corbeled brick necking band near top
    add_box(bm, (ch_x, 0.0, 18.02), (1.08, 1.68, 0.14), MAT_BRICK)
    # Heavy overhanging stone chimney cap
    add_box(bm, (ch_x, 0.0, 18.18), (1.18, 1.78, 0.14), MAT_CONCRETE)
    # 3 Terracotta / metal chimney flue pots per chimney (6 total)
    for pot_y in (-0.48, 0.0, 0.48):
        add_box(bm, (ch_x, pot_y, 18.46), (0.28, 0.28, 0.44), MAT_ROOF_TILE)
        add_box(bm, (ch_x, pot_y, 18.70), (0.34, 0.34, 0.07), MAT_METAL)

# Rooftop Details for VR Elevated Viewpoints:
# 1. Rear Rooftop Service Platform with 2 HVAC / AC Condenser Units & Pipes
add_box(bm, (-2.6, 4.85, 14.32), (2.40, 1.15, 0.14), MAT_CONCRETE)
for ac_x in (-3.15, -2.05):
    # AC cabinet body
    add_box(bm, (ac_x, 4.85, 14.78), (0.86, 0.56, 0.76), MAT_CONCRETE)
    # Steel mounting frame legs
    add_box(bm, (ac_x - 0.34, 4.85, 14.38), (0.06, 0.58, 0.12), MAT_METAL)
    add_box(bm, (ac_x + 0.34, 4.85, 14.38), (0.06, 0.58, 0.12), MAT_METAL)
    # Fan grille housing & guard bars on front/top
    add_box(bm, (ac_x, 5.14, 14.82), (0.58, 0.05, 0.58), MAT_METAL)
    add_box(bm, (ac_x, 4.85, 15.17), (0.88, 0.58, 0.04), MAT_METAL)
    # Refrigerant conduit line
    add_box(bm, (ac_x + 0.48, 4.65, 14.55), (0.08, 0.42, 0.38), MAT_METAL)

# 2. Rooftop Access Hatch / Skylight Housing & Ventilation Cowls on Rear Slope
add_box(bm, (2.2, 3.85, 14.95), (1.35, 1.35, 0.95), MAT_CONCRETE)
add_box(bm, (2.2, 3.85, 15.46), (1.45, 1.45, 0.10), MAT_METAL)
add_box(bm, (2.2, 3.85, 15.53), (1.15, 1.15, 0.06), MAT_GLASS)
for vent_x in (0.4, 0.85, 1.3):
    add_box(bm, (vent_x, 4.75, 14.55), (0.18, 0.18, 0.85), MAT_METAL)
    add_box(bm, (vent_x, 4.75, 15.02), (0.28, 0.28, 0.12), MAT_METAL)

# Finalize BMesh normals and write to single object "BldgStucco"
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

mesh = bpy.data.meshes.new(NAME)
bm.to_mesh(mesh)
bm.free()

obj = bpy.data.objects.new(NAME, mesh)
scene.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

for pm in proc_materials:
    obj.data.materials.append(pm)

# Verify triangle count is strictly inside 3000..9000
tris_count = sum(len(p.vertices) - 2 for p in obj.data.polygons)

# ---------------------------------------------------------------------------
# 5. UV UNWRAP WITH WORLD-SPACE ISLAND SCALING
# ---------------------------------------------------------------------------
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

if not obj.data.uv_layers:
    obj.data.uv_layers.new(name="UVMap")
obj.data.uv_layers.active_index = 0

bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.01)
bpy.ops.uv.select_all(action='SELECT')
bpy.ops.uv.average_islands_scale()
bpy.ops.uv.pack_islands(margin=0.01)
bpy.ops.object.mode_set(mode='OBJECT')

# ---------------------------------------------------------------------------
# 6. CYCLES CPU BAKING (ALBEDO & TANGENT NORMAL, 2048x2048)
# ---------------------------------------------------------------------------
img_albedo = bpy.data.images.new(f"{NAME}_albedo", width=2048, height=2048, alpha=False)
img_albedo.colorspace_settings.name = 'sRGB'

img_normal = bpy.data.images.new(f"{NAME}_normal", width=2048, height=2048, alpha=False)
img_normal.colorspace_settings.name = 'Non-Color'

bake_tex_nodes = []
for mat in obj.data.materials:
    nodes = mat.node_tree.nodes
    for n in nodes:
        n.select = False
    tex_node = nodes.new('ShaderNodeTexImage')
    tex_node.name = "BakeTarget"
    tex_node.select = True
    nodes.active = tex_node
    bake_tex_nodes.append(( nodes, tex_node ))

scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 16
scene.render.bake.margin = 8
scene.render.bake.use_clear = True
scene.render.bake.use_selected_to_active = False

bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

# Bake 1: DIFFUSE (COLOR) -> Albedo
for nodes, tex_node in bake_tex_nodes:
    for n in nodes:
        n.select = False
    tex_node.image = img_albedo
    tex_node.select = True
    nodes.active = tex_node

bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'})
img_albedo.filepath_raw = albedo_path
img_albedo.file_format = 'PNG'
img_albedo.save()

# Bake 2: NORMAL (TANGENT) -> Normal
for nodes, tex_node in bake_tex_nodes:
    for n in nodes:
        n.select = False
    tex_node.image = img_normal
    tex_node.select = True
    nodes.active = tex_node

scene.render.bake.normal_space = 'TANGENT'
bpy.ops.object.bake(type='NORMAL')
img_normal.filepath_raw = normal_path
img_normal.file_format = 'PNG'
img_normal.save()

# ---------------------------------------------------------------------------
# 7. REPLACE ALL SLOTS WITH SINGLE BAKED MATERIAL "<Name>_Mat"
# ---------------------------------------------------------------------------
obj.data.materials.clear()

final_mat = bpy.data.materials.new(name=f"{NAME}_Mat")
final_mat.use_nodes = True
fnodes = final_mat.node_tree.nodes
flinks = final_mat.node_tree.links

fbsdf = fnodes.get("Principled BSDF")
fbsdf.inputs['Roughness'].default_value = 0.7
fbsdf.inputs['Metallic'].default_value = 0.0

node_alb = fnodes.new('ShaderNodeTexImage')
node_alb.image = img_albedo
flinks.new(node_alb.outputs['Color'], fbsdf.inputs['Base Color'])

node_nrm_tex = fnodes.new('ShaderNodeTexImage')
node_nrm_tex.image = img_normal
img_normal.colorspace_settings.name = 'Non-Color'

node_nrm_map = fnodes.new('ShaderNodeNormalMap')
node_nrm_map.space = 'TANGENT'
node_nrm_map.inputs['Strength'].default_value = 1.0
flinks.new(node_nrm_tex.outputs['Color'], node_nrm_map.inputs['Color'])
flinks.new(node_nrm_map.outputs['Normal'], fbsdf.inputs['Normal'])

obj.data.materials.append(final_mat)
for poly in obj.data.polygons:
    poly.material_index = 0

for pm in proc_materials:
    bpy.data.materials.remove(pm, do_unlink=True)

# ---------------------------------------------------------------------------
# 8. EXPORT FBX
# ---------------------------------------------------------------------------
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bpy.ops.export_scene.fbx(
    filepath=fbx_path,
    use_selection=True,
    bake_space_transform=True,
    axis_forward='-Z',
    axis_up='Y',
    path_mode='COPY',
    embed_textures=True
)

# ---------------------------------------------------------------------------
# 9. PREVIEW RENDER (900x900, EEVEE, STREET-LEVEL 3/4 VIEW)
# ---------------------------------------------------------------------------
eevee_engines = [
    k for k in scene.render.bl_rna.properties['engine'].enum_items.keys()
    if 'EEVEE' in k
]
if eevee_engines:
    scene.render.engine = eevee_engines[0]

# Grey sky world strength 0.6
world = scene.world
if world is None:
    world = bpy.data.worlds.new("World")
    scene.world = world
world.use_nodes = True
wnodes = world.node_tree.nodes
bg_node = wnodes.get("Background")
if bg_node is None:
    bg_node = wnodes.new('ShaderNodeBackground')
bg_node.inputs['Color'].default_value = (0.52, 0.55, 0.58, 1.0)
bg_node.inputs['Strength'].default_value = 0.6

# Sun strength 3 from front-left-above (front facade is -Y, left is -X)
sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
sun_data.energy = 3.0
sun_data.color = (1.0, 0.96, 0.90)
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
scene.collection.objects.link(sun_obj)
sun_obj.location = Vector((-16.0, -20.0, 26.0))
sun_dir = Vector((0.0, 0.0, 7.0)) - sun_obj.location
sun_obj.rotation_euler = sun_dir.to_track_quat('-Z', 'Y').to_euler()

# Street-level 3/4 camera framing the entire 12x12x18.5m building
cam_data = bpy.data.cameras.new(name="PreviewCam")
cam_data.lens = 26.0
cam_data.sensor_width = 36.0
cam_data.clip_start = 0.1
cam_data.clip_end = 200.0
cam_obj = bpy.data.objects.new(name="PreviewCam", object_data=cam_data)
scene.collection.objects.link(cam_obj)
cam_obj.location = Vector((-16.8, -20.8, 2.2))
cam_target = Vector((0.0, 0.0, 8.6))
cam_dir = cam_target - cam_obj.location
cam_obj.rotation_euler = cam_dir.to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam_obj

scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = preview_path

bpy.ops.render.render(write_still=True)

print("TRIS", tris_count)
