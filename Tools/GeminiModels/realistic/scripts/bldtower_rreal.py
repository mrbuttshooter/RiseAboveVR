import bpy
import bmesh
import mathutils
import math
import sys
import os


def clear_scene():
    if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for col in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.images,
        bpy.data.lights,
        bpy.data.cameras,
        bpy.data.worlds,
    ):
        for item in list(col):
            col.remove(item)


def set_principled_default(bsdf, socket_names, value):
    for name in socket_names:
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = value
            return


def make_mix_color(nodes, links, blend_type, fac_in, col1_in, col2_in):
    node = nodes.new('ShaderNodeMix')
    node.data_type = 'RGBA'
    node.blend_type = blend_type
    node.clamp_factor = True
    if isinstance(fac_in, (int, float)):
        node.inputs['Factor'].default_value = float(fac_in)
    else:
        links.new(fac_in, node.inputs['Factor'])
    if isinstance(col1_in, tuple):
        node.inputs['A'].default_value = col1_in
    else:
        links.new(col1_in, node.inputs['A'])
    if isinstance(col2_in, tuple):
        node.inputs['B'].default_value = col2_in
    else:
        links.new(col2_in, node.inputs['B'])
    return node.outputs['Result']


def add_grime_layer(nodes, links, obj_coord_out, base_col_out, storey_h=3.35, grime_strength=0.42):
    sep = nodes.new('ShaderNodeSeparateXYZ')
    links.new(obj_coord_out, sep.inputs['Vector'])

    # Near-ground Z gradient (0 at ground -> 1 above 18 m)
    ground_div = nodes.new('ShaderNodeMath')
    ground_div.operation = 'DIVIDE'
    ground_div.use_clamp = True
    links.new(sep.outputs['Z'], ground_div.inputs[0])
    ground_div.inputs[1].default_value = 18.0

    ground_inv = nodes.new('ShaderNodeMath')
    ground_inv.operation = 'SUBTRACT'
    ground_inv.use_clamp = True
    ground_inv.inputs[0].default_value = 1.0
    links.new(ground_div.outputs['Value'], ground_inv.inputs[1])

    # Under-sill / floor-band repeating vertical gradient in Z
    sill_mod = nodes.new('ShaderNodeMath')
    sill_mod.operation = 'MODULO'
    links.new(sep.outputs['Z'], sill_mod.inputs[0])
    sill_mod.inputs[1].default_value = storey_h

    sill_div = nodes.new('ShaderNodeMath')
    sill_div.operation = 'DIVIDE'
    sill_div.use_clamp = True
    links.new(sill_mod.outputs['Value'], sill_div.inputs[0])
    sill_div.inputs[1].default_value = storey_h

    # Peak grime near top of each storey (right under sill/cornice above)
    sill_pow = nodes.new('ShaderNodeMath')
    sill_pow.operation = 'POWER'
    sill_pow.use_clamp = True
    links.new(sill_div.outputs['Value'], sill_pow.inputs[0])
    sill_pow.inputs[1].default_value = 4.0

    # Stretched vertical noise for rainwater/grime streaks
    map_streak = nodes.new('ShaderNodeMapping')
    map_streak.inputs['Scale'].default_value = (2.2, 2.2, 0.35)
    links.new(obj_coord_out, map_streak.inputs['Vector'])

    noise_streak = nodes.new('ShaderNodeTexNoise')
    noise_streak.inputs['Scale'].default_value = 3.5
    noise_streak.inputs['Detail'].default_value = 6.0
    noise_streak.inputs['Roughness'].default_value = 0.65
    links.new(map_streak.outputs['Vector'], noise_streak.inputs['Vector'])

    comb_z = nodes.new('ShaderNodeMath')
    comb_z.operation = 'MAXIMUM'
    comb_z.use_clamp = True
    links.new(ground_inv.outputs['Value'], comb_z.inputs[0])
    links.new(sill_pow.outputs['Value'], comb_z.inputs[1])

    grime_mask = nodes.new('ShaderNodeMath')
    grime_mask.operation = 'MULTIPLY'
    grime_mask.use_clamp = True
    links.new(comb_z.outputs['Value'], grime_mask.inputs[0])
    links.new(noise_streak.outputs['Fac'], grime_mask.inputs[1])

    grime_scaled = nodes.new('ShaderNodeMath')
    grime_scaled.operation = 'MULTIPLY'
    grime_scaled.use_clamp = True
    links.new(grime_mask.outputs['Value'], grime_scaled.inputs[0])
    grime_scaled.inputs[1].default_value = grime_strength

    dirty_col = (0.045, 0.042, 0.038, 1.0)
    return make_mix_color(nodes, links, 'MIX', grime_scaled.outputs['Value'], base_col_out, dirty_col)


def make_triplanar_brick_vector(nodes, links, obj_coord_out):
    sep = nodes.new('ShaderNodeSeparateXYZ')
    links.new(obj_coord_out, sep.inputs['Vector'])

    add_xy = nodes.new('ShaderNodeMath')
    add_xy.operation = 'ADD'
    links.new(sep.outputs['X'], add_xy.inputs[0])
    links.new(sep.outputs['Y'], add_xy.inputs[1])

    comb = nodes.new('ShaderNodeCombineXYZ')
    links.new(add_xy.outputs['Value'], comb.inputs['X'])
    links.new(sep.outputs['Z'], comb.inputs['Y'])
    comb.inputs['Z'].default_value = 0.0
    return comb.outputs['Vector']


