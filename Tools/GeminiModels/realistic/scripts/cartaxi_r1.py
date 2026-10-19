import bpy
import bmesh
import mathutils
from mathutils import Vector, Matrix
import math
import sys
import os


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
    for cam in list(bpy.data.cameras):
        bpy.data.cameras.remove(cam, do_unlink=True)
    for lgt in list(bpy.data.lights):
        bpy.data.lights.remove(lgt, do_unlink=True)
    for wrld in list(bpy.data.worlds):
        bpy.data.worlds.remove(wrld, do_unlink=True)


def set_bsdf_input(bsdf, names, value):
    if isinstance(names, str):
        names = [names]
    for name in names:
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = value
            return True
    return False


def get_bsdf_input(bsdf, names):
    if isinstance(names, str):
        names = [names]
    for name in names:
        if name in bsdf.inputs:
            return bsdf.inputs[name]
    return None


def add_dirt_overlay(nodes, links, base_color_socket, base_rough_val, normal_socket=None):
    tex_coord = nodes.new("ShaderNodeTexCoord")
    sep_xyz = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tex_coord.outputs["Object"], sep_xyz.inputs["Vector"])

    map_z = nodes.new("ShaderNodeMapRange")
    map_z.clamp = True
    map_z.inputs["From Min"].default_value = 0.0
    map_z.inputs["From Max"].default_value = 0.25
    map_z.inputs["To Min"].default_value = 1.0
    map_z.inputs["To Max"].default_value = 0.0
    links.new(sep_xyz.outputs["Z"], map_z.inputs["Value"])

    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 14.0
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.65
    links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])

    noise_remap = nodes.new("ShaderNodeMapRange")
    noise_remap.clamp = True
    noise_remap.inputs["From Min"].default_value = 0.32
    noise_remap.inputs["From Max"].default_value = 0.72
    noise_remap.inputs["To Min"].default_value = 0.15
    noise_remap.inputs["To Max"].default_value = 1.0
    links.new(noise.outputs["Fac"], noise_remap.inputs["Value"])

    dirt_fac = nodes.new("ShaderNodeMath")
    dirt_fac.operation = 'MULTIPLY'
    links.new(map_z.outputs["Result"], dirt_fac.inputs[0])
    links.new(noise_remap.outputs["Result"], dirt_fac.inputs[1])

    dirt_strength = nodes.new("ShaderNodeMath")
    dirt_strength.operation = 'MULTIPLY'
    dirt_strength.inputs[1].default_value = 0.42
    links.new(dirt_fac.outputs["Value"], dirt_strength.inputs[0])

    mix_col = nodes.new("ShaderNodeMix")
    mix_col.data_type = 'RGBA'
    mix_col.inputs[7].default_value = (0.21, 0.18, 0.15, 1.0)
    links.new(dirt_strength.outputs["Value"], mix_col.inputs["Factor"])
    if isinstance(base_color_socket, tuple):
        mix_col.inputs[6].default_value = base_color_socket
    else:
        links.new(base_color_socket, mix_col.inputs[6])

    rough_mix = nodes.new("ShaderNodeMath")
    rough_mix.operation = 'MULTIPLY_ADD'
    rough_mix.inputs[1].default_value = 0.45
    rough_mix.inputs[2].default_value = base_rough_val
    links.new(dirt_strength.outputs["Value"], rough_mix.inputs[0])

    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = 0.003
    links.new(dirt_strength.outputs["Value"], bump.inputs["Height"])
    if normal_socket is not None:
        links.new(normal_socket, bump.inputs["Normal"])

    return mix_col.outputs[2], rough_mix.outputs["Value"], bump.outputs["Normal"], tex_coord, sep_xyz


def make_band_mask(nodes, links, val_socket, center, half_width, feather=0.002):
    diff = nodes.new("ShaderNodeMath")
    diff.operation = 'SUBTRACT'
    diff.inputs[1].default_value = center
    links.new(val_socket, diff.inputs[0])

    abs_n = nodes.new("ShaderNodeMath")
    abs_n.operation = 'ABSOLUTE'
    links.new(diff.outputs["Value"], abs_n.inputs[0])

    remap = nodes.new("ShaderNodeMapRange")
    remap.clamp = True
    remap.inputs["From Min"].default_value = half_width
    remap.inputs["From Max"].default_value = half_width + feather
    remap.inputs["To Min"].default_value = 1.0
    remap.inputs["To Max"].default_value = 0.0
    links.new(abs_n.outputs["Value"], remap.inputs["Value"])
    return remap.outputs["Result"]


def make_range_mask(nodes, links, val_socket, min_v, max_v, feather=0.005):
    center = 0.5 * (min_v + max_v)
    half_w = 0.5 * (max_v - min_v)
    return make_band_mask(nodes, links, val_socket, center, half_w, feather)


def combine_masks(nodes, links, mask_a, mask_b, op='MULTIPLY'):
    m = nodes.new("ShaderNodeMath")
    m.operation = op
    if op == 'MAXIMUM':
        m.use_clamp = True
    links.new(mask_a, m.inputs[0])
    links.new(mask_b, m.inputs[1])
    return m.outputs["Value"]


