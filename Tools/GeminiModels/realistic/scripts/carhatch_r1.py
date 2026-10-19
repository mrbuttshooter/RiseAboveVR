import bpy
from mathutils import Euler
import bmesh
from mathutils import Vector, Matrix
import math
import sys
import os


def clear_scene():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block, do_unlink=True)
    for block in list(bpy.data.materials):
        bpy.data.materials.remove(block, do_unlink=True)
    for block in list(bpy.data.images):
        bpy.data.images.remove(block, do_unlink=True)
    for block in list(bpy.data.lights):
        bpy.data.lights.remove(block, do_unlink=True)
    for block in list(bpy.data.cameras):
        bpy.data.cameras.remove(block, do_unlink=True)


def set_principled_input(bsdf, names, value):
    for name in names:
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = value
            return


def get_principled_input(bsdf, names):
    for name in names:
        if name in bsdf.inputs:
            return bsdf.inputs[name]
    return None


def add_road_dirt_nodes(nt, loc_x, loc_y, base_color_socket, base_rough_val):
    tex_coord = nt.nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (loc_x - 700, loc_y)

    sep_xyz = nt.nodes.new('ShaderNodeSeparateXYZ')
    sep_xyz.location = (loc_x - 500, loc_y + 60)
    nt.links.new(tex_coord.outputs['Object'], sep_xyz.inputs['Vector'])

    map_z = nt.nodes.new('ShaderNodeMapRange')
    map_z.location = (loc_x - 320, loc_y + 80)
    map_z.clamp = True
    map_z.inputs['From Min'].default_value = 0.0
    map_z.inputs['From Max'].default_value = 0.25
    map_z.inputs['To Min'].default_value = 1.0
    map_z.inputs['To Max'].default_value = 0.0
    nt.links.new(sep_xyz.outputs['Z'], map_z.inputs['Value'])

    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.location = (loc_x - 500, loc_y - 120)
    noise.inputs['Scale'].default_value = 15.0
    noise.inputs['Detail'].default_value = 6.0
    noise.inputs['Roughness'].default_value = 0.65
    nt.links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])

    mult_dirt = nt.nodes.new('ShaderNodeMath')
    mult_dirt.operation = 'MULTIPLY'
    mult_dirt.use_clamp = True
    mult_dirt.location = (loc_x - 140, loc_y)
    nt.links.new(map_z.outputs['Result'], mult_dirt.inputs[0])
    nt.links.new(noise.outputs['Fac'], mult_dirt.inputs[1])

    scale_dirt = nt.nodes.new('ShaderNodeMath')
    scale_dirt.operation = 'MULTIPLY'
    scale_dirt.use_clamp = True
    scale_dirt.location = (loc_x + 20, loc_y)
    scale_dirt.inputs[1].default_value = 0.42
    nt.links.new(mult_dirt.outputs['Value'], scale_dirt.inputs[0])

    mix_col = nt.nodes.new('ShaderNodeMixRGB')
    mix_col.blend_type = 'MIX'
    mix_col.location = (loc_x + 200, loc_y + 80)
    mix_col.inputs['Color2'].default_value = (0.19, 0.17, 0.145, 1.0)
    nt.links.new(scale_dirt.outputs['Value'], mix_col.inputs['Fac'])
    nt.links.new(base_color_socket, mix_col.inputs['Color1'])

    mix_rough = nt.nodes.new('ShaderNodeMath')
    mix_rough.operation = 'ADD'
    mix_rough.use_clamp = True
    mix_rough.location = (loc_x + 200, loc_y - 80)
    mix_rough.inputs[0].default_value = base_rough_val
    nt.links.new(scale_dirt.outputs['Value'], mix_rough.inputs[1])

    return mix_col.outputs['Color'], mix_rough.outputs['Value'], tex_coord, sep_xyz, noise


def add_line_seam(nt, val_socket, target_val, half_width, gate_min_socket, min_val, gate_max_socket, max_val, loc):
    comp = nt.nodes.new('ShaderNodeMath')
    comp.operation = 'COMPARE'
    comp.location = loc
    comp.inputs[1].default_value = target_val
    comp.inputs[2].default_value = half_width
    nt.links.new(val_socket, comp.inputs[0])

    g1 = nt.nodes.new('ShaderNodeMath')
    g1.operation = 'GREATER_THAN'
    g1.location = (loc[0], loc[1] - 140)
    g1.inputs[1].default_value = min_val
    nt.links.new(gate_min_socket, g1.inputs[0])

    g2 = nt.nodes.new('ShaderNodeMath')
    g2.operation = 'LESS_THAN'
    g2.location = (loc[0], loc[1] - 280)
    g2.inputs[1].default_value = max_val
    nt.links.new(gate_max_socket, g2.inputs[0])

    m1 = nt.nodes.new('ShaderNodeMath')
    m1.operation = 'MULTIPLY'
    m1.location = (loc[0] + 160, loc[1] - 70)
    nt.links.new(comp.outputs['Value'], m1.inputs[0])
    nt.links.new(g1.outputs['Value'], m1.inputs[1])

    m2 = nt.nodes.new('ShaderNodeMath')
    m2.operation = 'MULTIPLY'
    m2.location = (loc[0] + 320, loc[1] - 140)
    nt.links.new(m1.outputs['Value'], m2.inputs[0])
    nt.links.new(g2.outputs['Value'], m2.inputs[1])

    return m2.outputs['Value']