def create_procedural_materials():
    mats = {}

    # 0: Brick with mortar and colour variation (lobby piers & podium accents)
    mat_brick = bpy.data.materials.new("Mat_Brick")
    mat_brick.use_nodes = True
    n = mat_brick.node_tree.nodes
    l = mat_brick.node_tree.links
    n.clear()
    out = n.new('ShaderNodeOutputMaterial')
    bsdf = n.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.82
    l.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    tc = n.new('ShaderNodeTexCoord')
    vec2d = make_triplanar_brick_vector(n, l, tc.outputs['Object'])

    noise_var = n.new('ShaderNodeTexNoise')
    noise_var.inputs['Scale'].default_value = 2.8
    noise_var.inputs['Detail'].default_value = 4.0
    l.new(tc.outputs['Object'], noise_var.inputs['Vector'])

    col_b1 = make_mix_color(
        n, l, 'MIX', noise_var.outputs['Fac'],
        (0.36, 0.16, 0.11, 1.0), (0.46, 0.22, 0.15, 1.0)
    )
    col_b2 = make_mix_color(
        n, l, 'MIX', noise_var.outputs['Fac'],
        (0.24, 0.11, 0.08, 1.0), (0.32, 0.14, 0.10, 1.0)
    )

    brick = n.new('ShaderNodeTexBrick')
    brick.offset = 0.5
    brick.inputs['Mortar'].default_value = (0.52, 0.50, 0.47, 1.0)
    brick.inputs['Scale'].default_value = 3.2
    brick.inputs['Mortar Size'].default_value = 0.025
    brick.inputs['Mortar Smooth'].default_value = 0.1
    brick.inputs['Bias'].default_value = 0.1
    brick.inputs['Brick Width'].default_value = 0.75
    brick.inputs['Row Height'].default_value = 0.28
    l.new(vec2d, brick.inputs['Vector'])
    l.new(col_b1, brick.inputs['Color1'])
    l.new(col_b2, brick.inputs['Color2'])

    col_grime = add_grime_layer(n, l, tc.outputs['Object'], brick.outputs['Color'], 3.35, 0.48)
    l.new(col_grime, bsdf.inputs['Base Color'])

    bump = n.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.55
    bump.inputs['Distance'].default_value = 0.015
    l.new(brick.outputs['Fac'], bump.inputs['Height'])
    l.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    mats['brick'] = mat_brick

    # 1: Painted render / stucco with stains
    mat_stucco = bpy.data.materials.new("Mat_Stucco")
    mat_stucco.use_nodes = True
    n = mat_stucco.node_tree.nodes
    l = mat_stucco.node_tree.links
    n.clear()
    out = n.new('ShaderNodeOutputMaterial')
    bsdf = n.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.78
    l.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    tc = n.new('ShaderNodeTexCoord')
    noise_stain = n.new('ShaderNodeTexNoise')
    noise_stain.inputs['Scale'].default_value = 0.85
    noise_stain.inputs['Detail'].default_value = 6.0
    noise_stain.inputs['Roughness'].default_value = 0.65
    l.new(tc.outputs['Object'], noise_stain.inputs['Vector'])

    noise_fine = n.new('ShaderNodeTexNoise')
    noise_fine.inputs['Scale'].default_value = 14.0
    noise_fine.inputs['Detail'].default_value = 8.0
    l.new(tc.outputs['Object'], noise_fine.inputs['Vector'])

    stucco_col = make_mix_color(
        n, l, 'MIX', noise_stain.outputs['Fac'],
        (0.64, 0.62, 0.58, 1.0), (0.45, 0.43, 0.39, 1.0)
    )
    stucco_grime = add_grime_layer(n, l, tc.outputs['Object'], stucco_col, 3.35, 0.45)
    l.new(stucco_grime, bsdf.inputs['Base Color'])

    bump = n.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.35
    bump.inputs['Distance'].default_value = 0.01
    l.new(noise_fine.outputs['Fac'], bump.inputs['Height'])
    l.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    mats['stucco'] = mat_stucco

    # 2: Concrete with seams
    mat_conc = bpy.data.materials.new("Mat_Concrete")
    mat_conc.use_nodes = True
    n = mat_conc.node_tree.nodes
    l = mat_conc.node_tree.links
    n.clear()
    out = n.new('ShaderNodeOutputMaterial')
    bsdf = n.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.76
    l.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    tc = n.new('ShaderNodeTexCoord')
    vec2d = make_triplanar_brick_vector(n, l, tc.outputs['Object'])

    conc_noise = n.new('ShaderNodeTexNoise')
    conc_noise.inputs['Scale'].default_value = 1.6
    conc_noise.inputs['Detail'].default_value = 7.0
    conc_noise.inputs['Roughness'].default_value = 0.6
    l.new(tc.outputs['Object'], conc_noise.inputs['Vector'])

    c1 = make_mix_color(
        n, l, 'MIX', conc_noise.outputs['Fac'],
        (0.46, 0.47, 0.48, 1.0), (0.56, 0.57, 0.58, 1.0)
    )
    c2 = make_mix_color(
        n, l, 'MIX', conc_noise.outputs['Fac'],
        (0.40, 0.41, 0.42, 1.0), (0.51, 0.52, 0.53, 1.0)
    )

    seams = n.new('ShaderNodeTexBrick')
    seams.offset = 0.0
    seams.inputs['Mortar'].default_value = (0.22, 0.23, 0.24, 1.0)
    seams.inputs['Scale'].default_value = 0.65
    seams.inputs['Mortar Size'].default_value = 0.012
    seams.inputs['Mortar Smooth'].default_value = 0.05
    seams.inputs['Brick Width'].default_value = 1.8
    seams.inputs['Row Height'].default_value = 1.1
    l.new(vec2d, seams.inputs['Vector'])
    l.new(c1, seams.inputs['Color1'])
    l.new(c2, seams.inputs['Color2'])

    conc_grime = add_grime_layer(n, l, tc.outputs['Object'], seams.outputs['Color'], 3.35, 0.42)
    l.new(conc_grime, bsdf.inputs['Base Color'])

    bump_h = n.new('ShaderNodeMath')
    bump_h.operation = 'MULTIPLY'
    l.new(seams.outputs['Fac'], bump_h.inputs[0])
    l.new(conc_noise.outputs['Fac'], bump_h.inputs[1])

    bump = n.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.45
    bump.inputs['Distance'].default_value = 0.012
    l.new(bump_h.outputs['Value'], bump.inputs['Height'])
    l.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    mats['concrete'] = mat_conc

    # 3: Window glass (dark, slightly reflective, with faint interior/curtain variation & mullions/floor lines)
    mat_glass = bpy.data.materials.new("Mat_Glass")
    mat_glass.use_nodes = True
    n = mat_glass.node_tree.nodes
    l = mat_glass.node_tree.links
    n.clear()
    out = n.new('ShaderNodeOutputMaterial')
    bsdf = n.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.14
    set_principled_default(bsdf, ('Specular IOR Level', 'Specular'), 0.85)
    l.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    tc = n.new('ShaderNodeTexCoord')
    vec2d = make_triplanar_brick_vector(n, l, tc.outputs['Object'])

    # Room/curtain interior variation using quantized brick blocks + vertical wave folds
    curtain_noise = n.new('ShaderNodeTexNoise')
    curtain_noise.inputs['Scale'].default_value = 2.4
    curtain_noise.inputs['Detail'].default_value = 3.0
    l.new(tc.outputs['Object'], curtain_noise.inputs['Vector'])

    map_curtain = n.new('ShaderNodeMapping')
    map_curtain.inputs['Scale'].default_value = (6.5, 6.5, 0.4)
    l.new(tc.outputs['Object'], map_curtain.inputs['Vector'])

    fold_noise = n.new('ShaderNodeTexNoise')
    fold_noise.inputs['Scale'].default_value = 3.2
    fold_noise.inputs['Detail'].default_value = 4.0
    l.new(map_curtain.outputs['Vector'], fold_noise.inputs['Vector'])

    pane_dark = make_mix_color(
        n, l, 'MIX', fold_noise.outputs['Fac'],
        (0.06, 0.11, 0.15, 1.0), (0.11, 0.18, 0.23, 1.0)
    )
    pane_warm = make_mix_color(
        n, l, 'MIX', curtain_noise.outputs['Fac'],
        (0.14, 0.21, 0.26, 1.0), (0.28, 0.26, 0.21, 1.0)
    )

    mullion_grid = n.new('ShaderNodeTexBrick')
    mullion_grid.offset = 0.0
    mullion_grid.inputs['Mortar'].default_value = (0.18, 0.21, 0.24, 1.0)
    mullion_grid.inputs['Scale'].default_value = 1.0
    mullion_grid.inputs['Mortar Size'].default_value = 0.032
    mullion_grid.inputs['Mortar Smooth'].default_value = 0.02
    mullion_grid.inputs['Bias'].default_value = -0.15
    mullion_grid.inputs['Brick Width'].default_value = 1.55
    mullion_grid.inputs['Row Height'].default_value = 1.675
    l.new(vec2d, mullion_grid.inputs['Vector'])
    l.new(pane_dark, mullion_grid.inputs['Color1'])
    l.new(pane_warm, mullion_grid.inputs['Color2'])

    glass_grime = add_grime_layer(n, l, tc.outputs['Object'], mullion_grid.outputs['Color'], 3.35, 0.25)
    l.new(glass_grime, bsdf.inputs['Base Color'])

    bump = n.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.35
    bump.inputs['Distance'].default_value = 0.008
    l.new(mullion_grid.outputs['Fac'], bump.inputs['Height'])
    l.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    mats['glass'] = mat_glass

    # 4: Metal frames & vertical steel fins (plus red warning light housing at top of antenna Z > 119.3)
    mat_metal = bpy.data.materials.new("Mat_Metal")
    mat_metal.use_nodes = True
    n = mat_metal.node_tree.nodes
    l = mat_metal.node_tree.links
    n.clear()
    out = n.new('ShaderNodeOutputMaterial')
    bsdf = n.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.38
    set_principled_default(bsdf, ('Specular IOR Level', 'Specular'), 0.75)
    l.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    tc = n.new('ShaderNodeTexCoord')
    map_brush = n.new('ShaderNodeMapping')
    map_brush.inputs['Scale'].default_value = (4.0, 4.0, 0.5)
    l.new(tc.outputs['Object'], map_brush.inputs['Vector'])

    brush_noise = n.new('ShaderNodeTexNoise')
    brush_noise.inputs['Scale'].default_value = 8.0
    brush_noise.inputs['Detail'].default_value = 5.0
    l.new(map_brush.outputs['Vector'], brush_noise.inputs['Vector'])

    steel_col = make_mix_color(
        n, l, 'MIX', brush_noise.outputs['Fac'],
        (0.22, 0.25, 0.28, 1.0), (0.34, 0.38, 0.42, 1.0)
    )
    steel_grime = add_grime_layer(n, l, tc.outputs['Object'], steel_col, 3.35, 0.35)

    # Check Z > 119.35 m for the red aircraft-warning light housing at antenna pinnacle
    sep_z = n.new('ShaderNodeSeparateXYZ')
    l.new(tc.outputs['Object'], sep_z.inputs['Vector'])
    is_beacon = n.new('ShaderNodeMath')
    is_beacon.operation = 'GREATER_THAN'
    l.new(sep_z.outputs['Z'], is_beacon.inputs[0])
    is_beacon.inputs[1].default_value = 119.38

    beacon_col = make_mix_color(
        n, l, 'MIX', brush_noise.outputs['Fac'],
        (0.88, 0.08, 0.05, 1.0), (0.98, 0.22, 0.12, 1.0)
    )
    final_metal_col = make_mix_color(
        n, l, 'MIX', is_beacon.outputs['Value'],
        steel_grime, beacon_col
    )
    l.new(final_metal_col, bsdf.inputs['Base Color'])

    bump = n.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.25
    bump.inputs['Distance'].default_value = 0.006
    l.new(brush_noise.outputs['Fac'], bump.inputs['Height'])
    l.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    mats['metal'] = mat_metal

    # 5: Roof membrane
    mat_roof = bpy.data.materials.new("Mat_Roof")
    mat_roof.use_nodes = True
    n = mat_roof.node_tree.nodes
    l = mat_roof.node_tree.links
    n.clear()
    out = n.new('ShaderNodeOutputMaterial')
    bsdf = n.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.88
    l.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    tc = n.new('ShaderNodeTexCoord')
    roof_gran = n.new('ShaderNodeTexNoise')
    roof_gran.inputs['Scale'].default_value = 22.0
    roof_gran.inputs['Detail'].default_value = 8.0
    roof_gran.inputs['Roughness'].default_value = 0.75
    l.new(tc.outputs['Object'], roof_gran.inputs['Vector'])

    roof_stain = n.new('ShaderNodeTexNoise')
    roof_stain.inputs['Scale'].default_value = 0.7
    roof_stain.inputs['Detail'].default_value = 4.0
    l.new(tc.outputs['Object'], roof_stain.inputs['Vector'])

    r_col1 = make_mix_color(
        n, l, 'MIX', roof_gran.outputs['Fac'],
        (0.15, 0.16, 0.17, 1.0), (0.23, 0.24, 0.26, 1.0)
    )
    r_col2 = make_mix_color(
        n, l, 'MIX', roof_stain.outputs['Fac'],
        r_col1, (0.10, 0.11, 0.12, 1.0)
    )
    roof_grime = add_grime_layer(n, l, tc.outputs['Object'], r_col2, 3.35, 0.30)
    l.new(roof_grime, bsdf.inputs['Base Color'])

    bump = n.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.50
    bump.inputs['Distance'].default_value = 0.01
    l.new(roof_gran.outputs['Fac'], bump.inputs['Height'])
    l.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    mats['roof'] = mat_roof

    return mats