def create_procedural_materials():
    mats = {}

    # 1. TaxiPaint_Mat: NYC Taxi Yellow non-metallic paint with clearcoat, panel gaps, checker stripe, and lower dirt
    mat_paint = bpy.data.materials.new("TaxiPaint_Mat")
    mat_paint.use_nodes = True
    nodes = mat_paint.node_tree.nodes
    links = mat_paint.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    set_bsdf_input(bsdf, ["Metallic"], 0.0)
    set_bsdf_input(bsdf, ["Specular IOR Level", "Specular"], 0.55)
    set_bsdf_input(bsdf, ["Coat Weight", "Clearcoat"], 1.0)
    set_bsdf_input(bsdf, ["Coat Roughness", "Clearcoat Roughness"], 0.03)

    tex_coord = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tex_coord.outputs["Object"], sep.inputs["Vector"])

    abs_x = nodes.new("ShaderNodeMath")
    abs_x.operation = 'ABSOLUTE'
    links.new(sep.outputs["X"], abs_x.inputs[0])

    # Checker stripe along the doors: |X| > 0.80, -0.85 < Y < 0.96, 0.575 < Z < 0.635
    chk_x = make_range_mask(nodes, links, abs_x.outputs["Value"], 0.80, 0.95, 0.005)
    chk_y = make_range_mask(nodes, links, sep.outputs["Y"], -0.84, 0.96, 0.006)
    chk_z = make_range_mask(nodes, links, sep.outputs["Z"], 0.575, 0.635, 0.003)
    chk_xy = combine_masks(nodes, links, chk_x, chk_y, 'MULTIPLY')
    chk_mask = combine_masks(nodes, links, chk_xy, chk_z, 'MULTIPLY')

    checker_tex = nodes.new("ShaderNodeTexChecker")
    checker_tex.inputs["Scale"].default_value = 33.333
    checker_tex.inputs["Color1"].default_value = (0.04, 0.04, 0.04, 1.0)
    checker_tex.inputs["Color2"].default_value = (0.96, 0.96, 0.96, 1.0)
    links.new(tex_coord.outputs["Object"], checker_tex.inputs["Vector"])

    paint_checker_mix = nodes.new("ShaderNodeMix")
    paint_checker_mix.data_type = 'RGBA'
    paint_checker_mix.inputs[6].default_value = (0.95, 0.61, 0.015, 1.0)
    links.new(chk_mask, paint_checker_mix.inputs["Factor"])
    links.new(checker_tex.outputs["Color"], paint_checker_mix.inputs[7])

    # Panel gap seams in Object (X, Y, Z) coordinates
    side_mask = make_range_mask(nodes, links, abs_x.outputs["Value"], 0.72, 0.95, 0.01)
    door_z_mask = make_range_mask(nodes, links, sep.outputs["Z"], 0.22, 0.95, 0.01)
    side_door_zone = combine_masks(nodes, links, side_mask, door_z_mask, 'MULTIPLY')

    seam_d1 = combine_masks(nodes, links, make_band_mask(nodes, links, sep.outputs["Y"], -0.86, 0.0045, 0.0025), side_door_zone)
    seam_d2 = combine_masks(nodes, links, make_band_mask(nodes, links, sep.outputs["Y"], 0.19, 0.0045, 0.0025), side_door_zone)
    seam_d3 = combine_masks(nodes, links, make_band_mask(nodes, links, sep.outputs["Y"], 0.99, 0.0045, 0.0025), side_door_zone)

    sill_y_mask = make_range_mask(nodes, links, sep.outputs["Y"], -0.86, 0.99, 0.01)
    sill_zone = combine_masks(nodes, links, side_mask, sill_y_mask)
    seam_sill = combine_masks(nodes, links, make_band_mask(nodes, links, sep.outputs["Z"], 0.23, 0.0045, 0.0025), sill_zone)

    # Hood seams
    hood_y_mask = make_range_mask(nodes, links, sep.outputs["Y"], -2.28, -0.91, 0.01)
    hood_z_mask = make_range_mask(nodes, links, sep.outputs["Z"], 0.65, 1.02, 0.01)
    hood_zone = combine_masks(nodes, links, hood_y_mask, hood_z_mask)
    seam_hood_side = combine_masks(nodes, links, make_band_mask(nodes, links, abs_x.outputs["Value"], 0.61, 0.0045, 0.0025), hood_zone)

    hood_x_mask = make_range_mask(nodes, links, abs_x.outputs["Value"], 0.0, 0.61, 0.01)
    hood_top_zone = combine_masks(nodes, links, hood_x_mask, hood_z_mask)
    seam_hood_front = combine_masks(nodes, links, make_band_mask(nodes, links, sep.outputs["Y"], -2.28, 0.0045, 0.0025), hood_top_zone)
    seam_hood_rear = combine_masks(nodes, links, make_band_mask(nodes, links, sep.outputs["Y"], -0.91, 0.0045, 0.0025), hood_top_zone)

    # Trunk seams
    trunk_y_mask = make_range_mask(nodes, links, sep.outputs["Y"], 1.44, 2.34, 0.01)
    trunk_z_mask = make_range_mask(nodes, links, sep.outputs["Z"], 0.78, 1.08, 0.01)
    trunk_zone = combine_masks(nodes, links, trunk_y_mask, trunk_z_mask)
    seam_trunk_side = combine_masks(nodes, links, make_band_mask(nodes, links, abs_x.outputs["Value"], 0.56, 0.0045, 0.0025), trunk_zone)

    trunk_x_mask = make_range_mask(nodes, links, abs_x.outputs["Value"], 0.0, 0.56, 0.01)
    trunk_top_zone = combine_masks(nodes, links, trunk_x_mask, trunk_z_mask)
    seam_trunk_front = combine_masks(nodes, links, make_band_mask(nodes, links, sep.outputs["Y"], 1.44, 0.0045, 0.0025), trunk_top_zone)

    all_seams = seam_d1
    for s in [seam_d2, seam_d3, seam_sill, seam_hood_side, seam_hood_front, seam_hood_rear, seam_trunk_side, seam_trunk_front]:
        all_seams = combine_masks(nodes, links, all_seams, s, 'MAXIMUM')

    seam_col_mix = nodes.new("ShaderNodeMix")
    seam_col_mix.data_type = 'RGBA'
    seam_col_mix.inputs[7].default_value = (0.05, 0.04, 0.02, 1.0)
    links.new(all_seams, seam_col_mix.inputs["Factor"])
    links.new(paint_checker_mix.outputs[2], seam_col_mix.inputs[6])

    seam_bump = nodes.new("ShaderNodeBump")
    seam_bump.invert = True
    seam_bump.inputs["Strength"].default_value = 0.85
    seam_bump.inputs["Distance"].default_value = 0.006
    links.new(all_seams, seam_bump.inputs["Height"])

    col_out, rough_out, norm_out, _, _ = add_dirt_overlay(
        nodes, links, seam_col_mix.outputs[2], 0.14, seam_bump.outputs["Normal"]
    )
    links.new(col_out, get_bsdf_input(bsdf, ["Base Color"]))
    links.new(rough_out, get_bsdf_input(bsdf, ["Roughness"]))
    links.new(norm_out, get_bsdf_input(bsdf, ["Normal"]))
    mats["paint"] = mat_paint

    # 2. BlackTrim_Mat: Black plastic lower trim, grille, pillars, wipers, underbody
    mat_trim = bpy.data.materials.new("BlackTrim_Mat")
    mat_trim.use_nodes = True
    nodes = mat_trim.node_tree.nodes
    links = mat_trim.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    set_bsdf_input(bsdf, ["Metallic"], 0.0)
    set_bsdf_input(bsdf, ["Specular IOR Level", "Specular"], 0.35)

    grain = nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 180.0
    grain.inputs["Detail"].default_value = 4.0
    grain_bump = nodes.new("ShaderNodeBump")
    grain_bump.inputs["Strength"].default_value = 0.06
    grain_bump.inputs["Distance"].default_value = 0.001
    links.new(grain.outputs["Fac"], grain_bump.inputs["Height"])

    col_out, rough_out, norm_out, _, _ = add_dirt_overlay(
        nodes, links, (0.075, 0.078, 0.085, 1.0), 0.52, grain_bump.outputs["Normal"]
    )
    links.new(col_out, get_bsdf_input(bsdf, ["Base Color"]))
    links.new(rough_out, get_bsdf_input(bsdf, ["Roughness"]))
    links.new(norm_out, get_bsdf_input(bsdf, ["Normal"]))
    mats["trim"] = mat_trim

    # 3. Chrome_Mat: Chrome window trim, badges, exhaust tips, inner reflectors
    mat_chrome = bpy.data.materials.new("Chrome_Mat")
    mat_chrome.use_nodes = True
    nodes = mat_chrome.node_tree.nodes
    links = mat_chrome.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    set_bsdf_input(bsdf, ["Base Color"], (0.83, 0.85, 0.88, 1.0))
    set_bsdf_input(bsdf, ["Metallic"], 0.25)
    set_bsdf_input(bsdf, ["Roughness"], 0.08)
    set_bsdf_input(bsdf, ["Coat Weight", "Clearcoat"], 1.0)
    mats["chrome"] = mat_chrome

    # 4. Glass_Mat: Dark tinted glass with subtle interior seats/dashboard silhouette visibility
    mat_glass = bpy.data.materials.new("Glass_Mat")
    mat_glass.use_nodes = True
    nodes = mat_glass.node_tree.nodes
    links = mat_glass.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    set_bsdf_input(bsdf, ["Metallic"], 0.0)
    set_bsdf_input(bsdf, ["Roughness"], 0.06)
    set_bsdf_input(bsdf, ["Coat Weight", "Clearcoat"], 1.0)
    set_bsdf_input(bsdf, ["Transmission Weight", "Transmission"], 0.22)

    tc_g = nodes.new("ShaderNodeTexCoord")
    sep_g = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc_g.outputs["Object"], sep_g.inputs["Vector"])
    abs_gx = nodes.new("ShaderNodeMath")
    abs_gx.operation = 'ABSOLUTE'
    links.new(sep_g.outputs["X"], abs_gx.inputs[0])

    # Seat/headrest & dashboard silhouette shapes in object coordinates
    seat_x = make_range_mask(nodes, links, abs_gx.outputs["Value"], 0.14, 0.56, 0.08)
    seat_y1 = make_range_mask(nodes, links, sep_g.outputs["Y"], -0.15, 0.22, 0.08)
    seat_y2 = make_range_mask(nodes, links, sep_g.outputs["Y"], 0.65, 1.08, 0.08)
    dash_y = make_range_mask(nodes, links, sep_g.outputs["Y"], -0.82, -0.42, 0.08)
    seat_z = make_range_mask(nodes, links, sep_g.outputs["Z"], 0.85, 1.24, 0.06)
    dash_z = make_range_mask(nodes, links, sep_g.outputs["Z"], 0.88, 1.06, 0.06)

    seats_y = combine_masks(nodes, links, seat_y1, seat_y2, 'MAXIMUM')
    seats_xy = combine_masks(nodes, links, seat_x, seats_y, 'MULTIPLY')
    seats_sil = combine_masks(nodes, links, seats_xy, seat_z, 'MULTIPLY')
    dash_sil = combine_masks(nodes, links, dash_y, dash_z, 'MULTIPLY')
    interior_sil = combine_masks(nodes, links, seats_sil, dash_sil, 'MAXIMUM')

    glass_mix = nodes.new("ShaderNodeMix")
    glass_mix.data_type = 'RGBA'
    glass_mix.inputs[6].default_value = (0.09, 0.12, 0.16, 1.0)
    glass_mix.inputs[7].default_value = (0.20, 0.23, 0.27, 1.0)
    links.new(interior_sil, glass_mix.inputs["Factor"])
    links.new(glass_mix.outputs[2], get_bsdf_input(bsdf, ["Base Color"]))
    mats["glass"] = mat_glass

    # 5. Headlight_Mat: Clear lens over bright reflector optics
    mat_hl = bpy.data.materials.new("Headlight_Mat")
    mat_hl.use_nodes = True
    nodes = mat_hl.node_tree.nodes
    links = mat_hl.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    set_bsdf_input(bsdf, ["Roughness"], 0.05)
    set_bsdf_input(bsdf, ["Coat Weight", "Clearcoat"], 1.0)
    set_bsdf_input(bsdf, ["Transmission Weight", "Transmission"], 0.25)

    tc_hl = nodes.new("ShaderNodeTexCoord")
    vor_hl = nodes.new("ShaderNodeTexVoronoi")
    vor_hl.inputs["Scale"].default_value = 28.0
    links.new(tc_hl.outputs["Object"], vor_hl.inputs["Vector"])

    hl_mix = nodes.new("ShaderNodeMix")
    hl_mix.data_type = 'RGBA'
    hl_mix.inputs[6].default_value = (0.88, 0.92, 0.98, 1.0)
    hl_mix.inputs[7].default_value = (0.45, 0.50, 0.58, 1.0)
    links.new(vor_hl.outputs["Distance"], hl_mix.inputs["Factor"])

    hl_bump = nodes.new("ShaderNodeBump")
    hl_bump.inputs["Strength"].default_value = 0.25
    hl_bump.inputs["Distance"].default_value = 0.004
    links.new(vor_hl.outputs["Distance"], hl_bump.inputs["Height"])

    links.new(hl_mix.outputs[2], get_bsdf_input(bsdf, ["Base Color"]))
    links.new(hl_bump.outputs["Normal"], get_bsdf_input(bsdf, ["Normal"]))
    mats["headlight"] = mat_hl

    # 6. Taillight_Mat: Ruby red taillight lens over reflector ribs
    mat_tl = bpy.data.materials.new("Taillight_Mat")
    mat_tl.use_nodes = True
    nodes = mat_tl.node_tree.nodes
    links = mat_tl.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    set_bsdf_input(bsdf, ["Roughness"], 0.08)
    set_bsdf_input(bsdf, ["Coat Weight", "Clearcoat"], 1.0)
    set_bsdf_input(bsdf, ["Transmission Weight", "Transmission"], 0.2)

    tc_tl = nodes.new("ShaderNodeTexCoord")
    wave_tl = nodes.new("ShaderNodeTexWave")
    wave_tl.wave_type = 'BANDS'
    wave_tl.bands_direction = 'Z'
    wave_tl.inputs["Scale"].default_value = 40.0
    links.new(tc_tl.outputs["Object"], wave_tl.inputs["Vector"])

    tl_mix = nodes.new("ShaderNodeMix")
    tl_mix.data_type = 'RGBA'
    tl_mix.inputs[6].default_value = (0.78, 0.04, 0.05, 1.0)
    tl_mix.inputs[7].default_value = (0.36, 0.01, 0.02, 1.0)
    links.new(wave_tl.outputs["Fac"], tl_mix.inputs["Factor"])

    tl_bump = nodes.new("ShaderNodeBump")
    tl_bump.inputs["Strength"].default_value = 0.25
    tl_bump.inputs["Distance"].default_value = 0.003
    links.new(wave_tl.outputs["Fac"], tl_bump.inputs["Height"])

    links.new(tl_mix.outputs[2], get_bsdf_input(bsdf, ["Base Color"]))
    links.new(tl_bump.outputs["Normal"], get_bsdf_input(bsdf, ["Normal"]))
    mats["taillight"] = mat_tl

    # 7. Tyre_Mat: Black rubber with sidewall lettering hint (noise) + lower dirt
    mat_tyre = bpy.data.materials.new("Tyre_Mat")
    mat_tyre.use_nodes = True
    nodes = mat_tyre.node_tree.nodes
    links = mat_tyre.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    set_bsdf_input(bsdf, ["Metallic"], 0.0)
    set_bsdf_input(bsdf, ["Specular IOR Level", "Specular"], 0.22)

    tc_t = nodes.new("ShaderNodeTexCoord")
    noise_sidewall = nodes.new("ShaderNodeTexNoise")
    noise_sidewall.inputs["Scale"].default_value = 95.0
    noise_sidewall.inputs["Detail"].default_value = 8.0
    noise_sidewall.inputs["Roughness"].default_value = 0.75
    links.new(tc_t.outputs["Object"], noise_sidewall.inputs["Vector"])

    sw_remap = nodes.new("ShaderNodeMapRange")
    sw_remap.clamp = True
    sw_remap.inputs["From Min"].default_value = 0.58
    sw_remap.inputs["From Max"].default_value = 0.75
    sw_remap.inputs["To Min"].default_value = 0.0
    sw_remap.inputs["To Max"].default_value = 1.0
    links.new(noise_sidewall.outputs["Fac"], sw_remap.inputs["Value"])

    tyre_col_mix = nodes.new("ShaderNodeMix")
    tyre_col_mix.data_type = 'RGBA'
    tyre_col_mix.inputs[6].default_value = (0.065, 0.068, 0.072, 1.0)
    tyre_col_mix.inputs[7].default_value = (0.14, 0.145, 0.15, 1.0)
    links.new(sw_remap.outputs["Result"], tyre_col_mix.inputs["Factor"])

    tyre_bump = nodes.new("ShaderNodeBump")
    tyre_bump.inputs["Strength"].default_value = 0.35
    tyre_bump.inputs["Distance"].default_value = 0.003
    links.new(sw_remap.outputs["Result"], tyre_bump.inputs["Height"])

    col_out, rough_out, norm_out, _, _ = add_dirt_overlay(
        nodes, links, tyre_col_mix.outputs[2], 0.72, tyre_bump.outputs["Normal"]
    )
    links.new(col_out, get_bsdf_input(bsdf, ["Base Color"]))
    links.new(rough_out, get_bsdf_input(bsdf, ["Roughness"]))
    links.new(norm_out, get_bsdf_input(bsdf, ["Normal"]))
    mats["tyre"] = mat_tyre

    # 8. AlloyRim_Mat: 17-inch silver alloy rims
    mat_rim = bpy.data.materials.new("AlloyRim_Mat")
    mat_rim.use_nodes = True
    nodes = mat_rim.node_tree.nodes
    links = mat_rim.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    set_bsdf_input(bsdf, ["Metallic"], 0.22)
    set_bsdf_input(bsdf, ["Coat Weight", "Clearcoat"], 0.8)

    col_out, rough_out, norm_out, _, _ = add_dirt_overlay(
        nodes, links, (0.72, 0.75, 0.79, 1.0), 0.18, None
    )
    links.new(col_out, get_bsdf_input(bsdf, ["Base Color"]))
    links.new(rough_out, get_bsdf_input(bsdf, ["Roughness"]))
    links.new(norm_out, get_bsdf_input(bsdf, ["Normal"]))
    mats["rim"] = mat_rim

    # 9. Brake_Mat: Brushed steel brake discs
    mat_brake = bpy.data.materials.new("Brake_Mat")
    mat_brake.use_nodes = True
    nodes = mat_brake.node_tree.nodes
    links = mat_brake.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    set_bsdf_input(bsdf, ["Base Color"], (0.45, 0.47, 0.50, 1.0))
    set_bsdf_input(bsdf, ["Metallic"], 0.2)
    set_bsdf_input(bsdf, ["Roughness"], 0.35)
    mats["brake"] = mat_brake

    # 10. NumberPlate_Mat: White number plate with procedural dark characters
    mat_plate = bpy.data.materials.new("NumberPlate_Mat")
    mat_plate.use_nodes = True
    nodes = mat_plate.node_tree.nodes
    links = mat_plate.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    set_bsdf_input(bsdf, ["Roughness"], 0.3)

    tc_p = nodes.new("ShaderNodeTexCoord")
    sep_p = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc_p.outputs["Object"], sep_p.inputs["Vector"])
    abs_px = nodes.new("ShaderNodeMath")
    abs_px.operation = 'ABSOLUTE'
    links.new(sep_p.outputs["X"], abs_px.inputs[0])

    # Procedural character blocks along X within the plate width
    wave_px = nodes.new("ShaderNodeTexWave")
    wave_px.wave_type = 'BANDS'
    wave_px.bands_direction = 'X'
    wave_px.inputs["Scale"].default_value = 36.0
    links.new(tc_p.outputs["Object"], wave_px.inputs["Vector"])

    char_thresh = nodes.new("ShaderNodeMapRange")
    char_thresh.clamp = True
    char_thresh.inputs["From Min"].default_value = 0.52
    char_thresh.inputs["From Max"].default_value = 0.58
    char_thresh.inputs["To Min"].default_value = 0.0
    char_thresh.inputs["To Max"].default_value = 1.0
    links.new(wave_px.outputs["Fac"], char_thresh.inputs["Value"])

    px_zone = make_range_mask(nodes, links, abs_px.outputs["Value"], 0.0, 0.125, 0.004)
    char_mask = combine_masks(nodes, links, char_thresh.outputs["Result"], px_zone, 'MULTIPLY')

    plate_mix = nodes.new("ShaderNodeMix")
    plate_mix.data_type = 'RGBA'
    plate_mix.inputs[6].default_value = (0.94, 0.95, 0.97, 1.0)
    plate_mix.inputs[7].default_value = (0.08, 0.10, 0.16, 1.0)
    links.new(char_mask, plate_mix.inputs["Factor"])
    links.new(plate_mix.outputs[2], get_bsdf_input(bsdf, ["Base Color"]))
    mats["plate"] = mat_plate

    # 11. TaxiSign_Mat: White roof sign box with dark lettering hint
    mat_sign = bpy.data.materials.new("TaxiSign_Mat")
    mat_sign.use_nodes = True
    nodes = mat_sign.node_tree.nodes
    links = mat_sign.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    set_bsdf_input(bsdf, ["Base Color"], (0.96, 0.96, 0.92, 1.0))
    set_bsdf_input(bsdf, ["Roughness"], 0.22)
    mats["sign"] = mat_sign

    return mats


