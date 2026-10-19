import bpy
from mathutils import Euler
import bmesh
from mathutils import Vector, Matrix
import math
import sys
import os


def clear_scene():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block_col in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.images,
        bpy.data.lights,
        bpy.data.cameras,
        bpy.data.Worlds if hasattr(bpy.data, "Worlds") else bpy.data.worlds,
    ):
        for block in list(block_col):
            if block.users == 0:
                block_col.remove(block)


def set_bsdf_input(bsdf, names, value):
    if isinstance(names, str):
        names = (names,)
    for name in names:
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = value
            return bsdf.inputs[name]
    return None


def get_bsdf_input(bsdf, names):
    if isinstance(names, str):
        names = (names,)
    for name in names:
        if name in bsdf.inputs:
            return bsdf.inputs[name]
    return None


def add_compare_node(nt, links, val_socket, target, eps):
    cmp_node = nt.nodes.new('ShaderNodeMath')
    cmp_node.operation = 'COMPARE'
    links.new(val_socket, cmp_node.inputs[0])
    cmp_node.inputs[1].default_value = target
    cmp_node.inputs[2].default_value = eps
    return cmp_node.outputs[0]


def add_range_mask(nt, links, val_socket, low, high):
    mid = 0.5 * (low + high)
    half = 0.5 * abs(high - low)
    return add_compare_node(nt, links, val_socket, mid, half)


def math_op(nt, links, op, a, b=None, clamp=False):
    node = nt.nodes.new('ShaderNodeMath')
    node.operation = op
    node.use_clamp = clamp
    if isinstance(a, (int, float)):
        node.inputs[0].default_value = a
    else:
        links.new(a, node.inputs[0])
    if b is not None:
        if isinstance(b, (int, float)):
            node.inputs[1].default_value = b
        else:
            links.new(b, node.inputs[1])
    return node.outputs[0]


def mix_rgb(nt, links, fac, col1, col2, blend_type='MIX', clamp=True):
    if 'ShaderNodeMix' in dir(bpy.types):
        node = nt.nodes.new('ShaderNodeMix')
        node.data_type = 'RGBA'
        node.blend_type = blend_type
        node.clamp_factor = clamp
        if isinstance(fac, (int, float)):
            node.inputs['Factor'].default_value = fac
        else:
            links.new(fac, node.inputs['Factor'])
        if isinstance(col1, tuple):
            node.inputs['A'].default_value = col1
        else:
            links.new(col1, node.inputs['A'])
        if isinstance(col2, tuple):
            node.inputs['B'].default_value = col2
        else:
            links.new(col2, node.inputs['B'])
        return node.outputs['Result']
    else:
        node = nt.nodes.new('ShaderNodeMixRGB')
        node.blend_type = blend_type
        node.use_clamp = clamp
        if isinstance(fac, (int, float)):
            node.inputs['Fac'].default_value = fac
        else:
            links.new(fac, node.inputs['Fac'])
        if isinstance(col1, tuple):
            node.inputs['Color1'].default_value = col1
        else:
            links.new(col1, node.inputs['Color1'])
        if isinstance(col2, tuple):
            node.inputs['Color2'].default_value = col2
        else:
            links.new(col2, node.inputs['Color2'])
        return node.outputs['Color']


def build_dirt_mask(nt, links, obj_coord, z_socket):
    map_range = nt.nodes.new('ShaderNodeMapRange')
    map_range.clamp = True
    map_range.inputs['From Min'].default_value = 0.0
    map_range.inputs['From Max'].default_value = 0.25
    map_range.inputs['To Min'].default_value = 1.0
    map_range.inputs['To Max'].default_value = 0.0
    links.new(z_socket, map_range.inputs['Value'])

    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 16.0
    noise.inputs['Detail'].default_value = 6.0
    noise.inputs['Roughness'].default_value = 0.65
    links.new(obj_coord, noise.inputs['Vector'])

    noisy_grad = math_op(nt, links, 'MULTIPLY', map_range.outputs['Result'], noise.outputs['Fac'], clamp=True)
    dirt_mask = math_op(nt, links, 'MULTIPLY', noisy_grad, 0.55, clamp=True)
    return dirt_mask, noise.outputs['Fac']


def build_panel_gap_mask(nt, links, x_socket, y_socket, z_socket):
    abs_x = math_op(nt, links, 'ABSOLUTE', x_socket)
    side_mask = math_op(nt, links, 'GREATER_THAN', abs_x, 0.72)
    door_z_mask = add_range_mask(nt, links, z_socket, 0.26, 1.04)
    side_door_zone = math_op(nt, links, 'MULTIPLY', side_mask, door_z_mask)

    gap_eps = 0.009
    door_y1 = add_compare_node(nt, links, y_socket, -0.88, gap_eps)
    door_y2 = add_compare_node(nt, links, y_socket, 0.05, gap_eps)
    door_y3 = add_compare_node(nt, links, y_socket, 0.94, gap_eps)
    door_y_any = math_op(nt, links, 'MAXIMUM', math_op(nt, links, 'MAXIMUM', door_y1, door_y2), door_y3)
    door_Vertical = math_op(nt, links, 'MULTIPLY', door_y_any, side_door_zone)

    door_bot = add_compare_node(nt, links, z_socket, 0.30, gap_eps)
    door_bot_y = add_range_mask(nt, links, y_socket, -0.88, 0.94)
    door_horiz = math_op(nt, links, 'MULTIPLY', math_op(nt, links, 'MULTIPLY', door_bot, door_bot_y), side_mask)

    hood_x_zone = math_op(nt, links, 'LESS_THAN', abs_x, 0.73)
    hood_z_zone = math_op(nt, links, 'GREATER_THAN', z_socket, 0.72)
    hood_top_zone = math_op(nt, links, 'MULTIPLY', hood_x_zone, hood_z_zone)
    hood_back = math_op(nt, links, 'MULTIPLY', add_compare_node(nt, links, y_socket, -1.04, gap_eps), hood_top_zone)
    hood_front = math_op(nt, links, 'MULTIPLY', add_compare_node(nt, links, y_socket, -2.14, gap_eps), hood_top_zone)
    hood_side_y = add_range_mask(nt, links, y_socket, -2.14, -1.04)
    hood_side_x = add_compare_node(nt, links, abs_x, 0.72, gap_eps)
    hood_sides = math_op(nt, links, 'MULTIPLY', math_op(nt, links, 'MULTIPLY', hood_side_x, hood_side_y), hood_z_zone)

    trunk_x_zone = math_op(nt, links, 'LESS_THAN', abs_x, 0.68)
    trunk_z_zone = add_range_mask(nt, links, z_socket, 0.55, 1.58)
    trunk_y_zone = math_op(nt, links, 'GREATER_THAN', y_socket, 1.78)
    trunk_side_x = add_compare_node(nt, links, abs_x, 0.67, gap_eps)
    trunk_sides = math_op(
        nt,
        links,
        'MULTIPLY',
        math_op(nt, links, 'MULTIPLY', trunk_side_x, trunk_z_zone),
        trunk_y_zone,
    )
    trunk_bot = math_op(
        nt,
        links,
        'MULTIPLY',
        math_op(nt, links, 'MULTIPLY', add_compare_node(nt, links, z_socket, 0.62, gap_eps), trunk_x_zone),
        trunk_y_zone,
    )

    gaps_1 = math_op(nt, links, 'MAXIMUM', door_Vertical, door_horiz)
    gaps_2 = math_op(nt, links, 'MAXIMUM', math_op(nt, links, 'MAXIMUM', hood_back, hood_front), hood_sides)
    gaps_3 = math_op(nt, links, 'MAXIMUM', trunk_sides, trunk_bot)
    total_gaps = math_op(nt, links, 'MAXIMUM', math_op(nt, links, 'MAXIMUM', gaps_1, gaps_2), gaps_3, clamp=True)
    return total_gaps