def add_box(bm, cx, cy, z0, z1, sx, sy, mat_idx, top=True, bottom=False):
    hx = sx * 0.5
    hy = sy * 0.5
    coords = [
        (cx - hx, cy - hy, z0),
        (cx + hx, cy - hy, z0),
        (cx + hx, cy + hy, z0),
        (cx - hx, cy + hy, z0),
        (cx - hx, cy - hy, z1),
        (cx + hx, cy - hy, z1),
        (cx + hx, cy + hy, z1),
        (cx - hx, cy + hy, z1),
    ]
    v = [bm.verts.new(c) for c in coords]
    quads = [
        (v[0], v[1], v[5], v[4]),  # -Y
        (v[1], v[2], v[6], v[5]),  # +X
        (v[2], v[3], v[7], v[6]),  # +Y
        (v[3], v[0], v[4], v[7]),  # -X
    ]
    if top:
        quads.append((v[4], v[5], v[6], v[7]))
    if bottom:
        quads.append((v[3], v[2], v[1], v[0]))
    created = []
    for q in quads:
        f = bm.faces.new(q)
        f.material_index = mat_idx
        created.append(f)
    return created


def add_ring_band(bm, z0, z1, inner_h, outer_h, mat_idx):
    vi = [
        bm.verts.new((-inner_h, -inner_h, z0)),
        bm.verts.new((inner_h, -inner_h, z0)),
        bm.verts.new((inner_h, inner_h, z0)),
        bm.verts.new((-inner_h, inner_h, z0)),
        bm.verts.new((-inner_h, -inner_h, z1)),
        bm.verts.new((inner_h, -inner_h, z1)),
        bm.verts.new((inner_h, inner_h, z1)),
        bm.verts.new((-inner_h, inner_h, z1)),
    ]
    vo = [
        bm.verts.new((-outer_h, -outer_h, z0)),
        bm.verts.new((outer_h, -outer_h, z0)),
        bm.verts.new((outer_h, outer_h, z0)),
        bm.verts.new((-outer_h, outer_h, z0)),
        bm.verts.new((-outer_h, -outer_h, z1)),
        bm.verts.new((outer_h, -outer_h, z1)),
        bm.verts.new((outer_h, outer_h, z1)),
        bm.verts.new((-outer_h, outer_h, z1)),
    ]
    for i in range(4):
        ni = (i + 1) % 4
        # Outer vertical face
        f_out = bm.faces.new((vo[i], vo[ni], vo[ni + 4], vo[i + 4]))
        f_out.material_index = mat_idx
        # Top ledge
        f_top = bm.faces.new((vi[i + 4], vo[i + 4], vo[ni + 4], vi[ni + 4]))
        f_top.material_index = mat_idx
        # Bottom soffit
        f_bot = bm.faces.new((vo[i], vi[i], vi[ni], vo[ni]))
        f_bot.material_index = mat_idx