def assign_materials_to_obj(obj, mats_list):
    obj.data.materials.clear()
    for m in mats_list:
        obj.data.materials.append(m)


def build_car_body(mats):
    # Profile stations along Y from -2.44 (front) to +2.44 (rear)
    # Columns: (y, z_center, z_rail, z_belt, z_shoulder, w_top, w_body, y_sweep)
    stations = [
        (-2.36, 0.18, 0.18, 0.20, 0.19, 0.72, 0.78, 0.10),
        (-2.44, 0.34, 0.34, 0.36, 0.30, 0.76, 0.84, 0.12),
        (-2.43, 0.56, 0.56, 0.54, 0.46, 0.78, 0.88, 0.11),
        (-2.32, 0.70, 0.69, 0.66, 0.58, 0.80, 0.91, 0.08),
        (-2.12, 0.77, 0.76, 0.73, 0.65, 0.82, 0.95, 0.04),
        (-1.94, 0.81, 0.80, 0.78, 0.70, 0.84, 0.98, 0.02),
        # Front wheel arch stations (center Y = -1.41, R = 0.375)
        (-1.785, 0.84, 0.83, 0.81, 0.73, 0.85, 0.995, 0.0),
        (-1.69,  0.86, 0.85, 0.83, 0.75, 0.85, 1.00,  0.0),
        (-1.56,  0.88, 0.87, 0.85, 0.77, 0.86, 1.00,  0.0),
        (-1.41,  0.895, 0.885, 0.865, 0.78, 0.86, 1.00, 0.0),
        (-1.26,  0.91, 0.90, 0.88, 0.79, 0.86, 1.00,  0.0),
        (-1.13,  0.925, 0.915, 0.895, 0.80, 0.86, 1.00, 0.0),
        (-1.035, 0.935, 0.925, 0.905, 0.81, 0.86, 0.995, 0.0),
        # Cowl & Windscreen & Cabin
        (-0.90, 0.945, 0.94, 0.915, 0.82, 0.85, 0.99, 0.0),
        (-0.68, 1.12,  1.13, 0.925, 0.83, 0.76, 0.99, 0.0),
        (-0.46, 1.28,  1.29, 0.935, 0.84, 0.70, 0.99, 0.0),
        (-0.24, 1.415, 1.40, 0.945, 0.845, 0.65, 0.99, 0.0),
        ( 0.00, 1.445, 1.425, 0.955, 0.85, 0.64, 0.99, 0.0),
        ( 0.25, 1.450, 1.430, 0.965, 0.855, 0.64, 0.99, 0.0),
        ( 0.52, 1.435, 1.415, 0.975, 0.865, 0.64, 0.995, 0.0),
        ( 0.80, 1.390, 1.375, 0.990, 0.88, 0.65, 1.00, 0.0),
        # Rear wheel arch stations (center Y = +1.41, R = 0.375) & C-pillar / Rear glass
        ( 1.035, 1.26, 1.27, 1.005, 0.89, 0.69, 1.00, 0.0),
        ( 1.13,  1.20, 1.21, 1.01,  0.895, 0.71, 1.00, 0.0),
        ( 1.26,  1.12, 1.13, 1.015, 0.90, 0.74, 1.00, 0.0),
        ( 1.41,  1.04, 1.045, 1.02, 0.905, 0.77, 1.00, 0.0),
        ( 1.56,  1.035, 1.03, 1.015, 0.90, 0.78, 1.00, 0.0),
        ( 1.69,  1.03, 1.025, 1.01, 0.895, 0.78, 1.00, 0.0),
        ( 1.785, 1.025, 1.02, 1.00, 0.89, 0.77, 0.995, 0.0),
        # Trunk & Rear Bumper
        ( 2.04, 1.015, 1.01, 0.98, 0.87, 0.75, 0.96, -0.03),
        ( 2.26, 1.015, 1.00, 0.95, 0.84, 0.72, 0.92, -0.06),
        ( 2.38, 0.84,  0.83, 0.80, 0.72, 0.70, 0.89, -0.09),
        ( 2.44, 0.62,  0.61, 0.58, 0.50, 0.68, 0.86, -0.10),
        ( 2.43, 0.36,  0.36, 0.35, 0.30, 0.66, 0.83, -0.09),
        ( 2.34, 0.20,  0.20, 0.21, 0.20, 0.64, 0.78, -0.07),
    ]

    bm = bmesh.new()
    half_W = 0.92  # 1.84 m total width
    z_axle = 0.334
    r_arch = 0.375

    rings = []
    for st in stations:
        y_base, z_c, z_r, z_b, z_sh, w_top, w_body, y_sw = st

        # Check front or rear wheel arch proximity
        dy_f = abs(y_base - (-1.41))
        dy_r = abs(y_base - 1.41)
        in_arch = False
        arch_h = 0.0
        flare_h = 0.0
        flare_x = 0.0
        if dy_f < r_arch - 0.001:
            in_arch = True
            arch_h = math.sqrt(max(0.0, r_arch * r_arch - dy_f * dy_f))
            flare_h = math.sqrt(max(0.0, (r_arch + 0.055) ** 2 - dy_f * dy_f))
            flare_x = 0.014 * (arch_h / r_arch)
        elif dy_r < r_arch - 0.001:
            in_arch = True
            arch_h = math.sqrt(max(0.0, r_arch * r_arch - dy_r * dy_r))
            flare_h = math.sqrt(max(0.0, (r_arch + 0.055) ** 2 - dy_r * dy_r))
            flare_x = 0.014 * (arch_h / r_arch)

        z_sill = 0.175
        if in_arch:
            z_arch_cut = max(z_sill, z_axle + arch_h)
            z_arch_flare = max(0.35, z_axle + flare_h)
        else:
            z_arch_cut = z_sill
            z_arch_flare = min(0.36, z_sh - 0.04)

        # Recession in side window zone (-0.68 <= y <= 1.26)
        in_cabin_side = (-0.70 <= y_base <= 1.28)
        win_inset = 0.022 if in_cabin_side else 0.0
        in_windscreen = (-0.75 <= y_base <= -0.35) or (0.95 <= y_base <= 1.30)
        top_inset = -0.018 if in_windscreen else 0.0

        # Right side cross-section points j = 0 .. 11 (from top center to bottom center)
        x_top_edge = half_W * w_top
        x_belt = half_W * w_body * 0.935
        x_shoulder = half_W * w_body * 0.992
        x_mid_door = half_W * w_body * (1.00 + flare_x)
        x_flare = half_W * w_body * (0.985 + flare_x)
        x_sill = half_W * w_body * (0.955 + flare_x * 0.5)

        pts_right = [
            (0.0,                        y_base,                z_c + top_inset),
            (x_top_edge * 0.48,          y_base + y_sw * 0.18,  z_c - 0.005 + top_inset),
            (x_top_edge * 0.88,          y_base + y_sw * 0.45,  z_r - 0.004 + top_inset * 0.5),
            (x_top_edge * 1.00,          y_base + y_sw * 0.60,  z_r),
            (0.5 * (x_top_edge + x_belt) - win_inset, y_base + y_sw * 0.75, 0.5 * (z_r + z_b)),
            (x_belt,                     y_base + y_sw * 0.88,  z_b),
            (x_shoulder,                 y_base + y_sw * 0.96,  z_sh),
            (x_mid_door,                 y_base + y_sw * 1.00,  0.54 * z_sh + 0.46 * z_arch_flare),
            (x_flare,                    y_base + y_sw * 0.98,  z_arch_flare),
            (x_sill,                     y_base + y_sw * 0.92,  z_arch_cut),
            (0.52 * w_body,              y_base + y_sw * 0.50,  z_arch_cut),
            (0.50 * w_body,              y_base + y_sw * 0.45,  0.17),
            (0.0,                        y_base,                0.17),
        ]

        # Build full closed loop around X (right side 0..12, then left side 11..1 mirrored)
        ring_verts = []
        for x, y, z in pts_right:
            ring_verts.append(bm.verts.new((x, y, z)))
        for idx in range(len(pts_right) - 2, 0, -1):
            x, y, z = pts_right[idx]
            ring_verts.append(bm.verts.new((-x, y, z)))
        rings.append((y_base, in_arch, ring_verts))

    bm.verts.ensure_lookup_table()
    n_loop = len(rings[0][2])

    for i in range(len(rings) - 1):
        y0, arch0, r0 = rings[i]
        y1, arch1, r1 = rings[i + 1]
        y_mid = 0.5 * (y0 + y1)
        for j in range(n_loop):
            jn = (j + 1) % n_loop
            v00 = r0[j]
            v01 = r0[jn]
            v11 = r1[jn]
            v10 = r1[j]
            try:
                f = bm.faces.new((v00, v01, v11, v10))
            except ValueError:
                continue
            f.smooth = True

            # Determine material assignment for each quad
            # Right side indices: 0..12, Left side indices: 13..23
            j_sym = j if j <= 12 else (24 - j)
            if j_sym >= 9:
                # Wheel well liner or underbody or lower sill
                f.material_index = 1  # BlackTrim_Mat
            elif j_sym == 8 and (y_mid < -2.30 or y_mid > 2.30 or (-1.02 < y_mid < 1.02)):
                # Lower rocker skirt and front/rear lower valence
                f.material_index = 1  # BlackTrim_Mat
            elif j_sym in (3, 4) and (-0.70 < y_mid < 1.25):
                # Inner window frame recess
                f.material_index = 1  # BlackTrim_Mat
            else:
                f.material_index = 0  # TaxiPaint_Mat

    # Cap front nose and rear tail if needed
    bm.edges.ensure_lookup_table()
    for e in bm.edges:
        e.smooth = True

    mesh = bpy.data.meshes.new("CarBody_Mesh")
    bm.to_mesh(mesh)
    bm.free()

    body_obj = bpy.data.objects.new("CarBody", mesh)
    bpy.context.collection.objects.link(body_obj)
    assign_materials_to_obj(body_obj, [mats["paint"], mats["trim"]])

    # Apply Subdivision Surface modifier (Level 1) as requested
    bpy.context.view_layer.objects.active = body_obj
    body_obj.select_set(True)
    sub = body_obj.modifiers.new(name="Subsurf", type='SUBSURF')
    sub.levels = 1
    sub.render_levels = 1
    bpy.ops.object.modifier_apply(modifier=sub.name)

    return body_obj