def create_procedural_materials():
    mats = {}

    # 1. Mat_Paint: Metallic silver-grey car paint with clearcoat, lower 25cm road dirt, and panel gaps
    mat_paint = bpy.data.materials.new(name="Mat_Paint")
    mat_paint.use_nodes = True
    nt = mat_paint.node_tree
    nt.nodes.clear()

    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (1200, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (900, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    set_principled_input(bsdf, ['Metallic'], 0.82)
    set_principled_input(bsdf, ['Coat Weight', 'Clearcoat'], 1.0)
    set_principled_input(bsdf, ['Coat Roughness', 'Clearcoat Roughness'], 0.03)

    tc = nt.nodes.new('ShaderNodeTexCoord')
    tc.location = (-1200, 200)
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    sep.location = (-1000, 200)
    nt.links.new(tc.outputs['Object'], sep.inputs['Vector'])

    abs_x = nt.nodes.new('ShaderNodeMath')
    abs_x.operation = 'ABSOLUTE'
    abs_x.location = (-820, 300)
    nt.links.new(sep.outputs['X'], abs_x.inputs[0])

    flake_noise = nt.nodes.new('ShaderNodeTexNoise')
    flake_noise.location = (-820, 500)
    flake_noise.inputs['Scale'].default_value = 320.0
    flake_noise.inputs['Detail'].default_value = 4.0
    nt.links.new(tc.outputs['Object'], flake_noise.inputs['Vector'])

    shimmer = nt.nodes.new('ShaderNodeMath')
    shimmer.operation = 'MULTIPLY_ADD'
    shimmer.location = (-620, 650)
    shimmer.inputs[1].default_value = -0.10
    shimmer.inputs[2].default_value = 0.58
    nt.links.new(sep.outputs['Z'], shimmer.inputs[0])

    mix_flake = nt.nodes.new('ShaderNodeMixRGB')
    mix_flake.location = (-440, 520)
    mix_flake.inputs['Color1'].default_value = (0.49, 0.515, 0.545, 1.0)
    mix_flake.inputs['Color2'].default_value = (0.61, 0.64, 0.675, 1.0)
    nt.links.new(flake_noise.outputs['Fac'], mix_flake.inputs['Fac'])

    mix_shade = nt.nodes.new('ShaderNodeMixRGB')
    mix_shade.blend_type = 'MIX'
    mix_shade.location = (-260, 520)
    mix_shade.inputs['Color2'].default_value = (0.38, 0.40, 0.43, 1.0)
    nt.links.new(shimmer.outputs['Value'], mix_shade.inputs['Fac'])
    nt.links.new(mix_flake.outputs['Color'], mix_shade.inputs['Color1'])

    # Panel gap seams (front door, B-pillar door seam, rear door, hood side, hood front/back, trunk, sill)
    side_mask = nt.nodes.new('ShaderNodeMath')
    side_mask.operation = 'GREATER_THAN'
    side_mask.location = (-650, 200)
    side_mask.inputs[1].default_value = 0.74
    nt.links.new(abs_x.outputs['Value'], side_mask.inputs[0])

    s_door_f = add_line_seam(nt, sep.outputs['Y'], -0.87, 0.0065, sep.outputs['Z'], 0.23, sep.outputs['Z'], 0.90, (-600, 0))
    s_door_m = add_line_seam(nt, sep.outputs['Y'], 0.02, 0.0065, sep.outputs['Z'], 0.23, sep.outputs['Z'], 0.92, (-600, -350))
    s_door_r = add_line_seam(nt, sep.outputs['Y'], 0.93, 0.0065, sep.outputs['Z'], 0.34, sep.outputs['Z'], 0.94, (-600, -700))
    s_sill = add_line_seam(nt, sep.outputs['Z'], 0.245, 0.0065, sep.outputs['Y'], -0.88, sep.outputs['Y'], 0.94, (-600, -1050))

    add_s1 = nt.nodes.new('ShaderNodeMath')
    add_s1.operation = 'MAXIMUM'
    add_s1.location = (-200, -100)
    nt.links.new(s_door_f, add_s1.inputs[0])
    nt.links.new(s_door_m, add_s1.inputs[1])

    add_s2 = nt.nodes.new('ShaderNodeMath')
    add_s2.operation = 'MAXIMUM'
    add_s2.location = (-200, -260)
    nt.links.new(s_door_r, add_s2.inputs[0])
    nt.links.new(s_sill, add_s2.inputs[1])

    add_side_all = nt.nodes.new('ShaderNodeMath')
    add_side_all.operation = 'MAXIMUM'
    add_side_all.location = (-40, -180)
    nt.links.new(add_s1.outputs['Value'], add_side_all.inputs[0])
    nt.links.new(add_s2.outputs['Value'], add_side_all.inputs[1])

    side_seams = nt.nodes.new('ShaderNodeMath')
    side_seams.operation = 'MULTIPLY'
    side_seams.location = (100, -180)
    nt.links.new(add_side_all.outputs['Value'], side_seams.inputs[0])
    nt.links.new(side_mask.outputs['Value'], side_seams.inputs[1])

    # Hood & trunk seams
    s_hood_side = add_line_seam(nt, abs_x.outputs['Value'], 0.67, 0.0065, sep.outputs['Y'], -1.94, sep.outputs['Y'], -1.01, (-600, -1400))
    s_hood_front = add_line_seam(nt, sep.outputs['Y'], -1.93, 0.0065, sep.outputs['Z'], 0.62, abs_x.outputs['Value'], 0.68, (-600, -1750))
    s_trunk_side = add_line_seam(nt, abs_x.outputs['Value'], 0.56, 0.0065, sep.outputs['Y'], 1.40, sep.outputs['Y'], 2.08, (-600, -2100))
    s_bumper_f = add_line_seam(nt, sep.outputs['Y'], -1.66, 0.0065, sep.outputs['Z'], 0.30, sep.outputs['Z'], 0.66, (-600, -2450))
    s_bumper_r = add_line_seam(nt, sep.outputs['Y'], 1.66, 0.0065, sep.outputs['Z'], 0.30, sep.outputs['Z'], 0.78, (-600, -2800))

    top_z_gate = nt.nodes.new('ShaderNodeMath')
    top_z_gate.operation = 'GREATER_THAN'
    top_z_gate.location = (-200, -1550)
    top_z_gate.inputs[1].default_value = 0.60
    nt.links.new(sep.outputs['Z'], top_z_gate.inputs[0])

    add_h1 = nt.nodes.new('ShaderNodeMath')
    add_h1.operation = 'MAXIMUM'
    add_h1.location = (-200, -1700)
    nt.links.new(s_hood_side, add_h1.inputs[0])
    nt.links.new(s_trunk_side, add_h1.inputs[1])

    mult_h1 = nt.nodes.new('ShaderNodeMath')
    mult_h1.operation = 'MULTIPLY'
    mult_h1.location = (-40, -1650)
    nt.links.new(add_h1.outputs['Value'], mult_h1.inputs[0])
    nt.links.new(top_z_gate.outputs['Value'], mult_h1.inputs[1])

    add_h2 = nt.nodes.new('ShaderNodeMath')
    add_h2.operation = 'MAXIMUM'
    add_h2.location = (-40, -1850)
    nt.links.new(mult_h1.outputs['Value'], add_h2.inputs[0])
    nt.links.new(s_hood_front, add_h2.inputs[1])

    add_b1 = nt.nodes.new('ShaderNodeMath')
    add_b1.operation = 'MAXIMUM'
    add_b1.location = (-40, -2150)
    nt.links.new(s_bumper_f, add_b1.inputs[0])
    nt.links.new(s_bumper_r, add_b1.inputs[1])

    mult_b1 = nt.nodes.new('ShaderNodeMath')
    mult_b1.operation = 'MULTIPLY'
    mult_b1.location = (100, -2150)
    nt.links.new(add_b1.outputs['Value'], mult_b1.inputs[0])
    nt.links.new(side_mask.outputs['Value'], mult_b1.inputs[1])

    all_seams_1 = nt.nodes.new('ShaderNodeMath')
    all_seams_1.operation = 'MAXIMUM'
    all_seams_1.location = (240, -400)
    nt.links.new(side_seams.outputs['Value'], all_seams_1.inputs[0])
    nt.links.new(add_h2.outputs['Value'], all_seams_1.inputs[1])

    all_seams = nt.nodes.new('ShaderNodeMath')
    all_seams.operation = 'MAXIMUM'
    all_seams.use_clamp = True
    all_seams.location = (380, -400)
    nt.links.new(all_seams_1.outputs['Value'], all_seams.inputs[0])
    nt.links.new(mult_b1.outputs['Value'], all_seams.inputs[1])

    dirt_col, dirt_rough, _, _, dirt_noise = add_road_dirt_nodes(nt, -100, 300, mix_shade.outputs['Color'], 0.18)

    paint_with_seams = nt.nodes.new('ShaderNodeMixRGB')
    paint_with_seams.blend_type = 'MIX'
    paint_with_seams.location = (580, 260)
    paint_with_seams.inputs['Color2'].default_value = (0.025, 0.028, 0.032, 1.0)
    nt.links.new(all_seams.outputs['Value'], paint_with_seams.inputs['Fac'])
    nt.links.new(dirt_col, paint_with_seams.inputs['Color1'])

    nt.links.new(paint_with_seams.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(dirt_rough, bsdf.inputs['Roughness'])

    seam_inv = nt.nodes.new('ShaderNodeMath')
    seam_inv.operation = 'MULTIPLY_ADD'
    seam_inv.location = (540, -250)
    seam_inv.inputs[1].default_value = -1.0
    seam_inv.inputs[2].default_value = 0.5
    nt.links.new(all_seams.outputs['Value'], seam_inv.inputs[0])

    bump_paint = nt.nodes.new('ShaderNodeBump')
    bump_paint.location = (700, -220)
    bump_paint.inputs['Strength'].default_value = 0.85
    bump_paint.inputs['Distance'].default_value = 0.008
    nt.links.new(seam_inv.outputs['Value'], bump_paint.inputs['Height'])
    nt.links.new(bump_paint.outputs['Normal'], bsdf.inputs['Normal'])

    mats['paint'] = mat_paint

    # 2. Mat_Plastic: Black automotive trim + lower 25cm road dirt + micro-texture bump
    mat_plastic = bpy.data.materials.new(name="Mat_Plastic")
    mat_plastic.use_nodes = True
    nt = mat_plastic.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (700, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (420, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    set_principled_input(bsdf, ['Metallic'], 0.05)

    rgb_p = nt.nodes.new('ShaderNodeRGB')
    rgb_p.outputs[0].default_value = (0.055, 0.058, 0.065, 1.0)
    rgb_p.location = (-400, 200)
    d_col, d_rough, _, _, d_noise = add_road_dirt_nodes(nt, -100, 100, rgb_p.outputs['Color'], 0.52)
    nt.links.new(d_col, bsdf.inputs['Base Color'])
    nt.links.new(d_rough, bsdf.inputs['Roughness'])

    bump_p = nt.nodes.new('ShaderNodeBump')
    bump_p.location = (200, -180)
    bump_p.inputs['Strength'].default_value = 0.15
    bump_p.inputs['Distance'].default_value = 0.003
    nt.links.new(d_noise.outputs['Fac'], bump_p.inputs['Height'])
    nt.links.new(bump_p.outputs['Normal'], bsdf.inputs['Normal'])
    mats['plastic'] = mat_plastic

    # 3. Mat_Grille: Black honeycomb mesh grille
    mat_grille = bpy.data.materials.new(name="Mat_Grille")
    mat_grille.use_nodes = True
    nt = mat_grille.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (750, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (480, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    set_principled_input(bsdf, ['Roughness'], 0.42)
    set_principled_input(bsdf, ['Metallic'], 0.1)

    tc_g = nt.nodes.new('ShaderNodeTexCoord')
    tc_g.location = (-500, 0)
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.location = (-280, 0)
    vor.feature = 'DISTANCE_TO_EDGE'
    vor.inputs['Scale'].default_value = 46.0
    if 'Randomness' in vor.inputs:
        vor.inputs['Randomness'].default_value = 0.15
    nt.links.new(tc_g.outputs['Object'], vor.inputs['Vector'])

    ramp_g = nt.nodes.new('ShaderNodeValToRGB')
    ramp_g.location = (-60, 100)
    ramp_g.color_ramp.elements[0].position = 0.06
    ramp_g.color_ramp.elements[0].color = (0.09, 0.095, 0.105, 1.0)
    ramp_g.color_ramp.elements[1].position = 0.13
    ramp_g.color_ramp.elements[1].color = (0.012, 0.012, 0.015, 1.0)
    nt.links.new(vor.outputs['Distance'], ramp_g.inputs['Fac'])
    nt.links.new(ramp_g.outputs['Color'], bsdf.inputs['Base Color'])

    bump_g = nt.nodes.new('ShaderNodeBump')
    bump_g.location = (220, -150)
    bump_g.inputs['Strength'].default_value = 0.9
    bump_g.inputs['Distance'].default_value = 0.012
    nt.links.new(ramp_g.outputs['Color'], bump_g.inputs['Height'])
    nt.links.new(bump_g.outputs['Normal'], bsdf.inputs['Normal'])
    mats['grille'] = mat_grille

    # 4. Mat_Chrome: Bright chrome trim & brake disc rotor
    mat_chrome = bpy.data.materials.new(name="Mat_Chrome")
    mat_chrome.use_nodes = True
    nt = mat_chrome.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (500, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (220, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    set_principled_input(bsdf, ['Base Color'], (0.82, 0.84, 0.87, 1.0))
    set_principled_input(bsdf, ['Metallic'], 0.96)
    set_principled_input(bsdf, ['Roughness'], 0.10)
    mats['chrome'] = mat_chrome

    # 5. Mat_Alloy: 16-inch dark gunmetal / machined alloy rims
    mat_alloy = bpy.data.materials.new(name="Mat_Alloy")
    mat_alloy.use_nodes = True
    nt = mat_alloy.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (750, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (480, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    set_principled_input(bsdf, ['Metallic'], 0.90)
    set_principled_input(bsdf, ['Roughness'], 0.22)
    set_principled_input(bsdf, ['Coat Weight', 'Clearcoat'], 0.7)

    tc_a = nt.nodes.new('ShaderNodeTexCoord')
    tc_a.location = (-550, 100)
    sep_a = nt.nodes.new('ShaderNodeSeparateXYZ')
    sep_a.location = (-350, 100)
    nt.links.new(tc_a.outputs['Object'], sep_a.inputs['Vector'])

    abs_xa = nt.nodes.new('ShaderNodeMath')
    abs_xa.operation = 'ABSOLUTE'
    abs_xa.location = (-160, 150)
    nt.links.new(sep_a.outputs['X'], abs_xa.inputs[0])

    ramp_a = nt.nodes.new('ShaderNodeValToRGB')
    ramp_a.location = (40, 150)
    ramp_a.color_ramp.elements[0].position = 0.82
    ramp_a.color_ramp.elements[0].color = (0.14, 0.15, 0.165, 1.0)
    ramp_a.color_ramp.elements[1].position = 0.865
    ramp_a.color_ramp.elements[1].color = (0.36, 0.38, 0.41, 1.0)
    nt.links.new(abs_xa.outputs['Value'], ramp_a.inputs['Fac'])

    noise_a = nt.nodes.new('ShaderNodeTexNoise')
    noise_a.location = (-160, -120)
    noise_a.inputs['Scale'].default_value = 90.0
    nt.links.new(tc_a.outputs['Object'], noise_a.inputs['Vector'])

    bump_a = nt.nodes.new('ShaderNodeBump')
    bump_a.location = (220, -120)
    bump_a.inputs['Strength'].default_value = 0.12
    bump_a.inputs['Distance'].default_value = 0.002
    nt.links.new(noise_a.outputs['Fac'], bump_a.inputs['Height'])

    nt.links.new(ramp_a.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(bump_a.outputs['Normal'], bsdf.inputs['Normal'])
    mats['alloy'] = mat_alloy

    # 6. Mat_Tyre: Black rubber tyres with sidewall lettering hint (noise) + tread bump + road dirt
    mat_tyre = bpy.data.materials.new(name="Mat_Tyre")
    mat_tyre.use_nodes = True
    nt = mat_tyre.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (950, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (680, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    set_principled_input(bsdf, ['Metallic'], 0.0)

    tc_t = nt.nodes.new('ShaderNodeTexCoord')
    tc_t.location = (-850, 100)
    sep_t = nt.nodes.new('ShaderNodeSeparateXYZ')
    sep_t.location = (-650, 100)
    nt.links.new(tc_t.outputs['Object'], sep_t.inputs['Vector'])

    abs_ty = nt.nodes.new('ShaderNodeMath')
    abs_ty.operation = 'ABSOLUTE'
    abs_ty.location = (-460, 220)
    nt.links.new(sep_t.outputs['Y'], abs_ty.inputs[0])

    dy = nt.nodes.new('ShaderNodeMath')
    dy.operation = 'SUBTRACT'
    dy.location = (-280, 220)
    dy.inputs[1].default_value = 1.31
    nt.links.new(abs_ty.outputs['Value'], dy.inputs[0])

    dz = nt.nodes.new('ShaderNodeMath')
    dz.operation = 'SUBTRACT'
    dz.location = (-280, 80)
    dz.inputs[1].default_value = 0.316
    nt.links.new(sep_t.outputs['Z'], dz.inputs[0])

    dy2 = nt.nodes.new('ShaderNodeMath')
    dy2.operation = 'MULTIPLY'
    dy2.location = (-100, 220)
    nt.links.new(dy.outputs['Value'], dy2.inputs[0])
    nt.links.new(dy.outputs['Value'], dy2.inputs[1])

    dz2 = nt.nodes.new('ShaderNodeMath')
    dz2.operation = 'MULTIPLY'
    dz2.location = (-100, 80)
    nt.links.new(dz.outputs['Value'], dz2.inputs[0])
    nt.links.new(dz.outputs['Value'], dz2.inputs[1])

    r2 = nt.nodes.new('ShaderNodeMath')
    r2.operation = 'ADD'
    r2.location = (60, 150)
    nt.links.new(dy2.outputs['Value'], r2.inputs[0])
    nt.links.new(dz2.outputs['Value'], r2.inputs[1])

    rad = nt.nodes.new('ShaderNodeMath')
    rad.operation = 'SQRT'
    rad.location = (200, 150)
    nt.links.new(r2.outputs['Value'], rad.inputs[0])

    sw_band = nt.nodes.new('ShaderNodeMath')
    sw_band.operation = 'COMPARE'
    sw_band.location = (360, 150)
    sw_band.inputs[1].default_value = 0.255
    sw_band.inputs[2].default_value = 0.024
    nt.links.new(rad.outputs['Value'], sw_band.inputs[0])

    sw_noise = nt.nodes.new('ShaderNodeTexNoise')
    sw_noise.location = (-280, -140)
    sw_noise.inputs['Scale'].default_value = 68.0
    sw_noise.inputs['Detail'].default_value = 8.0
    sw_noise.inputs['Roughness'].default_value = 0.8
    nt.links.new(tc_t.outputs['Object'], sw_noise.inputs['Vector'])

    sw_thresh = nt.nodes.new('ShaderNodeMath')
    sw_thresh.operation = 'GREATER_THAN'
    sw_thresh.location = (-80, -140)
    sw_thresh.inputs[1].default_value = 0.56
    nt.links.new(sw_noise.outputs['Fac'], sw_thresh.inputs[0])

    letter_mask = nt.nodes.new('ShaderNodeMath')
    letter_mask.operation = 'MULTIPLY'
    letter_mask.location = (500, 40)
    nt.links.new(sw_band.outputs['Value'], letter_mask.inputs[0])
    nt.links.new(sw_thresh.outputs['Value'], letter_mask.inputs[1])

    tread_vor = nt.nodes.new('ShaderNodeTexVoronoi')
    tread_vor.location = (-280, -340)
    tread_vor.feature = 'DISTANCE_TO_EDGE'
    tread_vor.inputs['Scale'].default_value = 38.0
    nt.links.new(tc_t.outputs['Object'], tread_vor.inputs['Vector'])

    tread_band = nt.nodes.new('ShaderNodeMath')
    tread_band.operation = 'GREATER_THAN'
    tread_band.location = (200, -300)
    tread_band.inputs[1].default_value = 0.295
    nt.links.new(rad.outputs['Value'], tread_band.inputs[0])

    tread_h = nt.nodes.new('ShaderNodeMath')
    tread_h.operation = 'MULTIPLY'
    tread_h.location = (380, -300)
    nt.links.new(tread_vor.outputs['Distance'], tread_h.inputs[0])
    nt.links.new(tread_band.outputs['Value'], tread_h.inputs[1])

    total_bump_h = nt.nodes.new('ShaderNodeMath')
    total_bump_h.operation = 'ADD'
    total_bump_h.location = (520, -200)
    nt.links.new(letter_mask.outputs['Value'], total_bump_h.inputs[0])
    nt.links.new(tread_h.outputs['Value'], total_bump_h.inputs[1])

    tyre_col = nt.nodes.new('ShaderNodeMixRGB')
    tyre_col.location = (250, 340)
    tyre_col.inputs['Color1'].default_value = (0.042, 0.044, 0.048, 1.0)
    tyre_col.inputs['Color2'].default_value = (0.095, 0.10, 0.108, 1.0)
    nt.links.new(letter_mask.outputs['Value'], tyre_col.inputs['Fac'])

    td_col, td_rough, _, _, _ = add_road_dirt_nodes(nt, 300, 480, tyre_col.outputs['Color'], 0.78)
    nt.links.new(td_col, bsdf.inputs['Base Color'])
    nt.links.new(td_rough, bsdf.inputs['Roughness'])

    bump_t = nt.nodes.new('ShaderNodeBump')
    bump_t.location = (520, -60)
    bump_t.inputs['Strength'].default_value = 0.65
    bump_t.inputs['Distance'].default_value = 0.006
    nt.links.new(total_bump_h.outputs['Value'], bump_t.inputs['Height'])
    nt.links.new(bump_t.outputs['Normal'], bsdf.inputs['Normal'])
    mats['tyre'] = mat_tyre

    # 7. Mat_Glass: Dark tinted glass with slight interior visibility (seats/dashboard silhouettes)
    mat_glass = bpy.data.materials.new(name="Mat_Glass")
    mat_glass.use_nodes = True
    nt = mat_glass.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (800, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (520, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    set_principled_input(bsdf, ['Roughness'], 0.05)
    set_principled_input(bsdf, ['Metallic'], 0.15)
    set_principled_input(bsdf, ['Coat Weight', 'Clearcoat'], 1.0)
    set_principled_input(bsdf, ['Transmission Weight', 'Transmission'], 0.22)

    tc_gl = nt.nodes.new('ShaderNodeTexCoord')
    tc_gl.location = (-700, 100)
    sep_gl = nt.nodes.new('ShaderNodeSeparateXYZ')
    sep_gl.location = (-500, 100)
    nt.links.new(tc_gl.outputs['Object'], sep_gl.inputs['Vector'])

    abs_gx = nt.nodes.new('ShaderNodeMath')
    abs_gx.operation = 'ABSOLUTE'
    abs_gx.location = (-320, 220)
    nt.links.new(sep_gl.outputs['X'], abs_gx.inputs[0])

    # Seat headrest / backrest silhouette in object space
    seat_x = nt.nodes.new('ShaderNodeMath')
    seat_x.operation = 'COMPARE'
    seat_x.location = (-140, 260)
    seat_x.inputs[1].default_value = 0.30
    seat_x.inputs[2].default_value = 0.16
    nt.links.new(abs_gx.outputs['Value'], seat_x.inputs[0])

    seat_y = nt.nodes.new('ShaderNodeMath')
    seat_y.operation = 'COMPARE'
    seat_y.location = (-140, 100)
    seat_y.inputs[1].default_value = 0.05
    seat_y.inputs[2].default_value = 0.22
    nt.links.new(sep_gl.outputs['Y'], seat_y.inputs[0])

    seat_z = nt.nodes.new('ShaderNodeMath')
    seat_z.operation = 'COMPARE'
    seat_z.location = (-140, -60)
    seat_z.inputs[1].default_value = 1.04
    seat_z.inputs[2].default_value = 0.15
    nt.links.new(sep_gl.outputs['Z'], seat_z.inputs[0])

    dash_y = nt.nodes.new('ShaderNodeMath')
    dash_y.operation = 'COMPARE'
    dash_y.location = (-140, -220)
    dash_y.inputs[1].default_value = -0.68
    dash_y.inputs[2].default_value = 0.22
    nt.links.new(sep_gl.outputs['Y'], dash_y.inputs[0])

    dash_z = nt.nodes.new('ShaderNodeMath')
    dash_z.operation = 'COMPARE'
    dash_z.location = (-140, -380)
    dash_z.inputs[1].default_value = 0.96
    dash_z.inputs[2].default_value = 0.09
    nt.links.new(sep_gl.outputs['Z'], dash_z.inputs[0])

    s_xy = nt.nodes.new('ShaderNodeMath')
    s_xy.operation = 'MULTIPLY'
    s_xy.location = (40, 180)
    nt.links.new(seat_x.outputs['Value'], s_xy.inputs[0])
    nt.links.new(seat_y.outputs['Value'], s_xy.inputs[1])

    s_xyz = nt.nodes.new('ShaderNodeMath')
    s_xyz.operation = 'MULTIPLY'
    s_xyz.location = (180, 120)
    nt.links.new(s_xy.outputs['Value'], s_xyz.inputs[0])
    nt.links.new(seat_z.outputs['Value'], s_xyz.inputs[1])

    d_yz = nt.nodes.new('ShaderNodeMath')
    d_yz.operation = 'MULTIPLY'
    d_yz.location = (40, -300)
    nt.links.new(dash_y.outputs['Value'], d_yz.inputs[0])
    nt.links.new(dash_z.outputs['Value'], d_yz.inputs[1])

    sil_mask = nt.nodes.new('ShaderNodeMath')
    sil_mask.operation = 'MAXIMUM'
    sil_mask.location = (220, -60)
    nt.links.new(s_xyz.outputs['Value'], sil_mask.inputs[0])
    nt.links.new(d_yz.outputs['Value'], sil_mask.inputs[1])

    glass_mix = nt.nodes.new('ShaderNodeMixRGB')
    glass_mix.location = (350, 100)
    glass_mix.inputs['Color1'].default_value = (0.045, 0.062, 0.075, 1.0)
    glass_mix.inputs['Color2'].default_value = (0.135, 0.142, 0.158, 1.0)
    nt.links.new(sil_mask.outputs['Value'], glass_mix.inputs['Fac'])
    nt.links.new(glass_mix.outputs['Color'], bsdf.inputs['Base Color'])
    mats['glass'] = mat_glass

    # 8. Mat_Headlight: Clear headlight lenses over bright LED DRLs & reflector
    mat_hl = bpy.data.materials.new(name="Mat_Headlight")
    mat_hl.use_nodes = True
    nt = mat_hl.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (700, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (420, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    set_principled_input(bsdf, ['Roughness'], 0.08)
    set_principled_input(bsdf, ['Coat Weight', 'Clearcoat'], 1.0)

    tc_h = nt.nodes.new('ShaderNodeTexCoord')
    tc_h.location = (-550, 100)
    vor_h = nt.nodes.new('ShaderNodeTexVoronoi')
    vor_h.location = (-320, 100)
    vor_h.feature = 'DISTANCE_TO_EDGE'
    vor_h.inputs['Scale'].default_value = 28.0
    nt.links.new(tc_h.outputs['Object'], vor_h.inputs['Vector'])

    ramp_h = nt.nodes.new('ShaderNodeValToRGB')
    ramp_h.location = (-80, 120)
    ramp_h.color_ramp.elements[0].position = 0.08
    ramp_h.color_ramp.elements[0].color = (0.94, 0.97, 1.0, 1.0)
    ramp_h.color_ramp.elements[1].position = 0.25
    ramp_h.color_ramp.elements[1].color = (0.58, 0.63, 0.70, 1.0)
    nt.links.new(vor_h.outputs['Distance'], ramp_h.inputs['Fac'])
    nt.links.new(ramp_h.outputs['Color'], bsdf.inputs['Base Color'])

    bump_h = nt.nodes.new('ShaderNodeBump')
    bump_h.location = (180, -140)
    bump_h.inputs['Strength'].default_value = 0.35
    bump_h.inputs['Distance'].default_value = 0.004
    nt.links.new(vor_h.outputs['Distance'], bump_h.inputs['Height'])
    nt.links.new(bump_h.outputs['Normal'], bsdf.inputs['Normal'])
    mats['headlight'] = mat_hl

    # 9. Mat_Taillight: Red taillight lenses over LED light bars
    mat_tl = bpy.data.materials.new(name="Mat_Taillight")
    mat_tl.use_nodes = True
    nt = mat_tl.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (700, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (420, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    set_principled_input(bsdf, ['Roughness'], 0.10)
    set_principled_input(bsdf, ['Coat Weight', 'Clearcoat'], 1.0)

    tc_tl = nt.nodes.new('ShaderNodeTexCoord')
    tc_tl.location = (-550, 100)
    wave_tl = nt.nodes.new('ShaderNodeTexWave')
    wave_tl.location = (-320, 100)
    wave_tl.wave_type = 'BANDS'
    wave_tl.bands_direction = 'Z'
    wave_tl.inputs['Scale'].default_value = 22.0
    nt.links.new(tc_tl.outputs['Object'], wave_tl.inputs['Vector'])

    ramp_tl = nt.nodes.new('ShaderNodeValToRGB')
    ramp_tl.location = (-80, 120)
    ramp_tl.color_ramp.elements[0].position = 0.3
    ramp_tl.color_ramp.elements[0].color = (0.48, 0.02, 0.025, 1.0)
    ramp_tl.color_ramp.elements[1].position = 0.7
    ramp_tl.color_ramp.elements[1].color = (0.92, 0.08, 0.06, 1.0)
    nt.links.new(wave_tl.outputs['Color'], ramp_tl.inputs['Fac'])
    nt.links.new(ramp_tl.outputs['Color'], bsdf.inputs['Base Color'])

    bump_tl = nt.nodes.new('ShaderNodeBump')
    bump_tl.location = (180, -140)
    bump_tl.inputs['Strength'].default_value = 0.3
    bump_tl.inputs['Distance'].default_value = 0.004
    nt.links.new(wave_tl.outputs['Fac'], bump_tl.inputs['Height'])
    nt.links.new(bump_tl.outputs['Normal'], bsdf.inputs['Normal'])
    mats['taillight'] = mat_tl

    # 10. Mat_Plate: White number plate with blue EU band and dark characters
    mat_plate = bpy.data.materials.new(name="Mat_Plate")
    mat_plate.use_nodes = True
    nt = mat_plate.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (850, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (580, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    set_principled_input(bsdf, ['Roughness'], 0.28)

    tc_pl = nt.nodes.new('ShaderNodeTexCoord')
    tc_pl.location = (-750, 100)
    sep_pl = nt.nodes.new('ShaderNodeSeparateXYZ')
    sep_pl.location = (-550, 100)
    nt.links.new(tc_pl.outputs['Object'], sep_pl.inputs['Vector'])

    eu_strip = nt.nodes.new('ShaderNodeMath')
    eu_strip.operation = 'LESS_THAN'
    eu_strip.location = (-340, 260)
    eu_strip.inputs[1].default_value = -0.20
    nt.links.new(sep_pl.outputs['X'], eu_strip.inputs[0])

    char_x = nt.nodes.new('ShaderNodeMath')
    char_x.operation = 'COMPARE'
    char_x.location = (-340, 80)
    char_x.inputs[1].default_value = 0.02
    char_x.inputs[2].default_value = 0.19
    nt.links.new(sep_pl.outputs['X'], char_x.inputs[0])

    wave_pl = nt.nodes.new('ShaderNodeTexWave')
    wave_pl.location = (-340, -100)
    wave_pl.wave_type = 'BANDS'
    wave_pl.bands_direction = 'X'
    wave_pl.inputs['Scale'].default_value = 34.0
    wave_pl.inputs['Distortion'].default_value = 2.2
    nt.links.new(tc_pl.outputs['Object'], wave_pl.inputs['Vector'])

    char_thresh = nt.nodes.new('ShaderNodeMath')
    char_thresh.operation = 'GREATER_THAN'
    char_thresh.location = (-120, -100)
    char_thresh.inputs[1].default_value = 0.62
    nt.links.new(wave_pl.outputs['Fac'], char_thresh.inputs[0])

    char_mask = nt.nodes.new('ShaderNodeMath')
    char_mask.operation = 'MULTIPLY'
    char_mask.location = (80, 0)
    nt.links.new(char_x.outputs['Value'], char_mask.inputs[0])
    nt.links.new(char_thresh.outputs['Value'], char_mask.inputs[1])

    base_pl = nt.nodes.new('ShaderNodeMixRGB')
    base_pl.location = (80, 220)
    base_pl.inputs['Color1'].default_value = (0.91, 0.92, 0.93, 1.0)
    base_pl.inputs['Color2'].default_value = (0.04, 0.18, 0.68, 1.0)
    nt.links.new(eu_strip.outputs['Value'], base_pl.inputs['Fac'])

    final_pl = nt.nodes.new('ShaderNodeMixRGB')
    final_pl.location = (300, 140)
    final_pl.inputs['Color2'].default_value = (0.04, 0.04, 0.05, 1.0)
    nt.links.new(char_mask.outputs['Value'], final_pl.inputs['Fac'])
    nt.links.new(base_pl.outputs['Color'], final_pl.inputs['Color1'])
    nt.links.new(final_pl.outputs['Color'], bsdf.inputs['Base Color'])

    bump_pl = nt.nodes.new('ShaderNodeBump')
    bump_pl.location = (340, -120)
    bump_pl.inputs['Strength'].default_value = 0.45
    bump_pl.inputs['Distance'].default_value = 0.004
    nt.links.new(char_mask.outputs['Value'], bump_pl.inputs['Height'])
    nt.links.new(bump_pl.outputs['Normal'], bsdf.inputs['Normal'])
    mats['plate'] = mat_plate

    return mats


def build_body_shell(mats):
    # Longitudinal stations for VW Golf-style 5-door hatchback
    # Length: 4.28m (Y in [-2.14, 2.14]), Width: 1.79m (X in [-0.895, 0.895]), Height: 1.46m (Z in [0, 1.46]), Wheelbase: 2.62m (axles at +-1.31)
    y_stations = [
        -2.14, -2.10, -2.02, -1.91, -1.78,
        -1.66, -1.56, -1.44, -1.31, -1.18, -1.06, -0.96,
        -0.86, -0.64, -0.34, 0.02, 0.38, 0.72,
        0.96, 1.06, 1.18, 1.31, 1.44, 1.56, 1.66,
        1.80, 1.94, 2.04, 2.11, 2.14
    ]

    def interp_curve(y, pts):
        if y <= pts[0][0]:
            return pts[0][1]
        if y >= pts[-1][0]:
            return pts[-1][1]
        for i in range(len(pts) - 1):
            y0, v0 = pts[i]
            y1, v1 = pts[i + 1]
            if y0 <= y <= y1:
                t = (y - y0) / max(1e-6, (y1 - y0))
                t_smooth = t * t * (3.0 - 2.0 * t)
                return v0 + (v1 - v0) * t_smooth
        return pts[-1][1]

    top_profile = [
        (-2.14, 0.44), (-2.10, 0.56), (-2.02, 0.67), (-1.91, 0.72),
        (-1.55, 0.80), (-1.06, 0.88), (-0.86, 0.99), (-0.64, 1.19),
        (-0.34, 1.425), (0.02, 1.458), (0.38, 1.462), (0.72, 1.452),
        (1.06, 1.438), (1.36, 1.418), (1.44, 1.37), (1.66, 1.18),
        (1.94, 0.94), (2.04, 0.86), (2.11, 0.58), (2.14, 0.42)
    ]

    belt_profile = [
        (-2.14, 0.42), (-2.02, 0.63), (-1.66, 0.76), (-1.06, 0.87),
        (-0.34, 0.90), (0.38, 0.92), (1.18, 0.95), (1.66, 0.95),
        (1.94, 0.92), (2.04, 0.84), (2.14, 0.40)
    ]

    shoulder_profile = [
        (-2.14, 0.38), (-2.02, 0.58), (-1.66, 0.69), (-1.06, 0.78),
        (-0.34, 0.81), (0.38, 0.83), (1.31, 0.85), (1.94, 0.84),
        (2.04, 0.74), (2.14, 0.36)
    ]

    plan_width = [
        (-2.14, 0.66), (-2.10, 0.76), (-2.02, 0.84), (-1.78, 0.95),
        (-1.31, 1.00), (0.0, 0.99), (1.31, 1.00), (1.80, 0.94),
        (2.04, 0.85), (2.11, 0.76), (2.14, 0.66)
    ]

    cantrail_width = [
        (-2.14, 0.44), (-1.91, 0.64), (-1.06, 0.73), (-0.34, 0.605),
        (0.38, 0.60), (1.18, 0.575), (1.44, 0.555), (1.94, 0.62),
        (2.14, 0.46)
    ]

    bm = bmesh.new()
    rings = []

    for y in y_stations:
        z_top = interp_curve(y, top_profile)
        z_belt = min(z_top - 0.02, interp_curve(y, belt_profile))
        z_shld = min(z_belt - 0.03, interp_curve(y, shoulder_profile))
        w_fac = interp_curve(y, plan_width)
        x_cant = interp_curve(y, cantrail_width)

        # Check front or rear wheel arch cutout
        in_front_arch = -1.66 <= y <= -0.96
        in_rear_arch = 0.96 <= y <= 1.66
        arch_r = 0.355
        arch_z_center = 0.316

        if in_front_arch:
            dy = y - (-1.31)
            h_arc = math.sqrt(max(0.0, arch_r * arch_r - dy * dy))
            z_bot_outer = arch_z_center + h_arc
            z_fender = min(z_shld - 0.02, z_bot_outer + 0.075)
            x_fender = 0.896
            x_bot_outer = 0.885
            x_bot_inner = 0.76
            z_bot_inner = z_bot_outer + 0.01
            z_well = max(0.64, z_bot_outer + 0.08)
        elif in_rear_arch:
            dy = y - 1.31
            h_arc = math.sqrt(max(0.0, arch_r * arch_r - dy * dy))
            z_bot_outer = arch_z_center + h_arc
            z_fender = min(z_shld - 0.02, z_bot_outer + 0.075)
            x_fender = 0.896
            x_bot_outer = 0.885
            x_bot_inner = 0.76
            z_bot_inner = z_bot_outer + 0.01
            z_well = max(0.64, z_bot_outer + 0.08)
        else:
            if y < -1.66:
                z_bot_outer = 0.168 + max(0.0, (-1.85 - y) * 0.06)
            elif y > 1.66:
                z_bot_outer = 0.185 + max(0.0, (y - 1.85) * 0.10)
            else:
                z_bot_outer = 0.175
            z_fender = 0.50
            x_fender = 0.888 * w_fac
            x_bot_outer = 0.845 * w_fac
            x_bot_inner = 0.72 * w_fac
            z_bot_inner = 0.172
            z_well = 0.172

        x_shld = 0.865 * w_fac
        x_belt = 0.795 * w_fac
        z_cant = max(z_belt + 0.015, z_top - 0.032)
        z_mid_glass = 0.52 * z_belt + 0.48 * z_cant
        x_mid_glass = 0.52 * x_belt + 0.48 * x_cant

        # Tumblehome inset on cabin glass zone
        if -0.82 <= y <= 1.25:
            x_mid_glass -= 0.016

        # Right side profile points (from top-outer to bottom-inner)
        half_pts = [
            (0.26 * w_fac, z_top - 0.006),
            (x_cant, z_cant),
            (x_mid_glass, z_mid_glass),
            (x_belt, z_belt),
            (x_shld, z_shld),
            (x_fender, z_fender),
            (x_bot_outer, z_bot_outer),
            (x_bot_inner, z_bot_inner),
            (0.48 * w_fac, z_well),
        ]

        ring_verts = []
        # Top center
        ring_verts.append(bm.verts.new((0.0, y, z_top)))
        # Right side (+X)
        for px, pz in half_pts:
            ring_verts.append(bm.verts.new((px, y, pz)))
        # Bottom center
        ring_verts.append(bm.verts.new((0.0, y, 0.170)))
        # Left side (-X) from bottom-inner back up to top-outer
        for px, pz in reversed(half_pts):
            ring_verts.append(bm.verts.new((-px, y, pz)))

        rings.append(ring_verts)

    n_ring = len(rings[0])
    for i in range(len(rings) - 1):
        r0 = rings[i]
        r1 = rings[i + 1]
        y_mid = 0.5 * (y_stations[i] + y_stations[i + 1])
        for j in range(n_ring):
            jn = (j + 1) % n_ring
            f = bm.faces.new((r0[j], r0[jn], r1[jn], r1[j]))
            # Assign material index: 0 = Paint, 1 = Plastic (underbody & wheel wells & recessed window bed)
            is_under_or_well = (7 <= j <= 12)
            is_side_window_bed = (-0.82 <= y_mid <= 1.15) and (j in (2, 3, 16, 17))
            is_windscreen_bed = (-0.98 <= y_mid <= -0.36) and (j in (0, 1, 18, 19))
            is_rear_glass_bed = (1.42 <= y_mid <= 1.92) and (j in (0, 1, 18, 19))
            if is_under_or_well or is_side_window_bed or is_windscreen_bed or is_rear_glass_bed:
                f.material_index = 1
            else:
                f.material_index = 0

    # Cap front and rear ends cleanly
    front_ring = rings[0]
    for j in range(1, n_ring // 2):
        f = bm.faces.new((front_ring[j - 1], front_ring[n_ring - j], front_ring[n_ring - j - 1], front_ring[j]))
        f.material_index = 0

    rear_ring = rings[-1]
    for j in range(1, n_ring // 2):
        f = bm.faces.new((rear_ring[j], rear_ring[n_ring - j - 1], rear_ring[n_ring - j], rear_ring[j - 1]))
        f.material_index = 0

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new("CarBody_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("CarBody", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mats['paint'])
    obj.data.materials.append(mats['plastic'])

    # Apply Subdivision Surface modifier (level 1) as required
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    sub = obj.modifiers.new(name="Subsurf", type='SUBSURF')
    sub.levels = 1
    sub.render_levels = 1
    bpy.ops.object.modifier_apply(modifier=sub.name)

    # Rescale body shell to exact target dimensions after Subsurf smoothing
    verts = obj.data.vertices
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    cur_w = max(xs) - min(xs)
    cur_l = max(ys) - min(ys)
    cur_z_max = max(zs)
    cur_z_min = min(zs)
    sx = 1.79 / max(1e-5, cur_w)
    sy = 4.28 / max(1e-5, cur_l)
    sz = (1.46 - 0.168) / max(1e-5, (cur_z_max - cur_z_min))
    y_mid_cur = 0.5 * (max(ys) + min(ys))
    for v in verts:
        v.co.x *= sx
        v.co.y = (v.co.y - y_mid_cur) * sy
        v.co.z = 0.168 + (v.co.z - cur_z_min) * sz

    obj.data.update()
    return obj


def add_curved_grid_patch(bm, corner_grid, mat_idx, thickness=0.0):
    rows = len(corner_grid)
    cols = len(corner_grid[0])
    v_grid = [[bm.verts.new(corner_grid[r][c]) for c in range(cols)] for r in range(rows)]
    faces = []
    for r in range(rows - 1):
        for c in range(cols - 1):
            f = bm.faces.new((v_grid[r][c], v_grid[r][c + 1], v_grid[r + 1][c + 1], v_grid[r + 1][c]))
            f.material_index = mat_idx
            faces.append(f)
    if thickness != 0.0:
        bmesh.ops.recalc_face_normals(bm, faces=faces)
        ret = bmesh.ops.extrude_face_region(bm, geom=faces)
        ext_verts = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]
        for v in ext_verts:
            n = v.normal
            if n.length > 1e-5:
                v.co += n * thickness
            else:
                v.co.z += thickness
        for e in ret['geom']:
            if isinstance(e, bmesh.types.BMFace):
                e.material_index = mat_idx


def add_box(bm, center, size, mat_idx, rot_euler=(0.0, 0.0, 0.0)):
    res = bmesh.ops.create_cube(bm, size=1.0)
    verts = res['verts']
    rot_mat = Euler(rot_euler, 'XYZ').to_matrix().to_4x4()
    for v in verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z *= size[2]
        v.co = (rot_mat @ v.co) + Vector(center)
    for f in bm.faces:
        if all(v in verts for v in f.verts):
            f.material_index = mat_idx


def build_windows_and_pillars(mats):
    bm = bmesh.new()

    # 0 = glass, 1 = paint, 2 = plastic
    # 1. Front Windscreen (inset slightly into body, curved 6x6 grid)
    ws_grid = []
    for r in range(6):
        v = r / 5.0
        y_base = -1.03 + v * (-0.34 - (-1.03))
        z_base = 0.875 + v * (1.422 - 0.875) + math.sin(v * math.pi) * 0.018
        w_half = 0.72 - v * (0.72 - 0.575)
        row = []
        for c in range(7):
            u = (c / 6.0) * 2.0 - 1.0
            x = u * w_half
            arch = (1.0 - u * u)
            y = y_base - arch * 0.055
            z = z_base + arch * 0.016 - 0.005
            row.append((x, y, z))
        ws_grid.append(row)
    add_curved_grid_patch(bm, ws_grid, mat_idx=0, thickness=0.004)

    # 2. Rear Tailgate Window (curved 5x6 grid, inset)
    rw_grid = []
    for r in range(5):
        v = r / 4.0
        y_base = 1.38 + v * (1.94 - 1.38)
        z_base = 1.40 - v * (1.40 - 0.935) + math.sin(v * math.pi) * 0.015
        w_half = 0.54 + v * (0.63 - 0.54)
        row = []
        for c in range(7):
            u = (c / 6.0) * 2.0 - 1.0
            x = u * w_half
            arch = (1.0 - u * u)
            y = y_base + arch * 0.045
            z = z_base + arch * 0.012 - 0.005
            row.append((x, y, z))
        rw_grid.append(row)
    add_curved_grid_patch(bm, rw_grid, mat_idx=0, thickness=0.004)

    # 3. Side Windows (Front Door + Rear Door, Left and Right, inset into cabin)
    for side in (-1.0, 1.0):
        # Front door window
        fw_grid = []
        for r in range(4):
            v = r / 3.0
            row = []
            for c in range(6):
                u = c / 5.0
                y_bot = -0.86 + u * (-0.01 - (-0.86))
                y_top = -0.34 + u * (-0.01 - (-0.34))
                y = y_bot + v * (y_top - y_bot)
                z_bot = 0.885 + u * (0.91 - 0.885)
                z_top = 1.365 + math.sin(u * math.pi) * 0.015
                z = z_bot + v * (z_top - z_bot)
                x_bot = 0.782 - abs(u - 0.4) * 0.015
                x_top = 0.608
                x = side * (x_bot + v * (x_top - x_bot) + math.sin(v * math.pi) * 0.014)
                row.append((x, y, z))
            fw_grid.append(row)
        add_curved_grid_patch(bm, fw_grid, mat_idx=0, thickness=0.004 * side)

        # Rear door window
        rdw_grid = []
        for r in range(4):
            v = r / 3.0
            row = []
            for c in range(6):
                u = c / 5.0
                y_bot = 0.04 + u * (1.02 - 0.04)
                y_top = 0.04 + u * (1.14 - 0.04)
                y = y_bot + v * (y_top - y_bot)
                z_bot = 0.91 + u * (0.955 - 0.91)
                z_top = 1.368 - u * (1.368 - 1.335)
                z = z_bot + v * (z_top - z_bot)
                x_bot = 0.780 - u * 0.025
                x_top = 0.605 - u * 0.022
                x = side * (x_bot + v * (x_top - x_bot) + math.sin(v * math.pi) * 0.014)
                row.append((x, y, z))
            rdw_grid.append(row)
        add_curved_grid_patch(bm, rdw_grid, mat_idx=0, thickness=0.004 * side)

        # A-pillar (painted outer shell)
        ap_grid = []
        for r in range(2):
            dx = (r - 0.5) * 0.045
            row = []
            for c in range(6):
                u = c / 5.0
                y = -1.03 + u * (-0.30 - (-1.03))
                z = 0.875 + u * (1.425 - 0.875) + math.sin(u * math.pi) * 0.02
                x = side * (0.745 - u * (0.745 - 0.595) + dx)
                row.append((x, y, z))
            ap_grid.append(row)
        add_curved_grid_patch(bm, ap_grid, mat_idx=1, thickness=0.016)

        # B-pillar (gloss black vertical pillar between front and rear doors)
        bp_grid = []
        for r in range(4):
            v = r / 3.0
            z = 0.905 + v * (1.372 - 0.905)
            x = side * (0.790 + v * (0.614 - 0.790) + math.sin(v * math.pi) * 0.014)
            row = [(x, -0.02, z), (x, 0.015, z), (x, 0.05, z)]
            bp_grid.append(row)
        add_curved_grid_patch(bm, bp_grid, mat_idx=2, thickness=0.010 * side)

        # Wide VW Golf C-pillar (body paint)
        cp_grid = []
        for r in range(4):
            v = r / 3.0
            row = []
            for c in range(4):
                u = c / 3.0
                y_front = 1.02 + v * (1.14 - 1.02)
                y_back = 1.88 + v * (1.40 - 1.88)
                y = y_front + u * (y_back - y_front)
                z = (0.95 - u * 0.02) + v * (1.39 - (0.95 - u * 0.02))
                x_bot = 0.765 - u * 0.08
                x_top = 0.585 - u * 0.035
                x = side * (x_bot + v * (x_top - x_bot) + math.sin(v * math.pi) * 0.015)
                row.append((x, y, z))
            cp_grid.append(row)
        add_curved_grid_patch(bm, cp_grid, mat_idx=1, thickness=0.014 * side)

        # Lower window weatherstrip trim along beltline
        add_box(bm, (side * 0.792, 0.06, 0.915), (0.018, 1.88, 0.018), mat_idx=2, rot_euler=(0.035, 0.0, 0.0))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("WindowsPillars_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("WindowsPillars", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mats['glass'])
    obj.data.materials.append(mats['paint'])
    obj.data.materials.append(mats['plastic'])
    return obj


def build_roof_spoiler_and_interior(mats):
    bm = bmesh.new()
    # 0 = paint, 1 = plastic, 2 = taillight (3rd brake light)

    # Roof spoiler above the tailgate
    sp_grid = []
    for r in range(4):
        v = r / 3.0
        y = 1.32 + v * (1.60 - 1.32)
        z_center = 1.422 + v * 0.018 - (v * v) * 0.012
        row = []
        for c in range(9):
            u = (c / 8.0) * 2.0 - 1.0
            x = u * (0.565 - v * 0.025)
            z = z_center - (u * u) * 0.022
            row.append((x, y, z))
        sp_grid.append(row)
    add_curved_grid_patch(bm, sp_grid, mat_idx=0, thickness=-0.026)

    # Black aerodynamic side fins under the spoiler flanking the rear glass
    for side in (-1.0, 1.0):
        add_box(bm, (side * 0.555, 1.54, 1.28), (0.022, 0.24, 0.22), mat_idx=1, rot_euler=(-0.58, 0.0, 0.0))

    # High-mount 3rd brake light strip under spoiler trailing edge
    add_box(bm, (0.0, 1.59, 1.408), (0.38, 0.022, 0.016), mat_idx=2)

    # Shark-fin roof antenna
    add_box(bm, (0.0, 1.16, 1.455), (0.032, 0.14, 0.065), mat_idx=0, rot_euler=(-0.25, 0.0, 0.0))

    # Interior cabin silhouettes (dashboard, steering wheel, front bucket seats, rear bench)
    # Dashboard
    add_box(bm, (0.0, -0.74, 0.84), (1.26, 0.36, 0.22), mat_idx=1)
    # Steering wheel
    add_box(bm, (-0.34, -0.52, 0.94), (0.32, 0.05, 0.32), mat_idx=1, rot_euler=(-0.38, 0.0, 0.0))
    # Front seats + headrests
    for side in (-1.0, 1.0):
        add_box(bm, (side * 0.32, -0.08, 0.56), (0.44, 0.46, 0.14), mat_idx=1)
        add_box(bm, (side * 0.32, 0.10, 0.82), (0.42, 0.12, 0.48), mat_idx=1, rot_euler=(-0.22, 0.0, 0.0))
        add_box(bm, (side * 0.32, 0.15, 1.14), (0.20, 0.10, 0.16), mat_idx=1)
    # Rear bench + headrests
    add_box(bm, (0.0, 0.78, 0.80), (1.20, 0.14, 0.44), mat_idx=1, rot_euler=(-0.18, 0.0, 0.0))
    for rx in (-0.36, 0.0, 0.36):
        add_box(bm, (rx, 0.84, 1.09), (0.18, 0.09, 0.13), mat_idx=1)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("SpoilerInterior_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("SpoilerInterior", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mats['paint'])
    obj.data.materials.append(mats['plastic'])
    obj.data.materials.append(mats['taillight'])
    return obj


def build_bumpers_and_grilles(mats):
    bm = bmesh.new()
    # 0 = grille, 1 = plastic, 2 = chrome, 3 = paint, 4 = taillight

    # 1. Front Lower Honeycomb Grille (curved patch recessed at front bumper)
    lg_grid = []
    for r in range(4):
        v = r / 3.0
        z = 0.21 + v * (0.37 - 0.21)
        row = []
        for c in range(9):
            u = (c / 8.0) * 2.0 - 1.0
            x = u * (0.58 - v * 0.04)
            y = -2.132 + (u * u) * 0.095
            row.append((x, y, z))
        lg_grid.append(row)
    add_curved_grid_patch(bm, lg_grid, mat_idx=0, thickness=0.025)

    # Lower bumper splitter lip + horizontal intake strakes
    for z_bar in (0.195, 0.26, 0.325, 0.38):
        bar_grid = []
        for r in range(2):
            zz = z_bar + r * 0.014
            row = []
            for c in range(9):
                u = (c / 8.0) * 2.0 - 1.0
                x = u * 0.76
                y = -2.142 + (u * u) * 0.135
                row.append((x, y, zz))
            bar_grid.append(row)
        add_curved_grid_patch(bm, bar_grid, mat_idx=1, thickness=0.022)

    # Side bumper C-bezels around side air intakes
    for side in (-1.0, 1.0):
        add_box(bm, (side * 0.67, -2.04, 0.29), (0.16, 0.04, 0.16), mat_idx=1, rot_euler=(0.0, 0.0, side * 0.32))
        add_box(bm, (side * 0.67, -2.055, 0.33), (0.14, 0.02, 0.018), mat_idx=2, rot_euler=(0.0, 0.0, side * 0.32))

    # 2. Upper Radiator Grille + Chrome Trim Strip + Central VW-style Emblem
    ug_grid = []
    for r in range(3):
        v = r / 2.0
        z = 0.635 + v * (0.70 - 0.635)
        row = []
        for c in range(9):
            u = (c / 8.0) * 2.0 - 1.0
            x = u * 0.51
            y = -2.095 + (u * u) * 0.075
            row.append((x, y, z))
        ug_grid.append(row)
    add_curved_grid_patch(bm, ug_grid, mat_idx=0, thickness=0.025)

    # Chrome strip across upper grille
    cs_grid = []
    for r in range(2):
        z = 0.658 + r * 0.014
        row = []
        for c in range(9):
            u = (c / 8.0) * 2.0 - 1.0
            x = u * 0.52
            y = -2.104 + (u * u) * 0.075
            row.append((x, y, z))
        cs_grid.append(row)
    add_curved_grid_patch(bm, cs_grid, mat_idx=2, thickness=0.015)

    # Front & Rear circular emblems
    for ey, ez, ny in ((-2.108, 0.675, -1.0), (2.018, 0.855, 1.0)):
        res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=20, radius1=0.058, radius2=0.058, depth=0.018)
        for v in res['verts']:
            v.co = Matrix.Rotation(math.pi * 0.5, 4, 'X') @ v.co
            v.co += Vector((0.0, ey, ez))
        for f in bm.faces:
            if all(v in res['verts'] for v in f.verts):
                f.material_index = 2

    # 3. Rear Bumper Lower Valance / Diffuser + Reflectors + Twin Exhaust Tips
    rd_grid = []
    for r in range(4):
        v = r / 3.0
        z = 0.195 + v * (0.335 - 0.195)
        row = []
        for c in range(9):
            u = (c / 8.0) * 2.0 - 1.0
            x = u * 0.72
            y = 2.132 - (u * u) * 0.095 - (1.0 - v) * 0.025
            row.append((x, y, z))
        rd_grid.append(row)
    add_curved_grid_patch(bm, rd_grid, mat_idx=1, thickness=-0.025)

    # Diffuser vertical fins
    for fx in (-0.27, -0.09, 0.09, 0.27):
        add_box(bm, (fx, 2.118, 0.245), (0.016, 0.045, 0.085), mat_idx=1)

    # Rear bumper red reflectors
    for side in (-1.0, 1.0):
        add_box(bm, (side * 0.65, 2.095, 0.315), (0.16, 0.02, 0.024), mat_idx=4, rot_euler=(0.0, 0.0, -side * 0.24))

    # Twin chrome exhaust tips on left rear
    for ex in (-0.49, -0.39):
        res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16, radius1=0.034, radius2=0.034, depth=0.09)
        for v in res['verts']:
            v.co = Matrix.Rotation(math.pi * 0.5, 4, 'X') @ v.co
            v.co += Vector((ex, 2.11, 0.225))
        for f in bm.faces:
            if all(v in res['verts'] for v in f.verts):
                f.material_index = 2

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("BumpersGrilles_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("BumpersGrilles", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mats['grille'])
    obj.data.materials.append(mats['plastic'])
    obj.data.materials.append(mats['chrome'])
    obj.data.materials.append(mats['paint'])
    obj.data.materials.append(mats['taillight'])
    return obj


def build_lights_mirrors_handles_plates_wipers(mats):
    bm = bmesh.new()
    # 0 = headlight, 1 = taillight, 2 = plastic, 3 = paint, 4 = chrome, 5 = plate

    for side in (-1.0, 1.0):
        # 1. LED Headlights: Recessed dark reflector + internal LED DRL tubes + clear outer lens
        hl_ref_grid = []
        hl_lens_grid = []
        for r in range(4):
            v = r / 3.0
            row_ref = []
            row_lens = []
            for c in range(6):
                u = c / 5.0
                x = side * (0.50 + u * (0.835 - 0.50))
                y_front = -2.075 + u * (-1.74 - (-2.075))
                z_bot = 0.635 + u * (0.675 - 0.635)
                z_top = 0.705 + u * (0.765 - 0.705)
                z = z_bot + v * (z_top - z_bot)
                y_lens = y_front + v * 0.045 - math.sin(u * math.pi) * 0.018
                y_ref = y_lens + 0.022 + math.sin(v * math.pi) * 0.012
                row_ref.append((x, y_ref, z))
                row_lens.append((x, y_lens, z))
            hl_ref_grid.append(row_ref)
            hl_lens_grid.append(row_lens)
        add_curved_grid_patch(bm, hl_ref_grid, mat_idx=2, thickness=0.015)
        add_curved_grid_patch(bm, hl_lens_grid, mat_idx=0, thickness=0.005)

        # Dual internal LED DRL U-signature tubes & projector domes inside the headlight
        for px, py, pz in ((0.59, -1.96, 0.675), (0.72, -1.86, 0.695)):
            add_box(bm, (side * px, py, pz), (0.075, 0.025, 0.048), mat_idx=4, rot_euler=(0.0, 0.0, side * 0.62))
            add_box(bm, (side * px, py - 0.008, pz - 0.018), (0.085, 0.012, 0.012), mat_idx=0, rot_euler=(0.0, 0.0, side * 0.62))

        # 2. LED Taillights: Inner reflector + LED bars + outer lens shell
        tl_ref_grid = []
        tl_lens_grid = []
        for r in range(4):
            v = r / 3.0
            row_ref = []
            row_lens = []
            for c in range(6):
                u = c / 5.0
                x = side * (0.43 + u * (0.835 - 0.43))
                y_back = 2.045 - u * (2.045 - 1.83)
                z_bot = 0.795 + u * (0.815 - 0.795)
                z_top = 0.875 + u * (0.915 - 0.875)
                z = z_bot + v * (z_top - z_bot)
                y_lens = y_back - v * 0.025 + math.sin(u * math.pi) * 0.016
                y_ref = y_lens - 0.018
                row_ref.append((x, y_ref, z))
                row_lens.append((x, y_lens, z))
            tl_ref_grid.append(row_ref)
            tl_lens_grid.append(row_lens)
        add_curved_grid_patch(bm, tl_ref_grid, mat_idx=2, thickness=-0.015)
        add_curved_grid_patch(bm, tl_lens_grid, mat_idx=1, thickness=-0.005)

        # 3. Side Mirrors: Stalk + sculpted painted housing cap + LED blinker + mirror glass
        add_box(bm, (side * 0.825, -0.78, 0.90), (0.09, 0.06, 0.032), mat_idx=2, rot_euler=(0.0, -side * 0.25, side * 0.2))
        # Mirror cap (sculpted grid)
        mc_grid = []
        for r in range(4):
            v = r / 3.0
            z = 0.885 + v * 0.095
            row = []
            for c in range(5):
                u = c / 4.0
                x = side * (0.855 + u * 0.145)
                y = -0.82 + math.sin(u * math.pi) * 0.025 + math.sin(v * math.pi) * 0.018
                row.append((x, y, z))
            mc_grid.append(row)
        add_curved_grid_patch(bm, mc_grid, mat_idx=3, thickness=0.055)
        # Mirror glass facing +Y
        add_box(bm, (side * 0.928, -0.758, 0.932), (0.125, 0.008, 0.078), mat_idx=4, rot_euler=(0.0, 0.0, -side * 0.12))
        # Mirror LED turn signal strip
        add_box(bm, (side * 0.935, -0.832, 0.925), (0.12, 0.012, 0.010), mat_idx=0, rot_euler=(0.0, 0.0, -side * 0.12))

        # 4. Door Handles (Front & Rear Doors)
        for hy, hz in ((-0.20, 0.825), (0.64, 0.845)):
            # Recessed dark cup
            add_box(bm, (side * 0.875, hy, hz), (0.012, 0.16, 0.042), mat_idx=2)
            # Painted pull bar
            add_box(bm, (side * 0.892, hy - 0.01, hz), (0.018, 0.145, 0.024), mat_idx=3)
            # Keyhole end cap
            add_box(bm, (side * 0.890, hy + 0.078, hz), (0.018, 0.032, 0.024), mat_idx=3)

    # 5. Number Plates (Front and Rear)
    # Front plate at Y = -2.142, Z = 0.465
    add_box(bm, (0.0, -2.138, 0.465), (0.535, 0.016, 0.122), mat_idx=2)
    add_box(bm, (0.0, -2.148, 0.465), (0.515, 0.008, 0.108), mat_idx=5)
    # Rear plate at Y = 2.092, Z = 0.645
    add_box(bm, (0.0, 2.092, 0.645), (0.535, 0.016, 0.122), mat_idx=2, rot_euler=(-0.12, 0.0, 0.0))
    add_box(bm, (0.0, 2.100, 0.645), (0.515, 0.008, 0.108), mat_idx=5, rot_euler=(-0.12, 0.0, 0.0))

    # 6. Wipers (2 front windscreen wipers + 1 rear tailgate wiper)
    for wx_start, wx_end, wy in ((-0.48, 0.06, -1.01), (-0.04, 0.52, -0.99)):
        w_mid = 0.5 * (wx_start + wx_end)
        w_len = abs(wx_end - wx_start)
        add_box(bm, (w_mid, wy, 0.895), (w_len, 0.016, 0.014), mat_idx=2, rot_euler=(0.45, 0.0, -0.06))
        add_box(bm, (wx_start + 0.04, wy - 0.02, 0.885), (0.03, 0.04, 0.02), mat_idx=2)

    # Rear wiper at base of rear tailgate glass
    add_box(bm, (0.16, 1.945, 0.945), (0.34, 0.015, 0.014), mat_idx=2, rot_euler=(-0.55, 0.0, 0.04))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("Details_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("CarDetails", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mats['headlight'])
    obj.data.materials.append(mats['taillight'])
    obj.data.materials.append(mats['plastic'])
    obj.data.materials.append(mats['paint'])
    obj.data.materials.append(mats['chrome'])
    obj.data.materials.append(mats['plate'])
    return obj


def build_four_wheels(mats):
    bm = bmesh.new()
    # 0 = tyre, 1 = alloy, 2 = chrome (brake disc & lug bolts), 3 = plastic (inner barrel & brake caliper)

    wheel_positions = [
        (-0.775, -1.31, 0.316, -1.0),
        (0.775, -1.31, 0.316, 1.0),
        (-0.775, 1.31, 0.316, -1.0),
        (0.775, 1.31, 0.316, 1.0),
    ]

    n_seg = 36
    # Tyre + rim cross-section profile in (local_x, radius) where local_x = +1 points outward
    # Outer tyre radius = 0.316 m (touches Z=0 when center is at Z=0.316), 16-inch rim radius = 0.203 m
    tyre_profile = [
        (0.088, 0.203),   # outer bead
        (0.101, 0.228),   # lower outer sidewall
        (0.104, 0.262),   # mid outer sidewall bulge
        (0.098, 0.298),   # outer shoulder
        (0.082, 0.314),   # outer tread edge
        (0.000, 0.316),   # tread center crown (touches Z=0!)
        (-0.082, 0.314),  # inner tread edge
        (-0.098, 0.298),  # inner shoulder
        (-0.102, 0.258),  # inner sidewall
        (-0.088, 0.203),  # inner bead
    ]

    rim_profile = [
        (-0.088, 0.203),  # inner rim lip
        (-0.070, 0.184),  # inner barrel drop
        (0.055, 0.186),   # outer barrel bed
        (0.082, 0.196),   # outer flange step
        (0.090, 0.203),   # outer rim lip
        (0.084, 0.190),   # spoke outer attachment ring
    ]

    for wx, wy, wz, side in wheel_positions:
        # 1. Tyre ring
        t_rings = []
        for s in range(n_seg):
            ang = (2.0 * math.pi * s) / n_seg
            ca = math.cos(ang)
            sa = math.sin(ang)
            ring = []
            for lx, r in tyre_profile:
                x = wx + side * lx
                y = wy + r * ca
                z = wz + r * sa
                ring.append(bm.verts.new((x, y, z)))
            t_rings.append(ring)

        for s in range(n_seg):
            sn = (s + 1) % n_seg
            for p in range(len(tyre_profile) - 1):
                if side > 0:
                    verts = (t_rings[s][p], t_rings[sn][p], t_rings[sn][p + 1], t_rings[s][p + 1])
                else:
                    verts = (t_rings[s][p], t_rings[s][p + 1], t_rings[sn][p + 1], t_rings[sn][p])
                f = bm.faces.new(verts)
                f.material_index = 0

        # 2. Rim barrel & outer flange
        r_rings = []
        for s in range(n_seg):
            ang = (2.0 * math.pi * s) / n_seg
            ca = math.cos(ang)
            sa = math.sin(ang)
            ring = []
            for lx, r in rim_profile:
                x = wx + side * lx
                y = wy + r * ca
                z = wz + r * sa
                ring.append(bm.verts.new((x, y, z)))
            r_rings.append(ring)

        for s in range(n_seg):
            sn = (s + 1) % n_seg
            for p in range(len(rim_profile) - 1):
                if side > 0:
                    verts = (r_rings[s][p], r_rings[sn][p], r_rings[sn][p + 1], r_rings[s][p + 1])
                else:
                    verts = (r_rings[s][p], r_rings[s][p + 1], r_rings[sn][p + 1], r_rings[sn][p])
                f = bm.faces.new(verts)
                f.material_index = 1 if p >= 2 else 3

        # 3. Central hub cylinder + 5 lug bolts
        res_hub = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=20, radius1=0.062, radius2=0.056, depth=0.036)
        for v in res_hub['verts']:
            v.co = Matrix.Rotation(side * math.pi * 0.5, 4, 'Y') @ v.co
            v.co += Vector((wx + side * 0.064, wy, wz))
        for f in bm.faces:
            if all(v in res_hub['verts'] for v in f.verts):
                f.material_index = 1

        # 5 Lug bolts
        for b_idx in range(5):
            b_ang = (2.0 * math.pi * b_idx) / 5.0
            by = wy + 0.036 * math.cos(b_ang)
            bz = wz + 0.036 * math.sin(b_ang)
            add_box(bm, (wx + side * 0.081, by, bz), (0.012, 0.014, 0.014), mat_idx=2, rot_euler=(b_ang, 0.0, 0.0))

        # 4. 10 Multi-spoke dark alloy blades (5 twin-spoke V-pairs)
        for sp_pair in range(5):
            base_ang = (2.0 * math.pi * sp_pair) / 5.0
            for sub_dir in (-1.0, 1.0):
                ang_in = base_ang + sub_dir * 0.14
                ang_out = base_ang + sub_dir * 0.26
                r_in = 0.052
                r_out = 0.192
                w_in = 0.014
                w_out = 0.011

                t_in = Vector((-math.sin(ang_in), math.cos(ang_in)))
                t_out = Vector((-math.sin(ang_out), math.cos(ang_out)))
                c_in = Vector((wy + r_in * math.cos(ang_in), wz + r_in * math.sin(ang_in)))
                c_out = Vector((wy + r_out * math.cos(ang_out), wz + r_out * math.sin(ang_out)))

                x_front_in = wx + side * 0.076
                x_front_out = wx + side * 0.086
                x_back_in = wx + side * 0.052
                x_back_out = wx + side * 0.064

                p0 = bm.verts.new((x_front_in, (c_in - t_in * w_in).x, (c_in - t_in * w_in).y))
                p1 = bm.verts.new((x_front_in, (c_in + t_in * w_in).x, (c_in + t_in * w_in).y))
                p2 = bm.verts.new((x_front_out, (c_out + t_out * w_out).x, (c_out + t_out * w_out).y))
                p3 = bm.verts.new((x_front_out, (c_out - t_out * w_out).x, (c_out - t_out * w_out).y))

                q0 = bm.verts.new((x_back_in, (c_in - t_in * w_in).x, (c_in - t_in * w_in).y))
                q1 = bm.verts.new((x_back_in, (c_in + t_in * w_in).x, (c_in + t_in * w_in).y))
                q2 = bm.verts.new((x_back_out, (c_out + t_out * w_out).x, (c_out + t_out * w_out).y))
                q3 = bm.verts.new((x_back_out, (c_out - t_out * w_out).x, (c_out - t_out * w_out).y))

                spoke_faces = [
                    bm.faces.new((p0, p1, p2, p3)),
                    bm.faces.new((q3, q2, q1, q0)),
                    bm.faces.new((p0, p3, q3, q0)),
                    bm.faces.new((p2, p1, q1, q2)),
                    bm.faces.new((p3, p2, q2, q3)),
                    bm.faces.new((p1, p0, q0, q1)),
                ]
                for sf in spoke_faces:
                    sf.material_index = 1

        # 5. Brake Disc & Brake Caliper behind the alloy spokes
        res_disc = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=24, radius1=0.148, radius2=0.148, depth=0.020)
        for v in res_disc['verts']:
            v.co = Matrix.Rotation(math.pi * 0.5, 4, 'Y') @ v.co
            v.co += Vector((wx + side * 0.022, wy, wz))
        for f in bm.faces:
            if all(v in res_disc['verts'] for v in f.verts):
                f.material_index = 2

        # Brake caliper housing
        cal_y = wy + (0.115 if wy < 0 else -0.115)
        add_box(bm, (wx + side * 0.026, cal_y, wz + 0.045), (0.048, 0.068, 0.125), mat_idx=3, rot_euler=(0.35, 0.0, 0.0))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("Wheels_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("CarWheels", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mats['tyre'])
    obj.data.materials.append(mats['alloy'])
    obj.data.materials.append(mats['chrome'])
    obj.data.materials.append(mats['plastic'])
    return obj


def join_and_finalize_geometry(parts, target_name="CarHatch"):
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()

    car_obj = bpy.context.view_layer.objects.active
    car_obj.name = target_name
    car_obj.data.name = target_name + "_Mesh"

    # Ensure tyres touch Z=0 and origin is at (0, 0, 0) bottom centre between the wheels
    verts = car_obj.data.vertices
    min_z = min(v.co.z for v in verts)
    if abs(min_z) > 1e-5:
        for v in verts:
            v.co.z -= min_z
    car_obj.location = (0.0, 0.0, 0.0)
    car_obj.rotation_euler = (0.0, 0.0, 0.0)
    car_obj.scale = (1.0, 1.0, 1.0)
    car_obj.data.update()

    # Smooth shading with sharp edges on panel creases (> 34 deg)
    bm = bmesh.new()
    bm.from_mesh(car_obj.data)
    angle_thresh = math.radians(34.0)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2:
            ang = e.calc_face_angle(0.0)
            e.smooth = (ang < angle_thresh)
        else:
            e.smooth = False
    bm.to_mesh(car_obj.data)
    bm.free()

    if hasattr(car_obj.data, "use_auto_smooth"):
        try:
            car_obj.data.use_auto_smooth = True
            car_obj.data.auto_smooth_angle = math.radians(35.0)
        except Exception:
            pass

    # Verify triangle count is strictly within 8000-20000
    tris = sum(len(p.vertices) - 2 for p in car_obj.data.polygons)
    if tris < 8000:
        bm = bmesh.new()
        bm.from_mesh(car_obj.data)
        faces_sorted = sorted(bm.faces, key=lambda f: f.calc_area(), reverse=True)
        need_faces = max(1, (9500 - tris) // 6)
        bmesh.ops.subdivide_edges(
            bm,
            edges=list({e for f in faces_sorted[:need_faces] for e in f.edges}),
            cuts=1,
            use_grid_fill=True,
        )
        bm.to_mesh(car_obj.data)
        bm.free()
    elif tris > 20000:
        dec = car_obj.modifiers.new(name="Decimate", type='DECIMATE')
        dec.ratio = 16500.0 / float(tris)
        bpy.ops.object.modifier_apply(modifier=dec.name)

    car_obj.data.update()
    return car_obj


def unwrap_and_bake(car_obj, out_dir, name="CarHatch"):
    bpy.ops.object.select_all(action='DESELECT')
    car_obj.select_set(True)
    bpy.context.view_layer.objects.active = car_obj

    if not car_obj.data.uv_layers:
        car_obj.data.uv_layers.new(name="UVMap")
    car_obj.data.uv_layers.active_index = 0

    # 2. UV unwrap with exact requested operators and arguments
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.tool_settings.use_uv_select_sync = True
    bpy.ops.mesh.select_all(action='SELECT')
    try:
        bpy.ops.uv.select_all(action='SELECT')
    except Exception:
        pass
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.01)
    bpy.ops.mesh.select_all(action='SELECT')
    try:
        bpy.ops.uv.select_all(action='SELECT')
    except Exception:
        pass
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')

    # 3. Create 2048x2048 images: "<Name>_albedo" and "<Name>_normal" (Non-Color)
    img_albedo = bpy.data.images.new(name=f"{name}_albedo", width=2048, height=2048, alpha=False)
    img_albedo.colorspace_settings.name = 'sRGB'

    img_normal = bpy.data.images.new(name=f"{name}_normal", width=2048, height=2048, alpha=False)
    img_normal.colorspace_settings.name = 'Non-Color'

    albedo_nodes = {}
    normal_nodes = {}
    saved_metallic = {}

    for mat in car_obj.data.materials:
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        n_alb = nt.nodes.new('ShaderNodeTexImage')
        n_alb.name = "Bake_Albedo_Node"
        n_alb.image = img_albedo
        n_alb.location = (-1200, -600)
        albedo_nodes[mat.name] = n_alb

        n_nrm = nt.nodes.new('ShaderNodeTexImage')
        n_nrm.name = "Bake_Normal_Node"
        n_nrm.image = img_normal
        n_nrm.location = (-1200, -900)
        normal_nodes[mat.name] = n_nrm

        for node in nt.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                m_sock = get_principled_input(node, ['Metallic'])
                t_sock = get_principled_input(node, ['Transmission Weight', 'Transmission'])
                saved_metallic[mat.name] = (
                    m_sock.default_value if m_sock else 0.0,
                    t_sock.default_value if t_sock else 0.0,
                )

    # 4. Configure Cycles CPU, 16 samples, margin 8
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 16
    scene.render.bake.margin = 8

    # Temporarily zero Metallic & Transmission during DIFFUSE COLOR bake so Cycles outputs pure Base Color instead of black on metals
    for mat in car_obj.data.materials:
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        for node in nt.nodes:
            node.select = False
            if node.type == 'BSDF_PRINCIPLED':
                set_principled_input(node, ['Metallic'], 0.0)
                set_principled_input(node, ['Transmission Weight', 'Transmission'], 0.0)
        n_alb = albedo_nodes[mat.name]
        n_alb.select = True
        nt.nodes.active = n_alb

    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=8, use_clear=True)

    # Restore Metallic & Transmission and activate Normal image node in EVERY material before NORMAL bake
    for mat in car_obj.data.materials:
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        m_val, t_val = saved_metallic.get(mat.name, (0.0, 0.0))
        for node in nt.nodes:
            node.select = False
            if node.type == 'BSDF_PRINCIPLED':
                set_principled_input(node, ['Metallic'], m_val)
                set_principled_input(node, ['Transmission Weight', 'Transmission'], t_val)
        n_nrm = normal_nodes[mat.name]
        n_nrm.select = True
        nt.nodes.active = n_nrm

    scene.render.bake.normal_space = 'TANGENT'
    bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=8, use_clear=True)

    # Save PNGs next to output FBX
    albedo_path = os.path.join(out_dir, f"{name}_albedo.png")
    normal_path = os.path.join(out_dir, f"{name}_normal.png")

    img_albedo.filepath_raw = albedo_path
    img_albedo.file_format = 'PNG'
    img_albedo.save()
    img_albedo.filepath = albedo_path
    try:
        img_albedo.pack()
    except Exception:
        pass

    img_normal.filepath_raw = normal_path
    img_normal.file_format = 'PNG'
    img_normal.save()
    img_normal.filepath = normal_path
    try:
        img_normal.pack()
    except Exception:
        pass

    # 5. Replace all slots with ONE material "<Name>_Mat"
    final_mat = bpy.data.materials.new(name=f"{name}_Mat")
    final_mat.use_nodes = True
    nt = final_mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (500, 0)

    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (200, 0)
    set_principled_input(bsdf, ['Roughness'], 0.35)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    tex_alb = nt.nodes.new('ShaderNodeTexImage')
    tex_alb.location = (-350, 200)
    tex_alb.image = img_albedo
    nt.links.new(tex_alb.outputs['Color'], bsdf.inputs['Base Color'])

    tex_nrm = nt.nodes.new('ShaderNodeTexImage')
    tex_nrm.location = (-450, -150)
    tex_nrm.image = img_normal
    img_normal.colorspace_settings.name = 'Non-Color'

    norm_map = nt.nodes.new('ShaderNodeNormalMap')
    norm_map.location = (-120, -150)
    nt.links.new(tex_nrm.outputs['Color'], norm_map.inputs['Color'])
    nt.links.new(norm_map.outputs['Normal'], bsdf.inputs['Normal'])

    car_obj.data.materials.clear()
    car_obj.data.materials.append(final_mat)
    for poly in car_obj.data.polygons:
        poly.material_index = 0


def export_and_render_preview(car_obj, raw_out_path):
    out_path = os.path.abspath(raw_out_path)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if out_path.lower().endswith(".fbx"):
        fbx_path = out_path
        png_path = out_path[:-4] + ".png"
    else:
        fbx_path = out_path + ".fbx"
        png_path = out_path + ".png"

    bpy.ops.object.select_all(action='DESELECT')
    car_obj.select_set(True)
    bpy.context.view_layer.objects.active = car_obj

    bpy.ops.export_scene.fbx(
        filepath=fbx_path,
        use_selection=True,
        bake_space_transform=True,
        axis_forward='-Z',
        axis_up='Y',
        path_mode='COPY',
        embed_textures=True,
    )

    scene = bpy.context.scene
    engine_keys = scene.render.bl_rna.properties['engine'].enum_items.keys()
    if 'BLENDER_EEVEE_NEXT' in engine_keys:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    elif 'BLENDER_EEVEE' in engine_keys:
        scene.render.engine = 'BLENDER_EEVEE'
    else:
        for k in engine_keys:
            if 'EEVEE' in k:
                scene.render.engine = k
                break

    # Grey sky world strength 0.6
    if not scene.world:
        scene.world = bpy.data.worlds.new("PreviewWorld")
    scene.world.use_nodes = True
    w_nt = scene.world.node_tree
    bg_node = None
    for n in w_nt.nodes:
        if n.type == 'BACKGROUND':
            bg_node = n
            break
    if not bg_node:
        w_nt.nodes.clear()
        w_out = w_nt.nodes.new('ShaderNodeOutputWorld')
        bg_node = w_nt.nodes.new('ShaderNodeBackground')
        w_nt.links.new(bg_node.outputs['Background'], w_out.inputs['Surface'])
    bg_node.inputs['Color'].default_value = (0.52, 0.54, 0.57, 1.0)
    bg_node.inputs['Strength'].default_value = 0.6

    # Sun strength 3 from front-left-above
    sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
    sun_data.energy = 3.0
    sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
    bpy.context.collection.objects.link(sun_obj)
    sun_obj.location = (-4.5, -5.5, 6.5)
    sun_dir = Vector((0.0, 0.0, 0.5)) - sun_obj.location
    sun_obj.rotation_euler = sun_dir.to_track_quat('-Z', 'Y').to_euler()

    # Camera at 1.5 m height in a front 3/4 view framing the whole car
    cam_data = bpy.data.cameras.new(name="PreviewCam")
    cam_data.lens = 38.0
    cam_obj = bpy.data.objects.new(name="PreviewCam", object_data=cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = (-3.55, -4.35, 1.5)
    look_target = Vector((0.0, 0.05, 0.66))
    cam_dir = look_target - cam_obj.location
    cam_obj.rotation_euler = cam_dir.to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = png_path
    bpy.ops.render.render(write_still=True)

    if out_path.lower().endswith(".fbx"):
        alt_png = out_path + ".png"
        if alt_png != png_path:
            scene.render.filepath = alt_png
            bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv
    if "--" in argv:
        extra = argv[argv.index("--") + 1:]
        out_arg = extra[0] if extra else "CarHatch.fbx"
    else:
        out_arg = "CarHatch.fbx"

    out_abs = os.path.abspath(out_arg)
    out_dir = os.path.dirname(out_abs)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    else:
        out_dir = os.getcwd()

    clear_scene()
    mats = create_procedural_materials()

    body_obj = build_body_shell(mats)
    win_obj = build_windows_and_pillars(mats)
    sp_obj = build_roof_spoiler_and_interior(mats)
    bmp_obj = build_bumpers_and_grilles(mats)
    det_obj = build_lights_mirrors_handles_plates_wipers(mats)
    whl_obj = build_four_wheels(mats)

    car_obj = join_and_finalize_geometry(
        [body_obj, win_obj, sp_obj, bmp_obj, det_obj, whl_obj],
        target_name="CarHatch",
    )

    unwrap_and_bake(car_obj, out_dir=out_dir, name="CarHatch")
    export_and_render_preview(car_obj, out_abs)

    tris = sum(len(p.vertices) - 2 for p in car_obj.data.polygons)
    print("TRIS", tris)


if __name__ == "__main__":
    main()