def add_parapet_with_coping(bm, z_deck, outer_h, wall_t, wall_h, coping_over, coping_h, mat_wall, mat_coping, mat_roof):
    inner_h = outer_h - wall_t
    z_top = z_deck + wall_h
    # Roof membrane deck inside parapet
    v_deck = [
        bm.verts.new((-inner_h, -inner_h, z_deck)),
        bm.verts.new((inner_h, -inner_h, z_deck)),
        bm.verts.new((inner_h, inner_h, z_deck)),
        bm.verts.new((-inner_h, inner_h, z_deck)),
    ]
    f_deck = bm.faces.new(v_deck)
    f_deck.material_index = mat_roof

    v_in_top = [
        bm.verts.new((-inner_h, -inner_h, z_top)),
        bm.verts.new((inner_h, -inner_h, z_top)),
        bm.verts.new((inner_h, inner_h, z_top)),
        bm.verts.new((-inner_h, inner_h, z_top)),
    ]
    v_out_bot = [
        bm.verts.new((-outer_h, -outer_h, z_deck)),
        bm.verts.new((outer_h, -outer_h, z_deck)),
        bm.verts.new((outer_h, outer_h, z_deck)),
        bm.verts.new((-outer_h, outer_h, z_deck)),
    ]
    v_out_top = [
        bm.verts.new((-outer_h, -outer_h, z_top)),
        bm.verts.new((outer_h, -outer_h, z_top)),
        bm.verts.new((outer_h, outer_h, z_top)),
        bm.verts.new((-outer_h, outer_h, z_top)),
    ]
    for i in range(4):
        ni = (i + 1) % 4
        # Inner parapet wall facing roof
        fi = bm.faces.new((v_deck[ni], v_deck[i], v_in_top[i], v_in_top[ni]))
        fi.material_index = mat_wall
        # Outer parapet wall
        fo = bm.faces.new((v_out_bot[i], v_out_bot[ni], v_out_top[ni], v_out_top[i]))
        fo.material_index = mat_wall

    # Coping cap overhanging both inner and outer parapet walls
    c_in = inner_h - coping_over
    c_out = outer_h + coping_over
    zc0 = z_top
    zc1 = z_top + coping_h
    vi0 = [
        bm.verts.new((-c_in, -c_in, zc0)),
        bm.verts.new((c_in, -c_in, zc0)),
        bm.verts.new((c_in, c_in, zc0)),
        bm.verts.new((-c_in, c_in, zc0)),
    ]
    vi1 = [
        bm.verts.new((-c_in, -c_in, zc1)),
        bm.verts.new((c_in, -c_in, zc1)),
        bm.verts.new((c_in, c_in, zc1)),
        bm.verts.new((-c_in, c_in, zc1)),
    ]
    vo0 = [
        bm.verts.new((-c_out, -c_out, zc0)),
        bm.verts.new((c_out, -c_out, zc0)),
        bm.verts.new((c_out, c_out, zc0)),
        bm.verts.new((-c_out, c_out, zc0)),
    ]
    vo1 = [
        bm.verts.new((-c_out, -c_out, zc1)),
        bm.verts.new((c_out, -c_out, zc1)),
        bm.verts.new((c_out, c_out, zc1)),
        bm.verts.new((-c_out, c_out, zc1)),
    ]
    for i in range(4):
        ni = (i + 1) % 4
        f1 = bm.faces.new((vo0[i], vo0[ni], vo1[ni], vo1[i]))
        f2 = bm.faces.new((vi0[ni], vi0[i], vi1[i], vi1[ni]))
        f3 = bm.faces.new((vi1[i], vo1[i], vo1[ni], vi1[ni]))
        f1.material_index = mat_coping
        f2.material_index = mat_coping
        f3.material_index = mat_coping