def create_grid_surface(name, u_steps, v_steps, eval_fn, mat, flip_normals=False):
    bm = bmesh.new()
    grid = []
    for iu in range(u_steps + 1):
        u = iu / float(u_steps)
        row = []
        for iv in range(v_steps + 1):
            v = iv / float(v_steps)
            co = eval_fn(u, v)
            row.append(bm.verts.new(co))
        grid.append(row)

    for iu in range(u_steps):
        for iv in range(v_steps):
            v00 = grid[iu][iv]
            v10 = grid[iu + 1][iv]
            v11 = grid[iu + 1][iv + 1]
            v01 = grid[iu][iv + 1]
            verts = (v00, v01, v11, v10) if flip_normals else (v00, v10, v11, v01)
            f = bm.faces.new(verts)
            f.smooth = True

    mesh = bpy.data.meshes.new(name + "_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    assign_materials_to_obj(obj, [mat])
    return obj


def create_extruded_strip(name, path_pts, half_w, thickness, mat):
    bm = bmesh.new()
    rings = []
    n = len(path_pts)
    for i, (p, up_vec, side_vec) in enumerate(path_pts):
        p = Vector(p)
        u = Vector(up_vec).normalized() * half_w
        s = Vector(side_vec).normalized() * thickness
        c0 = bm.verts.new(p - u)
        c1 = bm.verts.new(p - u + s)
        c2 = bm.verts.new(p + u + s)
        c3 = bm.verts.new(p + u)
        rings.append((c0, c1, c2, c3))

    for i in range(n - 1):
        r0 = rings[i]
        r1 = rings[i + 1]
        for k in range(4):
            kn = (k + 1) % 4
            f = bm.faces.new((r0[k], r0[kn], r1[kn], r1[k]))
            f.smooth = True
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])

    mesh = bpy.data.meshes.new(name + "_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    assign_materials_to_obj(obj, [mat])
    return obj


def build_windows_and_pillars(mats):
    parts = []

    # 1. Front Windscreen (inset slightly into the body)
    def windscreen_fn(u, v):
        # u: -1 to 1 across X; v: 0 (bottom cowl) to 1 (roof header)
        s = (u - 0.5) * 2.0
        w = (1.0 - v) * 0.66 + v * 0.555
        x = s * w
        arch_s = 1.0 - s * s
        y = (1.0 - v) * (-0.905) + v * (-0.245) - 0.055 * arch_s
        z = (1.0 - v) * 0.948 + v * 1.408 + 0.024 * arch_s
        return (x, y, z)

    parts.append(create_grid_surface("Windscreen", 8, 6, windscreen_fn, mats["glass"], flip_normals=False))

    # 2. Rear Window / Backlight (inset slightly)
    def rear_window_fn(u, v):
        # u: 0..1 across X; v: 0 (roof rear) to 1 (trunk deck base)
        s = (u - 0.5) * 2.0
        w = (1.0 - v) * 0.545 + v * 0.625
        x = s * w
        arch_s = 1.0 - s * s
        y = (1.0 - v) * 0.79 + v * 1.42 + 0.045 * arch_s
        z = (1.0 - v) * 1.385 + v * 1.040 + 0.020 * arch_s
        return (x, y, z)

    parts.append(create_grid_surface("RearWindow", 8, 6, rear_window_fn, mats["glass"], flip_normals=True))

    # 3. Side Windows (Front door, Rear door, Quarter window) + A/B/C Pillars + Chrome Trim
    for side in (-1.0, 1.0):
        flip = (side < 0)

        # Front door glass
        def front_side_glass(u, v, s=side):
            y = (1.0 - u) * (-0.68) + u * 0.16
            z_bot = (1.0 - u) * 0.928 + u * 0.958
            z_top = (1.0 - u) * (1.14 + u * 0.27) + u * 1.405
            if u < 0.48:
                t = u / 0.48
                z_top = (1.0 - t) * 1.12 + t * 1.395
            else:
                t = (u - 0.48) / 0.52
                z_top = (1.0 - t) * 1.395 + t * 1.410
            z = (1.0 - v) * z_bot + v * z_top
            x_bot = 0.840
            x_top = 0.600 + 0.03 * (1.0 - u)
            x = s * ((1.0 - v) * x_bot + v * x_top + 0.012 * math.sin(v * math.pi))
            return (x, y, z)

        parts.append(create_grid_surface(f"FrontSideGlass_{side}", 6, 4, front_side_glass, mats["glass"], flip_normals=flip))

        # Rear door glass
        def rear_side_glass(u, v, s=side):
            y = (1.0 - u) * 0.22 + u * 0.92
            z_bot = (1.0 - u) * 0.960 + u * 0.992
            z_top = (1.0 - u) * 1.410 + u * 1.355
            z = (1.0 - v) * z_bot + v * z_top
            x_bot = 0.845
            x_top = 0.600 + 0.025 * u
            x = s * ((1.0 - v) * x_bot + v * x_top + 0.012 * math.sin(v * math.pi))
            return (x, y, z)

        parts.append(create_grid_surface(f"RearSideGlass_{side}", 6, 4, rear_side_glass, mats["glass"], flip_normals=flip))

        # Rear quarter glass
        def quarter_glass(u, v, s=side):
            y = (1.0 - u) * 0.95 + u * 1.24
            z_bot = (1.0 - u) * 0.994 + u * 1.015
            z_top = (1.0 - u) * 1.345 + u * 1.055
            z = (1.0 - v) * z_bot + v * z_top
            x_bot = 0.842 - 0.03 * u
            x_top = 0.625 + 0.14 * u
            x = s * ((1.0 - v) * x_bot + v * x_top)
            return (x, y, z)

        parts.append(create_grid_surface(f"QuarterGlass_{side}", 4, 3, quarter_glass, mats["glass"], flip_normals=flip))

        # A-pillar
        a_pts = [
            ((side * 0.73, -0.92, 0.95), (0, 0.4, 0.9), (side, -0.3, 0.3)),
            ((side * 0.68, -0.68, 1.13), (0, 0.4, 0.9), (side, -0.3, 0.3)),
            ((side * 0.63, -0.45, 1.29), (0, 0.4, 0.9), (side, -0.3, 0.3)),
            ((side * 0.59, -0.22, 1.415), (0, 0.5, 0.85), (side, -0.2, 0.4)),
        ]
        parts.append(create_extruded_strip(f"APillar_{side}", a_pts, 0.034, 0.024, mats["paint"]))

        # B-pillar (gloss black vertical divider between front and rear doors)
        b_pts = [
            ((side * 0.848, 0.19, 0.955), (0, 1, 0), (side, 0, 0.2)),
            ((side * 0.740, 0.19, 1.180), (0, 1, 0), (side, 0, 0.3)),
            ((side * 0.605, 0.19, 1.412), (0, 1, 0), (side, 0, 0.4)),
        ]
        parts.append(create_extruded_strip(f"BPillar_{side}", b_pts, 0.042, 0.018, mats["trim"]))

        # Quarter window divider bar
        q_pts = [
            ((side * 0.846, 0.935, 0.992), (0, 1, 0), (side, 0, 0.2)),
            ((side * 0.730, 0.935, 1.175), (0, 1, 0), (side, 0, 0.3)),
            ((side * 0.620, 0.935, 1.350), (0, 1, 0), (side, 0, 0.4)),
        ]
        parts.append(create_extruded_strip(f"QPillar_{side}", q_pts, 0.018, 0.016, mats["trim"]))

        # C-pillar
        c_pts = [
            ((side * 0.595, 0.78, 1.392), (0, 0.6, 0.8), (side, 0.2, 0.4)),
            ((side * 0.650, 1.02, 1.275), (0, 0.6, 0.8), (side, 0.2, 0.4)),
            ((side * 0.715, 1.24, 1.140), (0, 0.6, 0.8), (side, 0.2, 0.4)),
            ((side * 0.775, 1.44, 1.035), (0, 0.6, 0.8), (side, 0.2, 0.4)),
        ]
        parts.append(create_extruded_strip(f"CPillar_{side}", c_pts, 0.048, 0.025, mats["paint"]))

        # Chrome Window Trim (Beltline + Upper Roof Arch surround)
        belt_pts = [
            ((side * 0.848, -0.72, 0.925), (0, 0, 1), (side, 0, 0)),
            ((side * 0.858, -0.25, 0.945), (0, 0, 1), (side, 0, 0)),
            ((side * 0.862,  0.25, 0.965), (0, 0, 1), (side, 0, 0)),
            ((side * 0.862,  0.80, 0.990), (0, 0, 1), (side, 0, 0)),
            ((side * 0.835,  1.26, 1.018), (0, 0, 1), (side, 0, 0)),
        ]
        parts.append(create_extruded_strip(f"ChromeBelt_{side}", belt_pts, 0.011, 0.012, mats["chrome"]))

        arch_trim_pts = [
            ((side * 0.838, -0.72, 0.935), (0, 0, 1), (side, 0, 0)),
            ((side * 0.675, -0.50, 1.240), (0, 0, 1), (side, 0, 0.3)),
            ((side * 0.605, -0.22, 1.408), (0, 0, 1), (side, 0, 0.4)),
            ((side * 0.598,  0.25, 1.422), (0, 0, 1), (side, 0, 0.4)),
            ((side * 0.605,  0.78, 1.382), (0, 0, 1), (side, 0, 0.4)),
            ((side * 0.695,  1.05, 1.220), (0, 0, 1), (side, 0, 0.3)),
            ((side * 0.830,  1.26, 1.030), (0, 0, 1), (side, 0, 0)),
        ]
        parts.append(create_extruded_strip(f"ChromeArch_{side}", arch_trim_pts, 0.010, 0.012, mats["chrome"]))

    return parts


def create_box_mesh(bm, center, size, rot_euler=(0.0, 0.0, 0.0), mat_idx=0, bevel=False):
    cx, cy, cz = center
    sx, sy, sz = size
    mat_rot = mathutils.Euler(rot_euler, 'XYZ').to_matrix().to_4x4()
    mat_xf = Matrix.Translation((cx, cy, cz)) @ mat_rot
    res = bmesh.ops.create_cube(bm, size=1.0)
    verts = res["verts"]
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=verts)
    bmesh.ops.transform(bm, matrix=mat_xf, verts=verts)
    for f in bm.faces:
        if all(v in verts for v in f.verts):
            f.material_index = mat_idx
            f.smooth = bevel
    return verts