def create_materials():
    mats = {}

    def new_mat(name):
        m = bpy.data.materials.new(name=name)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
        nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
        return m, nt, nt.links, bsdf

    # 1. Metallic Dark Blue Car Paint with Clear Coat, Panel Gaps & Road Dirt
    m, nt, links, bsdf = new_mat("Mat_Paint")
    tex_coord = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    links.new(tex_coord.outputs['Object'], sep.inputs['Vector'])

    flake_noise = nt.nodes.new('ShaderNodeTexNoise')
    flake_noise.inputs['Scale'].default_value = 350.0
    flake_noise.inputs['Detail'].default_value = 4.0
    links.new(tex_coord.outputs['Object'], flake_noise.inputs['Vector'])

    paint_col = mix_rgb(
        nt,
        links,
        flake_noise.outputs['Fac'],
        (0.018, 0.055, 0.175, 1.0),
        (0.038, 0.105, 0.285, 1.0),
    )
    z_grad = nt.nodes.new('ShaderNodeMapRange')
    z_grad.clamp = True
    z_grad.inputs['From Min'].default_value = 0.25
    z_grad.inputs['From Max'].default_value = 1.60
    z_grad.inputs['To Min'].default_value = 0.0
    z_grad.inputs['To Max'].default_value = 0.35
    links.new(sep.outputs['Z'], z_grad.inputs['Value'])
    paint_shaded = mix_rgb(nt, links, z_grad.outputs['Result'], paint_col, (0.055, 0.145, 0.36, 1.0))

    gap_mask = build_panel_gap_mask(nt, links, sep.outputs['X'], sep.outputs['Y'], sep.outputs['Z'])
    dirt_mask, dirt_noise = build_dirt_mask(nt, links, tex_coord.outputs['Object'], sep.outputs['Z'])

    col_with_gaps = mix_rgb(nt, links, gap_mask, paint_shaded, (0.005, 0.007, 0.012, 1.0))
    col_final = mix_rgb(nt, links, dirt_mask, col_with_gaps, (0.15, 0.13, 0.11, 1.0))
    links.new(col_final, bsdf.inputs['Base Color'])

    rough_with_dirt = math_op(nt, links, 'ADD', 0.16, math_op(nt, links, 'MULTIPLY', dirt_mask, 0.65), clamp=True)
    links.new(rough_with_dirt, bsdf.inputs['Roughness'])
    set_bsdf_input(bsdf, 'Metallic', 0.85)
    set_bsdf_input(bsdf, ('Coat Weight', 'Clearcoat'), 1.0)
    set_bsdf_input(bsdf, ('Coat Roughness', 'Clearcoat Roughness'), 0.03)

    bump_gap = nt.nodes.new('ShaderNodeBump')
    bump_gap.invert = True
    bump_gap.inputs['Strength'].default_value = 0.85
    bump_gap.inputs['Distance'].default_value = 0.012
    links.new(gap_mask, bump_gap.inputs['Height'])

    bump_dirt = nt.nodes.new('ShaderNodeBump')
    bump_dirt.inputs['Strength'].default_value = 0.15
    bump_dirt.inputs['Distance'].default_value = 0.004
    links.new(math_op(nt, links, 'MULTIPLY', dirt_mask, dirt_noise), bump_dirt.inputs['Height'])
    links.new(bump_gap.outputs['Normal'], bump_dirt.inputs['Normal'])
    links.new(bump_dirt.outputs['Normal'], bsdf.inputs['Normal'])
    mats['paint'] = m

    # 2. Black Plastic Trim (Cladding, Roof Rails, Bumpers, Grille, Pillars) + Road Dirt
    m, nt, links, bsdf = new_mat("Mat_Plastic")
    tex_coord = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    links.new(tex_coord.outputs['Object'], sep.inputs['Vector'])

    grain = nt.nodes.new('ShaderNodeTexNoise')
    grain.inputs['Scale'].default_value = 180.0
    grain.inputs['Detail'].default_value = 5.0
    links.new(tex_coord.outputs['Object'], grain.inputs['Vector'])

    base_plastic = mix_rgb(nt, links, grain.outputs['Fac'], (0.028, 0.030, 0.033, 1.0), (0.048, 0.050, 0.055, 1.0))
    dirt_mask, dirt_noise = build_dirt_mask(nt, links, tex_coord.outputs['Object'], sep.outputs['Z'])
    plastic_col = mix_rgb(nt, links, dirt_mask, base_plastic, (0.16, 0.14, 0.115, 1.0))
    links.new(plastic_col, bsdf.inputs['Base Color'])
    set_bsdf_input(bsdf, 'Roughness', 0.58)
    set_bsdf_input(bsdf, 'Metallic', 0.05)

    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.18
    bump.inputs['Distance'].default_value = 0.003
    links.new(grain.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    mats['plastic'] = m

    # 3. Black Rubber Tyres with Sidewall Lettering Hint & Tread Noise
    m, nt, links, bsdf = new_mat("Mat_Tyre")
    tex_coord = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    links.new(tex_coord.outputs['Object'], sep.inputs['Vector'])

    sidewall_noise = nt.nodes.new('ShaderNodeTexNoise')
    sidewall_noise.inputs['Scale'].default_value = 85.0
    sidewall_noise.inputs['Detail'].default_value = 8.0
    sidewall_noise.inputs['Distortion'].default_value = 1.4
    links.new(tex_coord.outputs['Object'], sidewall_noise.inputs['Vector'])

    wave = nt.nodes.new('ShaderNodeTexWave')
    wave.wave_type = 'RINGS'
    wave.inputs['Scale'].default_value = 28.0
    wave.inputs['Distortion'].default_value = 3.5
    links.new(tex_coord.outputs['Object'], wave.inputs['Vector'])

    letter_hint = math_op(nt, links, 'MULTIPLY', sidewall_noise.outputs['Fac'], wave.outputs['Fac'], clamp=True)
    dirt_mask, _ = build_dirt_mask(nt, links, tex_coord.outputs['Object'], sep.outputs['Z'])
    rubber_col = mix_rgb(nt, links, letter_hint, (0.022, 0.023, 0.025, 1.0), (0.058, 0.060, 0.064, 1.0))
    rubber_dirty = mix_rgb(nt, links, math_op(nt, links, 'MULTIPLY', dirt_mask, 0.45), rubber_col, (0.13, 0.11, 0.09, 1.0))
    links.new(rubber_dirty, bsdf.inputs['Base Color'])
    set_bsdf_input(bsdf, 'Roughness', 0.72)
    set_bsdf_input(bsdf, 'Metallic', 0.0)

    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.45
    bump.inputs['Distance'].default_value = 0.005
    links.new(letter_hint, bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    mats['tyre'] = m

    # 4. Two-Tone Alloy Rims (Bright Machined Face & Dark Gunmetal Inner)
    m, nt, links, bsdf = new_mat("Mat_Rim")
    tex_coord = nt.nodes.new('ShaderNodeTexCoord')
    brushed = nt.nodes.new('ShaderNodeTexNoise')
    brushed.inputs['Scale'].default_value = 220.0
    brushed.inputs['Detail'].default_value = 4.0
    links.new(tex_coord.outputs['Object'], brushed.inputs['Vector'])
    rim_col = mix_rgb(nt, links, brushed.outputs['Fac'], (0.72, 0.75, 0.79, 1.0), (0.86, 0.88, 0.92, 1.0))
    links.new(rim_col, bsdf.inputs['Base Color'])
    set_bsdf_input(bsdf, 'Metallic', 0.92)
    set_bsdf_input(bsdf, 'Roughness', 0.18)
    mats['rim'] = m

    m, nt, links, bsdf = new_mat("Mat_RimDark")
    set_bsdf_input(bsdf, 'Base Color', (0.14, 0.15, 0.17, 1.0))
    set_bsdf_input(bsdf, 'Metallic', 0.85)
    set_bsdf_input(bsdf, 'Roughness', 0.28)
    mats['rim_dark'] = m

    # 5. Chrome Trim & Brake Discs
    m, nt, links, bsdf = new_mat("Mat_Chrome")
    set_bsdf_input(bsdf, 'Base Color', (0.88, 0.90, 0.93, 1.0))
    set_bsdf_input(bsdf, 'Metallic', 0.96)
    set_bsdf_input(bsdf, 'Roughness', 0.10)
    mats['chrome'] = m

    # 6. Dark Tinted Glass with Slight Interior Visibility
    m, nt, links, bsdf = new_mat("Mat_Glass")
    tex_coord = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    links.new(tex_coord.outputs['Object'], sep.inputs['Vector'])

    headrest_x = add_compare_node(nt, links, math_op(nt, links, 'ABSOLUTE', sep.outputs['X']), 0.38, 0.14)
    seat_y1 = add_compare_node(nt, links, sep.outputs['Y'], -0.05, 0.18)
    seat_y2 = add_compare_node(nt, links, sep.outputs['Y'], 0.85, 0.18)
    seats_mask = math_op(nt, links, 'MULTIPLY', headrest_x, math_op(nt, links, 'MAXIMUM', seat_y1, seat_y2))
    dash_mask = add_range_mask(nt, links, sep.outputs['Y'], -0.95, -0.52)
    interior_hint = math_op(nt, links, 'MAXIMUM', seats_mask, math_op(nt, links, 'MULTIPLY', dash_mask, 0.6), clamp=True)

    sky_grad = nt.nodes.new('ShaderNodeMapRange')
    sky_grad.clamp = True
    sky_grad.inputs['From Min'].default_value = 1.02
    sky_grad.inputs['From Max'].default_value = 1.60
    sky_grad.inputs['To Min'].default_value = 0.0
    sky_grad.inputs['To Max'].default_value = 1.0
    links.new(sep.outputs['Z'], sky_grad.inputs['Value'])

    glass_base = mix_rgb(nt, links, interior_hint, (0.045, 0.060, 0.075, 1.0), (0.095, 0.090, 0.088, 1.0))
    glass_col = mix_rgb(nt, links, math_op(nt, links, 'MULTIPLY', sky_grad.outputs['Result'], 0.45), glass_base, (0.16, 0.21, 0.27, 1.0))
    links.new(glass_col, bsdf.inputs['Base Color'])
    set_bsdf_input(bsdf, 'Roughness', 0.05)
    set_bsdf_input(bsdf, 'Metallic', 0.15)
    set_bsdf_input(bsdf, ('Transmission Weight', 'Transmission'), 0.35)
    set_bsdf_input(bsdf, ('Coat Weight', 'Clearcoat'), 1.0)
    mats['glass'] = m

    # 7. Clear Headlight Lenses (over Reflector & DRL detail)
    m, nt, links, bsdf = new_mat("Mat_HeadlightLens")
    tex_coord = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    links.new(tex_coord.outputs['Object'], sep.inputs['Vector'])

    abs_x = math_op(nt, links, 'ABSOLUTE', sep.outputs['X'])
    proj1 = add_compare_node(nt, links, abs_x, 0.64, 0.045)
    proj2 = add_compare_node(nt, links, abs_x, 0.77, 0.045)
    drl_strip = add_compare_node(nt, links, sep.outputs['Z'], 0.86, 0.015)
    bright_mask = math_op(nt, links, 'MAXIMUM', math_op(nt, links, 'MAXIMUM', proj1, proj2), drl_strip, clamp=True)

    hl_col = mix_rgb(nt, links, bright_mask, (0.55, 0.62, 0.72, 1.0), (0.95, 0.97, 1.0, 1.0))
    links.new(hl_col, bsdf.inputs['Base Color'])
    set_bsdf_input(bsdf, 'Roughness', 0.04)
    set_bsdf_input(bsdf, ('Transmission Weight', 'Transmission'), 0.65)
    set_bsdf_input(bsdf, ('Coat Weight', 'Clearcoat'), 1.0)

    wave = nt.nodes.new('ShaderNodeTexWave')
    wave.inputs['Scale'].default_value = 60.0
    links.new(tex_coord.outputs['Object'], wave.inputs['Vector'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.25
    bump.inputs['Distance'].default_value = 0.004
    links.new(wave.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    mats['headlight_lens'] = m

    # 8. Red Taillight Lenses
    m, nt, links, bsdf = new_mat("Mat_TaillightLens")
    tex_coord = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    links.new(tex_coord.outputs['Object'], sep.inputs['Vector'])

    led_bar = add_compare_node(nt, links, sep.outputs['Z'], 1.05, 0.022)
    rev_strip = add_compare_node(nt, links, sep.outputs['Z'], 1.00, 0.012)
    tl_base = mix_rgb(nt, links, led_bar, (0.48, 0.015, 0.02, 1.0), (0.92, 0.06, 0.05, 1.0))
    tl_col = mix_rgb(nt, links, rev_strip, tl_base, (0.88, 0.85, 0.85, 1.0))
    links.new(tl_col, bsdf.inputs['Base Color'])
    set_bsdf_input(bsdf, 'Roughness', 0.06)
    set_bsdf_input(bsdf, ('Transmission Weight', 'Transmission'), 0.45)
    set_bsdf_input(bsdf, ('Coat Weight', 'Clearcoat'), 1.0)
    mats['taillight_lens'] = m

    # 9. White Number Plate with Dark Characters
    m, nt, links, bsdf = new_mat("Mat_Plate")
    tex_coord = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    links.new(tex_coord.outputs['Object'], sep.inputs['Vector'])

    eu_band = math_op(nt, links, 'LESS_THAN', sep.outputs['X'], -0.20)
    char_x_zone = add_range_mask(nt, links, sep.outputs['X'], -0.17, 0.22)
    wave_x = nt.nodes.new('ShaderNodeTexWave')
    wave_x.wave_type = 'BANDS'
    wave_x.bands_direction = 'X'
    wave_x.inputs['Scale'].default_value = 32.0
    wave_x.inputs['Distortion'].default_value = 2.2
    links.new(tex_coord.outputs['Object'], wave_x.inputs['Vector'])

    checker = nt.nodes.new('ShaderNodeTexChecker')
    checker.inputs['Scale'].default_value = 55.0
    links.new(tex_coord.outputs['Object'], checker.inputs['Vector'])

    char_bars = math_op(nt, links, 'GREATER_THAN', math_op(nt, links, 'MULTIPLY', wave_x.outputs['Fac'], checker.outputs['Fac']), 0.28)
    char_mask = math_op(nt, links, 'MULTIPLY', char_bars, char_x_zone)

    plate_bg = mix_rgb(nt, links, eu_band, (0.92, 0.93, 0.94, 1.0), (0.02, 0.12, 0.48, 1.0))
    plate_col = mix_rgb(nt, links, char_mask, plate_bg, (0.03, 0.03, 0.04, 1.0))
    links.new(plate_col, bsdf.inputs['Base Color'])
    set_bsdf_input(bsdf, 'Roughness', 0.28)
    mats['plate'] = m

    # 10. Interior Material
    m, nt, links, bsdf = new_mat("Mat_Interior")
    set_bsdf_input(bsdf, 'Base Color', (0.06, 0.065, 0.075, 1.0))
    set_bsdf_input(bsdf, 'Roughness', 0.65)
    mats['interior'] = m

    return mats


def create_mesh_obj(name, bm, mat):
    mesh = bpy.data.meshes.new(name)
    bm.normal_update()
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if e.is_boundary or e.calc_face_angle(0.0) > math.radians(40.0):
            e.smooth = False
        else:
            e.smooth = True
    bm.to_mesh(mesh)
    bm.free()
    if hasattr(mesh, "use_auto_smooth"):
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = math.radians(40.0)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    if mat is not None:
        obj.data.materials.append(mat)
    return obj


def wheel_arch_height(y, z_base=0.21):
    for y_axle in (-1.345, 1.345):
        dy = abs(y - y_axle)
        if dy < 0.44:
            # Trapezoidal/rounded SUV wheel arch opening
            t = dy / 0.44
            h = math.sqrt(max(0.0, 1.0 - t * t))
            h_trap = min(1.0, h * 1.18)
            return max(z_base, 0.365 + 0.41 * h_trap)
    return z_base


def get_body_profile_at_y(y):
    z_sill = wheel_arch_height(y, 0.215)
    in_arch = z_sill > 0.23

    # Nose to tail width taper
    if y < -1.85:
        t = (y - (-2.28)) / 0.43
        t = max(0.0, min(1.0, t))
        w_scale = 0.72 + 0.28 * math.sin(t * math.pi * 0.5)
    elif y > 1.85:
        t = (2.26 - y) / 0.41
        t = max(0.0, min(1.0, t))
        w_scale = 0.80 + 0.20 * math.sin(t * math.pi * 0.5)
    else:
        w_scale = 1.0

    # Top centerline height (hood, windscreen, roof, spoiler, tailgate, rear bumper)
    if y <= -2.18:
        t = (y - (-2.28)) / 0.10
        z_top = 0.48 + 0.34 * max(0.0, min(1.0, t))
    elif y <= -1.04:
        t = (y - (-2.18)) / 1.14
        z_top = 0.82 + 0.21 * (t ** 0.75)
    elif y <= -0.34:
        t = (y - (-1.04)) / 0.70
        z_top = 1.03 + 0.59 * (t ** 0.90)
    elif y <= 1.78:
        t = (y - (-0.34)) / 2.12
        z_top = 1.62 + 0.025 * math.sin(t * math.pi) - 0.02 * (t ** 2)
    elif y <= 1.88:
        z_top = 1.615
    elif y <= 2.16:
        t = (y - 1.88) / 0.28
        z_top = 1.615 - 0.515 * t
    else:
        t = (y - 2.16) / 0.10
        z_top = 1.10 - 0.48 * max(0.0, min(1.0, t))

    # Beltline height (shoulder line rising gently from nose to rear D-pillar)
    if y <= -2.18:
        z_belt = min(z_top - 0.02, 0.74)
    elif y <= -1.04:
        t = (y - (-2.18)) / 1.14
        z_belt = 0.80 + 0.21 * (t ** 0.8)
    else:
        t = max(0.0, min(1.0, (y - (-1.04)) / 3.20))
        z_belt = 1.01 + 0.11 * t

    z_belt = min(z_belt, z_top - 0.03)
    z_mid = max(z_sill + 0.04, 0.56 + 0.05 * ((y + 2.3) / 4.6))
    z_low = max(z_sill + 0.015, 0.36)

    x_sill = 0.875 * w_scale
    x_low = 0.905 * w_scale
    x_mid = 0.925 * w_scale
    x_belt = 0.855 * w_scale

    # Tumblehome greenhouse width
    if -0.98 < y < 2.05 and z_top > z_belt + 0.08:
        x_roof_rail = 0.645 * w_scale
        x_crown = 0.32 * w_scale
        # Slight window recess in the body side between beltline and roof rail
        in_side_window = (-0.86 < y < 1.64)
        x_win_mid = (0.715 if in_side_window else 0.755) * w_scale
        z_win_mid = z_belt + 0.52 * (z_top - z_belt)
        z_cantrail = z_top - 0.035
    else:
        x_roof_rail = 0.72 * w_scale
        x_crown = 0.36 * w_scale
        x_win_mid = 0.80 * w_scale
        z_win_mid = z_belt + 0.45 * (z_top - z_belt)
        z_cantrail = z_top - 0.018

    # Recess windscreen and rear window slightly on top centerline
    z_center_top = z_top
    if -1.00 < y < -0.38:
        z_center_top -= 0.022
    elif 1.86 < y < 2.14:
        z_center_top -= 0.022

    # Inner wheel housing points when over a wheel arch
    x_under_in = (x_sill - 0.27) if in_arch else (x_sill - 0.06)
    z_under_in = z_sill if in_arch else 0.215

    # Return ordered half-section points from bottom centerline (x=0) up to top centerline (x=0)
    pts = [
        (0.0, 0.215),
        (max(0.18, x_under_in), 0.215),
        (max(0.20, x_under_in), z_under_in),
        (x_sill, z_sill),
        (x_low, max(z_sill + 0.012, z_low)),
        (x_mid, max(z_sill + 0.035, z_mid)),
        (x_belt, max(z_sill + 0.065, z_belt)),
        (x_win_mid, max(z_sill + 0.085, z_win_mid)),
        (x_roof_rail, max(z_sill + 0.10, z_cantrail)),
        (x_crown, z_center_top),
        (0.0, z_center_top),
    ]
    return pts


def build_suv_body(mats):
    bm = bmesh.new()
    y_stations = [
        -2.28, -2.23, -2.16, -1.96, -1.79, -1.68, -1.52, -1.345, -1.17, -1.04,
        -0.91, -0.75, -0.52, -0.34, -0.15, 0.05, 0.35, 0.65, 0.91, 1.04,
        1.17, 1.345, 1.52, 1.68, 1.79, 1.88, 1.98, 2.10, 2.18, 2.26,
    ]

    rings = []
    for y in y_stations:
        half_pts = get_body_profile_at_y(y)
        # Build full closed loop around X (right side +X from bottom to top, then left side -X from top to bottom)
        ring_verts = []
        # Bottom center
        ring_verts.append(bm.verts.new((0.0, y, half_pts[0][1])))
        # Right side (+X) inner points
        for x, z in half_pts[1:-1]:
            ring_verts.append(bm.verts.new((x, y, z)))
        # Top center
        ring_verts.append(bm.verts.new((0.0, y, half_pts[-1][1])))
        # Left side (-X) inner points in reverse
        for x, z in reversed(half_pts[1:-1]):
            ring_verts.append(bm.verts.new((-x, y, z)))
        rings.append(ring_verts)

    n_ring = len(rings[0])
    for i in range(len(rings) - 1):
        r1 = rings[i]
        r2 = rings[i + 1]
        for j in range(n_ring):
            jn = (j + 1) % n_ring
            v1, v2, v3, v4 = r1[j], r1[jn], r2[jn], r2[j]
            bm.faces.new((v1, v2, v3, v4))

    # Cap front nose and rear tail
    front_ring = rings[0]
    top_idx = len(get_body_profile_at_y(y_stations[0])) - 1
    for j in range(1, top_idx):
        v_r1 = front_ring[j - 1]
        v_r2 = front_ring[j]
        v_l2 = front_ring[(n_ring - j) % n_ring]
        v_l1 = front_ring[(n_ring - (j - 1)) % n_ring]
        verts = []
        for v in (v_r1, v_r2, v_l2, v_l1):
            if v not in verts:
                verts.append(v)
        if len(verts) >= 3:
            bm.faces.new(tuple(reversed(verts)))

    rear_ring = rings[-1]
    for j in range(1, top_idx):
        v_r1 = rear_ring[j - 1]
        v_r2 = rear_ring[j]
        v_l2 = rear_ring[(n_ring - j) % n_ring]
        v_l1 = rear_ring[(n_ring - (j - 1)) % n_ring]
        verts = []
        for v in (v_r1, v_r2, v_l2, v_l1):
            if v not in verts:
                verts.append(v)
        if len(verts) >= 3:
            bm.faces.new(tuple(verts))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    body_obj = create_mesh_obj("BodyShell", bm, mats['paint'])

    # Apply Subdivision Surface modifier (level 1) as required
    sub = body_obj.modifiers.new(name="Subsurf", type='SUBSURF')
    sub.levels = 1
    sub.render_levels = 1
    bpy.context.view_layer.objects.active = body_obj
    bpy.ops.object.modifier_apply(modifier=sub.name)

    # Refresh sharp edges after subdivision
    bm2 = bmesh.new()
    bm2.from_mesh(body_obj.data)
    for f in bm2.faces:
        f.smooth = True
    for e in bm2.edges:
        if e.is_boundary or e.calc_face_angle(0.0) > math.radians(38.0):
            e.smooth = False
        else:
            e.smooth = True
    bm2.to_mesh(body_obj.data)
    bm2.free()
    return body_obj


def add_quad_grid(bm, grid):
    rows = len(grid)
    cols = len(grid[0])
    vgrid = [[bm.verts.new(pt) for pt in row] for row in grid]
    for r in range(rows - 1):
        for c in range(cols - 1):
            bm.faces.new((vgrid[r][c], vgrid[r + 1][c], vgrid[r + 1][c + 1], vgrid[r][c + 1]))
    return vgrid


def add_solid_strip(bm, outer_grid, thickness_vec):
    rows = len(outer_grid)
    cols = len(outer_grid[0])
    v_out = [[bm.verts.new(pt) for pt in row] for row in outer_grid]
    v_in = [[bm.verts.new((pt[0] + thickness_vec[0], pt[1] + thickness_vec[1], pt[2] + thickness_vec[2])) for pt in row] for row in outer_grid]

    for r in range(rows - 1):
        for c in range(cols - 1):
            bm.faces.new((v_out[r][c], v_out[r + 1][c], v_out[r + 1][c + 1], v_out[r][c + 1]))
            bm.faces.new((v_in[r][c], v_in[r][c + 1], v_in[r + 1][c + 1], v_in[r + 1][c]))

    for c in range(cols - 1):
        bm.faces.new((v_out[0][c], v_out[0][c + 1], v_in[0][c + 1], v_in[0][c]))
        bm.faces.new((v_out[-1][c + 1], v_out[-1][c], v_in[-1][c], v_in[-1][c + 1]))

    for r in range(rows - 1):
        bm.faces.new((v_out[r + 1][0], v_out[r][0], v_in[r][0], v_in[r + 1][0]))
        bm.faces.new((v_out[r][cols - 1], v_out[r + 1][cols - 1], v_in[r + 1][cols - 1], v_in[r][cols - 1]))


def build_windows(mats):
    bm = bmesh.new()

    # 1. Curved Front Windscreen (inset slightly into body)
    ws_rows = []
    for i in range(7):
        v = i / 6.0
        y_base = -1.01 + 0.64 * v
        z = 1.035 + 0.555 * (v ** 0.92)
        w_half = 0.72 - 0.12 * v
        row = []
        for j in range(9):
            u = (j / 8.0) * 2.0 - 1.0
            x = u * w_half
            arch_y = 0.055 * (1.0 - u * u)
            arch_z = 0.018 * (1.0 - u * u)
            row.append((x, y_base - arch_y, z + arch_z))
        ws_rows.append(row)
    add_solid_strip(bm, ws_rows, (0.0, 0.012, -0.012))

    # 2. Curved Rear Tailgate Window
    rw_rows = []
    for i in range(6):
        v = i / 5.0
        y_base = 1.86 + 0.28 * v
        z = 1.565 - 0.435 * v
        w_half = 0.56 + 0.09 * v
        row = []
        for j in range(9):
            u = (j / 8.0) * 2.0 - 1.0
            x = u * w_half
            arch_y = 0.045 * (1.0 - u * u)
            arch_z = 0.015 * (1.0 - u * u)
            row.append((x, y_base + arch_y, z + arch_z))
        rw_rows.append(row)
    add_solid_strip(bm, rw_rows, (0.0, -0.012, -0.012))

    # 3. Side Windows (Front Door, Rear Door, Rear Quarter on Left & Right, inset into body)
    side_panels = [
        # Front door glass
        [(-0.88, -0.34, 0.02), (-0.36, -0.34, 0.02)],
        # Rear door glass
        [(0.08, 0.48, 0.94), (0.08, 0.48, 0.90)],
        # Rear quarter glass (with upward RAV4 beltline sweep)
        [(0.99, 1.32, 1.66), (0.95, 1.24, 1.48)],
    ]
    for side in (-1.0, 1.0):
        for idx, (y_bot_pts, y_top_pts) in enumerate(side_panels):
            grid = []
            for r in range(4):
                vr = r / 3.0
                row = []
                for c in range(4):
                    uc = c / 3.0
                    y_b = (1.0 - uc) * y_bot_pts[0] + uc * y_bot_pts[-1]
                    y_t = (1.0 - uc) * y_top_pts[0] + uc * y_top_pts[-1]
                    y = (1.0 - vr) * y_b + vr * y_t
                    z_b = 1.02 + 0.032 * ((y + 1.0) / 2.7)
                    if idx == 2 and uc > 0.5:
                        z_b += 0.045 * (uc - 0.5) * 2.0
                    z_t = 1.565 - 0.025 * max(0.0, (y - 0.5) / 1.2)
                    z = (1.0 - vr) * z_b + vr * z_t
                    x_b = 0.835
                    x_t = 0.648
                    x_mag = (1.0 - vr) * x_b + vr * x_t + 0.014 * math.sin(vr * math.pi)
                    row.append((side * x_mag, y, z))
                grid.append(row)
            add_solid_strip(bm, grid, (-side * 0.012, 0.0, 0.0))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return create_mesh_obj("Windows", bm, mats['glass'])


def build_pillars(mats):
    bm_paint = bmesh.new()
    bm_black = bmesh.new()

    for side in (-1.0, 1.0):
        # A-pillar (painted outer shell along windscreen edge)
        a_grid = []
        for r in range(6):
            t = r / 5.0
            y = -1.03 + 0.68 * t
            z = 1.02 + 0.595 * (t ** 0.92)
            x_in = (0.71 - 0.11 * t) * side
            x_out = (0.835 - 0.185 * t) * side
            a_grid.append([(x_in, y - 0.015, z + 0.01), (x_out, y + 0.03, z - 0.01)])
        add_solid_strip(bm_paint, a_grid, (-side * 0.025, 0.02, -0.02))

        # B-pillar (black gloss trim between front and rear doors)
        b_grid = []
        for r in range(5):
            t = r / 4.0
            z = 1.015 + 0.555 * t
            x = (0.842 * (1.0 - t) + 0.652 * t + 0.012 * math.sin(t * math.pi)) * side
            b_grid.append([(x, 0.015, z), (x, 0.085, z)])
        add_solid_strip(bm_black, b_grid, (-side * 0.022, 0.0, 0.0))

        # C-pillar (black trim between rear door and quarter window)
        c_grid = []
        for r in range(5):
            t = r / 4.0
            z = 1.04 + 0.525 * t
            y1 = 0.935 - 0.035 * t
            y2 = 0.995 - 0.040 * t
            x = (0.840 * (1.0 - t) + 0.652 * t + 0.012 * math.sin(t * math.pi)) * side
            c_grid.append([(x, y1, z), (x, y2, z)])
        add_solid_strip(bm_black, c_grid, (-side * 0.022, 0.0, 0.0))

        # D-pillar (painted wide SUV rear pillar from quarter glass to tailgate)
        d_grid = []
        for r in range(5):
            t = r / 4.0
            z = 1.09 + 0.48 * t
            y1 = 1.66 - 0.18 * t
            y2 = 2.13 - 0.25 * t
            x1 = (0.835 * (1.0 - t) + 0.645 * t) * side
            x2 = (0.745 * (1.0 - t) + 0.575 * t) * side
            d_grid.append([(x1, y1, z), (x2, y2, z)])
        add_solid_strip(bm_paint, d_grid, (-side * 0.025, -0.02, -0.015))

    bmesh.ops.recalc_face_normals(bm_paint, faces=bm_paint.faces)
    bmesh.ops.recalc_face_normals(bm_black, faces=bm_black.faces)
    obj_p1 = create_mesh_obj("Pillars_Paint", bm_paint, mats['paint'])
    obj_p2 = create_mesh_obj("Pillars_Black", bm_black, mats['plastic'])
    return [obj_p1, obj_p2]


def build_bumpers_and_grille(mats):
    bm_plastic = bmesh.new()
    bm_chrome = bmesh.new()
    bm_paint = bmesh.new()

    # 1. Front Bumper Lower Air Dam & Cladding Wrap (Y = -2.30 to -1.78)
    fb_grid = []
    for r in range(5):
        t = r / 4.0
        z = 0.21 + 0.28 * t
        row = []
        for c in range(11):
            u = (c / 10.0) * 2.0 - 1.0
            au = abs(u)
            x = u * (0.86 + 0.04 * t)
            if au < 0.58:
                y = -2.30 + 0.06 * (au / 0.58) ** 2 - 0.012 * math.sin(t * math.pi)
            else:
                s = (au - 0.58) / 0.42
                y = -2.24 + 0.46 * (s ** 1.4)
            row.append((x, y, z))
        fb_grid.append(row)
    add_solid_strip(bm_plastic, fb_grid, (0.0, 0.035, 0.0))

    # Front Silver Skid Plate Garnish
    skid_f = []
    for r in range(3):
        t = r / 2.0
        z = 0.215 + 0.11 * t
        row = []
        for c in range(7):
            u = (c / 6.0) * 2.0 - 1.0
            x = u * (0.48 - 0.05 * t)
            y = -2.308 + 0.025 * (u * u) + 0.015 * (1.0 - t)
            row.append((x, y, z))
        skid_f.append(row)
    add_solid_strip(bm_chrome, skid_f, (0.0, 0.02, 0.0))

    # Front Lower Intake Grille Louvers
    for z_bar in (0.27, 0.32, 0.37, 0.42):
        bar_grid = []
        for r in range(2):
            z = z_bar + r * 0.014
            row = []
            for c in range(7):
                u = (c / 6.0) * 2.0 - 1.0
                x = u * 0.50
                y = -2.306 + 0.035 * (u * u)
                row.append((x, y, z))
            bar_grid.append(row)
        add_solid_strip(bm_plastic, bar_grid, (0.0, 0.03, 0.0))

    # 2. Large Octagonal RAV4 Upper Grille (Y = -2.285, Z = 0.54 to 0.81)
    ug_grid = []
    for r in range(5):
        t = r / 4.0
        z = 0.54 + 0.27 * t
        w = 0.54 - 0.08 * abs(t - 0.55) * 2.0
        row = []
        for c in range(9):
            u = (c / 8.0) * 2.0 - 1.0
            x = u * w
            y = -2.285 + 0.045 * (u * u) + 0.02 * t
            row.append((x, y, z))
        ug_grid.append(row)
    add_solid_strip(bm_plastic, ug_grid, (0.0, 0.035, 0.0))

    # Upper Grille Horizontal Mesh Crossbars & Vertical Struts
    for z_bar in (0.58, 0.63, 0.68, 0.73, 0.78):
        t = (z_bar - 0.54) / 0.27
        w = 0.52 - 0.07 * abs(t - 0.55) * 2.0
        bar = []
        for r in range(2):
            z = z_bar + r * 0.015
            row = []
            for c in range(7):
                u = (c / 6.0) * 2.0 - 1.0
                x = u * w
                y = -2.295 + 0.045 * (u * u) + 0.02 * t
                row.append((x, y, z))
            bar.append(row)
        add_solid_strip(bm_plastic, bar, (0.0, 0.025, 0.0))

    # Central Chrome SUV Emblem Badge on Upper Grille
    emb_verts_f = []
    emb_verts_b = []
    for k in range(16):
        ang = (k / 16.0) * 2.0 * math.pi
        x = 0.075 * math.cos(ang)
        z = 0.72 + 0.052 * math.sin(ang)
        y = -2.302 + 0.006 * (x * x)
        emb_verts_f.append(bm_chrome.verts.new((x, y, z)))
        emb_verts_b.append(bm_chrome.verts.new((x, y + 0.02, z)))
    bm_chrome.faces.new(tuple(emb_verts_f))
    bm_chrome.faces.new(tuple(reversed(emb_verts_b)))
    for k in range(16):
        kn = (k + 1) % 16
        bm_chrome.faces.new((emb_verts_f[k], emb_verts_b[k], emb_verts_b[kn], emb_verts_f[kn]))

    # Front Painted Bumper Upper Fascia Bridge & Fog Light Bezels
    for side in (-1.0, 1.0):
        fog_grid = []
        for r in range(4):
            t = r / 3.0
            z = 0.34 + 0.20 * t
            row = []
            for c in range(4):
                u = c / 3.0
                x = side * (0.58 + 0.25 * u)
                y = -2.26 + 0.14 * (u ** 1.3)
                row.append((x, y, z))
            fog_grid.append(row)
        add_solid_strip(bm_plastic, fog_grid, (-side * 0.015, 0.025, 0.0))

    # 3. Rear Bumper Cladding & Diffuser (Y = 1.78 to 2.30)
    rb_grid = []
    for r in range(5):
        t = r / 4.0
        z = 0.23 + 0.34 * t
        row = []
        for c in range(11):
            u = (c / 10.0) * 2.0 - 1.0
            au = abs(u)
            x = u * (0.86 + 0.03 * t)
            if au < 0.62:
                y = 2.30 - 0.05 * (au / 0.62) ** 2 + 0.01 * math.sin(t * math.pi)
            else:
                s = (au - 0.62) / 0.38
                y = 2.25 - 0.47 * (s ** 1.35)
            row.append((x, y, z))
        rb_grid.append(row)
    add_solid_strip(bm_plastic, rb_grid, (0.0, -0.035, 0.0))

    # Rear Silver Diffuser Skid Plate
    skid_r = []
    for r in range(3):
        t = r / 2.0
        z = 0.235 + 0.14 * t
        row = []
        for c in range(7):
            u = (c / 6.0) * 2.0 - 1.0
            x = u * (0.54 - 0.04 * t)
            y = 2.306 - 0.025 * (u * u)
            row.append((x, y, z))
        skid_r.append(row)
    add_solid_strip(bm_chrome, skid_r, (0.0, -0.02, 0.0))

    # Dual Chrome Exhaust Tailpipes
    for side in (-1.0, 1.0):
        cx = side * 0.53
        cz = 0.265
        r_out = 0.044
        r_in = 0.035
        ring_f_out, ring_b_out, ring_f_in, ring_b_in = [], [], [], []
        for k in range(14):
            ang = (k / 14.0) * 2.0 * math.pi
            dx, dz = math.cos(ang), math.sin(ang)
            ring_f_out.append(bm_chrome.verts.new((cx + r_out * dx, 2.29, cz + r_out * dz)))
            ring_b_out.append(bm_chrome.verts.new((cx + r_out * dx, 2.12, cz + r_out * dz)))
            ring_f_in.append(bm_chrome.verts.new((cx + r_in * dx, 2.29, cz + r_in * dz)))
            ring_b_in.append(bm_chrome.verts.new((cx + r_in * dx, 2.18, cz + r_in * dz)))
        for k in range(14):
            kn = (k + 1) % 14
            bm_chrome.faces.new((ring_f_out[k], ring_f_out[kn], ring_b_out[kn], ring_b_out[k]))
            bm_chrome.faces.new((ring_f_out[kn], ring_f_out[k], ring_f_in[k], ring_f_in[kn]))
            bm_chrome.faces.new((ring_f_in[kn], ring_f_in[k], ring_b_in[k], ring_b_in[kn]))
        bm_chrome.faces.new(tuple(ring_b_in))

    bmesh.ops.recalc_face_normals(bm_plastic, faces=bm_plastic.faces)
    bmesh.ops.recalc_face_normals(bm_chrome, faces=bm_chrome.faces)
    objs = [
        create_mesh_obj("Bumpers_Plastic", bm_plastic, mats['plastic']),
        create_mesh_obj("Bumpers_Chrome", bm_chrome, mats['chrome']),
    ]
    bm_paint.free()
    return objs


def build_cladding(mats):
    bm = bmesh.new()

    # 1. 4x Trapezoidal/Octagonal RAV4 Wheel Arch Fender Flares
    for side in (-1.0, 1.0):
        for y_axle in (-1.345, 1.345):
            arch_grid = []
            n_pts = 11
            for r in range(3):
                rad_offset = r * 0.042
                x_protrude = (0.018 if r == 1 else (0.012 if r == 0 else 0.002)) * side
                row = []
                for c in range(n_pts):
                    ang = math.pi * (0.04 + 0.92 * (c / (n_pts - 1)))
                    dy = -0.435 * math.cos(ang)
                    y = y_axle + dy
                    # Flat-topped SUV arch flare contour
                    sin_a = math.sin(ang)
                    h_inner = min(1.0, sin_a * 1.18)
                    z_inner = max(0.22, 0.365 + 0.405 * h_inner)
                    z = z_inner + rad_offset * sin_a
                    y_flare = y + (dy / 0.435) * rad_offset * 0.85
                    x_base = 0.885 + 0.032 * sin_a
                    x = side * x_base + x_protrude
                    row.append((x, y_flare, z))
                arch_grid.append(row)
            add_solid_strip(bm, arch_grid, (-side * 0.025, 0.0, 0.0))

        # 2. Lower Door Sill Rocker Cladding between Front & Rear Arches
        sill_grid = []
        for r in range(4):
            t = r / 3.0
            z = 0.215 + 0.135 * t
            x = side * (0.882 + 0.032 * math.sin(t * math.pi * 0.85))
            row = []
            for c in range(7):
                u = c / 6.0
                y = -0.91 + 1.82 * u
                row.append((x, y, z))
            sill_grid.append(row)
        add_solid_strip(bm, sill_grid, (-side * 0.025, 0.0, 0.0))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return create_mesh_obj("WheelArchCladding", bm, mats['plastic'])


def build_lights(mats):
    bm_refl = bmesh.new()
    bm_hl_lens = bmesh.new()
    bm_tl_lens = bmesh.new()

    for side in (-1.0, 1.0):
        # 1. Headlights (Reflector housing + Dual Projector bowls + Clear outer lens)
        hl_in_grid = []
        hl_out_grid = []
        for r in range(4):
            t = r / 3.0
            z_base = 0.74 + 0.13 * t
            row_in = []
            row_out = []
            for c in range(6):
                u = c / 5.0
                x = side * (0.51 + 0.37 * u)
                y_front = -2.26 + 0.22 * (u ** 1.35) + 0.025 * t
                z = z_base + 0.035 * u
                row_out.append((x, y_front - 0.008, z))
                row_in.append((x, y_front + 0.045 - 0.018 * math.sin(u * math.pi), z))
            hl_in_grid.append(row_in)
            hl_out_grid.append(row_out)

        add_solid_strip(bm_refl, hl_in_grid, (0.0, 0.02, 0.0))
        add_solid_strip(bm_hl_lens, hl_out_grid, (0.0, 0.008, 0.0))

        # Projector LED Barrels inside Headlight
        for x_proj, y_proj, z_proj in ((0.61 * side, -2.20, 0.81), (0.74 * side, -2.14, 0.83)):
            ring1, ring2 = [], []
            for k in range(10):
                ang = (k / 10.0) * 2.0 * math.pi
                dx, dz = 0.032 * math.cos(ang), 0.032 * math.sin(ang)
                ring1.append(bm_refl.verts.new((x_proj + dx, y_proj, z_proj + dz)))
                ring2.append(bm_refl.verts.new((x_proj + 0.6 * dx, y_proj + 0.045, z_proj + 0.6 * dz)))
            for k in range(10):
                kn = (k + 1) % 10
                bm_refl.faces.new((ring1[k], ring1[kn], ring2[kn], ring2[k]))
            bm_refl.faces.new(tuple(ring1))

        # 2. Taillights (Reflector + Sculpted Red Outer Lens wrapping rear corners)
        tl_in_grid = []
        tl_out_grid = []
        for r in range(4):
            t = r / 3.0
            z_base = 0.96 + 0.14 * t
            row_in = []
            row_out = []
            for c in range(6):
                u = c / 5.0
                x = side * (0.44 + 0.43 * u)
                y_rear = 2.23 - 0.21 * (u ** 1.5) - 0.02 * t
                z = z_base + 0.02 * (1.0 - u)
                row_out.append((x, y_rear + 0.012, z))
                row_in.append((x, y_rear - 0.032 + 0.015 * math.sin(u * math.pi), z))
            tl_in_grid.append(row_in)
            tl_out_grid.append(row_out)

        add_solid_strip(bm_refl, tl_in_grid, (0.0, -0.02, 0.0))
        add_solid_strip(bm_tl_lens, tl_out_grid, (0.0, -0.008, 0.0))

    # Rear Tailgate Chrome Garnish Bar connecting left & right taillights
    garnish_grid = []
    for r in range(3):
        t = r / 2.0
        z = 0.985 + 0.035 * t
        row = []
        for c in range(7):
            u = (c / 6.0) * 2.0 - 1.0
            x = u * 0.45
            y = 2.238 - 0.015 * (u * u)
            row.append((x, y, z))
        garnish_grid.append(row)
    add_solid_strip(bm_refl, garnish_grid, (0.0, -0.018, 0.0))

    bmesh.ops.recalc_face_normals(bm_refl, faces=bm_refl.faces)
    bmesh.ops.recalc_face_normals(bm_hl_lens, faces=bm_hl_lens.faces)
    bmesh.ops.recalc_face_normals(bm_tl_lens, faces=bm_tl_lens.faces)

    return [
        create_mesh_obj("LightReflectors", bm_refl, mats['chrome']),
        create_mesh_obj("HeadlightLenses", bm_hl_lens, mats['headlight_lens']),
        create_mesh_obj("TaillightLenses", bm_tl_lens, mats['taillight_lens']),
    ]


def add_box_to_bm(bm, center, size, rot_euler=(0.0, 0.0, 0.0)):
    mat_rot = Euler(rot_euler, 'XYZ').to_matrix().to_4x4()
    mat_trans = Matrix.Translation(center)
    bmesh.ops.create_cube(bm, size=1.0, matrix=mat_trans @ mat_rot @ Matrix.Diagonal((size[0], size[1], size[2], 1.0)))


def build_details(mats):
    bm_paint = bmesh.new()
    bm_plastic = bmesh.new()
    bm_chrome = bmesh.new()
    bm_plate = bmesh.new()

    for side in (-1.0, 1.0):
        # 1. Side Mirrors (Pedestal stalk on door + sculpted aerodynamic housing + mirror glass)
        add_box_to_bm(
            bm_plastic,
            (side * 0.90, -0.74, 1.01),
            (0.09, 0.09, 0.06),
            (0.0, side * 0.35, -side * 0.15),
        )
        # Mirror housing cap (contoured 3D shell)
        m_grid = []
        for r in range(5):
            t = r / 4.0
            z = 1.02 + 0.115 * math.sin(t * math.pi * 0.85) + 0.02 * t
            row = []
            for c in range(5):
                u = c / 4.0
                x = side * (0.915 + 0.155 * u)
                y_front = -0.81 + 0.045 * (u ** 1.4) + 0.025 * (t - 0.5) ** 2
                row.append((x, y_front, z))
            m_grid.append(row)
        add_solid_strip(bm_paint, m_grid, (0.0, 0.085, 0.0))

        # Mirror reflective glass face on rear (+Y) side of housing
        add_box_to_bm(
            bm_chrome,
            (side * 0.995, -0.718, 1.075),
            (0.125, 0.012, 0.082),
            (0.0, 0.0, -side * 0.12),
        )

        # 2. Door Handles (Front & Rear doors)
        for y_handle in (-0.18, 0.72):
            # Front & rear handle mounts
            add_box_to_bm(bm_paint, (side * 0.915, y_handle - 0.085, 0.985), (0.035, 0.042, 0.032))
            add_box_to_bm(bm_paint, (side * 0.915, y_handle + 0.085, 0.985), (0.035, 0.042, 0.032))
            # Sculpted arched pull bar
            h_grid = []
            for r in range(3):
                z = 0.97 + r * 0.016
                row = []
                for c in range(6):
                    u = c / 5.0
                    y = y_handle - 0.095 + 0.19 * u
                    x = side * (0.922 + 0.024 * math.sin(u * math.pi))
                    row.append((x, y, z))
                h_grid.append(row)
            add_solid_strip(bm_paint, h_grid, (-side * 0.016, 0.0, 0.0))

        # 3. Raised SUV Roof Rails (X = ±0.55, Y = -0.26 to 1.66, Z up to 1.69 m)
        rail_grid = []
        for r in range(3):
            t = r / 2.0
            x_off = (t - 0.5) * 0.042
            row = []
            for c in range(11):
                u = c / 10.0
                y = -0.28 + 1.94 * u
                arch = math.sin(u * math.pi)
                z = 1.625 + 0.055 * (arch ** 0.55) + 0.012 * (1.0 - abs(t - 0.5) * 2.0)
                x = side * (0.555 - 0.035 * u) + x_off
                row.append((x, y, z))
            rail_grid.append(row)
        add_solid_strip(bm_plastic, rail_grid, (0.0, 0.0, -0.024))

        # Roof rail mounting feet (front, middle, rear)
        for y_foot, z_foot in ((-0.22, 1.63), (0.70, 1.645), (1.58, 1.622)):
            x_foot = side * (0.555 - 0.035 * ((y_foot + 0.28) / 1.94))
            add_box_to_bm(bm_plastic, (x_foot, y_foot, z_foot), (0.046, 0.16, 0.055))

    # 4. Roof Shark-Fin Antenna (Center rear roof)
    fin_grid = [
        [(0.0, 1.44, 1.625), (0.0, 1.54, 1.692), (0.0, 1.62, 1.690)],
        [(0.028, 1.46, 1.620), (0.016, 1.55, 1.655), (0.004, 1.63, 1.655)],
        [(-0.028, 1.46, 1.620), (-0.016, 1.55, 1.655), (-0.004, 1.63, 1.655)],
    ]
    add_box_to_bm(bm_paint, (0.0, 1.54, 1.652), (0.045, 0.15, 0.068), (-0.22, 0.0, 0.0))

    # 5. Windshield Wipers (2 front, 1 rear)
    # Front driver & passenger wipers
    for x_start, x_end, y_base, z_base in (
        (-0.56, 0.06, -0.99, 1.055),
        (-0.04, 0.58, -0.97, 1.062),
    ):
        cx = 0.5 * (x_start + x_end)
        length = abs(x_end - x_start)
        add_box_to_bm(bm_plastic, (cx, y_base, z_base), (length, 0.022, 0.018), (0.35, 0.04, 0.05))
        add_box_to_bm(bm_plastic, (x_start + 0.06, y_base - 0.02, z_base - 0.01), (0.18, 0.028, 0.022), (0.35, 0.0, 0.12))

    # Rear tailgate wiper
    add_box_to_bm(bm_plastic, (0.16, 2.155, 1.135), (0.34, 0.020, 0.018), (-0.45, 0.0, -0.06))
    add_box_to_bm(bm_plastic, (0.0, 2.162, 1.125), (0.045, 0.035, 0.032))

    # 6. Number Plates (Front & Back: frame + white plate with characters)
    # Front plate at Y = -2.312, Z = 0.45
    add_box_to_bm(bm_plastic, (0.0, -2.308, 0.45), (0.535, 0.022, 0.125))
    fp_grid = [
        [(-0.255, -2.320, 0.395), (0.255, -2.320, 0.395)],
        [(-0.255, -2.320, 0.505), (0.255, -2.320, 0.505)],
    ]
    add_solid_strip(bm_plate, fp_grid, (0.0, 0.008, 0.0))

    # Rear plate at Y = 2.248, Z = 0.84
    add_box_to_bm(bm_plastic, (0.0, 2.242, 0.84), (0.535, 0.022, 0.125), (-0.12, 0.0, 0.0))
    rp_grid = [
        [(0.255, 2.256, 0.785), (-0.255, 2.256, 0.785)],
        [(0.255, 2.243, 0.895), (-0.255, 2.243, 0.895)],
    ]
    add_solid_strip(bm_plate, rp_grid, (0.0, -0.008, 0.0))

    bmesh.ops.recalc_face_normals(bm_paint, faces=bm_paint.faces)
    bmesh.ops.recalc_face_normals(bm_plastic, faces=bm_plastic.faces)
    bmesh.ops.recalc_face_normals(bm_chrome, faces=bm_chrome.faces)
    bmesh.ops.recalc_face_normals(bm_plate, faces=bm_plate.faces)

    return [
        create_mesh_obj("Details_Paint", bm_paint, mats['paint']),
        create_mesh_obj("Details_Plastic", bm_plastic, mats['plastic']),
        create_mesh_obj("Details_Chrome", bm_chrome, mats['chrome']),
        create_mesh_obj("NumberPlates", bm_plate, mats['plate']),
    ]


def build_interior(mats):
    bm = bmesh.new()

    # Dashboard & Center Infotainment Screen
    add_box_to_bm(bm, (0.0, -0.78, 0.96), (1.42, 0.42, 0.24))
    add_box_to_bm(bm, (-0.38, -0.68, 1.08), (0.34, 0.22, 0.12))
    add_box_to_bm(bm, (0.0, -0.65, 1.11), (0.26, 0.04, 0.15), (-0.18, 0.0, 0.0))

    # Steering Wheel
    sw_verts_f, sw_verts_b = [], []
    for k in range(14):
        ang = (k / 14.0) * 2.0 * math.pi
        dx = 0.175 * math.cos(ang)
        dz = 0.175 * math.sin(ang)
        y = -0.52 - 0.35 * dz
        z = 1.03 + 0.93 * dz
        sw_verts_f.append(bm.verts.new((-0.38 + dx, y, z)))
        sw_verts_b.append(bm.verts.new((-0.38 + 0.78 * dx, y - 0.025, z - 0.015 * math.sin(ang))))
    for k in range(14):
        kn = (k + 1) % 14
        bm.faces.new((sw_verts_f[k], sw_verts_f[kn], sw_verts_b[kn], sw_verts_b[k]))

    # Center Console
    add_box_to_bm(bm, (0.0, -0.22, 0.72), (0.26, 0.85, 0.32))

    # Front Seats (Cushion + Backrest + Headrest)
    for side in (-1.0, 1.0):
        sx = side * 0.38
        add_box_to_bm(bm, (sx, -0.18, 0.68), (0.48, 0.50, 0.16))
        add_box_to_bm(bm, (sx, 0.02, 0.98), (0.46, 0.14, 0.54), (-0.22, 0.0, 0.0))
        add_box_to_bm(bm, (sx, 0.09, 1.32), (0.22, 0.11, 0.18), (-0.12, 0.0, 0.0))

    # Rear Bench Seat + 3 Headrests
    add_box_to_bm(bm, (0.0, 0.72, 0.70), (1.32, 0.48, 0.16))
    add_box_to_bm(bm, (0.0, 0.94, 1.00), (1.30, 0.14, 0.52), (-0.18, 0.0, 0.0))
    for hx in (-0.42, 0.0, 0.42):
        add_box_to_bm(bm, (hx, 1.00, 1.31), (0.20, 0.10, 0.16), (-0.10, 0.0, 0.0))

    # Cabin Floor / Parcel Shelf so no bottom light leaks through glass
    add_box_to_bm(bm, (0.0, 0.35, 0.56), (1.46, 2.50, 0.06))
    add_box_to_bm(bm, (0.0, 1.48, 0.98), (1.28, 0.92, 0.05))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return create_mesh_obj("Interior", bm, mats['interior'])


def build_wheels(mats):
    bm_tyre = bmesh.new()
    bm_rim = bmesh.new()
    bm_rim_dark = bmesh.new()
    bm_chrome = bmesh.new()

    wheel_positions = [
        (-0.795, -1.345, 0.365, -1.0),
        (0.795, -1.345, 0.365, 1.0),
        (-0.795, 1.345, 0.365, -1.0),
        (0.795, 1.345, 0.365, 1.0),
    ]

    r_tyre = 0.365
    r_shoulder = 0.352
    r_sidewall = 0.302
    r_rim = 0.229
    w_half = 0.114

    n_rad = 32

    for wx, wy, wz, side in wheel_positions:
        # 1. Tyre Profile Lathe around X axis (touches Z = 0.0 at bottom)
        tyre_prof = [
            (-w_half * 0.82, r_rim),
            (-w_half * 0.98, r_sidewall),
            (-w_half * 0.92, r_shoulder),
            (-w_half * 0.58, r_tyre),
            (-w_half * 0.20, r_tyre - 0.004),
            (0.0, r_tyre),
            (w_half * 0.20, r_tyre - 0.004),
            (w_half * 0.58, r_tyre),
            (w_half * 0.92, r_shoulder),
            (w_half * 0.98, r_sidewall),
            (w_half * 0.82, r_rim),
        ]

        rings = []
        for k in range(n_rad):
            ang = (k / n_rad) * 2.0 * math.pi
            ca, sa = math.cos(ang), math.sin(ang)
            ring = []
            for dx_local, rad in tyre_prof:
                px = wx + side * dx_local
                py = wy + rad * ca
                pz = wz + rad * sa
                ring.append(bm_tyre.verts.new((px, py, pz)))
            rings.append(ring)

        n_p = len(tyre_prof)
        for k in range(n_rad):
            kn = (k + 1) % n_rad
            for p in range(n_p - 1):
                v1, v2, v3, v4 = rings[k][p], rings[k][p + 1], rings[kn][p + 1], rings[kn][p]
                if side > 0:
                    bm_tyre.faces.new((v1, v2, v3, v4))
                else:
                    bm_tyre.faces.new((v4, v3, v2, v1))

        # 2. Dark Gunmetal Inner Rim Barrel & Back Cap
        barrel_prof = [
            (-w_half * 0.82, r_rim),
            (-w_half * 0.72, r_rim - 0.022),
            (w_half * 0.68, r_rim - 0.022),
            (w_half * 0.82, r_rim),
        ]
        b_rings = []
        for k in range(n_rad):
            ang = (k / n_rad) * 2.0 * math.pi
            ca, sa = math.cos(ang), math.sin(ang)
            r_list = []
            for dx_local, rad in barrel_prof:
                r_list.append(bm_rim_dark.verts.new((wx + side * dx_local, wy + rad * ca, wz + rad * sa)))
            b_rings.append(r_list)
        for k in range(n_rad):
            kn = (k + 1) % n_rad
            for p in range(len(barrel_prof) - 1):
                v1, v2, v3, v4 = b_rings[k][p], b_rings[k][p + 1], b_rings[kn][p + 1], b_rings[kn][p]
                if side > 0:
                    bm_rim_dark.faces.new((v1, v2, v3, v4))
                else:
                    bm_rim_dark.faces.new((v4, v3, v2, v1))

        # 3. 18-Inch Two-Tone Alloy Rim (Outer Machined Flange + Center Hub + 10 Split Y-Spokes)
        flange_prof = [
            (w_half * 0.70, r_rim - 0.022),
            (w_half * 0.84, r_rim - 0.006),
            (w_half * 0.86, r_rim + 0.003),
            (w_half * 0.78, r_rim + 0.003),
        ]
        f_rings = []
        for k in range(n_rad):
            ang = (k / n_rad) * 2.0 * math.pi
            ca, sa = math.cos(ang), math.sin(ang)
            r_list = []
            for dx_local, rad in flange_prof:
                r_list.append(bm_rim.verts.new((wx + side * dx_local, wy + rad * ca, wz + rad * sa)))
            f_rings.append(r_list)
        for k in range(n_rad):
            kn = (k + 1) % n_rad
            for p in range(len(flange_prof) - 1):
                v1, v2, v3, v4 = f_rings[k][p], f_rings[k][p + 1], f_rings[kn][p + 1], f_rings[kn][p]
                if side > 0:
                    bm_rim.faces.new((v1, v2, v3, v4))
                else:
                    bm_rim.faces.new((v4, v3, v2, v1))

        # Center Hub Cylinder
        r_hub = 0.068
        hub_f, hub_b = [], []
        for k in range(15):
            ang = (k / 15.0) * 2.0 * math.pi
            ca, sa = math.cos(ang), math.sin(ang)
            hub_f.append(bm_rim.verts.new((wx + side * (w_half * 0.74), wy + r_hub * ca, wz + r_hub * sa)))
            hub_b.append(bm_rim.verts.new((wx + side * (w_half * 0.42), wy + r_hub * ca, wz + r_hub * sa)))
        bm_rim.faces.new(tuple(hub_f if side > 0 else reversed(hub_f)))
        for k in range(15):
            kn = (k + 1) % 15
            bm_rim.faces.new((hub_f[k], hub_b[k], hub_b[kn], hub_f[kn]))

        # 5 Split Y-Spokes (10 angled spokes total) + 5 Chrome Lug Nuts
        for s_idx in range(5):
            base_ang = (s_idx / 5.0) * 2.0 * math.pi
            # Lug nut
            ln_y = wy + 0.042 * math.cos(base_ang)
            ln_z = wz + 0.042 * math.sin(base_ang)
            add_box_to_bm(bm_chrome, (wx + side * (w_half * 0.75), ln_y, ln_z), (0.018, 0.016, 0.016), (base_ang, 0.0, 0.0))

            for branch in (-1.0, 1.0):
                a_in = base_ang + branch * 0.08
                a_out = base_ang + branch * 0.24
                w_in = 0.015
                w_out = 0.021
                r_in = 0.062
                r_out = r_rim - 0.016
                x_face_in = wx + side * (w_half * 0.73)
                x_face_out = wx + side * (w_half * 0.83)
                x_back = wx + side * (w_half * 0.56)

                n_in_y, n_in_z = -math.sin(a_in) * w_in, math.cos(a_in) * w_in
                n_out_y, n_out_z = -math.sin(a_out) * w_out, math.cos(a_out) * w_out

                yi, zi = wy + r_in * math.cos(a_in), wz + r_in * math.sin(a_in)
                yo, zo = wy + r_out * math.cos(a_out), wz + r_out * math.sin(a_out)

                vf1 = bm_rim.verts.new((x_face_in, yi - n_in_y, zi - n_in_z))
                vf2 = bm_rim.verts.new((x_face_in, yi + n_in_y, zi + n_in_z))
                vf3 = bm_rim.verts.new((x_face_out, yo + n_out_y, zo + n_out_z))
                vf4 = bm_rim.verts.new((x_face_out, yo - n_out_y, zo - n_out_z))

                vb1 = bm_rim.verts.new((x_back, yi - n_in_y * 1.2, zi - n_in_z * 1.2))
                vb2 = bm_rim.verts.new((x_back, yi + n_in_y * 1.2, zi + n_in_z * 1.2))
                vb3 = bm_rim.verts.new((x_back, yo + n_out_y * 1.2, zo + n_out_z * 1.2))
                vb4 = bm_rim.verts.new((x_back, yo - n_out_y * 1.2, zo - n_out_z * 1.2))

                bm_rim.faces.new((vf1, vf2, vf3, vf4))
                bm_rim.faces.new((vb4, vb3, vb2, vb1))
                bm_rim.faces.new((vf1, vf4, vb4, vb1))
                bm_rim.faces.new((vf3, vf2, vb2, vb3))

        # 4. Brake Disc & Brake Caliper behind the Rim
        r_disc = 0.168
        r_disc_in = 0.072
        x_disc_f = wx + side * (w_half * 0.28)
        x_disc_b = wx + side * (w_half * 0.16)
        df_out, df_in, db_out = [], [], []
        for k in range(20):
            ang = (k / 20.0) * 2.0 * math.pi
            ca, sa = math.cos(ang), math.sin(ang)
            df_out.append(bm_chrome.verts.new((x_disc_f, wy + r_disc * ca, wz + r_disc * sa)))
            df_in.append(bm_chrome.verts.new((x_disc_f, wy + r_disc_in * ca, wz + r_disc_in * sa)))
            db_out.append(bm_chrome.verts.new((x_disc_b, wy + r_disc * ca, wz + r_disc * sa)))
        for k in range(20):
            kn = (k + 1) % 20
            bm_chrome.faces.new((df_in[k], df_out[k], df_out[kn], df_in[kn]))
            bm_chrome.faces.new((df_out[k], db_out[k], db_out[kn], df_out[kn]))

        # Brake Caliper
        cal_y = wy + (-0.125 if wy > 0 else 0.125)
        add_box_to_bm(bm_rim_dark, (wx + side * (w_half * 0.24), cal_y, wz + 0.055), (0.065, 0.085, 0.145), (0.35, 0.0, 0.0))

    bmesh.ops.recalc_face_normals(bm_tyre, faces=bm_tyre.faces)
    bmesh.ops.recalc_face_normals(bm_rim, faces=bm_rim.faces)
    bmesh.ops.recalc_face_normals(bm_rim_dark, faces=bm_rim_dark.faces)
    bmesh.ops.recalc_face_normals(bm_chrome, faces=bm_chrome.faces)

    return [
        create_mesh_obj("Wheels_Tyre", bm_tyre, mats['tyre']),
        create_mesh_obj("Wheels_Rim", bm_rim, mats['rim']),
        create_mesh_obj("Wheels_RimDark", bm_rim_dark, mats['rim_dark']),
        create_mesh_obj("Wheels_Brakes", bm_chrome, mats['chrome']),
    ]


def build_underbody_plate(mats):
    bm = bmesh.new()
    add_box_to_bm(bm, (0.0, 0.0, 0.23), (1.42, 3.60, 0.03))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return create_mesh_obj("Underbody", bm, mats['plastic'])


def join_and_unwrap(objs, target_name="CarSuv"):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()

    car_obj = bpy.context.view_layer.objects.active
    car_obj.name = target_name
    car_obj.data.name = target_name

    # Ensure origin is at (0, 0, 0) (bottom centre between the wheels, tyres touch Z=0)
    car_obj.location = (0.0, 0.0, 0.0)
    car_obj.rotation_euler = (0.0, 0.0, 0.0)
    car_obj.scale = (1.0, 1.0, 1.0)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # UV Unwrap
    if not car_obj.data.uv_layers:
        car_obj.data.uv_layers.new(name="UVMap")
    car_obj.data.uv_layers.active_index = 0

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.01)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')

    return car_obj


def bake_textures_and_replace_material(car_obj, out_dir, name="CarSuv"):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 16
    if hasattr(scene.cycles, "use_adaptive_sampling"):
        scene.cycles.use_adaptive_sampling = True

    img_albedo = bpy.data.images.new(f"{name}_albedo", width=2048, height=2048, alpha=False)
    img_albedo.colorspace_settings.name = 'sRGB'

    img_normal = bpy.data.images.new(f"{name}_normal", width=2048, height=2048, alpha=False)
    img_normal.colorspace_settings.name = 'Non-Color'

    mat_tex_nodes = []
    saved_metal_trans = []

    for slot in car_obj.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        node_alb = nt.nodes.new('ShaderNodeTexImage')
        node_alb.name = "Bake_Albedo_Node"
        node_alb.image = img_albedo

        node_nrm = nt.nodes.new('ShaderNodeTexImage')
        node_nrm.name = "Bake_Normal_Node"
        node_nrm.image = img_normal

        mat_tex_nodes.append((nt, node_alb, node_nrm))

        for n in nt.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                m_sock = get_bsdf_input(n, 'Metallic')
                t_sock = get_bsdf_input(n, ('Transmission Weight', 'Transmission'))
                m_val = m_sock.default_value if m_sock else 0.0
                t_val = t_sock.default_value if t_sock else 0.0
                saved_metal_trans.append((m_sock, m_val, t_sock, t_val))

    bpy.ops.object.select_all(action='DESELECT')
    car_obj.select_set(True)
    bpy.context.view_layer.objects.active = car_obj

    # Temporarily zero Metallic & Transmission during DIFFUSE (COLOR) bake so metals/glass bake true Base Color
    for m_sock, _, t_sock, _ in saved_metal_trans:
        if m_sock is not None:
            m_sock.default_value = 0.0
        if t_sock is not None:
            t_sock.default_value = 0.0

    # 1. Bake DIFFUSE (COLOR) into <Name>_albedo
    for nt, node_alb, _ in mat_tex_nodes:
        for n in nt.nodes:
            n.select = False
        node_alb.select = True
        nt.nodes.active = node_alb

    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    scene.render.bake.margin = 8
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=8)

    # Restore Metallic & Transmission values
    for m_sock, m_val, t_sock, t_val in saved_metal_trans:
        if m_sock is not None:
            m_sock.default_value = m_val
        if t_sock is not None:
            t_sock.default_value = t_val

    albedo_path = os.path.join(out_dir, f"{name}_albedo.png")
    img_albedo.filepath_raw = albedo_path
    img_albedo.file_format = 'PNG'
    img_albedo.save()

    # 2. Bake NORMAL (TANGENT) into <Name>_normal
    for nt, _, node_nrm in mat_tex_nodes:
        for n in nt.nodes:
            n.select = False
        node_nrm.select = True
        nt.nodes.active = node_nrm

    scene.render.bake.normal_space = 'TANGENT'
    scene.render.bake.margin = 8
    bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=8)

    normal_path = os.path.join(out_dir, f"{name}_normal.png")
    img_normal.filepath_raw = normal_path
    img_normal.file_format = 'PNG'
    img_normal.save()

    # 3. Replace all slots with ONE material "<Name>_Mat"
    final_mat = bpy.data.materials.new(name=f"{name}_Mat")
    final_mat.use_nodes = True
    fnt = final_mat.node_tree
    fnt.nodes.clear()

    out_node = fnt.nodes.new('ShaderNodeOutputMaterial')
    bsdf_node = fnt.nodes.new('ShaderNodeBsdfPrincipled')
    set_bsdf_input(bsdf_node, 'Roughness', 0.35)
    fnt.links.new(bsdf_node.outputs['BSDF'], out_node.inputs['Surface'])

    tex_alb = fnt.nodes.new('ShaderNodeTexImage')
    tex_alb.image = img_albedo
    fnt.links.new(tex_alb.outputs['Color'], bsdf_node.inputs['Base Color'])

    tex_nrm = fnt.nodes.new('ShaderNodeTexImage')
    tex_nrm.image = img_normal
    img_normal.colorspace_settings.name = 'Non-Color'

    nrm_map = fnt.nodes.new('ShaderNodeNormalMap')
    fnt.links.new(tex_nrm.outputs['Color'], nrm_map.inputs['Color'])
    fnt.links.new(nrm_map.outputs['Normal'], bsdf_node.inputs['Normal'])

    car_obj.data.materials.clear()
    car_obj.data.materials.append(final_mat)
    for poly in car_obj.data.polygons:
        poly.material_index = 0


def parse_output_paths():
    argv = sys.argv
    if "--" in argv:
        idx = argv.index("--")
        out_arg = argv[idx + 1] if idx + 1 < len(argv) else "CarSuv.fbx"
    else:
        out_arg = "CarSuv.fbx"

    out_arg = os.path.abspath(out_arg)
    if out_arg.lower().endswith(".fbx"):
        fbx_path = out_arg
        base_path = os.path.splitext(out_arg)[0]
    elif out_arg.lower().endswith(".png"):
        base_path = os.path.splitext(out_arg)[0]
        fbx_path = base_path + ".fbx"
    else:
        base_path = out_arg
        fbx_path = base_path + ".fbx"

    png_path = base_path + ".png"
    out_dir = os.path.dirname(fbx_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    else:
        out_dir = os.getcwd()
    return fbx_path, png_path, out_dir


def export_and_render_preview(car_obj, fbx_path, png_path):
    bpy.ops.object.select_all(action='DESELECT')
    car_obj.select_set(True)
    bpy.context.view_layer.objects.active = car_obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

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
    engine_keys = list(scene.render.bl_rna.properties['engine'].enum_items.keys())
    eevee_engines = [k for k in engine_keys if 'EEVEE' in k]
    if eevee_engines:
        scene.render.engine = eevee_engines[0]

    # Grey sky world strength 0.6
    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    wnt = world.node_tree
    bg_node = None
    for n in wnt.nodes:
        if n.type == 'BACKGROUND':
            bg_node = n
            break
    if bg_node is None:
        bg_node = wnt.nodes.new('ShaderNodeBackground')
        w_out = wnt.nodes.new('ShaderNodeOutputWorld')
        wnt.links.new(bg_node.outputs['Background'], w_out.inputs['Surface'])
    bg_node.inputs['Color'].default_value = (0.55, 0.57, 0.60, 1.0)
    bg_node.inputs['Strength'].default_value = 0.6

    # Sun strength 3 from front-left-above (car front is -Y, left is -X, above is +Z)
    sun_data = bpy.data.lights.new(name="SunLight", type='SUN')
    sun_data.energy = 3.0
    sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
    bpy.context.collection.objects.link(sun_obj)
    sun_obj.location = (-5.5, -6.5, 7.5)
    sun_dir = Vector((0.0, 0.0, 0.5)) - sun_obj.location
    sun_obj.rotation_euler = sun_dir.to_track_quat('-Z', 'Y').to_euler()

    # Camera at 1.5 m height in a front 3/4 view framing the whole car
    cam_data = bpy.data.cameras.new(name="PreviewCam")
    cam_data.lens = 45.0
    cam_obj = bpy.data.objects.new(name="PreviewCam", object_data=cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = (-4.4, -5.2, 1.5)
    look_target = Vector((0.0, 0.05, 0.72))
    cam_dir = look_target - cam_obj.location
    cam_obj.rotation_euler = cam_dir.to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = png_path
    bpy.ops.render.render(write_still=True)

    tris = sum(len(p.vertices) - 2 for p in car_obj.data.polygons)
    print("TRIS", tris)


def main():
    clear_scene()
    fbx_path, png_path, out_dir = parse_output_paths()
    mats = create_materials()

    objs = []
    objs.append(build_suv_body(mats))
    objs.append(build_windows(mats))
    objs.extend(build_pillars(mats))
    objs.extend(build_bumpers_and_grille(mats))
    objs.append(build_cladding(mats))
    objs.extend(build_lights(mats))
    objs.extend(build_details(mats))
    objs.append(build_interior(mats))
    objs.extend(build_wheels(mats))
    objs.append(build_underbody_plate(mats))

    car_obj = join_and_unwrap(objs, target_name="CarSuv")
    bake_textures_and_replace_material(car_obj, out_dir, name="CarSuv")
    export_and_render_preview(car_obj, fbx_path, png_path)


if __name__ == "__main__":
    main()