def add_facade_tier_bays(
    bm, z0, z1, half_w, bays_per_side, num_storeys,
    pier_inset, recess_depth, frame_thick,
    extrude_sill_storeys,
    mat_pier, mat_frame, mat_glass, mat_sill,
    skip_front_center_ground=False
):
    dz = (z1 - z0) / float(num_storeys)
    sides = [
        ((-half_w, -half_w), (half_w, -half_w)),  # 0: -Y front facade
        ((half_w, -half_w), (half_w, half_w)),    # 1: +X right facade
        ((half_w, half_w), (-half_w, half_w)),    # 2: +Y back facade
        ((-half_w, half_w), (-half_w, -half_w)),  # 3: -X left facade
    ]
    regular_bays = []
    sill_bay_set = set()
    entrance_face = None

    for s_idx, (p0, p1) in enumerate(sides):
        nb = bays_per_side[s_idx]
        v_grid = []
        for iz in range(num_storeys + 1):
            row = []
            zc = z0 + iz * dz
            for ix in range(nb + 1):
                t = ix / float(nb)
                xc = p0[0] + (p1[0] - p0[0]) * t
                yc = p0[1] + (p1[1] - p0[1]) * t
                row.append(bm.verts.new((xc, yc, zc)))
            v_grid.append(row)

        for iz in range(num_storeys):
            for ix in range(nb):
                f = bm.faces.new((
                    v_grid[iz][ix],
                    v_grid[iz][ix + 1],
                    v_grid[iz + 1][ix + 1],
                    v_grid[iz + 1][ix],
                ))
                f.material_index = mat_pier
                if skip_front_center_ground and s_idx == 0 and iz == 0 and ix == (nb // 2):
                    entrance_face = f
                else:
                    regular_bays.append(f)
                    if iz in extrude_sill_storeys:
                        sill_bay_set.add(f)

    # Step 1: Inset each bay face for structural surround / window opening
    ret1 = bmesh.ops.inset_individual(
        bm, faces=regular_bays, thickness=pier_inset, depth=0.0, use_even_offset=True
    )
    for f in ret1['faces']:
        f.material_index = mat_pier

    # Find bottom border quad under each window in sill_bay_set and extrude outward as 3D sill
    sill_faces = []
    for wf in regular_bays:
        if wf not in sill_bay_set:
            continue
        wc = wf.calc_center_median()
        best_f = None
        best_z = 1e9
        for e in wf.edges:
            for lf in e.link_faces:
                if lf is not wf and lf in ret1['faces']:
                    lc = lf.calc_center_median()
                    if lc.z < wc.z - 0.1 and lc.z < best_z:
                        best_z = lc.z
                        best_f = lf
        if best_f is not None:
            sill_faces.append(best_f)

    if sill_faces:
        ret_sill = bmesh.ops.inset_individual(
            bm, faces=sill_faces, thickness=0.015, depth=0.085, use_even_offset=True
        )
        for sf in sill_faces:
            sf.material_index = mat_sill
        for sf in ret_sill['faces']:
            sf.material_index = mat_sill

    # Step 2: Recess windows by recess_depth (0.20 m) with metal frame bevel
    ret2 = bmesh.ops.inset_individual(
        bm, faces=regular_bays, thickness=frame_thick, depth=-recess_depth, use_even_offset=True
    )
    for f in ret2['faces']:
        f.material_index = mat_frame
    for f in regular_bays:
        f.material_index = mat_glass

    # Ground-floor entrance on front facade (-Y)
    if entrance_face is not None:
        # Surround frame in brick/stone
        ret_e1 = bmesh.ops.inset_individual(
            bm, faces=[entrance_face], thickness=0.35, depth=0.0, use_even_offset=True
        )
        for f in ret_e1['faces']:
            f.material_index = mat_pier
        # Recess grand portal by 0.24 m
        ret_e2 = bmesh.ops.inset_individual(
            bm, faces=[entrance_face], thickness=0.10, depth=-0.24, use_even_offset=True
        )
        for f in ret_e2['faces']:
            f.material_index = mat_frame
        # Inner door frame & glass lobby doors
        ret_e3 = bmesh.ops.inset_individual(
            bm, faces=[entrance_face], thickness=0.18, depth=-0.06, use_even_offset=True
        )
        for f in ret_e3['faces']:
            f.material_index = mat_frame
        entrance_face.material_index = mat_glass


def add_vertical_fins(bm, z0, z1, wall_h, fin_outer_h, fin_thick, num_fins_per_side, mat_idx):
    span = wall_h * 1.82
    depth = fin_outer_h - wall_h
    for i in range(num_fins_per_side):
        t = -span * 0.5 + span * (i / float(num_fins_per_side - 1))
        # -Y and +Y facades
        add_box(bm, t, -(wall_h + depth * 0.5), z0, z1, fin_thick, depth, mat_idx, top=True, bottom=True)
        add_box(bm, t, (wall_h + depth * 0.5), z0, z1, fin_thick, depth, mat_idx, top=True, bottom=True)
        # -X and +X facades
        add_box(bm, -(wall_h + depth * 0.5), t, z0, z1, depth, fin_thick, mat_idx, top=True, bottom=True)
        add_box(bm, (wall_h + depth * 0.5), t, z0, z1, depth, fin_thick, mat_idx, top=True, bottom=True)


def add_ac_unit(bm, cx, cy, z_base, sx, sy, sh, mat_body, mat_dark):
    faces = add_box(bm, cx, cy, z_base, z_base + sh, sx, sy, mat_body, top=True, bottom=False)
    top_f = faces[-1]
    ret1 = bmesh.ops.inset_individual(bm, faces=[top_f], thickness=min(sx, sy) * 0.18, depth=0.0)
    for f in ret1['faces']:
        f.material_index = mat_body
    ret2 = bmesh.ops.inset_individual(bm, faces=[top_f], thickness=0.02, depth=-0.12)
    for f in ret2['faces']:
        f.material_index = mat_dark
    top_f.material_index = mat_dark


def add_cylinder_z(bm, cx, cy, z0, z1, r0, r1, segs, mat_idx, cap_top=True, cap_bot=False):
    ring0 = []
    ring1 = []
    for i in range(segs):
        ang = 2.0 * math.pi * i / float(segs)
        ca = math.cos(ang)
        sa = math.sin(ang)
        ring0.append(bm.verts.new((cx + r0 * ca, cy + r0 * sa, z0)))
        ring1.append(bm.verts.new((cx + r1 * ca, cy + r1 * sa, z1)))
    for i in range(segs):
        ni = (i + 1) % segs
        f = bm.faces.new((ring0[i], ring0[ni], ring1[ni], ring1[i]))
        f.material_index = mat_idx
    if cap_top:
        vc = bm.verts.new((cx, cy, z1))
        for i in range(segs):
            ni = (i + 1) % segs
            ft = bm.faces.new((ring1[i], ring1[ni], vc))
            ft.material_index = mat_idx
    if cap_bot:
        vb = bm.verts.new((cx, cy, z0))
        for i in range(segs):
            ni = (i + 1) % segs
            fb = bm.faces.new((ring0[ni], ring0[i], vb))
            fb.material_index = mat_idx


def build_bldg_tower(mats):
    mesh = bpy.data.meshes.new("BldgTower_Mesh")
    obj = bpy.data.objects.new("BldgTower", mesh)
    bpy.context.collection.objects.link(obj)

    mat_list = [
        mats['brick'],     # 0
        mats['stucco'],    # 1
        mats['concrete'],  # 2
        mats['glass'],     # 3
        mats['metal'],     # 4
        mats['roof'],      # 5
    ]
    for m in mat_list:
        obj.data.materials.append(m)

    bm = bmesh.new()

    # Ground base slab (20m x 20m at Z=0)
    v_ground = [
        bm.verts.new((-10.0, 10.0, 0.0)),
        bm.verts.new((10.0, 10.0, 0.0)),
        bm.verts.new((10.0, -10.0, 0.0)),
        bm.verts.new((-10.0, -10.0, 0.0)),
    ]
    f_ground = bm.faces.new(v_ground)
    f_ground.material_index = 2

    # 1. Ground-Floor Lobby (Storey 1: Z = 0.0 to 5.4 m, footprint 20m x 20m)
    add_facade_tier_bays(
        bm, z0=0.0, z1=5.4, half_w=9.75,
        bays_per_side=(3, 3, 3, 3), num_storeys=1,
        pier_inset=0.32, recess_depth=0.22, frame_thick=0.07,
        extrude_sill_storeys={0},
        mat_pier=0, mat_frame=4, mat_glass=3, mat_sill=2,
        skip_front_center_ground=True
    )
    # 4 Brick/concrete corner piers at full 20m x 20m footprint on Lobby
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            add_box(bm, sx * 9.65, sy * 9.65, 0.0, 5.4, 0.70, 0.70, 0, top=False, bottom=False)

    # Entrance steps, vestibule side columns, and cantilevered canopy on -Y facade
    add_box(bm, 0.0, -9.88, 0.0, 0.22, 5.2, 0.24, 2, top=True, bottom=False)
    add_box(bm, -2.4, -9.85, 0.22, 4.3, 0.36, 0.30, 0, top=True, bottom=False)
    add_box(bm, 2.4, -9.85, 0.22, 4.3, 0.36, 0.30, 0, top=True, bottom=False)
    add_box(bm, 0.0, -9.55, 4.20, 4.48, 6.2, 0.90, 4, top=True, bottom=True)
    add_box(bm, 0.0, -9.58, 4.48, 4.58, 5.8, 0.80, 3, top=True, bottom=False)
    # Lobby cornice band at Z = 5.25..5.55 m
    add_ring_band(bm, 5.25, 5.55, 9.72, 10.0, 2)

    # 2. Lower Tower Tier (Storeys 2 to 23 = 22 storeys: Z = 5.4 to 79.1 m, 2/3 height = 80m)
    add_facade_tier_bays(
        bm, z0=5.4, z1=79.1, half_w=9.70,
        bays_per_side=(2, 2, 2, 2), num_storeys=22,
        pier_inset=0.22, recess_depth=0.20, frame_thick=0.06,
        extrude_sill_storeys=set(range(0, 22, 2)),
        mat_pier=2, mat_frame=4, mat_glass=3, mat_sill=2,
        skip_front_center_ground=False
    )
    # Lower Tower corner piers and continuous floor/sill bands on all 22 storeys
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            add_box(bm, sx * 9.68, sy * 9.68, 5.4, 79.1, 0.56, 0.56, 1, top=True, bottom=False)

    storey_h_low = (79.1 - 5.4) / 22.0
    for iz in range(1, 22):
        zb = 5.4 + iz * storey_h_low
        add_ring_band(bm, zb - 0.09, zb + 0.09, 9.68, 9.88, 2)

    # Vertical steel fins on Lower Tower (5 per facade, reaching 20m x 20m outer footprint)
    add_vertical_fins(bm, 5.55, 79.1, 9.70, 10.0, 0.14, 5, 4)

    # Setback cornice & Roof Parapet with Coping at 2/3 height (Z = 79.1 to 80.15 m)
    add_ring_band(bm, 78.85, 79.15, 9.68, 10.0, 2)
    add_parapet_with_coping(
        bm, z_deck=79.1, outer_h=9.92, wall_t=0.35, wall_h=0.85,
        coping_over=0.08, coping_h=0.18, mat_wall=1, mat_coping=2, mat_roof=5
    )

    # Setback terrace rooftop details (AC units & vents at Z = 79.1 m)
    for sx in (-1.0, 1.0):
        add_ac_unit(bm, sx * 8.45, -8.45, 79.1, 1.3, 1.1, 0.95, 4, 2)
        add_ac_unit(bm, sx * 8.45, 8.45, 79.1, 1.3, 1.1, 0.95, 4, 2)
        add_box(bm, sx * 8.5, 0.0, 79.1, 80.2, 0.65, 0.65, 4, top=True, bottom=False)

    # 3. Upper Tower Tier (Storeys 24 to 35 = 12 storeys: Z = 79.1 to 112.4 m, footprint 14.8m x 14.8m)
    add_facade_tier_bays(
        bm, z0=79.1, z1=112.4, half_w=7.25,
        bays_per_side=(2, 2, 2, 2), num_storeys=12,
        pier_inset=0.20, recess_depth=0.20, frame_thick=0.06,
        extrude_sill_storeys=set(range(0, 12, 2)),
        mat_pier=2, mat_frame=4, mat_glass=3, mat_sill=2,
        skip_front_center_ground=False
    )
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            add_box(bm, sx * 7.22, sy * 7.22, 79.1, 112.4, 0.48, 0.48, 1, top=True, bottom=False)

    storey_h_up = (112.4 - 79.1) / 12.0
    for iz in range(1, 12):
        zb = 79.1 + iz * storey_h_up
        add_ring_band(bm, zb - 0.08, zb + 0.08, 7.23, 7.42, 2)

    # Vertical steel fins on Upper Tower (5 per facade)
    add_vertical_fins(bm, 79.1, 112.4, 7.25, 7.52, 0.12, 5, 4)

    # Main Roof Cornice & Parapet with Coping at Z = 112.4 m
    add_ring_band(bm, 112.15, 112.42, 7.22, 7.55, 2)
    add_parapet_with_coping(
        bm, z_deck=112.4, outer_h=7.42, wall_t=0.32, wall_h=0.80,
        coping_over=0.07, coping_h=0.16, mat_wall=1, mat_coping=2, mat_roof=5
    )

    # 4. Crown Structure (Z = 112.4 to 115.8 m, glass & steel fins)
    add_facade_tier_bays(
        bm, z0=112.4, z1=115.8, half_w=5.10,
        bays_per_side=(2, 2, 2, 2), num_storeys=2,
        pier_inset=0.18, recess_depth=0.18, frame_thick=0.05,
        extrude_sill_storeys={0},
        mat_pier=4, mat_frame=4, mat_glass=3, mat_sill=2,
        skip_front_center_ground=False
    )
    add_vertical_fins(bm, 112.4, 116.3, 5.10, 5.38, 0.11, 5, 4)
    add_parapet_with_coping(
        bm, z_deck=115.8, outer_h=5.20, wall_t=0.26, wall_h=0.55,
        coping_over=0.06, coping_h=0.14, mat_wall=1, mat_coping=2, mat_roof=5
    )

    # 5. Rooftop Details on Main Roof (Z = 112.4 m) & Crown Roof (Z = 115.8 m)
    # AC units and vents on Main Roof perimeter terrace
    for sx in (-1.0, 1.0):
        add_ac_unit(bm, sx * 6.1, -6.1, 112.4, 1.15, 1.0, 0.85, 4, 2)
        add_ac_unit(bm, sx * 6.1, 6.1, 112.4, 1.15, 1.0, 0.85, 4, 2)
        add_box(bm, sx * 6.15, 0.0, 112.4, 113.5, 0.55, 0.55, 4, top=True, bottom=False)

    # Lift housing / mechanical penthouse on Crown Roof (Z = 115.8 to 117.4 m)
    pent_faces = add_box(bm, 0.0, 0.55, 115.8, 117.35, 3.6, 3.2, 1, top=True, bottom=False)
    add_box(bm, 0.0, 0.55, 117.35, 117.50, 3.85, 3.45, 2, top=True, bottom=True)
    # Recessed maintenance door on lift housing front (-Y)
    door_f = pent_faces[0]
    ret_pd1 = bmesh.ops.inset_individual(bm, faces=[door_f], thickness=0.45, depth=0.0)
    for f in ret_pd1['faces']:
        f.material_index = 1
    ret_pd2 = bmesh.ops.inset_individual(bm, faces=[door_f], thickness=0.05, depth=-0.16)
    for f in ret_pd2['faces']:
        f.material_index = 4
    door_f.material_index = 4

    # Cylindrical Water Tank on steel support legs on Crown Roof
    wt_x, wt_y = -2.85, 2.35
    for lx in (-0.55, 0.55):
        for ly in (-0.55, 0.55):
            add_box(bm, wt_x + lx, wt_y + ly, 115.8, 116.55, 0.14, 0.14, 4, top=False, bottom=False)
    add_cylinder_z(bm, wt_x, wt_y, 116.5, 118.0, 0.95, 0.95, 8, 2, cap_top=False, cap_bot=True)
    add_cylinder_z(bm, wt_x, wt_y, 118.0, 118.45, 0.98, 0.08, 8, 4, cap_top=True, cap_bot=False)

    # Crown roof AC units & vents
    add_ac_unit(bm, 2.85, 2.35, 115.8, 1.35, 1.15, 0.90, 4, 2)
    add_ac_unit(bm, 2.85, -2.35, 115.8, 1.20, 1.05, 0.85, 4, 2)
    add_box(bm, -2.85, -2.35, 115.8, 116.85, 0.70, 0.70, 4, top=True, bottom=False)

    # 6. Antenna Mast & Red Aircraft-Warning Light Housing (Z = 117.50 to 120.00 m)
    # Tapered lower mast pedestal
    add_cylinder_z(bm, 0.0, 0.0, 117.50, 118.45, 0.55, 0.28, 8, 4, cap_top=True, cap_bot=False)
    # Upper steel spire shaft
    add_cylinder_z(bm, 0.0, 0.0, 118.45, 119.40, 0.20, 0.11, 8, 4, cap_top=True, cap_bot=False)
    # Antenna crossbars
    add_box(bm, 0.0, 0.0, 118.75, 118.83, 1.45, 0.08, 4, top=True, bottom=True)
    add_box(bm, 0.0, 0.0, 119.10, 119.17, 0.08, 1.15, 4, top=True, bottom=True)
    # Red aircraft-warning light housing (collar + crimson dome lens at Z = 119.40..120.00 m)
    add_cylinder_z(bm, 0.0, 0.0, 119.40, 119.58, 0.24, 0.28, 8, 4, cap_top=False, cap_bot=True)
    add_cylinder_z(bm, 0.0, 0.0, 119.58, 119.86, 0.26, 0.22, 8, 4, cap_top=False, cap_bot=False)
    add_cylinder_z(bm, 0.0, 0.0, 119.86, 120.00, 0.22, 0.04, 8, 4, cap_top=True, cap_bot=False)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = False
    for e in bm.edges:
        e.smooth = False

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    if hasattr(mesh, "use_auto_smooth"):
        mesh.use_auto_smooth = True

    return obj


def unwrap_and_bake(obj, out_dir):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    if not obj.data.uv_layers:
        obj.data.uv_layers.new(name="UVMap")

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.01)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')

    img_albedo = bpy.data.images.new("BldgTower_albedo", width=2048, height=2048, alpha=False)
    img_albedo.colorspace_settings.name = 'sRGB'

    img_normal = bpy.data.images.new("BldgTower_normal", width=2048, height=2048, alpha=False)
    img_normal.colorspace_settings.name = 'Non-Color'

    albedo_nodes = {}
    normal_nodes = {}
    for mat in obj.data.materials:
        nodes = mat.node_tree.nodes
        na = nodes.new('ShaderNodeTexImage')
        na.image = img_albedo
        nn = nodes.new('ShaderNodeTexImage')
        nn.image = img_normal
        albedo_nodes[mat.name] = na
        normal_nodes[mat.name] = nn

    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 16
    if hasattr(scene.cycles, "use_denoising"):
        scene.cycles.use_denoising = False
    scene.render.bake.margin = 8

    # Activate albedo image texture node in every material before DIFFUSE bake
    for mat in obj.data.materials:
        nodes = mat.node_tree.nodes
        for n in nodes:
            n.select = False
        na = albedo_nodes[mat.name]
        na.select = True
        nodes.active = na

    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=8)

    albedo_path = os.path.join(out_dir, "BldgTower_albedo.png")
    img_albedo.filepath_raw = albedo_path
    img_albedo.file_format = 'PNG'
    img_albedo.save()

    # Activate normal image texture node in every material before NORMAL bake
    for mat in obj.data.materials:
        nodes = mat.node_tree.nodes
        for n in nodes:
            n.select = False
        nn = normal_nodes[mat.name]
        nn.select = True
        nodes.active = nn

    scene.render.bake.normal_space = 'TANGENT'
    bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=8)

    normal_path = os.path.join(out_dir, "BldgTower_normal.png")
    img_normal.filepath_raw = normal_path
    img_normal.file_format = 'PNG'
    img_normal.save()

    # Replace all slots with ONE material "BldgTower_Mat"
    final_mat = bpy.data.materials.new("BldgTower_Mat")
    final_mat.use_nodes = True
    fnodes = final_mat.node_tree.nodes
    flinks = final_mat.node_tree.links
    fnodes.clear()

    out_node = fnodes.new('ShaderNodeOutputMaterial')
    bsdf = fnodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.7
    flinks.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

    tex_alb = fnodes.new('ShaderNodeTexImage')
    tex_alb.image = img_albedo
    flinks.new(tex_alb.outputs['Color'], bsdf.inputs['Base Color'])

    tex_nrm = fnodes.new('ShaderNodeTexImage')
    tex_nrm.image = img_normal
    img_normal.colorspace_settings.name = 'Non-Color'

    nrm_map = fnodes.new('ShaderNodeNormalMap')
    flinks.new(tex_nrm.outputs['Color'], nrm_map.inputs['Color'])
    flinks.new(nrm_map.outputs['Normal'], bsdf.inputs['Normal'])

    obj.data.materials.clear()
    obj.data.materials.append(final_mat)
    for poly in obj.data.polygons:
        poly.material_index = 0