def build_interior_silhouette(mats):
    bm = bmesh.new()
    # Dashboard
    create_box_mesh(bm, (0.0, -0.68, 0.88), (1.36, 0.36, 0.24), (0.15, 0.0, 0.0), 0)
    # Steering wheel
    mat_sw = Matrix.Translation((-0.36, -0.45, 0.95)) @ mathutils.Euler((1.15, 0.0, 0.0), 'XYZ').to_matrix().to_4x4()
    bmesh.ops.create_circle(bm, cap_ends=True, radius=0.17, segments=12, matrix=mat_sw)
    # Front seats + headrests
    for sx in (-0.36, 0.36):
        create_box_mesh(bm, (sx, -0.08, 0.62), (0.46, 0.48, 0.14), (0.0, 0.0, 0.0), 0)
        create_box_mesh(bm, (sx, 0.08, 0.88), (0.44, 0.12, 0.46), (-0.22, 0.0, 0.0), 0)
        create_box_mesh(bm, (sx, 0.14, 1.18), (0.22, 0.10, 0.16), (-0.15, 0.0, 0.0), 0)
    # Rear bench + headrests
    create_box_mesh(bm, (0.0, 0.78, 0.64), (1.28, 0.46, 0.16), (0.0, 0.0, 0.0), 0)
    create_box_mesh(bm, (0.0, 0.96, 0.90), (1.26, 0.14, 0.44), (-0.20, 0.0, 0.0), 0)
    for sx in (-0.38, 0.38):
        create_box_mesh(bm, (sx, 1.04, 1.18), (0.22, 0.10, 0.14), (-0.12, 0.0, 0.0), 0)

    mesh = bpy.data.meshes.new("Interior_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("Interior", mesh)
    bpy.context.collection.objects.link(obj)
    assign_materials_to_obj(obj, [mats["trim"]])
    return obj


def build_bumpers_and_grilles(mats):
    bm = bmesh.new()
    # Front lower Camry wide trapezoidal grille backing + 5 horizontal slats + splitter lip
    create_box_mesh(bm, (0.0, -2.415, 0.33), (1.26, 0.04, 0.24), (0.0, 0.0, 0.0), 0)
    for iz in range(5):
        z_slat = 0.22 + iz * 0.052
        w_slat = 1.32 - iz * 0.05
        create_box_mesh(bm, (0.0, -2.438 + iz * 0.003, z_slat), (w_slat, 0.035, 0.016), (0.0, 0.0, 0.0), 0)
    # Front lower lip spoiler
    create_box_mesh(bm, (0.0, -2.425, 0.185), (1.56, 0.10, 0.028), (0.0, 0.0, 0.0), 0)
    # Side fog-light intakes
    for sx in (-1.0, 1.0):
        create_box_mesh(bm, (sx * 0.72, -2.35, 0.32), (0.20, 0.06, 0.20), (0.0, 0.0, sx * 0.32), 0)
    # Upper grille V-wing & central chrome emblem
    create_box_mesh(bm, (0.0, -2.405, 0.625), (0.86, 0.045, 0.055), (0.12, 0.0, 0.0), 0)
    create_box_mesh(bm, (0.0, -2.428, 0.630), (0.13, 0.03, 0.085), (0.15, 0.0, 0.0), 1, bevel=True)

    # Rear lower diffuser valence + vertical fins + dual chrome exhaust pipes
    create_box_mesh(bm, (0.0, 2.415, 0.28), (1.42, 0.06, 0.16), (-0.12, 0.0, 0.0), 0)
    for sx in (-0.42, -0.14, 0.14, 0.42):
        create_box_mesh(bm, (sx, 2.435, 0.25), (0.02, 0.05, 0.11), (0.0, 0.0, 0.0), 0)

    # Dual exhaust pipes (left and right)
    for sx in (-0.58, 0.58):
        mat_ex = Matrix.Translation((sx, 2.41, 0.23)) @ mathutils.Euler((math.pi * 0.5, 0.0, 0.0), 'XYZ').to_matrix().to_4x4()
        res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=16, radius1=0.042, radius2=0.040, depth=0.14, matrix=mat_ex)
        for v in res["verts"]:
            for f in v.link_faces:
                f.material_index = 1
                f.smooth = True

    mesh = bpy.data.meshes.new("BumpersGrilles_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("BumpersGrilles", mesh)
    bpy.context.collection.objects.link(obj)
    assign_materials_to_obj(obj, [mats["trim"], mats["chrome"]])
    return obj


def build_lights(mats):
    parts = []
    # Headlights: reflector housing + internal projector domes + clear outer lens
    for side in (-1.0, 1.0):
        flip = (side < 0)

        def hl_reflector_fn(u, v, s=side):
            x = s * ((1.0 - u) * 0.44 + u * 0.84)
            y_base = (1.0 - u) * (-2.39) + u * (-2.04)
            z_bot = (1.0 - u) * 0.59 + u * 0.64
            z_top = (1.0 - u) * 0.67 + u * 0.74
            z = (1.0 - v) * z_bot + v * z_top
            depth = 0.032 * math.sin(u * math.pi) * math.sin(v * math.pi)
            y = y_base + depth
            return (x, y, z)

        def hl_lens_fn(u, v, s=side):
            x = s * ((1.0 - u) * 0.44 + u * 0.84)
            y_base = (1.0 - u) * (-2.395) + u * (-2.045)
            z_bot = (1.0 - u) * 0.59 + u * 0.64
            z_top = (1.0 - u) * 0.67 + u * 0.74
            z = (1.0 - v) * z_bot + v * z_top
            bulge = -0.012 * math.sin(u * math.pi) * math.sin(v * math.pi)
            y = y_base + bulge
            return (x, y, z)

        parts.append(create_grid_surface(f"HLReflector_{side}", 6, 4, hl_reflector_fn, mats["chrome"], flip_normals=flip))
        parts.append(create_grid_surface(f"HLLens_{side}", 6, 4, hl_lens_fn, mats["headlight"], flip_normals=flip))

        # Taillights: inner reflector + red wrap-around outer lens
        def tl_reflector_fn(u, v, s=side):
            x = s * ((1.0 - u) * 0.38 + u * 0.83)
            y_base = (1.0 - u) * 2.40 + u * 2.12
            z_bot = (1.0 - u) * 0.74 + u * 0.78
            z_top = (1.0 - u) * 0.86 + u * 0.91
            z = (1.0 - v) * z_bot + v * z_top
            depth = -0.025 * math.sin(u * math.pi) * math.sin(v * math.pi)
            y = y_base + depth
            return (x, y, z)

        def tl_lens_fn(u, v, s=side):
            x = s * ((1.0 - u) * 0.38 + u * 0.835)
            y_base = (1.0 - u) * 2.408 + u * 2.125
            z_bot = (1.0 - u) * 0.74 + u * 0.78
            z_top = (1.0 - u) * 0.86 + u * 0.91
            z = (1.0 - v) * z_bot + v * z_top
            bulge = 0.012 * math.sin(u * math.pi) * math.sin(v * math.pi)
            y = y_base + bulge
            return (x, y, z)

        parts.append(create_grid_surface(f"TLReflector_{side}", 6, 4, tl_reflector_fn, mats["chrome"], flip_normals=not flip))
        parts.append(create_grid_surface(f"TLLens_{side}", 6, 4, tl_lens_fn, mats["taillight"], flip_normals=not flip))

    return parts


def build_exterior_details(mats):
    bm = bmesh.new()
    # Material indices: 0=paint, 1=trim, 2=chrome, 3=plate, 4=sign

    # 1. Side Mirrors (Left and Right)
    for sx in (-1.0, 1.0):
        # Mirror stalk
        create_box_mesh(bm, (sx * 0.86, -0.58, 0.93), (0.09, 0.05, 0.03), (0.0, sx * 0.25, 0.0), 1, bevel=True)
        # Sculpted mirror cap (yellow paint)
        create_box_mesh(bm, (sx * 0.94, -0.56, 0.965), (0.13, 0.09, 0.085), (0.1, 0.0, sx * -0.18), 0, bevel=True)
        # Mirror glass face on +Y side
        create_box_mesh(bm, (sx * 0.94, -0.515, 0.965), (0.115, 0.012, 0.072), (0.0, 0.0, sx * -0.18), 2, bevel=False)

    # 2. Door Handles (4 handles: front & rear on both sides)
    for sx in (-1.0, 1.0):
        for y_h, z_h in [(-0.02, 0.855), (0.76, 0.880)]:
            # Handle bar + front/rear mounts
            create_box_mesh(bm, (sx * 0.916, y_h, z_h), (0.022, 0.16, 0.026), (0.0, 0.0, 0.0), 0, bevel=True)
            create_box_mesh(bm, (sx * 0.902, y_h - 0.065, z_h), (0.025, 0.03, 0.024), (0.0, 0.0, 0.0), 0, bevel=True)
            create_box_mesh(bm, (sx * 0.902, y_h + 0.065, z_h), (0.025, 0.03, 0.024), (0.0, 0.0, 0.0), 0, bevel=True)

    # 3. Windscreen Wipers (2 front wipers at base of windshield)
    for x0, x1, y_w, z_w in [(-0.54, 0.04, -0.89, 0.958), (-0.04, 0.52, -0.90, 0.955)]:
        cx = 0.5 * (x0 + x1)
        length = abs(x1 - x0)
        create_box_mesh(bm, (cx, y_w, z_w), (length, 0.018, 0.014), (0.25, 0.0, 0.06), 1)
        create_box_mesh(bm, (x0 + 0.08, y_w - 0.02, z_w - 0.005), (0.18, 0.012, 0.010), (0.25, 0.0, -0.12), 1)

    # 4. Number Plates Front and Back (white plate with dark characters)
    for y_p, z_p, tilt, sign_dir in [(-2.448, 0.43, 0.05, -1.0), (2.418, 0.76, -0.12, 1.0)]:
        # Black surround frame
        create_box_mesh(bm, (0.0, y_p, z_p), (0.32, 0.012, 0.16), (tilt, 0.0, 0.0), 1)
        # White plate face
        create_box_mesh(bm, (0.0, y_p + sign_dir * 0.004, z_p), (0.30, 0.010, 0.14), (tilt, 0.0, 0.0), 3)
        # Dark character strokes across plate center ("7Y48A")
        for idx, cx in enumerate([-0.10, -0.05, 0.0, 0.05, 0.10]):
            create_box_mesh(bm, (cx, y_p + sign_dir * 0.008, z_p - 0.005), (0.024, 0.006, 0.068), (tilt, 0.0, 0.0), 1)

    # 5. NYC Roof Sign Box "TAXI" (white box on roof with dark "TAXI" letters)
    sign_y = -0.04
    sign_z = 1.495
    # Black base pedestal mounts
    create_box_mesh(bm, (0.0, sign_y, 1.452), (0.44, 0.18, 0.022), (0.0, 0.0, 0.0), 1)
    # White aerodynamic roof sign box
    res_sign = bmesh.ops.create_cube(bm, size=1.0)
    s_verts = res_sign["verts"]
    for v in s_verts:
        vx, vy, vz = v.co.x, v.co.y, v.co.z
        top_taper = 0.82 if vz > 0 else 1.0
        v.co.x = vx * 0.44 * top_taper
        v.co.y = vy * 0.18 * (0.75 if vz > 0 else 1.0) + sign_y
        v.co.z = vz * 0.095 + sign_z
        for f in v.link_faces:
            f.material_index = 4
            f.smooth = True

    # Crisp 3D dark "TAXI" letters on front (-Y) and back (+Y) of roof sign box
    for y_face, tilt_x in [(sign_y - 0.082, -0.18), (sign_y + 0.082, 0.18)]:
        # Letter T (centered at x = -0.125)
        create_box_mesh(bm, (-0.125, y_face, sign_z + 0.022), (0.048, 0.008, 0.011), (tilt_x, 0.0, 0.0), 1)
        create_box_mesh(bm, (-0.125, y_face, sign_z - 0.002), (0.012, 0.008, 0.054), (tilt_x, 0.0, 0.0), 1)
        # Letter A (centered at x = -0.042)
        create_box_mesh(bm, (-0.054, y_face, sign_z - 0.002), (0.011, 0.008, 0.056), (tilt_x, -0.18, 0.0), 1)
        create_box_mesh(bm, (-0.030, y_face, sign_z - 0.002), (0.011, 0.008, 0.056), (tilt_x, 0.18, 0.0), 1)
        create_box_mesh(bm, (-0.042, y_face, sign_z - 0.005), (0.032, 0.008, 0.010), (tilt_x, 0.0, 0.0), 1)
        # Letter X (centered at x = +0.042)
        create_box_mesh(bm, (0.042, y_face, sign_z - 0.002), (0.011, 0.008, 0.060), (tilt_x, 0.42, 0.0), 1)
        create_box_mesh(bm, (0.042, y_face, sign_z - 0.002), (0.011, 0.008, 0.060), (tilt_x, -0.42, 0.0), 1)
        # Letter I (centered at x = +0.118)
        create_box_mesh(bm, (0.118, y_face, sign_z - 0.002), (0.013, 0.008, 0.056), (tilt_x, 0.0, 0.0), 1)

    # Shark-fin roof antenna at rear of roof
    create_box_mesh(bm, (0.0, 0.66, 1.445), (0.035, 0.14, 0.065), (-0.35, 0.0, 0.0), 0, bevel=True)

    mesh = bpy.data.meshes.new("ExteriorDetails_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("ExteriorDetails", mesh)
    bpy.context.collection.objects.link(obj)
    assign_materials_to_obj(obj, [mats["paint"], mats["trim"], mats["chrome"], mats["plate"], mats["sign"]])
    return obj


def build_four_wheels(mats):
    # Build all 4 wheels: tyre with sidewall + 17-inch multi-spoke silver alloy rim + brake disc & caliper behind
    # Material indices: 0=tyre, 1=rim, 2=brake, 3=trim (caliper/lug bolts)
    bm = bmesh.new()

    wheel_positions = [
        (-0.795, -1.41, 0.334, -1.0),
        ( 0.795, -1.41, 0.334,  1.0),
        (-0.795,  1.41, 0.334, -1.0),
        ( 0.795,  1.41, 0.334,  1.0),
    ]

    n_seg = 32
    r_tyre = 0.334
    r_rim = 0.216
    half_w = 0.108

    # Cross-section profile of tyre + outer rim barrel (local dx, radius)
    # Local dx > 0 is outward face of wheel
    tyre_profile = [
        (-half_w * 0.82, r_rim),
        (-half_w * 0.98, r_rim + 0.035),
        (-half_w * 1.02, r_rim + 0.075),
        (-half_w * 0.95, r_tyre - 0.016),
        (-half_w * 0.72, r_tyre),
        (-half_w * 0.22, r_tyre),
        ( half_w * 0.22, r_tyre),
        ( half_w * 0.72, r_tyre),
        ( half_w * 0.95, r_tyre - 0.016),
        ( half_w * 1.02, r_rim + 0.075),
        ( half_w * 0.98, r_rim + 0.035),
        ( half_w * 0.86, r_rim),
    ]

    rim_profile = [
        ( half_w * 0.86, r_rim),
        ( half_w * 0.92, r_rim - 0.010),
        ( half_w * 0.78, r_rim - 0.022),
        (-half_w * 0.45, r_rim - 0.026),
    ]

    for wx, wy, wz, side in wheel_positions:
        # 1. Tyre ring
        t_rings = []
        for dx, rad in tyre_profile:
            ring = []
            for iseg in range(n_seg):
                ang = (2.0 * math.pi * iseg) / n_seg
                px = wx + side * dx
                py = wy + rad * math.cos(ang)
                pz = wz + rad * math.sin(ang)
                ring.append(bm.verts.new((px, py, pz)))
            t_rings.append(ring)

        for ip in range(len(t_rings) - 1):
            r0 = t_rings[ip]
            r1 = t_rings[ip + 1]
            for iseg in range(n_seg):
                inext = (iseg + 1) % n_seg
                verts = (r0[iseg], r0[inext], r1[inext], r1[iseg]) if side > 0 else (r0[iseg], r1[iseg], r1[inext], r0[inext])
                f = bm.faces.new(verts)
                f.material_index = 0
                f.smooth = True

        # 2. Alloy Rim Barrel & Lip
        r_rings = []
        for dx, rad in rim_profile:
            ring = []
            for iseg in range(n_seg):
                ang = (2.0 * math.pi * iseg) / n_seg
                px = wx + side * dx
                py = wy + rad * math.cos(ang)
                pz = wz + rad * math.sin(ang)
                ring.append(bm.verts.new((px, py, pz)))
            r_rings.append(ring)

        for ip in range(len(r_rings) - 1):
            r0 = r_rings[ip]
            r1 = r_rings[ip + 1]
            for iseg in range(n_seg):
                inext = (iseg + 1) % n_seg
                verts = (r0[iseg], r0[inext], r1[inext], r1[iseg]) if side > 0 else (r0[iseg], r1[iseg], r1[inext], r0[inext])
                f = bm.faces.new(verts)
                f.material_index = 1
                f.smooth = True

        # 3. Center Hub Cap & 10 Multi-Spokes (5 V-spoke twin pairs)
        hub_r = 0.062
        hub_dx = half_w * 0.66
        cap_center = bm.verts.new((wx + side * (hub_dx + 0.006), wy, wz))
        hub_ring_front = []
        hub_ring_back = []
        n_hub = 20
        for ih in range(n_hub):
            ang = (2.0 * math.pi * ih) / n_hub
            cy = wy + hub_r * math.cos(ang)
            cz = wz + hub_r * math.sin(ang)
            hub_ring_front.append(bm.verts.new((wx + side * hub_dx, cy, cz)))
            hub_ring_back.append(bm.verts.new((wx + side * (hub_dx - 0.03), cy, cz)))

        for ih in range(n_hub):
            inh = (ih + 1) % n_hub
            verts_cap = (cap_center, hub_ring_front[ih], hub_ring_front[inh]) if side > 0 else (cap_center, hub_ring_front[inh], hub_ring_front[ih])
            f_cap = bm.faces.new(verts_cap)
            f_cap.material_index = 1
            f_cap.smooth = True

            verts_side = (hub_ring_front[ih], hub_ring_back[ih], hub_ring_back[inh], hub_ring_front[inh]) if side > 0 else (hub_ring_front[ih], hub_ring_front[inh], hub_ring_back[inh], hub_ring_back[ih])
            f_side = bm.faces.new(verts_side)
            f_side.material_index = 1
            f_side.smooth = True

        # 10 sculpted spokes (5 twin-spoke pairs)
        for pair_idx in range(5):
            base_ang = (2.0 * math.pi * pair_idx) / 5.0
            for sub_offset in (-0.18, 0.18):
                ang_in = base_ang + sub_offset * 0.65
                ang_out = base_ang + sub_offset * 1.15
                dir_in = Vector((0.0, math.cos(ang_in), math.sin(ang_in)))
                tan_in = Vector((0.0, -math.sin(ang_in), math.cos(ang_in)))
                dir_out = Vector((0.0, math.cos(ang_out), math.sin(ang_out)))
                tan_out = Vector((0.0, -math.sin(ang_out), math.cos(ang_out)))

                p_in = Vector((wx + side * (hub_dx - 0.004), wy, wz)) + dir_in * (hub_r * 0.88)
                p_mid = Vector((wx + side * (half_w * 0.85), wy, wz)) + (0.5 * (dir_in + dir_out)).normalized() * 0.135
                p_out = Vector((wx + side * (half_w * 0.82), wy, wz)) + dir_out * (r_rim - 0.014)

                w_in = 0.015
                w_mid = 0.013
                w_out = 0.016
                thick_vec = Vector((side * (-0.022), 0.0, 0.0))

                s_rings = []
                for pt, t_vec, sw in [(p_in, tan_in, w_in), (p_mid, 0.5 * (tan_in + tan_out), w_mid), (p_out, tan_out, w_out)]:
                    v0 = bm.verts.new(pt - t_vec * sw)
                    v1 = bm.verts.new(pt + t_vec * sw)
                    v2 = bm.verts.new(pt + t_vec * (sw * 0.8) + thick_vec)
                    v3 = bm.verts.new(pt - t_vec * (sw * 0.8) + thick_vec)
                    s_rings.append((v0, v1, v2, v3))

                for ir in range(2):
                    sr0 = s_rings[ir]
                    sr1 = s_rings[ir + 1]
                    for k in range(4):
                        kn = (k + 1) % 4
                        verts_sp = (sr0[k], sr0[kn], sr1[kn], sr1[k]) if side > 0 else (sr0[k], sr1[k], sr1[kn], sr0[kn])
                        f_sp = bm.faces.new(verts_sp)
                        f_sp.material_index = 1
                        f_sp.smooth = True

        # 4. Brake Disc & Brake Caliper behind the rim spokes
        disc_r_out = 0.162
        disc_r_in = 0.065
        disc_x = wx + side * (half_w * 0.22)
        n_disc = 24
        d_in_ring = []
        d_out_ring = []
        for idc in range(n_disc):
            ang = (2.0 * math.pi * idc) / n_disc
            ca, sa = math.cos(ang), math.sin(ang)
            d_in_ring.append(bm.verts.new((disc_x, wy + disc_r_in * ca, wz + disc_r_in * sa)))
            d_out_ring.append(bm.verts.new((disc_x, wy + disc_r_out * ca, wz + disc_r_out * sa)))

        for idc in range(n_disc):
            idn = (idc + 1) % n_disc
            verts_d = (d_in_ring[idc], d_out_ring[idc], d_out_ring[idn], d_in_ring[idn]) if side > 0 else (d_in_ring[idc], d_in_ring[idn], d_out_ring[idn], d_out_ring[idc])
            f_d = bm.faces.new(verts_d)
            f_d.material_index = 2
            f_d.smooth = True

        # Brake caliper block
        cal_y = wy - 0.12 if wy < 0 else wy + 0.12
        create_box_mesh(bm, (disc_x + side * 0.018, cal_y, wz + 0.04), (0.048, 0.075, 0.13), (0.35, 0.0, 0.0), 3, bevel=True)

    mesh = bpy.data.meshes.new("Wheels_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("Wheels", mesh)
    bpy.context.collection.objects.link(obj)
    assign_materials_to_obj(obj, [mats["tyre"], mats["rim"], mats["brake"], mats["trim"]])
    return obj


def join_and_finalize_car(objects_list):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects_list:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects_list[0]
    bpy.ops.object.join()

    car_obj = bpy.context.view_layer.objects.active
    car_obj.name = "CarTaxi"
    car_obj.data.name = "CarTaxi_Mesh"

    # Ensure origin is at (0, 0, 0) bottom centre between the wheels and tyres touch Z=0
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    min_z = min(v.co.z for v in car_obj.data.vertices)
    if abs(min_z) > 1e-5:
        for v in car_obj.data.vertices:
            v.co.z -= min_z

    # Smooth shading with auto-smooth / sharp edges on panel creases
    for poly in car_obj.data.polygons:
        poly.use_smooth = True

    bm = bmesh.new()
    bm.from_mesh(car_obj.data)
    for edge in bm.edges:
        if len(edge.link_faces) == 2:
            f0, f1 = edge.link_faces[0], edge.link_faces[1]
            if f0.material_index != f1.material_index or f0.normal.angle(f1.normal, 0.0) > math.radians(38.0):
                edge.smooth = False
    bm.to_mesh(car_obj.data)
    bm.free()

    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(38.0))
    except Exception:
        bpy.ops.object.shade_smooth()

    return car_obj


def uv_unwrap_and_bake(car_obj, out_dir):
    bpy.ops.object.select_all(action='DESELECT')
    car_obj.select_set(True)
    bpy.context.view_layer.objects.active = car_obj

    # Step 2: UV unwrap with smart_project, average_islands_scale, pack_islands
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.01)
    try:
        bpy.ops.uv.select_all(action='SELECT')
    except Exception:
        pass
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Step 3: Create 2048x2048 images "CarTaxi_albedo" and "CarTaxi_normal" (Non-Color)
    img_albedo = bpy.data.images.new("CarTaxi_albedo", width=2048, height=2048, alpha=False)
    img_normal = bpy.data.images.new("CarTaxi_normal", width=2048, height=2048, alpha=False)
    img_normal.colorspace_settings.name = 'Non-Color'

    albedo_nodes = []
    normal_nodes = []
    for mat in car_obj.data.materials:
        if mat is None or not mat.use_nodes:
            continue
        nodes = mat.node_tree.nodes
        n_alb = nodes.new("ShaderNodeTexImage")
        n_alb.name = "Bake_Albedo_Node"
        n_alb.image = img_albedo
        albedo_nodes.append((nodes, n_alb))

        n_nrm = nodes.new("ShaderNodeTexImage")
        n_nrm.name = "Bake_Normal_Node"
        n_nrm.image = img_normal
        normal_nodes.append((nodes, n_nrm))

    # Step 4: Cycles CPU, 16 samples, bake DIFFUSE (COLOR) then NORMAL (tangent), margin 8
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 16
    scene.render.bake.margin = 8
    scene.render.bake.use_clear = True

    # Activate albedo image texture node in EVERY material before DIFFUSE bake
    for nodes, n_alb in albedo_nodes:
        for n in nodes:
            n.select = False
        n_alb.select = True
        nodes.active = n_alb

    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=8, use_clear=True)

    # Activate normal image texture node in EVERY material before NORMAL bake
    for nodes, n_nrm in normal_nodes:
        for n in nodes:
            n.select = False
        n_nrm.select = True
        nodes.active = n_nrm

    scene.render.bake.normal_space = 'TANGENT'
    bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=8, use_clear=True)

    # Save PNGs next to the output FBX
    os.makedirs(out_dir, exist_ok=True)
    albedo_path = os.path.join(out_dir, "CarTaxi_albedo.png")
    normal_path = os.path.join(out_dir, "CarTaxi_normal.png")

    img_albedo.filepath_raw = albedo_path
    img_albedo.file_format = 'PNG'
    img_albedo.save()

    img_normal.filepath_raw = normal_path
    img_normal.file_format = 'PNG'
    img_normal.save()

    # Step 5: Replace all slots with ONE material "CarTaxi_Mat"
    final_mat = bpy.data.materials.new("CarTaxi_Mat")
    final_mat.use_nodes = True
    f_nodes = final_mat.node_tree.nodes
    f_links = final_mat.node_tree.links
    f_nodes.clear()

    f_out = f_nodes.new("ShaderNodeOutputMaterial")
    f_bsdf = f_nodes.new("ShaderNodeBsdfPrincipled")
    f_links.new(f_bsdf.outputs["BSDF"], f_out.inputs["Surface"])
    set_bsdf_input(f_bsdf, ["Roughness"], 0.35)
    set_bsdf_input(f_bsdf, ["Metallic"], 0.0)
    set_bsdf_input(f_bsdf, ["Coat Weight", "Clearcoat"], 0.35)

    tex_alb = f_nodes.new("ShaderNodeTexImage")
    tex_alb.image = img_albedo
    f_links.new(tex_alb.outputs["Color"], get_bsdf_input(f_bsdf, ["Base Color"]))

    tex_nrm = f_nodes.new("ShaderNodeTexImage")
    tex_nrm.image = img_normal
    tex_nrm.image.colorspace_settings.name = 'Non-Color'

    nrm_map = f_nodes.new("ShaderNodeNormalMap")
    nrm_map.space = 'TANGENT'
    f_links.new(tex_nrm.outputs["Color"], nrm_map.inputs["Color"])
    f_links.new(nrm_map.outputs["Normal"], get_bsdf_input(f_bsdf, ["Normal"]))

    car_obj.data.materials.clear()
    car_obj.data.materials.append(final_mat)
    for poly in car_obj.data.polygons:
        poly.material_index = 0


