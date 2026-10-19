import bpy
from mathutils import Euler
import bmesh
from mathutils import Vector, Matrix
import math
import sys
import os

NAME = "CarVan"

def clear_scene():
    if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for col in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.images,
        bpy.data.lights,
        bpy.data.cameras,
        bpy.data.curves,
    ):
        for block in list(col):
            col.remove(block)

def set_socket(node, names, val):
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = val
            return

def add_math(tree, op, a, b=None, clamp=False):
    n = tree.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    if isinstance(a, (int, float)):
        n.inputs[0].default_value = float(a)
    else:
        tree.links.new(a, n.inputs[0])
    if b is not None and len(n.inputs) > 1:
        if isinstance(b, (int, float)):
            n.inputs[1].default_value = float(b)
        else:
            tree.links.new(b, n.inputs[1])
    return n.outputs[0]

def add_mix_color(tree, fac, col_a, col_b, blend_type='MIX'):
    m = tree.nodes.new("ShaderNodeMix")
    m.data_type = 'RGBA'
    m.blend_type = blend_type
    fac_in = [s for s in m.inputs if s.type == 'VALUE'][0]
    rgba_ins = [s for s in m.inputs if s.type == 'RGBA']
    rgba_out = [s for s in m.outputs if s.type == 'RGBA'][0]
    if isinstance(fac, (int, float)):
        fac_in.default_value = float(fac)
    else:
        tree.links.new(fac, fac_in)
    if isinstance(col_a, (tuple, list)):
        rgba_ins[0].default_value = col_a
    else:
        tree.links.new(col_a, rgba_ins[0])
    if isinstance(col_b, (tuple, list)):
        rgba_ins[1].default_value = col_b
    else:
        tree.links.new(col_b, rgba_ins[1])
    return rgba_out

def make_base_material(name):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat, tree, bsdf

def build_road_dirt_mask(tree, obj_vec, sep_xyz):
    z = sep_xyz.outputs["Z"]
    noise1 = tree.nodes.new("ShaderNodeTexNoise")
    noise1.inputs["Scale"].default_value = 5.5
    noise1.inputs["Detail"].default_value = 6.0
    noise1.inputs["Roughness"].default_value = 0.65
    tree.links.new(obj_vec, noise1.inputs["Vector"])

    noise2 = tree.nodes.new("ShaderNodeTexNoise")
    noise2.inputs["Scale"].default_value = 28.0
    noise2.inputs["Detail"].default_value = 4.0
    tree.links.new(obj_vec, noise2.inputs["Vector"])

    n_Shift = add_math(tree, 'MULTIPLY', noise1.outputs["Fac"], 0.16)
    z_pert = add_math(tree, 'SUBTRACT', z, n_Shift)
    inv_z = add_math(tree, 'SUBTRACT', 0.27, z_pert)
    grad = add_math(tree, 'MULTIPLY', inv_z, 4.2, clamp=True)
    fine = add_math(tree, 'MULTIPLY', grad, noise2.outputs["Fac"], clamp=True)
    mask = add_math(tree, 'MULTIPLY', add_math(tree, 'ADD', grad, fine), 0.55, clamp=True)
    return mask, noise2.outputs["Fac"]

def line_mask(tree, coord_sock, center, half_width):
    diff = add_math(tree, 'SUBTRACT', coord_sock, center)
    adiff = add_math(tree, 'ABSOLUTE', diff)
    inv = add_math(tree, 'SUBTRACT', half_width, adiff)
    return add_math(tree, 'MULTIPLY', inv, 1.0 / max(half_width, 1e-4), clamp=True)

def range_mask(tree, coord_sock, lo, hi):
    mid = 0.5 * (lo + hi)
    half = 0.5 * (hi - lo)
    diff = add_math(tree, 'ABSOLUTE', add_math(tree, 'SUBTRACT', coord_sock, mid))
    sub = add_math(tree, 'SUBTRACT', half, diff)
    return add_math(tree, 'MULTIPLY', sub, 80.0, clamp=True)