def export_and_render(obj, fbx_path, png_path):
    scene = bpy.context.scene

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    bpy.ops.export_scene.fbx(
        filepath=fbx_path,
        use_selection=True,
        bake_space_transform=True,
        use_mesh_modifiers=True,
        axis_forward='-Z',
        axis_up='Y',
        path_mode='COPY',
        embed_textures=True,
    )

    # Set EEVEE engine from scene.render.bl_rna.properties['engine'].enum_items keys
    engine_keys = list(scene.render.bl_rna.properties['engine'].enum_items.keys())
    for ek in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        if ek in engine_keys:
            scene.render.engine = ek
            break
    else:
        for ek in engine_keys:
            if 'EEVEE' in ek:
                scene.render.engine = ek
                break

    # Grey sky world strength 0.6
    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    wnodes = world.node_tree.nodes
    wlinks = world.node_tree.links
    wnodes.clear()
    w_out = wnodes.new('ShaderNodeOutputWorld')
    w_bg = wnodes.new('ShaderNodeBackground')
    w_bg.inputs['Color'].default_value = (0.52, 0.55, 0.58, 1.0)
    w_bg.inputs['Strength'].default_value = 0.6
    wlinks.new(w_bg.outputs['Background'], w_out.inputs['Surface'])

    # Sun strength 3 from front-left-above (-X, -Y, +Z)
    sun_data = bpy.data.lights.new(name="Sun", type='SUN')
    sun_data.energy = 3.0
    sun_obj = bpy.data.objects.new(name="Sun", object_data=sun_data)
    scene.collection.objects.link(sun_obj)
    sun_obj.location = (-45.0, -55.0, 95.0)
    sun_dir = mathutils.Vector((0.0, 0.0, 45.0)) - sun_obj.location
    sun_obj.rotation_euler = sun_dir.to_track_quat('-Z', 'Y').to_euler()

    # Camera from street level 3/4 view framing the whole 120m building
    cam_data = bpy.data.cameras.new(name="Camera")
    cam_data.lens = 28.0
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.5
    cam_data.clip_end = 1000.0
    cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    cam_obj.location = (-95.0, -115.0, 5.5)
    look_target = mathutils.Vector((0.0, 0.0, 57.0))
    cam_dir = look_target - cam_obj.location
    cam_obj.rotation_euler = cam_dir.to_track_quat('-Z', 'Y').to_euler()

    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = png_path
    bpy.ops.render.render(write_still=True)

    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    print("TRIS", tris)


def main():
    raw_out = "BldgTower.fbx"
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if idx + 1 < len(sys.argv):
            raw_out = sys.argv[idx + 1]

    raw_out = os.path.abspath(raw_out)
    base, ext = os.path.splitext(raw_out)
    if ext.lower() == ".fbx":
        fbx_path = raw_out
        png_path = base + ".png"
    else:
        fbx_path = raw_out + ".fbx"
        png_path = raw_out + ".png"

    out_dir = os.path.dirname(fbx_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    clear_scene()
    mats = create_procedural_materials()
    obj = build_bldg_tower(mats)
    unwrap_and_bake(obj, out_dir)
    export_and_render(obj, fbx_path, png_path)


if __name__ == "__main__":
    main()