def export_and_render_preview(car_obj, fbx_path, png_path):
    bpy.ops.object.select_all(action='DESELECT')
    car_obj.select_set(True)
    bpy.context.view_layer.objects.active = car_obj

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

    scene = bpy.context.scene
    engine_keys = list(scene.render.bl_rna.properties['engine'].enum_items.keys())
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
    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    w_nodes = world.node_tree.nodes
    w_links = world.node_tree.links
    w_nodes.clear()
    w_out = w_nodes.new("ShaderNodeOutputWorld")
    w_bg = w_nodes.new("ShaderNodeBackground")
    w_bg.inputs["Color"].default_value = (0.55, 0.56, 0.58, 1.0)
    w_bg.inputs["Strength"].default_value = 0.6
    w_links.new(w_bg.outputs["Background"], w_out.inputs["Surface"])

    # Sun strength 3 from front-left-above (car front is -Y)
    sun_data = bpy.data.lights.new(name="Sun", type='SUN')
    sun_data.energy = 3.0
    sun_obj = bpy.data.objects.new(name="Sun", object_data=sun_data)
    bpy.context.collection.objects.link(sun_obj)
    sun_obj.location = (-4.0, -5.0, 6.0)
    sun_dir = Vector((0.0, 0.0, 0.5)) - sun_obj.location
    sun_obj.rotation_euler = sun_dir.to_track_quat('-Z', 'Y').to_euler()

    # Camera at 1.5 m height in a front 3/4 view framing the whole car
    cam_data = bpy.data.cameras.new(name="Camera")
    cam_data.lens = 42.0
    cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = (-3.65, -4.45, 1.50)
    target = Vector((0.0, -0.05, 0.68))
    cam_dir = target - cam_obj.location
    cam_obj.rotation_euler = cam_dir.to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = png_path
    bpy.ops.render.render(write_still=True)