def create_procedural_materials():
    mats = {}

    # 1. White Paint (Non-metallic Ford Transit Frozen White + panel gaps + lower 25cm road dirt)
    mat_paint, tree, bsdf = make_base_material("Mat_Paint")
    set_socket(bsdf, ["Metallic"], 0.0)
    set_socket(bsdf, ["Roughness"], 0.16)
    set_socket(bsdf, ["Coat Weight", "Clearcoat"], 1.0)
    set_socket(bsdf, ["Coat Roughness", "Clearcoat Roughness"], 0.04)

    tc = tree.nodes.new("ShaderNodeTexCoord")
    sep = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    x = sep.outputs["X"]
    y = sep.outputs["Y"]
    z = sep.outputs["Z"]
    ax = add_math(tree, 'ABSOLUTE', x)

    # Subtle vertical ambient shading on white paint
    z_norm = add_math(tree, 'MULTIPLY', z, 0.38, clamp=True)
    paint_base = add_mix_color(tree, z_norm, (0.84, 0.85, 0.87, 1.0), (0.94, 0.95, 0.96, 1.0))

    # Panel gap masks in Object space
    w_seam = 0.011
    side_zone = range_mask(tree, ax, 0.78, 1.08)
    door_z = range_mask(tree, z, 0.24, 2.24)

    # Front door front seam (Y = -1.70), B-pillar seam (Y = -0.46), Sliding door rear seam (Y = 1.12)
    s_fd_front = add_math(tree, 'MULTIPLY', line_mask(tree, y, -1.70, w_seam), range_mask(tree, z, 0.25, 1.24))
    s_b_pillar = add_math(tree, 'MULTIPLY', line_mask(tree, y, -0.46, w_seam), door_z)
    s_slide_rear = add_math(tree, 'MULTIPLY', line_mask(tree, y, 1.12, w_seam), door_z)
    s_slide_top = add_math(tree, 'MULTIPLY', line_mask(tree, z, 2.24, w_seam), range_mask(tree, y, -0.46, 1.12))
    side_seams = add_math(tree, 'MAXIMUM', add_math(tree, 'MAXIMUM', s_fd_front, s_b_pillar),
                          add_math(tree, 'MAXIMUM', s_slide_rear, s_slide_top))
    side_seams = add_math(tree, 'MULTIPLY', side_seams, side_zone)

    # Hood / bonnet seams
    hood_y = range_mask(tree, y, -2.62, -1.86)
    hood_z = range_mask(tree, z, 0.82, 1.25)
    s_hood_side = add_math(tree, 'MULTIPLY', line_mask(tree, ax, 0.76, w_seam), hood_y)
    s_hood_back = add_math(tree, 'MULTIPLY', line_mask(tree, y, -1.88, w_seam), range_mask(tree, ax, 0.0, 0.78))
    hood_seams = add_math(tree, 'MULTIPLY', add_math(tree, 'MAXIMUM', s_hood_side, s_hood_back), hood_z)

    # Twin rear doors center vertical seam (X = 0) and outer vertical seams (abs(X) = 0.87)
    rear_y = range_mask(tree, y, 2.55, 2.80)
    rear_z = range_mask(tree, z, 0.48, 2.46)
    s_rear_mid = add_math(tree, 'MULTIPLY', line_mask(tree, ax, 0.0, 0.012), rear_y)
    s_rear_out = add_math(tree, 'MULTIPLY', line_mask(tree, ax, 0.87, w_seam), rear_y)
    s_rear_top = add_math(tree, 'MULTIPLY', line_mask(tree, z, 2.44, w_seam),
                          add_math(tree, 'MULTIPLY', rear_y, range_mask(tree, ax, 0.0, 0.88)))
    rear_seams = add_math(tree, 'MULTIPLY',
                          add_math(tree, 'MAXIMUM', add_math(tree, 'MAXIMUM', s_rear_mid, s_rear_out), s_rear_top),
                          rear_z)

    all_seams = add_math(tree, 'MAXIMUM', add_math(tree, 'MAXIMUM', side_seams, hood_seams), rear_seams)

    # Road dirt on lower 25 cm
    dirt_mask, dirt_grain = build_road_dirt_mask(tree, tc.outputs["Object"], sep)
    paint_with_dirt = add_mix_color(tree, dirt_mask, paint_base, (0.32, 0.29, 0.25, 1.0))
    paint_final = add_mix_color(tree, all_seams, paint_with_dirt, (0.06, 0.065, 0.07, 1.0))
    tree.links.new(paint_final, bsdf.inputs["Base Color"])

    # Combine seam groove + dirt bump into Normal
    bump_seam = tree.nodes.new("ShaderNodeBump")
    bump_seam.invert = True
    bump_seam.inputs["Strength"].default_value = 0.9
    bump_seam.inputs["Distance"].default_value = 0.012
    tree.links.new(all_seams, bump_seam.inputs["Height"])

    bump_dirt = tree.nodes.new("ShaderNodeBump")
    bump_dirt.inputs["Strength"].default_value = 0.22
    bump_dirt.inputs["Distance"].default_value = 0.003
    dirt_h = add_math(tree, 'MULTIPLY', dirt_mask, dirt_grain)
    tree.links.new(dirt_h, bump_dirt.inputs["Height"])
    tree.links.new(bump_seam.outputs["Normal"], bump_dirt.inputs["Normal"])
    tree.links.new(bump_dirt.outputs["Normal"], bsdf.inputs["Normal"])
    mats["Paint"] = mat_paint

    # 2. Black Plastic Trim (Bumpers, Mirror Housings, Lower Cladding, Door Handles, Wipers)
    mat_plastic, tree, bsdf = make_base_material("Mat_Plastic")
    set_socket(bsdf, ["Metallic"], 0.0)
    set_socket(bsdf, ["Roughness"], 0.62)
    tc = tree.nodes.new("ShaderNodeTexCoord")
    sep = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(tc.outputs["Object"], sep.inputs["Vector"])

    p_noise = tree.nodes.new("ShaderNodeTexNoise")
    p_noise.inputs["Scale"].default_value = 160.0
    p_noise.inputs["Detail"].default_value = 5.0
    tree.links.new(tc.outputs["Object"], p_noise.inputs["Vector"])

    p_col = add_mix_color(tree, p_noise.outputs["Fac"], (0.065, 0.068, 0.072, 1.0), (0.105, 0.11, 0.118, 1.0))
    dirt_mask, dirt_grain = build_road_dirt_mask(tree, tc.outputs["Object"], sep)
    p_dirty = add_mix_color(tree, dirt_mask, p_col, (0.26, 0.23, 0.19, 1.0))
    tree.links.new(p_dirty, bsdf.inputs["Base Color"])

    p_bump = tree.nodes.new("ShaderNodeBump")
    p_bump.inputs["Strength"].default_value = 0.30
    p_bump.inputs["Distance"].default_value = 0.0025
    tree.links.new(p_noise.outputs["Fac"], p_bump.inputs["Height"])
    tree.links.new(p_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats["Plastic"] = mat_plastic

    # 3. Grille Mesh Material (Hexagonal grille & lower intake louvers)
    mat_grille, tree, bsdf = make_base_material("Mat_Grille")
    set_socket(bsdf, ["Metallic"], 0.05)
    set_socket(bsdf, ["Roughness"], 0.45)
    tc = tree.nodes.new("ShaderNodeTexCoord")
    wave = tree.nodes.new("ShaderNodeTexWave")
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Z'
    wave.inputs["Scale"].default_value = 28.0
    tree.links.new(tc.outputs["Object"], wave.inputs["Vector"])

    vor = tree.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 65.0
    tree.links.new(tc.outputs["Object"], vor.inputs["Vector"])

    comb = add_math(tree, 'MULTIPLY', wave.outputs["Fac"], vor.outputs["Distance"], clamp=True)
    g_col = add_mix_color(tree, comb, (0.025, 0.028, 0.03, 1.0), (0.14, 0.15, 0.16, 1.0))
    tree.links.new(g_col, bsdf.inputs["Base Color"])

    g_bump = tree.nodes.new("ShaderNodeBump")
    g_bump.inputs["Strength"].default_value = 0.85
    g_bump.inputs["Distance"].default_value = 0.008
    tree.links.new(comb, g_bump.inputs["Height"])
    tree.links.new(g_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats["Grille"] = mat_grille

    # 4. Dark Tinted Glass with Slight Interior Visibility (Seats & Dashboard Silhouettes)
    mat_glass, tree, bsdf = make_base_material("Mat_Glass")
    set_socket(bsdf, ["Metallic"], 0.0)
    set_socket(bsdf, ["Roughness"], 0.06)
    set_socket(bsdf, ["Coat Weight", "Clearcoat"], 1.0)
    set_socket(bsdf, ["Coat Roughness", "Clearcoat Roughness"], 0.02)

    tc = tree.nodes.new("ShaderNodeTexCoord")
    sep = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    gx = sep.outputs["X"]
    gy = sep.outputs["Y"]
    gz = sep.outputs["Z"]
    gax = add_math(tree, 'ABSOLUTE', gx)

    # Seat headrest & backrest silhouette at X around +-0.44, Z in [1.22, 1.72]
    seat_x = range_mask(tree, gax, 0.22, 0.68)
    seat_z = range_mask(tree, gz, 1.22, 1.72)
    seat_sil = add_math(tree, 'MULTIPLY', seat_x, seat_z)

    # Dashboard silhouette at lower windscreen Z in [1.14, 1.38]
    dash_sil = range_mask(tree, gz, 1.12, 1.36)

    # Sky reflection gradient near top of glass
    sky_grad = add_math(tree, 'MULTIPLY', add_math(tree, 'SUBTRACT', gz, 1.15), 1.05, clamp=True)
    glass_sky = add_mix_color(tree, sky_grad, (0.07, 0.09, 0.11, 1.0), (0.18, 0.23, 0.28, 1.0))
    glass_seat = add_mix_color(tree, add_math(tree, 'MULTIPLY', seat_sil, 0.65), glass_sky, (0.14, 0.13, 0.12, 1.0))
    glass_final = add_mix_color(tree, add_math(tree, 'MULTIPLY', dash_sil, 0.55), glass_seat, (0.04, 0.045, 0.05, 1.0))
    tree.links.new(glass_final, bsdf.inputs["Base Color"])
    mats["Glass"] = mat_glass

    # 5. Rubber Tyres with Sidewall Lettering Hint (Noise) & Tread Normal
    mat_tyre, tree, bsdf = make_base_material("Mat_Tyre")
    set_socket(bsdf, ["Metallic"], 0.0)
    set_socket(bsdf, ["Roughness"], 0.80)
    tc = tree.nodes.new("ShaderNodeTexCoord")
    sep = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(tc.outputs["Object"], sep.inputs["Vector"])

    # Sidewall noise & tread wave
    t_noise = tree.nodes.new("ShaderNodeTexNoise")
    t_noise.inputs["Scale"].default_value = 52.0
    t_noise.inputs["Detail"].default_value = 6.0
    tree.links.new(tc.outputs["Object"], t_noise.inputs["Vector"])

    t_wave = tree.nodes.new("ShaderNodeTexWave")
    t_wave.inputs["Scale"].default_value = 22.0
    t_wave.inputs["Distortion"].default_value = 1.5
    tree.links.new(tc.outputs["Object"], t_wave.inputs["Vector"])

    # Height band around tyre sidewall (Z around 0.08..0.66)
    z_band = range_mask(tree, sep.outputs["Z"], 0.07, 0.68)
    letter_hint = add_math(tree, 'MULTIPLY', z_band, t_noise.outputs["Fac"], clamp=True)
    tyre_col = add_mix_color(tree, letter_hint, (0.045, 0.046, 0.05, 1.0), (0.12, 0.12, 0.125, 1.0))
    tree.links.new(tyre_col, bsdf.inputs["Base Color"])

    t_bump = tree.nodes.new("ShaderNodeBump")
    t_bump.inputs["Strength"].default_value = 0.55
    t_bump.inputs["Distance"].default_value = 0.005
    b_val = add_math(tree, 'ADD', add_math(tree, 'MULTIPLY', letter_hint, 0.6),
                     add_math(tree, 'MULTIPLY', t_wave.outputs["Fac"], 0.4))
    tree.links.new(b_val, t_bump.inputs["Height"])
    tree.links.new(t_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats["Tyre"] = mat_tyre

    # 6. Steel Wheel / Multi-Spoke Silver Hub Cap Rim
    mat_rim, tree, bsdf = make_base_material("Mat_Rim")
    set_socket(bsdf, ["Metallic"], 0.05)
    set_socket(bsdf, ["Roughness"], 0.25)
    set_socket(bsdf, ["Coat Weight", "Clearcoat"], 0.6)
    tc = tree.nodes.new("ShaderNodeTexCoord")
    r_noise = tree.nodes.new("ShaderNodeTexNoise")
    r_noise.inputs["Scale"].default_value = 85.0
    tree.links.new(tc.outputs["Object"], r_noise.inputs["Vector"])
    r_col = add_mix_color(tree, r_noise.outputs["Fac"], (0.64, 0.67, 0.70, 1.0), (0.78, 0.80, 0.83, 1.0))
    tree.links.new(r_col, bsdf.inputs["Base Color"])
    mats["Rim"] = mat_rim

    # 7. Dark Steel Rim Barrel & Brake Disc Behind
    mat_brake, tree, bsdf = make_base_material("Mat_BrakeDisc")
    set_socket(bsdf, ["Metallic"], 0.05)
    set_socket(bsdf, ["Roughness"], 0.42)
    tc = tree.nodes.new("ShaderNodeTexCoord")
    b_wave = tree.nodes.new("ShaderNodeTexWave")
    b_wave.wave_type = 'RINGS'
    b_wave.inputs["Scale"].default_value = 40.0
    tree.links.new(tc.outputs["Object"], b_wave.inputs["Vector"])
    b_col = add_mix_color(tree, b_wave.outputs["Fac"], (0.28, 0.29, 0.31, 1.0), (0.48, 0.50, 0.52, 1.0))
    tree.links.new(b_col, bsdf.inputs["Base Color"])
    b_bump = tree.nodes.new("ShaderNodeBump")
    b_bump.inputs["Strength"].default_value = 0.35
    b_bump.inputs["Distance"].default_value = 0.003
    tree.links.new(b_wave.outputs["Fac"], b_bump.inputs["Height"])
    tree.links.new(b_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats["BrakeDisc"] = mat_brake

    # 8. Chrome Trim / Reflectors / Mirror Glass
    mat_chrome, tree, bsdf = make_base_material("Mat_Chrome")
    set_socket(bsdf, ["Metallic"], 0.05)
    set_socket(bsdf, ["Roughness"], 0.08)
    set_socket(bsdf, ["Coat Weight", "Clearcoat"], 1.0)
    tc = tree.nodes.new("ShaderNodeTexCoord")
    sep = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(tc.outputs["Normal"], sep.inputs["Vector"])
    c_grad = add_math(tree, 'MULTIPLY', add_math(tree, 'ADD', sep.outputs["Z"], 1.0), 0.5, clamp=True)
    c_col = add_mix_color(tree, c_grad, (0.68, 0.72, 0.76, 1.0), (0.94, 0.96, 0.98, 1.0))
    tree.links.new(c_col, bsdf.inputs["Base Color"])
    mats["Chrome"] = mat_chrome

    # 9. Clear Headlight Lenses (over reflector with projector eye & amber turn strip)
    mat_hl, tree, bsdf = make_base_material("Mat_HeadlightLens")
    set_socket(bsdf, ["Metallic"], 0.0)
    set_socket(bsdf, ["Roughness"], 0.05)
    set_socket(bsdf, ["Coat Weight", "Clearcoat"], 1.0)
    tc = tree.nodes.new("ShaderNodeTexCoord")
    sep = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    hx = add_math(tree, 'ABSOLUTE', sep.outputs["X"])
    hz = sep.outputs["Z"]

    # Projector hotspot around |X|=0.80, Z=0.82
    dx = add_math(tree, 'SUBTRACT', hx, 0.80)
    dz = add_math(tree, 'SUBTRACT', hz, 0.82)
    r2 = add_math(tree, 'ADD', add_math(tree, 'MULTIPLY', dx, dx), add_math(tree, 'MULTIPLY', dz, dz))
    proj = add_math(tree, 'SUBTRACT', 1.0, add_math(tree, 'MULTIPLY', r2, 120.0, clamp=True), clamp=True)

    # Amber outer corner indicator around |X| > 0.90 or Z > 0.91
    amber_mask = range_mask(tree, hx, 0.91, 1.02)

    h_wave = tree.nodes.new("ShaderNodeTexWave")
    h_wave.bands_direction = 'X'
    h_wave.inputs["Scale"].default_value = 55.0
    tree.links.new(tc.outputs["Object"], h_wave.inputs["Vector"])

    hl_base = add_mix_color(tree, h_wave.outputs["Fac"], (0.66, 0.72, 0.80, 1.0), (0.88, 0.92, 0.97, 1.0))
    hl_proj = add_mix_color(tree, proj, hl_base, (0.98, 0.99, 1.0, 1.0))
    hl_final = add_mix_color(tree, amber_mask, hl_proj, (0.92, 0.50, 0.06, 1.0))
    tree.links.new(hl_final, bsdf.inputs["Base Color"])

    h_bump = tree.nodes.new("ShaderNodeBump")
    h_bump.inputs["Strength"].default_value = 0.35
    h_bump.inputs["Distance"].default_value = 0.003
    tree.links.new(h_wave.outputs["Fac"], h_bump.inputs["Height"])
    tree.links.new(h_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats["HeadlightLens"] = mat_hl

    # 10. Red Taillight Lenses (Vertical Ford Transit taillights with reverse & amber chambers)
    mat_tl, tree, bsdf = make_base_material("Mat_TaillightLens")
    set_socket(bsdf, ["Metallic"], 0.0)
    set_socket(bsdf, ["Roughness"], 0.08)
    set_socket(bsdf, ["Coat Weight", "Clearcoat"], 1.0)
    tc = tree.nodes.new("ShaderNodeTexCoord")
    sep = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    tz = sep.outputs["Z"]

    rev_mask = range_mask(tree, tz, 0.90, 1.06)
    amb_mask = range_mask(tree, tz, 1.06, 1.20)

    t_wave = tree.nodes.new("ShaderNodeTexWave")
    t_wave.bands_direction = 'Z'
    t_wave.inputs["Scale"].default_value = 60.0
    tree.links.new(tc.outputs["Object"], t_wave.inputs["Vector"])

    tl_red = add_mix_color(tree, t_wave.outputs["Fac"], (0.58, 0.025, 0.03, 1.0), (0.88, 0.09, 0.07, 1.0))
    tl_amb = add_mix_color(tree, amb_mask, tl_red, (0.90, 0.42, 0.04, 1.0))
    tl_final = add_mix_color(tree, rev_mask, tl_amb, (0.84, 0.86, 0.89, 1.0))
    tree.links.new(tl_final, bsdf.inputs["Base Color"])

    tl_bump = tree.nodes.new("ShaderNodeBump")
    tl_bump.inputs["Strength"].default_value = 0.45
    tl_bump.inputs["Distance"].default_value = 0.003
    tree.links.new(t_wave.outputs["Fac"], tl_bump.inputs["Height"])
    tree.links.new(tl_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats["TaillightLens"] = mat_tl

    # 11. White Number Plate with Dark Characters & Blue Euro Strip
    mat_plate, tree, bsdf = make_base_material("Mat_Plate")
    set_socket(bsdf, ["Metallic"], 0.0)
    set_socket(bsdf, ["Roughness"], 0.22)
    tc = tree.nodes.new("ShaderNodeTexCoord")
    sep = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    px = sep.outputs["X"]
    pz = sep.outputs["Z"]

    # Front plate is centered at X=0, Z=0.38; Rear plate is centered at X=-0.38, Z=0.76
    # Shift X and Z for rear vs front using Y sign
    is_rear = range_mask(tree, sep.outputs["Y"], 0.0, 3.0)
    local_x = add_math(tree, 'ADD', px, add_math(tree, 'MULTIPLY', is_rear, 0.38))
    local_z = add_math(tree, 'SUBTRACT', pz, add_mix_val := add_math(tree, 'ADD', 0.38, add_math(tree, 'MULTIPLY', is_rear, 0.38)))

    # Left blue band at local_x in [-0.25, -0.20]
    blue_band = range_mask(tree, local_x, -0.255, -0.198)

    # Dark characters in local_x in [-0.16, 0.22], local_z in [-0.032, 0.032]
    char_box_x = range_mask(tree, local_x, -0.165, 0.225)
    char_box_z = range_mask(tree, local_z, -0.032, 0.032)
    in_char_zone = add_math(tree, 'MULTIPLY', char_box_x, char_box_z)

    # Character vertical strokes + horizontal bars via wave functions
    w_vert = tree.nodes.new("ShaderNodeTexWave")
    w_vert.bands_direction = 'X'
    w_vert.inputs["Scale"].default_value = 34.0
    tree.links.new(tc.outputs["Object"], w_vert.inputs["Vector"])

    w_horz = tree.nodes.new("ShaderNodeTexWave")
    w_horz.bands_direction = 'Z'
    w_horz.inputs["Scale"].default_value = 46.0
    tree.links.new(tc.outputs["Object"], w_horz.inputs["Vector"])

    # Gap in the middle of the registration text
    not_space = add_math(tree, 'SUBTRACT', 1.0, range_mask(tree, local_x, -0.03, 0.02))
    stroke_raw = add_math(tree, 'MAXIMUM',
                          add_math(tree, 'GREATER_THAN', w_vert.outputs["Fac"], 0.58),
                          add_math(tree, 'MULTIPLY',
                                   add_math(tree, 'GREATER_THAN', w_horz.outputs["Fac"], 0.66),
                                   add_math(tree, 'GREATER_THAN', w_vert.outputs["Fac"], 0.32)))
    char_mask = add_math(tree, 'MULTIPLY', add_math(tree, 'MULTIPLY', in_char_zone, not_space), stroke_raw, clamp=True)

    plate_bg = add_mix_color(tree, blue_band, (0.93, 0.94, 0.95, 1.0), (0.04, 0.19, 0.58, 1.0))
    plate_col = add_mix_color(tree, char_mask, plate_bg, (0.06, 0.065, 0.07, 1.0))
    tree.links.new(plate_col, bsdf.inputs["Base Color"])

    pl_bump = tree.nodes.new("ShaderNodeBump")
    pl_bump.inputs["Strength"].default_value = 0.35
    pl_bump.inputs["Distance"].default_value = 0.002
    tree.links.new(char_mask, pl_bump.inputs["Height"])
    tree.links.new(pl_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats["Plate"] = mat_plate

    return mats

def apply_smooth_and_sharp(mesh, angle_deg=38.0):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    for f in bm.faces:
        f.smooth = True
    thresh = math.radians(angle_deg)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            if e.calc_face_angle(0.0) > thresh:
                e.smooth = False
        else:
            e.smooth = False
    bm.to_mesh(mesh)
    bm.free()

def create_mesh_obj(name, bm, mat=None, subsurf_levels=0, sharp_angle=38.0):
    mesh = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    if mat is not None:
        mesh.materials.append(mat)
    if subsurf_levels > 0:
        mod = obj.modifiers.new("Subsurf", 'SUBSURF')
        mod.levels = subsurf_levels
        mod.render_levels = subsurf_levels
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    apply_smooth_and_sharp(obj.data, sharp_angle)
    return obj

def eval_van_station(y):
    # Returns (z_sill, z_top, x_scale, y_Sweep, arch_flare, in_cab_win, in_cargo_panel)
    # Front and rear wheel arch centers: Y = -1.70 and Y = +1.60, wheelbase = 3.30m
    z_sill = 0.24
    if y < -2.05:
        z_sill = 0.24 + 0.06 * (( -2.05 - y ) / 0.70) ** 1.4
    elif y > 2.02:
        z_sill = 0.26 + 0.05 * (( y - 2.02 ) / 0.72) ** 1.3

    arch_flare = 0.0
    for y_w in (-1.70, 1.60):
        dy = abs(y - y_w)
        r_cut = 0.445
        if dy < r_cut:
            rise = math.sqrt(max(0.0, r_cut * r_cut - dy * dy))
            z_sill = max(z_sill, 0.355 + rise * 0.96)
        if dy < r_cut + 0.09:
            t_fl = max(0.0, 1.0 - (dy / (r_cut + 0.09)) ** 2)
            arch_flare = max(arch_flare, 0.020 * t_fl)

    # Upper silhouette of Ford Transit L2H2 (total height 2.55m)
    if y <= -2.62:
        t = max(0.0, min(1.0, (y - (-2.74)) / 0.12))
        z_top = 0.56 + 0.35 * (t ** 0.75)
    elif y <= -1.88:
        t = (y - (-2.62)) / 0.74
        z_top = 0.91 + 0.28 * (t ** 0.85)
    elif y <= -1.80:
        z_top = 1.19
    elif y <= -1.00:
        t = (y - (-1.80)) / 0.80
        z_top = 1.19 + 0.93 * (t ** 0.92)
    elif y <= -0.42:
        t = (y - (-1.00)) / 0.58
        s = 1.0 - (1.0 - t) ** 2.2
        z_top = 2.12 + 0.415 * s
    elif y <= 2.42:
        t = (y - (-0.42)) / 2.84
        z_top = 2.535 + 0.015 * math.sin(t * math.pi)
    else:
        t = max(0.0, min(1.0, (y - 2.42) / 0.32))
        z_top = 2.535 - 0.075 * (t ** 1.8)

    # Plan view narrowing and corner sweep
    x_scale = 1.0
    y_sweep = 0.0
    if y < -1.85:
        t = max(0.0, min(1.0, (-1.85 - y) / 0.89))
        x_scale = 1.0 - 0.145 * (t ** 1.65)
        y_sweep = 0.135 * (t ** 1.5)
    elif y > 2.30:
        t = max(0.0, min(1.0, (y - 2.30) / 0.44))
        x_scale = 1.0 - 0.045 * (t ** 1.6)
        y_sweep = -0.045 * (t ** 1.5)

    in_cab_win = (-1.68 <= y <= -0.52)
    in_cargo_panel = (-0.34 <= y <= 1.02) or (1.22 <= y <= 2.48)
    return z_sill, z_top, x_scale, y_sweep, arch_flare, in_cab_win, in_cargo_panel

def build_van_body(mats):
    bm = bmesh.new()

    y_stations = [
        -2.74, -2.68, -2.62, -2.46, -2.28,
        -2.14, -2.02, -1.90, -1.80, -1.70, -1.60, -1.48, -1.34, -1.22,
        -1.08, -0.96, -0.74, -0.52, -0.44, -0.34,
        0.05, 0.50, 1.02, 1.12, 1.22,
        1.36, 1.48, 1.60, 1.72, 1.84, 1.98, 2.12,
        2.32, 2.48, 2.64, 2.74
    ]

    loops = []
    for y in y_stations:
        z_sill, z_top, x_sc, y_sw, flare, in_cab, in_cargo = eval_van_station(y)
        # Beltline height steps up from front mirror (1.15) to cargo beltline (1.26)
        if y < -1.75:
            z_belt = min(z_top - 0.06, 0.84 + 0.31 * max(0.0, (y - (-2.74)) / 0.99))
        elif y < -0.50:
            t_b = (y - (-1.75)) / 1.25
            z_belt = min(z_top - 0.08, 1.15 + 0.11 * t_b)
        else:
            z_belt = 1.26

        z_span_low = max(0.12, z_belt - z_sill)
        z_span_high = max(0.06, z_top - z_belt)

        # Recessed side window or blind cargo panel indentation
        recess = 0.0
        if in_cab:
            recess = -0.022
        elif in_cargo:
            recess = -0.012

        # Half cross-section from bottom underbody center (idx 0) to roof crown center (idx 14)
        # (x_val, y_val, z_val)
        half_pts = [
            (0.0, y, 0.24),
            (0.55 * x_sc, y, 0.24),
            (0.57 * x_sc, y, z_sill),
            (0.945 * x_sc + flare * 0.6, y + y_sw * 0.85, z_sill),
            (0.995 * x_sc + flare, y + y_sw * 0.95, z_sill + z_span_low * 0.24),
            (1.016 * x_sc + flare * 0.4, y + y_sw, z_sill + z_span_low * 0.52),
            (1.030 * x_sc, y + y_sw, z_belt - 0.02),
            (1.026 * x_sc + recess * 0.4, y + y_sw * 0.96, z_belt + z_span_high * 0.05),
            (1.002 * x_sc + recess, y + y_sw * 0.90, z_belt + z_span_high * 0.26),
            (0.972 * x_sc + recess, y + y_sw * 0.82, z_belt + z_span_high * 0.50),
            (0.948 * x_sc, y + y_sw * 0.72, z_belt + z_span_high * 0.64),
            (0.902 * x_sc, y + y_sw * 0.58, z_belt + z_span_high * 0.81),
            (0.795 * x_sc, y + y_sw * 0.40, z_belt + z_span_high * 0.935),
            (0.440 * x_sc, y + y_sw * 0.16, z_top - 0.008),
            (0.0, y, z_top),
        ]

        ring_verts = []
        # Right side: 0 .. 14
        for px, py, pz in half_pts:
            ring_verts.append(bm.verts.new((px, py, pz)))
        # Left side: 13 down to 1
        for px, py, pz in reversed(half_pts[1:-1]):
            ring_verts.append(bm.verts.new((-px, py, pz)))
        loops.append(ring_verts)

    n_ring = len(loops[0])
    for i in range(len(loops) - 1):
        r0 = loops[i]
        r1 = loops[i + 1]
        y_mid = 0.5 * (y_stations[i] + y_stations[i + 1])
        for j in range(n_ring):
            jn = (j + 1) % n_ring
            f = bm.faces.new((r0[j], r0[jn], r1[jn], r1[j]))
            # Assign material index: 0 = Paint, 1 = Plastic (underbody, wheel housing, lower cladding)
            # Indices on right side: 0..2 are underbody/wheel house, 3..4 are lower cladding/arch lip
            # Symmetric on left side: 26..27 are underbody/wheel house, 24..25 are lower cladding/arch lip
            if j in (0, 1, 2, 3, 24, 25, 26, 27):
                f.material_index = 1
            elif y_mid < -2.60 and j in (4, 5, 22, 23):
                f.material_index = 1
            else:
                f.material_index = 0

    # Cap front nose and rear doors by connecting right side (j) to left side (n_ring - j)
    front_ring = loops[0]
    for j in range(0, 14):
        v_r0 = front_ring[j]
        v_r1 = front_ring[j + 1]
        v_l1 = front_ring[(n_ring - (j + 1)) % n_ring]
        v_l0 = front_ring[(n_ring - j) % n_ring]
        verts = []
        for v in (v_r1, v_r0, v_l0, v_l1):
            if v not in verts:
                verts.append(v)
        if len(verts) >= 3:
            f = bm.faces.new(verts)
            f.material_index = 1 if j < 6 else 0

    rear_ring = loops[-1]
    for j in range(0, 14):
        v_r0 = rear_ring[j]
        v_r1 = rear_ring[j + 1]
        v_l1 = rear_ring[(n_ring - (j + 1)) % n_ring]
        v_l0 = rear_ring[(n_ring - j) % n_ring]
        verts = []
        for v in (v_r0, v_r1, v_l1, v_l0):
            if v not in verts:
                verts.append(v)
        if len(verts) >= 3:
            f = bm.faces.new(verts)
            f.material_index = 1 if j < 4 else 0

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new("Van_Body")
    bm.to_mesh(mesh)
    bm.free()

    mesh.materials.append(mats["Paint"])
    mesh.materials.append(mats["Plastic"])

    obj = bpy.data.objects.new("Van_Body", mesh)
    bpy.context.collection.objects.link(obj)
    mod = obj.modifiers.new("Subsurf", 'SUBSURF')
    mod.levels = 1
    mod.render_levels = 1
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    apply_smooth_and_sharp(obj.data, 36.0)
    return obj

def add_grid_patch(bm, grid, mat_idx=0, flip=False):
    rows = len(grid)
    cols = len(grid[0])
    vgrid = [[bm.verts.new(pt) for pt in row] for row in grid]
    for r in range(rows - 1):
        for c in range(cols - 1):
            v00 = vgrid[r][c]
            v10 = vgrid[r + 1][c]
            v11 = vgrid[r + 1][c + 1]
            v01 = vgrid[r][c + 1]
            f = bm.faces.new((v00, v01, v11, v10) if flip else (v00, v10, v11, v01))
            f.material_index = mat_idx
    return vgrid

def add_box_to_bm(bm, center, size, mat_idx=0, rx=0.0, ry=0.0, rz=0.0):
    rot = Euler((rx, ry, rz), 'XYZ').to_matrix().to_4x4()
    trans = Matrix.Translation(center) @ rot
    res = bmesh.ops.create_cube(bm, size=1.0)
    verts = res["verts"]
    for v in verts:
        v.co.x *= size[0]
        v.co.y *= size[1]
        v.co.z *= size[2]
        v.co = trans @ v.co
    for f in bm.faces:
        if all(v in verts for v in f.verts):
            f.material_index = mat_idx
    return verts

def build_windows_and_interior(mats):
    bm = bmesh.new()
    # Material slots: 0 = Glass, 1 = Plastic (interior cabin, seats, dashboard, bulkhead)

    # 1. Curved Windscreen Glass (inset slightly into the front windscreen pocket)
    ws_rows = 7
    ws_cols = 11
    ws_grid = []
    for r in range(ws_rows):
        tv = r / (ws_rows - 1)
        y_base = -1.80 + tv * 0.77
        z_base = 1.21 + tv * 0.88
        half_w = 0.86 - tv * 0.08
        row_pts = []
        for c in range(ws_cols):
            tu = (c / (ws_cols - 1)) * 2.0 - 1.0
            x_pt = tu * half_w
            curve_y = 0.095 * (tu * tu)
            curve_z = -0.018 * (tu * tu)
            row_pts.append((x_pt, y_base + curve_y, z_base + curve_z))
        ws_grid.append(row_pts)
    add_grid_patch(bm, ws_grid, mat_idx=0, flip=False)

    # 2. Left & Right Cab Side Windows (inset slightly into cab doors, with front Transit drop sill)
    for side in (-1.0, 1.0):
        sw_cols = 8
        sw_rows = 5
        sw_grid = []
        for r in range(sw_rows):
            tv = r / (sw_rows - 1)
            row_pts = []
            for c in range(sw_cols):
                tu = c / (sw_cols - 1)
                y_pt = -1.66 + tu * 1.14
                # Sill slopes up from 1.17 at front to 1.27 at rear; top slopes from 1.92 to 2.02
                z_bot = 1.17 + 0.10 * min(1.0, tu * 1.6)
                z_top = 1.88 + 0.13 * (tu ** 0.75)
                if tu < 0.18:
                    z_top = 1.38 + (z_top - 1.38) * (tu / 0.18)
                z_pt = z_bot + tv * (z_top - z_bot)
                # Follow body tumblehome, inset by ~1.4 cm
                x_mag = (1.005 - tv * 0.048) - 0.012 * ((2.0 * tu - 1.0) ** 2)
                row_pts.append((side * x_mag, y_pt, z_pt))
            sw_grid.append(row_pts)
        add_grid_patch(bm, sw_grid, mat_idx=0, flip=(side < 0))

    # 3. Interior Silhouettes (Dashboard, Steering Wheel, Driver & Passenger Seats, Headrests, Bulkhead)
    # Dashboard
    add_box_to_bm(bm, (0.0, -1.52, 1.14), (1.68, 0.42, 0.28), mat_idx=1, rx=0.15)
    add_box_to_bm(bm, (-0.44, -1.45, 1.29), (0.38, 0.26, 0.12), mat_idx=1)
    # Steering wheel & column
    add_box_to_bm(bm, (-0.44, -1.24, 1.24), (0.36, 0.06, 0.36), mat_idx=1, rx=0.55)
    # Driver seat + Passenger twin seat + headrests
    for sx, sw in ((-0.46, 0.48), (0.36, 0.76)):
        add_box_to_bm(bm, (sx, -0.82, 0.90), (sw, 0.50, 0.16), mat_idx=1)
        add_box_to_bm(bm, (sx, -0.62, 1.22), (sw, 0.14, 0.56), mat_idx=1, rx=-0.14)
    for hx in (-0.46, 0.16, 0.56):
        add_box_to_bm(bm, (hx, -0.58, 1.58), (0.22, 0.11, 0.20), mat_idx=1)
    # Cab bulkhead wall behind seats
    add_box_to_bm(bm, (0.0, -0.42, 1.42), (1.76, 0.06, 1.65), mat_idx=1)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("Van_Windows_Interior")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mats["Glass"])
    mesh.materials.append(mats["Plastic"])
    obj = bpy.data.objects.new("Van_Windows_Interior", mesh)
    bpy.context.collection.objects.link(obj)
    apply_smooth_and_sharp(obj.data, 35.0)
    return obj

def build_pillars(mats):
    bm = bmesh.new()
    # 0 = Paint, 1 = Plastic

    for side in (-1.0, 1.0):
        # A-pillar framing the windscreen & front cab door
        add_box_to_bm(bm, (side * 0.90, -1.42, 1.66), (0.075, 0.94, 0.075), mat_idx=0,
                      rx=0.84, ry=side * 0.08, rz=-side * 0.09)
        # Front quarter-window vertical division bar
        add_box_to_bm(bm, (side * 0.992, -1.38, 1.56), (0.028, 0.035, 0.72), mat_idx=1,
                      ry=-side * 0.06)
        # B-pillar between cab door and cargo bay
        add_box_to_bm(bm, (side * 0.995, -0.47, 1.64), (0.042, 0.095, 0.88), mat_idx=1,
                      ry=-side * 0.055)
        # C-pillar at mid cargo body
        add_box_to_bm(bm, (side * 0.990, 1.12, 1.72), (0.032, 0.075, 0.96), mat_idx=0,
                      ry=-side * 0.055)
        # D-pillar framing the rear corners
        add_box_to_bm(bm, (side * 0.945, 2.70, 2.02), (0.065, 0.085, 0.76), mat_idx=0,
                      ry=-side * 0.08)
        # Roof gutter / drip rail along cantrail
        add_box_to_bm(bm, (side * 0.922, 0.88, 2.28), (0.026, 3.55, 0.024), mat_idx=1)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("Van_Pillars")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mats["Paint"])
    mesh.materials.append(mats["Plastic"])
    obj = bpy.data.objects.new("Van_Pillars", mesh)
    bpy.context.collection.objects.link(obj)
    apply_smooth_and_sharp(obj.data, 35.0)
    return obj

def build_bumpers_and_grille(mats):
    bm = bmesh.new()
    # 0 = Plastic, 1 = Grille, 2 = Chrome, 3 = HeadlightLens, 4 = TaillightLens

    # 1. Curved Wrap-Around Front Bumper (Y from -2.765 to -1.96, Z from 0.20 to 0.66)
    fb_cols = 15
    fb_rows = 6
    front_outer = []
    front_inner = []
    for r in range(fb_rows):
        tv = r / (fb_rows - 1)
        z_pt = 0.20 + tv * 0.46
        # Profile protrusion at mid bumper height
        y_protrude = -0.025 * math.sin(tv * math.pi)
        row_out = []
        row_in = []
        for c in range(fb_cols):
            tu = (c / (fb_cols - 1)) * 2.0 - 1.0
            ang = tu * 1.12
            x_pt = math.sin(ang) * 1.035
            y_pt = -2.36 - math.cos(ang) * 0.405 + y_protrude
            if abs(tu) > 0.78:
                y_pt += (abs(tu) - 0.78) * 0.95
                x_pt = math.copysign(1.028, tu)
            row_out.append((x_pt, y_pt, z_pt))
            row_in.append((x_pt * 0.94, y_pt + 0.055, z_pt))
        front_outer.append(row_out)
        front_inner.append(row_in)

    vo = add_grid_patch(bm, front_outer, mat_idx=0, flip=True)
    vi = add_grid_patch(bm, front_inner, mat_idx=0, flip=False)
    for c in range(fb_cols - 1):
        f_top = bm.faces.new((vo[-1][c], vo[-1][c + 1], vi[-1][c + 1], vi[-1][c]))
        f_bot = bm.faces.new((vo[0][c + 1], vo[0][c], vi[0][c], vi[0][c + 1]))
        f_top.material_index = 0
        f_bot.material_index = 0

    # Lower bumper cooling air intake grille
    add_box_to_bm(bm, (0.0, -2.752, 0.29), (0.86, 0.04, 0.13), mat_idx=1)
    # Front bumper step recess
    add_box_to_bm(bm, (0.0, -2.758, 0.51), (0.64, 0.04, 0.06), mat_idx=0)
    # Front fog lamp bezels + clear lenses on left & right
    for side in (-1.0, 1.0):
        add_box_to_bm(bm, (side * 0.72, -2.685, 0.34), (0.18, 0.05, 0.13), mat_idx=0, rz=side * 0.25)
        add_box_to_bm(bm, (side * 0.72, -2.695, 0.34), (0.11, 0.04, 0.085), mat_idx=3, rz=side * 0.25)

    # 2. Iconic Ford Transit Hexagonal Upper Radiator Grille
    # Outer surround frame + recessed mesh + 3 horizontal twin-bars + central oval emblem
    hex_pts_out = [
        (-0.52, -2.715, 0.92), (0.52, -2.715, 0.92),
        (0.62, -2.705, 0.77), (0.50, -2.735, 0.62),
        (-0.50, -2.735, 0.62), (-0.62, -2.705, 0.77),
    ]
    hex_pts_in = [
        (-0.47, -2.732, 0.89), (0.47, -2.732, 0.89),
        (0.56, -2.722, 0.77), (0.45, -2.748, 0.65),
        (-0.45, -2.748, 0.65), (-0.56, -2.722, 0.77),
    ]
    hex_pts_back = [(x * 0.98, y + 0.028, z) for (x, y, z) in hex_pts_in]
    v_out = [bm.verts.new(p) for p in hex_pts_out]
    v_in = [bm.verts.new(p) for p in hex_pts_in]
    v_bk = [bm.verts.new(p) for p in hex_pts_back]
    for i in range(6):
        inext = (i + 1) % 6
        f1 = bm.faces.new((v_out[i], v_out[inext], v_in[inext], v_in[i]))
        f1.material_index = 0
        f2 = bm.faces.new((v_in[i], v_in[inext], v_bk[inext], v_bk[i]))
        f2.material_index = 0
    f_mesh = bm.faces.new(v_bk)
    f_mesh.material_index = 1

    # 3 horizontal grille bars + chrome accent strips
    for z_bar, w_bar in ((0.835, 0.96), (0.770, 1.06), (0.705, 0.94)):
        add_box_to_bm(bm, (0.0, -2.738, z_bar), (w_bar, 0.032, 0.028), mat_idx=0)
        add_box_to_bm(bm, (0.0, -2.748, z_bar), (w_bar * 0.96, 0.016, 0.012), mat_idx=2)

    # Central oval Transit emblem badge
    add_box_to_bm(bm, (0.0, -2.752, 0.775), (0.21, 0.028, 0.088), mat_idx=2)

    # 3. Wrap-Around Rear Bumper with Integrated Rear Step & Corner Caps
    rb_cols = 15
    rb_rows = 5
    rear_outer = []
    rear_inner = []
    for r in range(rb_rows):
        tv = r / (rb_rows - 1)
        z_pt = 0.23 + tv * 0.31
        row_out = []
        row_in = []
        for c in range(rb_cols):
            tu = (c / (rb_cols - 1)) * 2.0 - 1.0
            if abs(tu) < 0.74:
                x_pt = (tu / 0.74) * 0.95
                y_pt = 2.755 - 0.035 * ((tu / 0.74) ** 2)
            else:
                t_side = (abs(tu) - 0.74) / 0.26
                x_pt = math.copysign(0.95 + 0.078 * (t_side ** 0.5), tu)
                y_pt = 2.72 - t_side * 0.68
            row_out.append((x_pt, y_pt, z_pt))
            row_in.append((x_pt * 0.95, y_pt - 0.055, z_pt))
        rear_outer.append(row_out)
        rear_inner.append(row_in)

    rvo = add_grid_patch(bm, rear_outer, mat_idx=0, flip=False)
    rvi = add_grid_patch(bm, rear_inner, mat_idx=0, flip=True)
    for c in range(rb_cols - 1):
        f_top = bm.faces.new((rvo[-1][c + 1], rvo[-1][c], rvi[-1][c], rvi[-1][c + 1]))
        f_bot = bm.faces.new((rvo[0][c], rvo[0][c + 1], rvi[0][c + 1], rvi[0][c]))
        f_top.material_index = 0
        f_bot.material_index = 0

    # Rear bumper step platform & retro-reflectors
    add_box_to_bm(bm, (0.0, 2.762, 0.36), (1.18, 0.065, 0.085), mat_idx=0)
    for side in (-1.0, 1.0):
        add_box_to_bm(bm, (side * 0.76, 2.748, 0.33), (0.16, 0.025, 0.042), mat_idx=4)
        # Side lower body plastic rub strip between front and rear arches
        add_box_to_bm(bm, (side * 1.022, -0.05, 0.42), (0.024, 2.28, 0.13), mat_idx=0)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("Van_Bumpers_Grille")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mats["Plastic"])
    mesh.materials.append(mats["Grille"])
    mesh.materials.append(mats["Chrome"])
    mesh.materials.append(mats["HeadlightLens"])
    mesh.materials.append(mats["TaillightLens"])
    obj = bpy.data.objects.new("Van_Bumpers_Grille", mesh)
    bpy.context.collection.objects.link(obj)
    apply_smooth_and_sharp(obj.data, 35.0)
    return obj

def build_lights(mats):
    bm = bmesh.new()
    # 0 = Chrome (reflectors), 1 = HeadlightLens, 2 = TaillightLens, 3 = Plastic (housing bezel)

    # 1. Swept-Back Front Headlights (Reflector bowls + Projector dome + Clear outer lens)
    for side in (-1.0, 1.0):
        hl_cols = 6
        hl_rows = 5
        lens_grid = []
        refl_grid = []
        for r in range(hl_rows):
            tv = r / (hl_rows - 1)
            row_l = []
            row_r = []
            for c in range(hl_cols):
                tu = c / (hl_cols - 1)
                x_mag = 0.62 + tu * 0.365
                y_front = -2.685 + tu * 0.44 + tv * 0.14
                z_pt = 0.68 + tv * (0.22 + tu * 0.08) + tu * 0.04
                bulge = 0.022 * math.sin(tu * math.pi) * math.sin(tv * math.pi)
                row_l.append((side * (x_mag + bulge * 0.3), y_front - bulge, z_pt))
                # Inner reflector curved bowl behind the clear lens
                bowl = 0.032 * math.sin(tu * math.pi) * math.sin(tv * math.pi)
                row_r.append((side * (x_mag - 0.012), y_front + 0.022 + bowl, z_pt))
            lens_grid.append(row_l)
            refl_grid.append(row_r)

        flip_flag = (side > 0)
        vl = add_grid_patch(bm, lens_grid, mat_idx=1, flip=flip_flag)
        vr = add_grid_patch(bm, refl_grid, mat_idx=0, flip=flip_flag)
        # Bezel frame connecting outer lens perimeter to reflector housing
        for c in range(hl_cols - 1):
            f1 = bm.faces.new((vl[0][c], vl[0][c + 1], vr[0][c + 1], vr[0][c]))
            f2 = bm.faces.new((vl[-1][c + 1], vl[-1][c], vr[-1][c], vr[-1][c + 1]))
            f1.material_index = 3
            f2.material_index = 3
        # Inner projector bulb dome inside reflector
        add_box_to_bm(bm, (side * 0.78, -2.46, 0.81), (0.085, 0.065, 0.085), mat_idx=0, rz=side * 0.45)

    # 2. Tall Vertical Ford Transit Pillar Taillights (Reflector + Red/Clear/Amber Lens)
    for side in (-1.0, 1.0):
        tl_cols = 4
        tl_rows = 8
        tl_lens = []
        tl_refl = []
        for r in range(tl_rows):
            tv = r / (tl_rows - 1)
            z_pt = 0.68 + tv * 0.94
            row_l = []
            row_r = []
            for c in range(tl_cols):
                tu = c / (tl_cols - 1)
                x_mag = (0.895 + tu * 0.095) - tv * 0.022
                y_pt = 2.735 - tu * 0.065 + 0.015 * math.sin(tu * math.pi)
                row_l.append((side * x_mag, y_pt, z_pt))
                row_r.append((side * (x_mag - 0.012), y_pt - 0.022, z_pt))
            tl_lens.append(row_l)
            tl_refl.append(row_r)

        flip_tl = (side < 0)
        vtl = add_grid_patch(bm, tl_lens, mat_idx=2, flip=flip_tl)
        vtr = add_grid_patch(bm, tl_refl, mat_idx=0, flip=flip_tl)
        for r in range(tl_rows - 1):
            f_in = bm.faces.new((vtl[r][0], vtl[r + 1][0], vtr[r + 1][0], vtr[r][0]))
            f_out = bm.faces.new((vtl[r + 1][-1], vtl[r][-1], vtr[r][-1], vtr[r + 1][-1]))
            f_in.material_index = 3
            f_out.material_index = 3

    # 3. High-Mounted Third Brake Light above Twin Rear Doors
    add_box_to_bm(bm, (0.0, 2.712, 2.475), (0.34, 0.035, 0.042), mat_idx=3)
    add_box_to_bm(bm, (0.0, 2.725, 2.475), (0.30, 0.022, 0.028), mat_idx=2)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("Van_Lights")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mats["Chrome"])
    mesh.materials.append(mats["HeadlightLens"])
    mesh.materials.append(mats["TaillightLens"])
    mesh.materials.append(mats["Plastic"])
    obj = bpy.data.objects.new("Van_Lights", mesh)
    bpy.context.collection.objects.link(obj)
    apply_smooth_and_sharp(obj.data, 35.0)
    return obj

def build_mirrors_handles_plates_wipers(mats):
    bm = bmesh.new()
    # 0 = Plastic, 1 = Chrome (mirror glass), 2 = Plate, 3 = TaillightLens (mirror repeater)

    # 1. Commercial Dual-Glass Side Mirrors (Left & Right)
    for side in (-1.0, 1.0):
        # Triangular door mount base
        add_box_to_bm(bm, (side * 1.005, -1.56, 1.26), (0.035, 0.22, 0.18), mat_idx=0, ry=-side * 0.06)
        # Upper and lower twin support arms
        add_box_to_bm(bm, (side * 1.065, -1.54, 1.33), (0.12, 0.042, 0.032), mat_idx=0, rz=-side * 0.18)
        add_box_to_bm(bm, (side * 1.065, -1.54, 1.21), (0.12, 0.042, 0.032), mat_idx=0, rz=-side * 0.18)
        # Tall mirror housing shell
        add_box_to_bm(bm, (side * 1.135, -1.51, 1.31), (0.135, 0.115, 0.29), mat_idx=0, rz=-side * 0.15)
        # Front turn-signal repeater strip on mirror housing
        add_box_to_bm(bm, (side * 1.145, -1.565, 1.30), (0.11, 0.018, 0.032), mat_idx=3, rz=-side * 0.15)
        # Upper main flat mirror glass + lower wide-angle convex mirror glass facing +Y
        add_box_to_bm(bm, (side * 1.135, -1.452, 1.355), (0.115, 0.012, 0.165), mat_idx=1, rz=-side * 0.15)
        add_box_to_bm(bm, (side * 1.135, -1.452, 1.215), (0.115, 0.012, 0.075), mat_idx=1, rz=-side * 0.15)

    # 2. Door Handles, Sliding Door Track, Rear Door Hinges & Roof Antenna
    for side in (-1.0, 1.0):
        # Front cab door vertical grab handle + bezel
        add_box_to_bm(bm, (side * 1.028, -0.66, 1.09), (0.018, 0.068, 0.175), mat_idx=0)
        add_box_to_bm(bm, (side * 1.042, -0.66, 1.09), (0.022, 0.036, 0.145), mat_idx=0)
        # External rear barn-door hinges (upper and lower)
        add_box_to_bm(bm, (side * 0.905, 2.725, 0.68), (0.055, 0.048, 0.065), mat_idx=0)
        add_box_to_bm(bm, (side * 0.885, 2.715, 1.96), (0.055, 0.048, 0.065), mat_idx=0)

    # Right-side sliding cargo door vertical grab handle + sliding guide rail track
    add_box_to_bm(bm, (1.028, -0.28, 1.09), (0.018, 0.068, 0.175), mat_idx=0)
    add_box_to_bm(bm, (1.042, -0.28, 1.09), (0.022, 0.036, 0.145), mat_idx=0)
    add_box_to_bm(bm, (1.026, 1.35, 1.16), (0.018, 1.56, 0.028), mat_idx=0)

    # Rear right door vertical handle
    add_box_to_bm(bm, (0.085, 2.752, 0.98), (0.042, 0.032, 0.165), mat_idx=0)
    # Roof aerial antenna at front of high-roof forehead
    add_box_to_bm(bm, (0.0, -0.92, 2.28), (0.036, 0.055, 0.045), mat_idx=0)
    add_box_to_bm(bm, (0.0, -0.86, 2.42), (0.012, 0.012, 0.28), mat_idx=0, rx=-0.52)

    # 3. Front and Rear Number Plates (520mm x 110mm in black frames)
    # Front plate on front bumper center (Y = -2.768, Z = 0.38)
    add_box_to_bm(bm, (0.0, -2.762, 0.38), (0.535, 0.024, 0.124), mat_idx=0)
    add_box_to_bm(bm, (0.0, -2.772, 0.38), (0.515, 0.012, 0.108), mat_idx=2)

    # Rear plate on lower left rear door + license plate light housing above it
    add_box_to_bm(bm, (-0.38, 2.748, 0.76), (0.535, 0.022, 0.124), mat_idx=0)
    add_box_to_bm(bm, (-0.38, 2.758, 0.76), (0.515, 0.012, 0.108), mat_idx=2)
    add_box_to_bm(bm, (-0.38, 2.755, 0.855), (0.28, 0.035, 0.038), mat_idx=0)

    # 4. Windscreen Wipers (2 articulated wiper assemblies at base of windscreen)
    for wx_piv, wx_blade in ((-0.54, -0.22), (0.12, 0.44)):
        # Pivot cap
        add_box_to_bm(bm, (wx_piv, -1.84, 1.205), (0.045, 0.045, 0.035), mat_idx=0)
        # Wiper arm
        add_box_to_bm(bm, (0.5 * (wx_piv + wx_blade), -1.81, 1.225), (0.36, 0.022, 0.018),
                      mat_idx=0, rx=0.72, rz=-0.12)
        # Wiper blade + rubber squeegee
        add_box_to_bm(bm, (wx_blade, -1.78, 1.245), (0.58, 0.024, 0.020),
                      mat_idx=0, rx=0.78, rz=0.05)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("Van_Trim_Details")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mats["Plastic"])
    mesh.materials.append(mats["Chrome"])
    mesh.materials.append(mats["Plate"])
    mesh.materials.append(mats["TaillightLens"])
    obj = bpy.data.objects.new("Van_Trim_Details", mesh)
    bpy.context.collection.objects.link(obj)
    apply_smooth_and_sharp(obj.data, 35.0)
    return obj

def build_single_wheel_bm(cx, cy, cz, side):
    # Builds 1 complete wheel: Tyre with sidewall profile + Multi-spoke rim/hubcap + 5 lug bolts + Brake disc & Caliper
    # Material indices: 0 = Tyre, 1 = Rim, 2 = BrakeDisc, 3 = Plastic (caliper/dark inner barrel)
    bm = bmesh.new()
    n_seg = 32
    r_tyre = 0.375
    r_rim = 0.222
    r_hub = 0.068
    w_half = 0.118

    # Cross-section profile of tyre + outer rim lip + inner barrel (from outer rim edge around tyre to inner rim edge)
    # Local wheel x: side * dx (dx > 0 is outward face of wheel, dx < 0 is inward face)
    tyre_profile = [
        (w_half * 0.78, r_rim - 0.008, 1),
        (w_half * 0.86, r_rim + 0.006, 1),
        (w_half * 0.92, r_rim + 0.020, 0),
        (w_half * 1.02, 0.295, 0),
        (w_half * 0.96, 0.352, 0),
        (w_half * 0.80, r_tyre, 0),
        (w_half * 0.28, r_tyre, 0),
        (-w_half * 0.28, r_tyre, 0),
        (-w_half * 0.80, r_tyre, 0),
        (-w_half * 0.96, 0.352, 0),
        (-w_half * 1.00, 0.295, 0),
        (-w_half * 0.88, r_rim + 0.015, 0),
        (-w_half * 0.82, r_rim - 0.010, 3),
        (w_half * 0.42, r_rim - 0.018, 3),
    ]

    rings = []
    for dx, rad, _ in tyre_profile:
        ring = []
        for i in range(n_seg):
            ang = (2.0 * math.pi * i) / n_seg
            y_pt = cy + math.cos(ang) * rad
            z_pt = cz + math.sin(ang) * rad
            x_pt = cx + side * dx
            ring.append(bm.verts.new((x_pt, y_pt, z_pt)))
        rings.append(ring)

    for p_idx in range(len(tyre_profile)):
        p_next = (p_idx + 1) % len(tyre_profile)
        r0 = rings[p_idx]
        r1 = rings[p_next]
        mat_i = tyre_profile[p_idx][2]
        for i in range(n_seg):
            inext = (i + 1) % n_seg
            verts = (r0[i], r0[inext], r1[inext], r1[i]) if side > 0 else (r0[i], r1[i], r1[inext], r0[inext])
            f = bm.faces.new(verts)
            f.material_index = mat_i

    # Multi-Spoke Rim / Hubcap on the outer face (10 sculpted radial spokes with open vents between them)
    n_spokes = 10
    ring_outer_hub = []
    ring_inner_hub = []
    ring_center_cap = []
    for i in range(n_seg):
        ang = (2.0 * math.pi * i) / n_seg
        c_a = math.cos(ang)
        s_a = math.sin(ang)
        ring_outer_hub.append(bm.verts.new((cx + side * (w_half * 0.82), cy + c_a * (r_rim - 0.006), cz + s_a * (r_rim - 0.006))))
        ring_inner_hub.append(bm.verts.new((cx + side * (w_half * 0.72), cy + c_a * r_hub, cz + s_a * r_hub)))
        ring_center_cap.append(bm.verts.new((cx + side * (w_half * 0.78), cy + c_a * 0.032, cz + s_a * 0.032)))

    v_center = bm.verts.new((cx + side * (w_half * 0.80), cy, cz))
    for i in range(n_seg):
        inext = (i + 1) % n_seg
        f1 = bm.faces.new((ring_inner_hub[i], ring_inner_hub[inext], ring_center_cap[inext], ring_center_cap[i]) if side > 0
                          else (ring_inner_hub[i], ring_center_cap[i], ring_center_cap[inext], ring_inner_hub[inext]))
        f1.material_index = 1
        f2 = bm.faces.new((ring_center_cap[i], ring_center_cap[inext], v_center) if side > 0
                          else (ring_center_cap[inext], ring_center_cap[i], v_center))
        f2.material_index = 1

    # 10 sculpted 3D spokes connecting hub to outer rim ring (leaving open vent holes between spokes)
    for s in range(n_spokes):
        ang0 = (2.0 * math.pi * s) / n_spokes - 0.14
        ang1 = (2.0 * math.pi * s) / n_spokes + 0.14
        r_in = r_hub - 0.004
        r_out = r_rim - 0.004
        x_f = cx + side * (w_half * 0.86)
        x_b = cx + side * (w_half * 0.70)

        vf0 = bm.verts.new((x_f, cy + math.cos(ang0) * r_in, cz + math.sin(ang0) * r_in))
        vf1 = bm.verts.new((x_f, cy + math.cos(ang1) * r_in, cz + math.sin(ang1) * r_in))
        vf2 = bm.verts.new((x_f, cy + math.cos(ang1 * 0.98 + ang0 * 0.02) * r_out, cz + math.sin(ang1 * 0.98 + ang0 * 0.02) * r_out))
        vf3 = bm.verts.new((x_f, cy + math.cos(ang0 * 0.98 + ang1 * 0.02) * r_out, cz + math.sin(ang0 * 0.98 + ang1 * 0.02) * r_out))

        vb0 = bm.verts.new((x_b, cy + math.cos(ang0) * r_in, cz + math.sin(ang0) * r_in))
        vb1 = bm.verts.new((x_b, cy + math.cos(ang1) * r_in, cz + math.sin(ang1) * r_in))
        vb2 = bm.verts.new((x_b, cy + math.cos(ang1) * r_out, cz + math.sin(ang1) * r_out))
        vb3 = bm.verts.new((x_b, cy + math.cos(ang0) * r_out, cz + math.sin(ang0) * r_out))

        faces_quads = [
            (vf0, vf1, vf2, vf3),
            (vb1, vb0, vb3, vb2),
            (vf1, vb1, vb2, vf2),
            (vb0, vf0, vf3, vb3),
        ]
        for q in faces_quads:
            f = bm.faces.new(q if side > 0 else tuple(reversed(q)))
            f.material_index = 1

    # 5 Lug nuts around hub center
    for k in range(5):
        ang_l = (2.0 * math.pi * k) / 5.0
        ly = cy + math.cos(ang_l) * 0.050
        lz = cz + math.sin(ang_l) * 0.050
        lx = cx + side * (w_half * 0.78)
        add_box_to_bm(bm, (lx, ly, lz), (0.022, 0.016, 0.016), mat_idx=2)

    # Brake Disc Rotor + Brake Caliper visibly mounted behind the spokes
    r_disc = 0.165
    r_disc_in = 0.055
    x_disc_out = cx + side * (w_half * 0.34)
    x_disc_in = cx + side * (w_half * 0.22)
    disc_o1, disc_o2, disc_i1, disc_i2 = [], [], [], []
    n_disc = 24
    for i in range(n_disc):
        ang = (2.0 * math.pi * i) / n_disc
        ca, sa = math.cos(ang), math.sin(ang)
        disc_o1.append(bm.verts.new((x_disc_out, cy + ca * r_disc, cz + sa * r_disc)))
        disc_i1.append(bm.verts.new((x_disc_out, cy + ca * r_disc_in, cz + sa * r_disc_in)))
        disc_o2.append(bm.verts.new((x_disc_in, cy + ca * r_disc, cz + sa * r_disc)))
        disc_i2.append(bm.verts.new((x_disc_in, cy + ca * r_disc_in, cz + sa * r_disc_in)))

    for i in range(n_disc):
        inext = (i + 1) % n_disc
        q_front = (disc_i1[i], disc_i1[inext], disc_o1[inext], disc_o1[i])
        q_back = (disc_o2[i], disc_o2[inext], disc_i2[inext], disc_i2[i])
        q_edge = (disc_o1[i], disc_o1[inext], disc_o2[inext], disc_o2[i])
        for q in (q_front, q_back, q_edge):
            f = bm.faces.new(q if side > 0 else tuple(reversed(q)))
            f.material_index = 2

    # Brake Caliper straddling the rotor
    cal_y = cy + (0.115 if cy < 0 else -0.115)
    add_box_to_bm(bm, (cx + side * (w_half * 0.28), cal_y, cz + 0.045), (0.065, 0.085, 0.145), mat_idx=3)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm

def build_wheels(mats):
    wheel_specs = [
        ("Wheel_FL", -0.86, -1.70, 0.375, -1.0),
        ("Wheel_FR",  0.86, -1.70, 0.375,  1.0),
        ("Wheel_RL", -0.86,  1.60, 0.375, -1.0),
        ("Wheel_RR",  0.86,  1.60, 0.375,  1.0),
    ]
    objs = []
    for wname, wx, wy, wz, side in wheel_specs:
        bm = build_single_wheel_bm(wx, wy, wz, side)
        mesh = bpy.data.meshes.new(wname)
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(mats["Tyre"])
        mesh.materials.append(mats["Rim"])
        mesh.materials.append(mats["BrakeDisc"])
        mesh.materials.append(mats["Plastic"])
        obj = bpy.data.objects.new(wname, mesh)
        bpy.context.collection.objects.link(obj)
        apply_smooth_and_sharp(obj.data, 38.0)
        objs.append(obj)
    return objs

def main():
    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0

    # Parse output path after "--"
    out_fbx = os.path.abspath(f"{NAME}.fbx")
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if idx + 1 < len(sys.argv):
            out_fbx = os.path.abspath(sys.argv[idx + 1])
    if not out_fbx.lower().endswith(".fbx"):
        if os.path.isdir(out_fbx) or not os.path.splitext(out_fbx)[1]:
            os.makedirs(out_fbx, exist_ok=True)
            out_fbx = os.path.join(out_fbx, f"{NAME}.fbx")
        else:
            out_fbx = os.path.splitext(out_fbx)[0] + ".fbx"
    out_dir = os.path.dirname(out_fbx)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    preview_png = os.path.splitext(out_fbx)[0] + ".png"

    # Build Procedural Materials
    mats = create_procedural_materials()

    # Build Separate Shapes
    body_obj = build_van_body(mats)
    win_obj = build_windows_and_interior(mats)
    pillar_obj = build_pillars(mats)
    bumper_obj = build_bumpers_and_grille(mats)
    lights_obj = build_lights(mats)
    trim_obj = build_mirrors_handles_plates_wipers(mats)
    wheel_objs = build_wheels(mats)

    all_parts = [body_obj, win_obj, pillar_obj, bumper_obj, lights_obj, trim_obj] + wheel_objs

    # Join everything into ONE object named "CarVan" with origin at (0, 0, 0) and tyres touching Z = 0
    bpy.ops.object.select_all(action='DESELECT')
    for o in all_parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = body_obj
    bpy.ops.object.join()

    car_obj = bpy.context.view_layer.objects.active
    car_obj.name = NAME
    car_obj.data.name = NAME

    # Ensure tyres touch Z = 0 exactly and origin is at (0, 0, 0)
    min_z = min((car_obj.matrix_world @ v.co).z for v in car_obj.data.vertices)
    if abs(min_z) > 1e-5:
        for v in car_obj.data.vertices:
            v.co.z -= min_z
    car_obj.location = (0.0, 0.0, 0.0)
    car_obj.rotation_euler = (0.0, 0.0, 0.0)
    car_obj.scale = (1.0, 1.0, 1.0)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Refresh smooth shading / sharp edges after join
    apply_smooth_and_sharp(car_obj.data, 38.0)

    # UV Unwrap: smart_project -> average_islands_scale -> pack_islands
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

    # Create Bake Images 2048x2048
    img_albedo = bpy.data.images.new(f"{NAME}_albedo", width=2048, height=2048, alpha=False)
    img_albedo.colorspace_settings.name = 'sRGB'

    img_normal = bpy.data.images.new(f"{NAME}_normal", width=2048, height=2048, alpha=False)
    img_normal.colorspace_settings.name = 'Non-Color'

    # Configure Cycles CPU 16 samples
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 16
    scene.render.bake.margin = 8

    bpy.ops.object.select_all(action='DESELECT')
    car_obj.select_set(True)
    bpy.context.view_layer.objects.active = car_obj

    # Activate albedo image texture node in EVERY material and bake DIFFUSE (COLOR)
    for mat in car_obj.data.materials:
        if not mat or not mat.use_nodes:
            continue
        nodes = mat.node_tree.nodes
        for n in nodes:
            n.select = False
        tnode = nodes.new("ShaderNodeTexImage")
        tnode.name = "Bake_Albedo_Target"
        tnode.image = img_albedo
        tnode.select = True
        nodes.active = tnode

    scene.cycles.bake_type = 'DIFFUSE'
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=8, use_clear=True)

    # Activate normal image texture node in EVERY material and bake NORMAL (TANGENT)
    for mat in car_obj.data.materials:
        if not mat or not mat.use_nodes:
            continue
        nodes = mat.node_tree.nodes
        for n in nodes:
            n.select = False
        tnode = nodes.new("ShaderNodeTexImage")
        tnode.name = "Bake_Normal_Target"
        tnode.image = img_normal
        tnode.select = True
        nodes.active = tnode

    scene.cycles.bake_type = 'NORMAL'
    scene.render.bake.normal_space = 'TANGENT'
    bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=8, use_clear=True)

    # Save baked PNGs next to output FBX
    albedo_path = os.path.join(out_dir, f"{NAME}_albedo.png")
    normal_path = os.path.join(out_dir, f"{NAME}_normal.png")

    img_albedo.filepath_raw = albedo_path
    img_albedo.file_format = 'PNG'
    img_albedo.save()
    img_albedo.filepath = albedo_path

    img_normal.filepath_raw = normal_path
    img_normal.file_format = 'PNG'
    img_normal.save()
    img_normal.filepath = normal_path

    # Replace all material slots with ONE material "<Name>_Mat"
    final_mat, f_tree, f_bsdf = make_base_material(f"{NAME}_Mat")
    set_socket(f_bsdf, ["Roughness"], 0.35)
    set_socket(f_bsdf, ["Metallic"], 0.0)

    tex_alb = f_tree.nodes.new("ShaderNodeTexImage")
    tex_alb.image = img_albedo
    f_tree.links.new(tex_alb.outputs["Color"], f_bsdf.inputs["Base Color"])

    tex_nrm = f_tree.nodes.new("ShaderNodeTexImage")
    tex_nrm.image = img_normal
    img_normal.colorspace_settings.name = 'Non-Color'

    nmap = f_tree.nodes.new("ShaderNodeNormalMap")
    nmap.space = 'TANGENT'
    f_tree.links.new(tex_nrm.outputs["Color"], nmap.inputs["Color"])
    f_tree.links.new(nmap.outputs["Normal"], f_bsdf.inputs["Normal"])

    car_obj.data.materials.clear()
    car_obj.data.materials.append(final_mat)
    for poly in car_obj.data.polygons:
        poly.material_index = 0

    # Export FBX: selected only, apply transforms, axis_forward='-Z', axis_up='Y', path_mode='COPY', embed_textures=True
    bpy.ops.object.select_all(action='DESELECT')
    car_obj.select_set(True)
    bpy.context.view_layer.objects.active = car_obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    bpy.ops.export_scene.fbx(
        filepath=out_fbx,
        use_selection=True,
        bake_space_transform=True,
        axis_forward='-Z',
        axis_up='Y',
        path_mode='COPY',
        embed_textures=True,
    )

    # Preview Render Setup: 900x900, EEVEE, grey sky world strength 0.6, sun strength 3 from front-left-above, camera at 1.5 m
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

    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    w_nodes = world.node_tree.nodes
    w_links = world.node_tree.links
    w_nodes.clear()
    w_out = w_nodes.new("ShaderNodeOutputWorld")
    w_bg = w_nodes.new("ShaderNodeBackground")
    w_bg.inputs["Color"].default_value = (0.46, 0.48, 0.50, 1.0)
    w_bg.inputs["Strength"].default_value = 0.6
    w_links.new(w_bg.outputs["Background"], w_out.inputs["Surface"])

    # Sun light strength 3 from front-left-above (front is -Y, front-left is -X, -Y, +Z)
    sun_data = bpy.data.lights.new(name="Sun", type='SUN')
    sun_data.energy = 3.0
    sun_obj = bpy.data.objects.new(name="Sun", object_data=sun_data)
    bpy.context.collection.objects.link(sun_obj)
    sun_obj.location = (-4.5, -5.5, 6.5)
    sun_dir = (Vector((0.0, 0.0, 0.8)) - sun_obj.location).normalized()
    sun_obj.rotation_euler = sun_dir.to_track_quat('-Z', 'Y').to_euler()

    # Camera at 1.5 m height in a front 3/4 view framing the whole 5.53 m van
    cam_data = bpy.data.cameras.new(name="Camera")
    cam_data.lens = 36.0
    cam_data.sensor_width = 36.0
    cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = (-4.55, -5.55, 1.5)
    look_target = Vector((0.0, -0.05, 1.15))
    cam_dir = (look_target - cam_obj.location).normalized()
    cam_obj.rotation_euler = cam_dir.to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = preview_png
    bpy.ops.render.render(write_still=True)

    # Calculate and print triangle count
    car_obj.data.calc_loop_triangles()
    n_tris = len(car_obj.data.loop_triangles)
    print("TRIS", n_tris)

if __name__ == "__main__":
    main()