def main():
    out_arg = "CarTaxi.fbx"
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if idx + 1 < len(sys.argv):
            out_arg = sys.argv[idx + 1]

    out_arg = os.path.abspath(out_arg)
    base, ext = os.path.splitext(out_arg)
    if ext.lower() == ".fbx":
        fbx_path = out_arg
        png_path = base + ".png"
    else:
        fbx_path = out_arg + ".fbx"
        png_path = out_arg + ".png"

    out_dir = os.path.dirname(fbx_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    clear_scene()
    mats = create_procedural_materials()

    all_parts = []
    all_parts.append(build_car_body(mats))
    all_parts.extend(build_windows_and_pillars(mats))
    all_parts.append(build_interior_silhouette(mats))
    all_parts.append(build_bumpers_and_grilles(mats))
    all_parts.extend(build_lights(mats))
    all_parts.append(build_exterior_details(mats))
    all_parts.append(build_four_wheels(mats))

    car_obj = join_and_finalize_car(all_parts)
    uv_unwrap_and_bake(car_obj, out_dir)
    export_and_render_preview(car_obj, fbx_path, png_path)

    n_tris = sum(len(p.vertices) - 2 for p in car_obj.data.polygons)
    print("TRIS", n_tris)


if __name__ == "__main__":
    main()

