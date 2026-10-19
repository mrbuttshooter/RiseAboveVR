import bpy
import bmesh
import mathutils
from mathutils import Vector, Matrix
import math
import sys
import os

bpy.ops.wm.read_factory_settings(use_empty=True)

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for m in list(bpy.data.meshes):
    bpy.data.meshes.remove(m)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)
for img in list(bpy.data.images):
    bpy.data.images.remove(img)

BUILDING_NAME = "BldgOffice"

MAT_CONCRETE = 0
MAT_GLASS = 1
MAT_METAL = 2
MAT_BRICK = 3
MAT_STUCCO = 4
MAT_ROOF = 5


def add_grime_overlay(nt, links, base_color_socket, z_scale=42.0):
    tex_coord = nt.nodes.new("ShaderNodeTexCoord")
    sep_xyz = nt.nodes.new("ShaderNodeSeparateXYZ")
    links.new(tex_coord.outputs["Object"], sep_xyz.inputs["Vector"])

    ground_div = nt.nodes.new("ShaderNodeMath")
    ground_div.operation = "DIVIDE"
    ground_div.inputs[1].default_value = 9.0
    ground_div.use_clamp = True
    links.new(sep_xyz.outputs["Z"], ground_div.inputs[0])

    ground_inv = nt.nodes.new("ShaderNodeMath")
    ground_inv.operation = "SUBTRACT"
    ground_inv.inputs[0].default_value = 1.0
    ground_inv.use_clamp = True
    links.new(ground_div.outputs["Value"], ground_inv.inputs[1])

    sill_mod = nt.nodes.new("ShaderNodeMath")
    sill_mod.operation = "MODULO"
    sill_mod.inputs[1].default_value = 3.35
    links.new(sep_xyz.outputs["Z"], sill_mod.inputs[0])

    sill_div = nt.nodes.new("ShaderNodeMath")
    sill_div.operation = "DIVIDE"
    sill_div.inputs[1].default_value = 3.35
    links.new(sill_mod.outputs["Value"], sill_div.inputs[0])

    sill_ramp = nt.nodes.new("ShaderNodeValToRGB")
    sill_ramp.color_ramp.elements[0].position = 0.62
    sill_ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    sill_ramp.color_ramp.elements[1].position = 0.78
    sill_ramp.color_ramp.elements[1].color = (0.65, 0.65, 0.65, 1.0)
    el_top = sill_ramp.color_ramp.elements.new(0.86)
    el_top.color = (0.0, 0.0, 0.0, 1.0)
    links.new(sill_div.outputs["Value"], sill_ramp.inputs["Fac"])

    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (4.5, 4.5, 0.9)
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    streak_noise = nt.nodes.new("ShaderNodeTexNoise")
    streak_noise.inputs["Scale"].default_value = 3.2
    streak_noise.inputs["Detail"].default_value = 6.0
    streak_noise.inputs["Roughness"].default_value = 0.65
    links.new(mapping.outputs["Vector"], streak_noise.inputs["Vector"])

    sill_streaks = nt.nodes.new("ShaderNodeMath")
    sill_streaks.operation = "MULTIPLY"
    sill_streaks.use_clamp = True
    links.new(sill_ramp.outputs["Color"], sill_streaks.inputs[0])
    links.new(streak_noise.outputs["Fac"], sill_streaks.inputs[1])

    ground_streaks = nt.nodes.new("ShaderNodeMath")
    ground_streaks.operation = "MULTIPLY"
    ground_streaks.use_clamp = True
    links.new(ground_inv.outputs["Value"], ground_streaks.inputs[0])
    links.new(streak_noise.outputs["Fac"], ground_streaks.inputs[1])

    total_grime = nt.nodes.new("ShaderNodeMath")
    total_grime.operation = "ADD"
    total_grime.use_clamp = True
    links.new(sill_streaks.outputs["Value"], total_grime.inputs[0])
    links.new(ground_streaks.outputs["Value"], total_grime.inputs[1])

    grime_scale = nt.nodes.new("ShaderNodeMath")
    grime_scale.operation = "MULTIPLY"
    grime_scale.inputs[1].default_value = 0.55
    grime_scale.use_clamp = True
    links.new(total_grime.outputs["Value"], grime_scale.inputs[0])

    mix_grime = nt.nodes.new("ShaderNodeMixRGB")
    mix_grime.blend_type = "MIX"
    mix_grime.inputs["Color2"].default_value = (0.14, 0.13, 0.11, 1.0)
    links.new(grime_scale.outputs["Value"], mix_grime.inputs["Fac"])
    links.new(base_color_socket, mix_grime.inputs["Color1"])
    return mix_grime.outputs["Color"]


def create_wall_coords(nt, links):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sep.inputs["Vector"])

    add_xy = nt.nodes.new("ShaderNodeMath")
    add_xy.operation = "ADD"
    links.new(sep.outputs["X"], add_xy.inputs[0])
    links.new(sep.outputs["Y"], add_xy.inputs[1])

    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    links.new(add_xy.outputs["Value"], comb.inputs["X"])
    links.new(sep.outputs["Z"], comb.inputs["Y"])
    links.new(sep.outputs["X"], comb.inputs["Z"])
    return tc, comb.outputs["Vector"]


def make_concrete_mat():
    mat = bpy.data.materials.new("Proc_Concrete")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    links = nt.links

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.78
    bsdf.inputs["Metallic"].default_value = 0.0
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc, wall_vec = create_wall_coords(nt, links)

    panels = nt.nodes.new("ShaderNodeTexBrick")
    panels.offset = 0.5
    panels.inputs["Scale"].default_value = 0.6
    panels.inputs["Mortar Size"].default_value = 0.012
    panels.inputs["Mortar Smooth"].default_value = 0.2
    panels.inputs["Bias"].default_value = 0.0
    panels.inputs["Brick Width"].default_value = 2.0
    panels.inputs["Row Height"].default_value = 1.675
    panels.inputs["Color1"].default_value = (0.54, 0.55, 0.53, 1.0)
    panels.inputs["Color2"].default_value = (0.46, 0.47, 0.45, 1.0)
    panels.inputs["Mortar"].default_value = (0.24, 0.25, 0.24, 1.0)
    links.new(wall_vec, panels.inputs["Vector"])

    noise_fine = nt.nodes.new("ShaderNodeTexNoise")
    noise_fine.inputs["Scale"].default_value = 28.0
    noise_fine.inputs["Detail"].default_value = 8.0
    noise_fine.inputs["Roughness"].default_value = 0.7
    links.new(tc.outputs["Object"], noise_fine.inputs["Vector"])

    mix_pore = nt.nodes.new("ShaderNodeMixRGB")
    mix_pore.blend_type = "MULTIPLY"
    mix_pore.inputs["Fac"].default_value = 0.22
    links.new(panels.outputs["Color"], mix_pore.inputs["Color1"])
    links.new(noise_fine.outputs["Color"], mix_pore.inputs["Color2"])

    grimed = add_grime_overlay(nt, links, mix_pore.outputs["Color"])
    links.new(grimed, bsdf.inputs["Base Color"])

    bump_mix = nt.nodes.new("ShaderNodeMath")
    bump_mix.operation = "MULTIPLY_ADD"
    bump_mix.inputs[1].default_value = 0.65
    links.new(panels.outputs["Fac"], bump_mix.inputs[0])
    links.new(noise_fine.outputs["Fac"], bump_mix.inputs[2])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.02
    links.new(bump_mix.outputs["Value"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def make_glass_mat():
    mat = bpy.data.materials.new("Proc_Glass")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    links = nt.links

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.18
    bsdf.inputs["Metallic"].default_value = 0.0
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc, wall_vec = create_wall_coords(nt, links)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sep.inputs["Vector"])

    rooms = nt.nodes.new("ShaderNodeTexBrick")
    rooms.offset = 0.0
    rooms.inputs["Scale"].default_value = 1.0
    rooms.inputs["Mortar Size"].default_value = 0.04
    rooms.inputs["Mortar Smooth"].default_value = 0.15
    rooms.inputs["Brick Width"].default_value = 1.6
    rooms.inputs["Row Height"].default_value = 3.35
    rooms.inputs["Color1"].default_value = (0.11, 0.18, 0.24, 1.0)
    rooms.inputs["Color2"].default_value = (0.22, 0.30, 0.36, 1.0)
    rooms.inputs["Mortar"].default_value = (0.07, 0.10, 0.13, 1.0)
    links.new(wall_vec, rooms.inputs["Vector"])

    blinds = nt.nodes.new("ShaderNodeTexWave")
    blinds.wave_type = "BANDS"
    blinds.bands_direction = "X"
    blinds.inputs["Scale"].default_value = 18.0
    blinds.inputs["Distortion"].default_value = 0.4
    links.new(wall_vec, blinds.inputs["Vector"])

    blind_mix = nt.nodes.new("ShaderNodeMixRGB")
    blind_mix.blend_type = "MIX"
    blind_mix.inputs["Fac"].default_value = 0.25
    blind_mix.inputs["Color2"].default_value = (0.28, 0.34, 0.38, 1.0)
    links.new(rooms.outputs["Color"], blind_mix.inputs["Color1"])
    links.new(blinds.outputs["Color"], blind_mix.inputs["Color2"])

    z_grad = nt.nodes.new("ShaderNodeMath")
    z_grad.operation = "DIVIDE"
    z_grad.inputs[1].default_value = 45.0
    z_grad.use_clamp = True
    links.new(sep.outputs["Z"], z_grad.inputs[0])

    sky_tint = nt.nodes.new("ShaderNodeMixRGB")
    sky_tint.blend_type = "MIX"
    sky_tint.inputs["Color2"].default_value = (0.24, 0.36, 0.46, 1.0)
    links.new(z_grad.outputs["Value"], sky_tint.inputs["Fac"])
    links.new(blind_mix.outputs["Color"], sky_tint.inputs["Color1"])

    links.new(sky_tint.outputs["Color"], bsdf.inputs["Base Color"])

    glass_wave = nt.nodes.new("ShaderNodeTexNoise")
    glass_wave.inputs["Scale"].default_value = 1.8
    glass_wave.inputs["Detail"].default_value = 2.0
    links.new(tc.outputs["Object"], glass_wave.inputs["Vector"])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.05
    bump.inputs["Distance"].default_value = 0.005
    links.new(glass_wave.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def make_metal_mat():
    mat = bpy.data.materials.new("Proc_Metal")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    links = nt.links

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.45
    bsdf.inputs["Metallic"].default_value = 0.0
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc, wall_vec = create_wall_coords(nt, links)

    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 16.0
    noise.inputs["Detail"].default_value = 5.0
    links.new(tc.outputs["Object"], noise.inputs["Vector"])

    louver = nt.nodes.new("ShaderNodeTexWave")
    louver.wave_type = "BANDS"
    louver.bands_direction = "Z"
    louver.inputs["Scale"].default_value = 24.0
    links.new(tc.outputs["Object"], louver.inputs["Vector"])

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.2
    ramp.color_ramp.elements[0].color = (0.13, 0.15, 0.17, 1.0)
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (0.21, 0.23, 0.26, 1.0)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])

    mix_louver = nt.nodes.new("ShaderNodeMixRGB")
    mix_louver.blend_type = "MULTIPLY"
    mix_louver.inputs["Fac"].default_value = 0.18
    links.new(ramp.outputs["Color"], mix_louver.inputs["Color1"])
    links.new(louver.outputs["Color"], mix_louver.inputs["Color2"])

    grimed = add_grime_overlay(nt, links, mix_louver.outputs["Color"])
    links.new(grimed, bsdf.inputs["Base Color"])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.22
    bump.inputs["Distance"].default_value = 0.01
    links.new(louver.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def make_brick_mat():
    mat = bpy.data.materials.new("Proc_Brick")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    links = nt.links

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.82
    bsdf.inputs["Metallic"].default_value = 0.0
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc, wall_vec = create_wall_coords(nt, links)

    brick = nt.nodes.new("ShaderNodeTexBrick")
    brick.offset = 0.5
    brick.inputs["Scale"].default_value = 4.2
    brick.inputs["Mortar Size"].default_value = 0.025
    brick.inputs["Mortar Smooth"].default_value = 0.1
    brick.inputs["Bias"].default_value = -0.15
    brick.inputs["Brick Width"].default_value = 0.9
    brick.inputs["Row Height"].default_value = 0.32
    brick.inputs["Color1"].default_value = (0.36, 0.18, 0.13, 1.0)
    brick.inputs["Color2"].default_value = (0.22, 0.11, 0.09, 1.0)
    brick.inputs["Mortar"].default_value = (0.56, 0.54, 0.50, 1.0)
    links.new(wall_vec, brick.inputs["Vector"])

    grain = nt.nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 40.0
    grain.inputs["Detail"].default_value = 6.0
    links.new(tc.outputs["Object"], grain.inputs["Vector"])

    mix_grain = nt.nodes.new("ShaderNodeMixRGB")
    mix_grain.blend_type = "MULTIPLY"
    mix_grain.inputs["Fac"].default_value = 0.2
    links.new(brick.outputs["Color"], mix_grain.inputs["Color1"])
    links.new(grain.outputs["Color"], mix_grain.inputs["Color2"])

    grimed = add_grime_overlay(nt, links, mix_grain.outputs["Color"])
    links.new(grimed, bsdf.inputs["Base Color"])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.5
    bump.inputs["Distance"].default_value = 0.02
    links.new(brick.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def make_stucco_mat():
    mat = bpy.data.materials.new("Proc_Stucco")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    links = nt.links

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.85
    bsdf.inputs["Metallic"].default_value = 0.0
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")

    stains = nt.nodes.new("ShaderNodeTexNoise")
    stains.inputs["Scale"].default_value = 2.4
    stains.inputs["Detail"].default_value = 6.0
    stains.inputs["Roughness"].default_value = 0.65
    links.new(tc.outputs["Object"], stains.inputs["Vector"])

    fine = nt.nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 65.0
    fine.inputs["Detail"].default_value = 8.0
    links.new(tc.outputs["Object"], fine.inputs["Vector"])

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (0.48, 0.46, 0.42, 1.0)
    ramp.color_ramp.elements[1].position = 0.72
    ramp.color_ramp.elements[1].color = (0.72, 0.70, 0.66, 1.0)
    links.new(stains.outputs["Fac"], ramp.inputs["Fac"])

    grimed = add_grime_overlay(nt, links, ramp.outputs["Color"])
    links.new(grimed, bsdf.inputs["Base Color"])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.32
    bump.inputs["Distance"].default_value = 0.015
    links.new(fine.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def make_roof_mat():
    mat = bpy.data.materials.new("Proc_RoofMembrane")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    links = nt.links

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.9
    bsdf.inputs["Metallic"].default_value = 0.0
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")

    patches = nt.nodes.new("ShaderNodeTexNoise")
    patches.inputs["Scale"].default_value = 1.6
    patches.inputs["Detail"].default_value = 5.0
    links.new(tc.outputs["Object"], patches.inputs["Vector"])

    gravel = nt.nodes.new("ShaderNodeTexNoise")
    gravel.inputs["Scale"].default_value = 95.0
    gravel.inputs["Detail"].default_value = 8.0
    links.new(tc.outputs["Object"], gravel.inputs["Vector"])

    seams = nt.nodes.new("ShaderNodeTexWave")
    seams.wave_type = "BANDS"
    seams.bands_direction = "X"
    seams.inputs["Scale"].default_value = 2.5
    links.new(tc.outputs["Object"], seams.inputs["Vector"])

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.14, 0.15, 0.16, 1.0)
    ramp.color_ramp.elements[1].position = 0.78
    ramp.color_ramp.elements[1].color = (0.25, 0.26, 0.27, 1.0)
    links.new(patches.outputs["Fac"], ramp.inputs["Fac"])

    mix_gravel = nt.nodes.new("ShaderNodeMixRGB")
    mix_gravel.blend_type = "MULTIPLY"
    mix_gravel.inputs["Fac"].default_value = 0.25
    links.new(ramp.outputs["Color"], mix_gravel.inputs["Color1"])
    links.new(gravel.outputs["Color"], mix_gravel.inputs["Color2"])
    links.new(mix_gravel.outputs["Color"], bsdf.inputs["Base Color"])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.45
    bump.inputs["Distance"].default_value = 0.02
    links.new(gravel.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def make_quad(bm, p0, p1, p2, p3, out_normal, mat_idx):
    v0 = bm.verts.new(p0)
    v1 = bm.verts.new(p1)
    v2 = bm.verts.new(p2)
    v3 = bm.verts.new(p3)
    f = bm.faces.new((v0, v1, v2, v3))
    f.material_index = mat_idx
    f.normal_update()
    if f.normal.dot(out_normal) < 0.0:
        f.normal_flip()
        f.normal_update()
    return f


def add_box(bm, x0, x1, y0, y1, z0, z1, mat_idx, top_mat=None, skip_bottom=True, skip_back=None):
    if top_mat is None:
        top_mat = mat_idx
    faces = []
    if skip_back != "-Y":
        faces.append(make_quad(bm, (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), Vector((0, -1, 0)), mat_idx))
    if skip_back != "+Y":
        faces.append(make_quad(bm, (x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), Vector((0, 1, 0)), mat_idx))
    if skip_back != "-X":
        faces.append(make_quad(bm, (x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), Vector((-1, 0, 0)), mat_idx))
    if skip_back != "+X":
        faces.append(make_quad(bm, (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), Vector((1, 0, 0)), mat_idx))
    if skip_back != "+Z":
        faces.append(make_quad(bm, (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), Vector((0, 0, 1)), top_mat))
    if not skip_bottom and skip_back != "-Z":
        faces.append(make_quad(bm, (x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0), Vector((0, 0, -1)), mat_idx))
    return faces


def add_perimeter_band(bm, half_in, half_out, z0, z1, mat_idx, top_mat=None):
    if top_mat is None:
        top_mat = mat_idx
    add_box(bm, -half_out, half_out, -half_out, -half_in, z0, z1, mat_idx, top_mat=top_mat, skip_bottom=False)
    add_box(bm, -half_out, half_out, half_in, half_out, z0, z1, mat_idx, top_mat=top_mat, skip_bottom=False)
    add_box(bm, -half_out, -half_in, -half_in, half_in, z0, z1, mat_idx, top_mat=top_mat, skip_bottom=False)
    add_box(bm, half_in, half_out, -half_in, half_in, z0, z1, mat_idx, top_mat=top_mat, skip_bottom=False)


def build_facade_bay(bm, side, u0, u1, z0, z1, wall_coord, recess_depth=0.20, frame_thick=0.065, add_transom=False, wall_mat=MAT_CONCRETE):
    if side == "-Y":
        out_n = Vector((0.0, -1.0, 0.0))
        p0 = Vector((u0, -wall_coord, z0))
        p1 = Vector((u1, -wall_coord, z0))
        p2 = Vector((u1, -wall_coord, z1))
        p3 = Vector((u0, -wall_coord, z1))
        skip_back = "+Y"
    elif side == "+Y":
        out_n = Vector((0.0, 1.0, 0.0))
        p0 = Vector((u1, wall_coord, z0))
        p1 = Vector((u0, wall_coord, z0))
        p2 = Vector((u0, wall_coord, z1))
        p3 = Vector((u1, wall_coord, z1))
        skip_back = "-Y"
    elif side == "-X":
        out_n = Vector((-1.0, 0.0, 0.0))
        p0 = Vector((-wall_coord, u1, z0))
        p1 = Vector((-wall_coord, u0, z0))
        p2 = Vector((-wall_coord, u0, z1))
        p3 = Vector((-wall_coord, u1, z1))
        skip_back = "+X"
    else:
        out_n = Vector((1.0, 0.0, 0.0))
        p0 = Vector((wall_coord, u0, z0))
        p1 = Vector((wall_coord, u1, z0))
        p2 = Vector((wall_coord, u1, z1))
        p3 = Vector((wall_coord, u1, z1))
        p2 = Vector((wall_coord, u1, z1))
        p3 = Vector((wall_coord, u0, z1))
        skip_back = "-X"

    bay_face = make_quad(bm, p0, p1, p2, p3, out_n, wall_mat)

    res_recess = bmesh.ops.inset_individual(
        bm,
        faces=[bay_face],
        thickness=0.0,
        depth=-recess_depth,
        use_even_offset=True,
    )
    for rf in res_recess.get("faces", []):
        rf.normal_update()
        if rf.normal.z > 0.5:
            rf.material_index = MAT_METAL
        else:
            rf.material_index = wall_mat

    res_frame = bmesh.ops.inset_individual(
        bm,
        faces=[bay_face],
        thickness=frame_thick,
        depth=-0.02,
        use_even_offset=True,
    )
    for ff in res_frame.get("faces", []):
        ff.material_index = MAT_METAL

    bay_face.material_index = MAT_GLASS

    u_mid = 0.5 * (u0 + u1)
    m_half = 0.032
    sill_h = 0.065
    sill_out = 0.07

    if side == "-Y":
        add_box(bm, u0 - 0.02, u1 + 0.02, -(wall_coord + sill_out), -(wall_coord - recess_depth), z0 - sill_h, z0 + 0.01, MAT_CONCRETE, top_mat=MAT_METAL, skip_bottom=False, skip_back=skip_back)
        add_box(bm, u_mid - m_half, u_mid + m_half, -(wall_coord - recess_depth + 0.02), -(wall_coord - 0.05), z0 + frame_thick, z1 - frame_thick, MAT_METAL, skip_bottom=True, skip_back=skip_back)
        if add_transom:
            zt = z0 + 0.68 * (z1 - z0)
            add_box(bm, u0 + frame_thick, u1 - frame_thick, -(wall_coord - recess_depth + 0.02), -(wall_coord - 0.06), zt - 0.03, zt + 0.03, MAT_METAL, skip_bottom=False, skip_back=skip_back)
    elif side == "+Y":
        add_box(bm, u0 - 0.02, u1 + 0.02, wall_coord - recess_depth, wall_coord + sill_out, z0 - sill_h, z0 + 0.01, MAT_CONCRETE, top_mat=MAT_METAL, skip_bottom=False, skip_back=skip_back)
        add_box(bm, u_mid - m_half, u_mid + m_half, wall_coord - 0.05, wall_coord - recess_depth + 0.02, z0 + frame_thick, z1 - frame_thick, MAT_METAL, skip_bottom=True, skip_back=skip_back)
        if add_transom:
            zt = z0 + 0.68 * (z1 - z0)
            add_box(bm, u0 + frame_thick, u1 - frame_thick, wall_coord - 0.06, wall_coord - recess_depth + 0.02, zt - 0.03, zt + 0.03, MAT_METAL, skip_bottom=False, skip_back=skip_back)
    elif side == "-X":
        add_box(bm, -(wall_coord + sill_out), -(wall_coord - recess_depth), u0 - 0.02, u1 + 0.02, z0 - sill_h, z0 + 0.01, MAT_CONCRETE, top_mat=MAT_METAL, skip_bottom=False, skip_back=skip_back)
        add_box(bm, -(wall_coord - recess_depth + 0.02), -(wall_coord - 0.05), u_mid - m_half, u_mid + m_half, z0 + frame_thick, z1 - frame_thick, MAT_METAL, skip_bottom=True, skip_back=skip_back)
        if add_transom:
            zt = z0 + 0.68 * (z1 - z0)
            add_box(bm, -(wall_coord - recess_depth + 0.02), -(wall_coord - 0.06), u0 + frame_thick, u1 - frame_thick, zt - 0.03, zt + 0.03, MAT_METAL, skip_bottom=False, skip_back=skip_back)
    else:
        add_box(bm, wall_coord - recess_depth, wall_coord + sill_out, u0 - 0.02, u1 + 0.02, z0 - sill_h, z0 + 0.01, MAT_CONCRETE, top_mat=MAT_METAL, skip_bottom=False, skip_back=skip_back)
        add_box(bm, wall_coord - 0.05, wall_coord - recess_depth + 0.02, u_mid - m_half, u_mid + m_half, z0 + frame_thick, z1 - frame_thick, MAT_METAL, skip_bottom=True, skip_back=skip_back)
        if add_transom:
            zt = z0 + 0.68 * (z1 - z0)
            add_box(bm, wall_coord - 0.06, wall_coord - recess_depth + 0.02, u0 + frame_thick, u1 - frame_thick, zt - 0.03, zt + 0.03, MAT_METAL, skip_bottom=False, skip_back=skip_back)


def build_wall_strip(bm, side, u0, u1, z0, z1, wall_coord, mat_idx):
    if side == "-Y":
        make_quad(bm, (u0, -wall_coord, z0), (u1, -wall_coord, z0), (u1, -wall_coord, z1), (u0, -wall_coord, z1), Vector((0, -1, 0)), mat_idx)
    elif side == "+Y":
        make_quad(bm, (u1, wall_coord, z0), (u0, wall_coord, z0), (u0, wall_coord, z1), (u1, wall_coord, z1), Vector((0, 1, 0)), mat_idx)
    elif side == "-X":
        make_quad(bm, (-wall_coord, u1, z0), (-wall_coord, u0, z0), (-wall_coord, u0, z1), (-wall_coord, u1, z1), Vector((-1, 0, 0)), mat_idx)
    else:
        make_quad(bm, (wall_coord, u0, z0), (wall_coord, u1, z0), (wall_coord, u1, z1), (wall_coord, u0, z1), Vector((1, 0, 0)), mat_idx)


def build_office_building():
    mesh = bpy.data.meshes.new(BUILDING_NAME)
    obj = bpy.data.objects.new(BUILDING_NAME, mesh)
    bpy.context.collection.objects.link(obj)

    mats = [
        make_concrete_mat(),
        make_glass_mat(),
        make_metal_mat(),
        make_brick_mat(),
        make_stucco_mat(),
        make_roof_mat(),
    ]
    for m in mats:
        obj.data.materials.append(m)

    bm = bmesh.new()

    half_w = 8.0
    gf_h = 4.5
    num_upper = 11
    floor_h = 3.35
    main_roof_z = gf_h + num_upper * floor_h  # 41.35 m
    parapet_z = 42.0

    # Base foundation plinth at Z=0..0.28
    add_box(bm, -8.12, 8.12, -8.12, 8.12, 0.0, 0.28, MAT_BRICK, top_mat=MAT_CONCRETE, skip_bottom=False)

    # 4 corner columns on ground floor
    col_w = 1.15
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            cx0 = sx * half_w if sx < 0 else sx * half_w - col_w
            cx1 = cx0 + col_w
            cy0 = sy * half_w if sy < 0 else sy * half_w - col_w
            cy1 = cy0 + col_w
            add_box(bm, cx0, cx1, cy0, cy1, 0.28, gf_h, MAT_CONCRETE, skip_bottom=True)

    # Bay layout along each 16 m facade:
    # Corners [-8.0, -6.85] and [6.85, 8.0] (1.15m each)
    # 4 bays between -6.85 and 6.85 with 3 intermediate piers (0.36m wide)
    # Total span = 13.70m; 3 * 0.36 = 1.08m; 4 bays * 3.155m = 12.62m
    bay_intervals = []
    pier_intervals = [(-8.0, -6.85)]
    curr_u = -6.85
    bay_w = 3.155
    pier_w = 0.36
    for i in range(4):
        b0 = curr_u
        b1 = b0 + bay_w
        bay_intervals.append((b0, b1))
        curr_u = b1
        if i < 3:
            pier_intervals.append((curr_u, curr_u + pier_w))
            curr_u += pier_w
    pier_intervals.append((6.85, 8.0))

    # Ground floor front facade (-Y): deeply recessed glass lobby (Y = -7.05) with columns at Y = -8.0
    for px0, px1 in pier_intervals[1:-1]:
        add_box(bm, px0, px1, -8.02, -7.55, 0.28, gf_h, MAT_CONCRETE, skip_bottom=True)

    # Lobby soffit ceiling under 2nd floor overhang on -Y
    make_quad(bm, (-6.85, -8.0, 4.22), (6.85, -8.0, 4.22), (6.85, -7.05, 4.22), (-6.85, -7.05, 4.22), Vector((0, 0, -1)), MAT_STUCCO)
    make_quad(bm, (-6.85, -8.0, 4.22), (6.85, -8.0, 4.22), (6.85, -8.0, gf_h), (-6.85, -8.0, gf_h), Vector((0, -1, 0)), MAT_CONCRETE)
    # Recessed lobby side returns
    make_quad(bm, (-6.85, -8.0, 0.28), (-6.85, -7.05, 0.28), (-6.85, -7.05, 4.22), (-6.85, -8.0, 4.22), Vector((1, 0, 0)), MAT_BRICK)
    make_quad(bm, (6.85, -7.05, 0.28), (6.85, -8.0, 0.28), (6.85, -8.0, 4.22), (6.85, -7.05, 4.22), Vector((-1, 0, 0)), MAT_BRICK)
    # Lobby floor terrace between Y=-8.0 and Y=-7.05
    make_quad(bm, (-6.85, -8.0, 0.28), (6.85, -8.0, 0.28), (6.85, -7.05, 0.28), (-6.85, -7.05, 0.28), Vector((0, 0, 1)), MAT_CONCRETE)

    # Front lobby wall at Y = -7.05: outer 2 bays have brick base + tall lobby glazing; middle 2 bays form grand entrance
    for bi in (0, 3):
        u0, u1 = bay_intervals[bi]
        make_quad(bm, (u0, -7.05, 0.28), (u1, -7.05, 0.28), (u1, -7.05, 0.85), (u0, -7.05, 0.85), Vector((0, -1, 0)), MAT_BRICK)
        build_facade_bay(bm, "-Y", u0, u1, 0.85, 4.05, 7.05, recess_depth=0.18, frame_thick=0.07, add_transom=True, wall_mat=MAT_METAL)
        make_quad(bm, (u0, -7.05, 4.05), (u1, -7.05, 4.05), (u1, -7.05, 4.22), (u0, -7.05, 4.22), Vector((0, -1, 0)), MAT_STUCCO)

    # Middle 2 bays on -Y: grand entrance doors + transom glazing from u = -3.335 to +3.335
    ent_u0 = bay_intervals[1][0]
    ent_u1 = bay_intervals[2][1]
    make_quad(bm, (ent_u0, -7.05, 4.05), (ent_u1, -7.05, 4.05), (ent_u1, -7.05, 4.22), (ent_u0, -7.05, 4.22), Vector((0, -1, 0)), MAT_STUCCO)
    # 2 double-door portals + center pier
    for du0, du1 in ((ent_u0, -0.18), (0.18, ent_u1)):
        # Upper transom window
        build_facade_bay(bm, "-Y", du0, du1, 2.75, 4.05, 7.05, recess_depth=0.16, frame_thick=0.06, add_transom=False, wall_mat=MAT_METAL)
        # Recessed glass double door
        build_facade_bay(bm, "-Y", du0, du1, 0.28, 2.75, 7.05, recess_depth=0.22, frame_thick=0.08, add_transom=False, wall_mat=MAT_METAL)
        # Door handles
        dm = 0.5 * (du0 + du1)
        add_box(bm, dm - 0.14, dm - 0.08, -7.02, -6.86, 1.05, 1.65, MAT_METAL, skip_bottom=False)
        add_box(bm, dm + 0.08, dm + 0.14, -7.02, -6.86, 1.05, 1.65, MAT_METAL, skip_bottom=False)
    # Center mullion pillar between double doors
    add_box(bm, -0.18, 0.18, -7.15, -6.95, 0.28, 4.05, MAT_METAL, skip_bottom=True)

    # Front entrance steps at Y = -8.45..-8.0
    add_box(bm, -3.8, 3.8, -8.55, -8.0, 0.0, 0.14, MAT_CONCRETE, skip_bottom=False)
    add_box(bm, -3.6, 3.6, -8.30, -8.0, 0.14, 0.28, MAT_CONCRETE, skip_bottom=True)

    # Cantilevered entrance canopy on -Y
    add_box(bm, -4.4, 4.4, -9.55, -7.95, 3.68, 3.92, MAT_CONCRETE, top_mat=MAT_ROOF, skip_bottom=False)
    add_perimeter_band(bm, 0.0, 0.0, 0.0, 0.0, MAT_METAL) if False else None
    # Dark metal fascia wrap around canopy
    add_box(bm, -4.46, 4.46, -9.61, -9.52, 3.64, 3.98, MAT_METAL, skip_bottom=False)
    add_box(bm, -4.46, -4.38, -9.55, -7.95, 3.64, 3.98, MAT_METAL, skip_bottom=False)
    add_box(bm, 4.38, 4.46, -9.55, -7.95, 3.64, 3.98, MAT_METAL, skip_bottom=False)

    # Ground floor on other 3 sides (+Y, -X, +X)
    for side in ("+Y", "-X", "+X"):
        for p0, p1 in pier_intervals[1:-1]:
            build_wall_strip(bm, side, p0, p1, 0.28, gf_h, half_w, MAT_BRICK)
        for bi, (u0, u1) in enumerate(bay_intervals):
            build_wall_strip(bm, side, u0, u1, 4.05, gf_h, half_w, MAT_CONCRETE)
            if side == "+Y" and bi == 1:
                # Rear service double door
                build_facade_bay(bm, side, u0, u1, 0.28, 2.65, half_w, recess_depth=0.22, frame_thick=0.08, add_transom=False, wall_mat=MAT_METAL)
                build_facade_bay(bm, side, u0, u1, 2.65, 4.05, half_w, recess_depth=0.18, frame_thick=0.06, add_transom=False, wall_mat=MAT_METAL)
            else:
                build_wall_strip(bm, side, u0, u1, 0.28, 0.95, half_w, MAT_BRICK)
                build_facade_bay(bm, side, u0, u1, 0.95, 4.05, half_w, recess_depth=0.20, frame_thick=0.065, add_transom=True, wall_mat=MAT_BRICK)

    # Ground floor main cornice ledge at Z = 4.35..4.62
    add_perimeter_band(bm, 7.98, 8.24, 4.35, 4.62, MAT_CONCRETE, top_mat=MAT_CONCRETE)

    # Upper 11 Storeys (Floors 2..12)
    spandrel_h = 0.85
    for fl in range(num_upper):
        fz0 = gf_h + fl * floor_h
        fz_win0 = fz0 + spandrel_h
        fz1 = fz0 + floor_h
        has_transom = (fl in (0, 5, 10))

        # Floor band / cornice molding every storey
        add_perimeter_band(bm, 7.98, 8.15, fz0 + 0.05, fz0 + 0.22, MAT_CONCRETE, top_mat=MAT_CONCRETE)

        for side in ("-Y", "+Y", "-X", "+X"):
            # Continuous concrete spandrel band across entire 16m width
            build_wall_strip(bm, side, -half_w, half_w, fz0, fz_win0, half_w, MAT_CONCRETE)
            # Vertical structural piers in window zone
            for p0, p1 in pier_intervals:
                mat_p = MAT_CONCRETE if (abs(p0) > 6.8 or abs(p1) > 6.8) else MAT_METAL
                build_wall_strip(bm, side, p0, p1, fz_win0, fz1, half_w, mat_p)
            # 4 recessed curtain-wall bays per facade per floor
            for u0, u1 in bay_intervals:
                build_facade_bay(
                    bm,
                    side,
                    u0,
                    u1,
                    fz_win0,
                    fz1,
                    half_w,
                    recess_depth=0.20,
                    frame_thick=0.065,
                    add_transom=has_transom,
                    wall_mat=MAT_CONCRETE,
                )

    # Upper cornice below parapet at Z = 41.20..41.48
    add_perimeter_band(bm, 7.98, 8.28, main_roof_z - 0.15, main_roof_z + 0.12, MAT_CONCRETE, top_mat=MAT_CONCRETE)

    # Roof membrane deck at Z = 41.35
    make_quad(bm, (-7.65, -7.65, main_roof_z), (7.65, -7.65, main_roof_z), (7.65, 7.65, main_roof_z), (-7.65, 7.65, main_roof_z), Vector((0, 0, 1)), MAT_ROOF)

    # Roof parapet walls (Z = 41.35..42.05) and wide coping stone (Z = 42.05..42.20)
    add_perimeter_band(bm, 7.65, 8.02, main_roof_z, parapet_z, MAT_CONCRETE, top_mat=MAT_CONCRETE)
    add_perimeter_band(bm, 7.58, 8.12, parapet_z, parapet_z + 0.16, MAT_CONCRETE, top_mat=MAT_METAL)

    # Rooftop Lift / Stair Housing (Penthouse) at Z = 41.35..44.65
    ph_x0, ph_x1 = -2.8, 2.8
    ph_y0, ph_y1 = 0.6, 5.2
    ph_z0, ph_z1 = main_roof_z, main_roof_z + 3.30
    add_box(bm, ph_x0, ph_x1, ph_y0, ph_y1, ph_z0, ph_z1, MAT_STUCCO, top_mat=MAT_ROOF, skip_bottom=True)
    # Penthouse roof overhang coping
    add_box(bm, ph_x0 - 0.18, ph_x1 + 0.18, ph_y0 - 0.18, ph_y1 + 0.18, ph_z1, ph_z1 + 0.18, MAT_CONCRETE, top_mat=MAT_ROOF, skip_bottom=False)
    # Access door and louver vent on -Y face of lift housing
    build_facade_bay(bm, "-Y", -2.1, -1.0, ph_z0 + 0.12, ph_z0 + 2.25, -ph_y0, recess_depth=0.16, frame_thick=0.06, add_transom=False, wall_mat=MAT_METAL)
    build_facade_bay(bm, "-Y", 0.2, 2.1, ph_z0 + 0.90, ph_z0 + 2.25, -ph_y0, recess_depth=0.15, frame_thick=0.06, add_transom=True, wall_mat=MAT_METAL)
    # Step in front of rooftop access door
    add_box(bm, -2.25, -0.85, ph_y0 - 0.45, ph_y0, ph_z0, ph_z0 + 0.12, MAT_CONCRETE, skip_bottom=True)

    # Rooftop Cylindrical Water Tank on steel frame (front-right quadrant of roof)
    wt_cx, wt_cy = 4.6, 3.2
    wt_r = 1.35
    wt_z0 = main_roof_z + 0.65
    wt_z1 = main_roof_z + 2.85
    for lx in (-0.85, 0.85):
        for ly in (-0.85, 0.85):
            add_box(bm, wt_cx + lx - 0.10, wt_cx + lx + 0.10, wt_cy + ly - 0.10, wt_cy + ly + 0.10, main_roof_z, wt_z0, MAT_METAL, skip_bottom=True)
    add_box(bm, wt_cx - 1.15, wt_cx + 1.15, wt_cy - 1.15, wt_cy + 1.15, wt_z0 - 0.12, wt_z0, MAT_METAL, skip_bottom=False)
    n_seg = 12
    for i in range(n_seg):
        a0 = 2.0 * math.pi * i / n_seg
        a1 = 2.0 * math.pi * (i + 1) / n_seg
        x0 = wt_cx + wt_r * math.cos(a0)
        y0 = wt_cy + wt_r * math.sin(a0)
        x1 = wt_cx + wt_r * math.cos(a1)
        y1 = wt_cy + wt_r * math.sin(a1)
        n_out = Vector((math.cos(0.5 * (a0 + a1)), math.sin(0.5 * (a0 + a1)), 0.0))
        make_quad(bm, (x0, y0, wt_z0), (x1, y1, wt_z0), (x1, y1, wt_z1), (x0, y0, wt_z1), n_out, MAT_METAL)
        # Cone roof quad (degenerate-free trapezoids to small inner ring)
        ir = 0.22
        ix0 = wt_cx + ir * math.cos(a0)
        iy0 = wt_cy + ir * math.sin(a0)
        ix1 = wt_cx + ir * math.cos(a1)
        iy1 = wt_cy + ir * math.sin(a1)
        make_quad(bm, (x0, y0, wt_z1), (x1, y1, wt_z1), (ix1, iy1, wt_z1 + 0.28), (ix0, iy0, wt_z1 + 0.28), Vector((0, 0, 1)), MAT_METAL)

    # 4 Commercial HVAC / AC Chiller Units on front half of roof
    ac_coords = [
        (-5.2, -4.8),
        (-5.2, -1.8),
        (-1.2, -4.8),
        (2.8, -4.8),
    ]
    for ax, ay in ac_coords:
        aw, ad, ah = 2.1, 1.45, 1.25
        # Mounting rails
        add_box(bm, ax - 0.08, ax + aw + 0.08, ay, ay + 0.14, main_roof_z, main_roof_z + 0.12, MAT_CONCRETE, skip_bottom=True)
        add_box(bm, ax - 0.08, ax + aw + 0.08, ay + ad - 0.14, ay + ad, main_roof_z, main_roof_z + 0.12, MAT_CONCRETE, skip_bottom=True)
        # Main AC cabinet
        ac_faces = add_box(bm, ax, ax + aw, ay, ay + ad, main_roof_z + 0.12, main_roof_z + 0.12 + ah, MAT_METAL, top_mat=MAT_METAL, skip_bottom=False)
        # Dual fan shrouds on top
        for fi in (0.28, 0.72):
            fcx = ax + aw * fi
            fcy = ay + 0.5 * ad
            fr = 0.36
            shroud = add_box(bm, fcx - fr, fcx + fr, fcy - fr, fcy + fr, main_roof_z + 0.12 + ah, main_roof_z + 0.26 + ah, MAT_METAL, top_mat=MAT_METAL, skip_bottom=True)
            top_f = shroud[-1]
            res_fan = bmesh.ops.inset_individual(bm, faces=[top_f], thickness=0.06, depth=-0.10, use_even_offset=True)
            for sf in res_fan.get("faces", []):
                sf.material_index = MAT_METAL
            top_f.material_index = MAT_CONCRETE

    # Rooftop ventilation ducts & exhaust hoods
    add_box(bm, -1.8, -1.1, -0.8, 0.6, main_roof_z + 0.35, main_roof_z + 0.95, MAT_METAL, skip_bottom=False)
    add_box(bm, -4.1, -1.8, -1.1, -0.45, main_roof_z + 0.35, main_roof_z + 0.95, MAT_METAL, skip_bottom=False)
    for vx, vy in ((-5.6, 2.2), (-5.6, 4.4), (5.4, -1.2)):
        add_box(bm, vx - 0.25, vx + 0.25, vy - 0.25, vy + 0.25, main_roof_z, main_roof_z + 0.95, MAT_METAL, skip_bottom=True)
        add_box(bm, vx - 0.38, vx + 0.38, vy - 0.38, vy + 0.38, main_roof_z + 0.95, main_roof_z + 1.15, MAT_METAL, skip_bottom=False)

    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bm.normal_update()

    for f in bm.faces:
        f.smooth = False
    for e in bm.edges:
        e.smooth = False

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return obj


out_arg = "output/BldgOffice.fbx"
if "--" in sys.argv:
    idx = sys.argv.index("--")
    if idx + 1 < len(sys.argv):
        out_arg = sys.argv[idx + 1]

out_arg = os.path.abspath(out_arg)
if out_arg.lower().endswith(".fbx"):
    fbx_path = out_arg
    preview_path = out_arg[:-4] + ".png"
elif out_arg.lower().endswith(".png"):
    preview_path = out_arg
    fbx_path = out_arg[:-4] + ".fbx"
else:
    fbx_path = out_arg + ".fbx"
    preview_path = out_arg + ".png"

out_dir = os.path.dirname(fbx_path)
if out_dir:
    os.makedirs(out_dir, exist_ok=True)

bldg = build_office_building()

bpy.context.view_layer.objects.active = bldg
bldg.select_set(True)

if not bldg.data.uv_layers:
    bldg.data.uv_layers.new(name="UVMap")

bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.01)
bpy.ops.uv.average_islands_scale()
bpy.ops.uv.pack_islands(margin=0.01)
bpy.ops.object.mode_set(mode="OBJECT")

albedo_img = bpy.data.images.new(f"{BUILDING_NAME}_albedo", width=2048, height=2048, alpha=False)
albedo_img.colorspace_settings.name = "sRGB"

normal_img = bpy.data.images.new(f"{BUILDING_NAME}_normal", width=2048, height=2048, alpha=False)
normal_img.colorspace_settings.name = "Non-Color"

bake_nodes = []
for mat in bldg.data.materials:
    nt = mat.node_tree
    tex_node = nt.nodes.new("ShaderNodeTexImage")
    tex_node.name = "BakeTarget"
    bake_nodes.append((nt, tex_node))

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 16
scene.render.bake.margin = 8

for nt, tex_node in bake_nodes:
    for n in nt.nodes:
        n.select = False
    tex_node.image = albedo_img
    tex_node.select = True
    nt.nodes.active = tex_node

scene.render.bake.use_pass_direct = False
scene.render.bake.use_pass_indirect = False
scene.render.bake.use_pass_color = True
bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=8)

albedo_path = os.path.join(out_dir, f"{BUILDING_NAME}_albedo.png")
albedo_img.filepath_raw = albedo_path
albedo_img.file_format = "PNG"
albedo_img.save()

for nt, tex_node in bake_nodes:
    for n in nt.nodes:
        n.select = False
    tex_node.image = normal_img
    tex_node.select = True
    nt.nodes.active = tex_node

scene.render.bake.normal_space = "TANGENT"
bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", margin=8)

normal_path = os.path.join(out_dir, f"{BUILDING_NAME}_normal.png")
normal_img.filepath_raw = normal_path
normal_img.file_format = "PNG"
normal_img.save()

final_mat = bpy.data.materials.new(name=f"{BUILDING_NAME}_Mat")
final_mat.use_nodes = True
fnt = final_mat.node_tree
fnt.nodes.clear()
flinks = fnt.links

f_out = fnt.nodes.new("ShaderNodeOutputMaterial")
f_bsdf = fnt.nodes.new("ShaderNodeBsdfPrincipled")
f_bsdf.inputs["Roughness"].default_value = 0.7
f_bsdf.inputs["Metallic"].default_value = 0.0
flinks.new(f_bsdf.outputs["BSDF"], f_out.inputs["Surface"])

f_alb = fnt.nodes.new("ShaderNodeTexImage")
f_alb.image = albedo_img
flinks.new(f_alb.outputs["Color"], f_bsdf.inputs["Base Color"])

f_nrm_tex = fnt.nodes.new("ShaderNodeTexImage")
f_nrm_tex.image = normal_img
normal_img.colorspace_settings.name = "Non-Color"

f_nrm_map = fnt.nodes.new("ShaderNodeNormalMap")
f_nrm_map.inputs["Strength"].default_value = 1.0
flinks.new(f_nrm_tex.outputs["Color"], f_nrm_map.inputs["Color"])
flinks.new(f_nrm_map.outputs["Normal"], f_bsdf.inputs["Normal"])

bldg.data.materials.clear()
bldg.data.materials.append(final_mat)
for poly in bldg.data.polygons:
    poly.material_index = 0

bpy.ops.object.select_all(action="DESELECT")
bldg.select_set(True)
bpy.context.view_layer.objects.active = bldg
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bpy.ops.export_scene.fbx(
    filepath=fbx_path,
    use_selection=True,
    bake_space_transform=True,
    axis_forward="-Z",
    axis_up="Y",
    path_mode="COPY",
    embed_textures=True,
)

tris = sum(len(p.vertices) - 2 for p in bldg.data.polygons)
print("TRIS", tris)

engine_keys = list(scene.render.bl_rna.properties["engine"].enum_items.keys())
for cand in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    if cand in engine_keys:
        scene.render.engine = cand
        break
else:
    for k in engine_keys:
        if "EEVEE" in k:
            scene.render.engine = k
            break

world = bpy.data.worlds.new("SkyWorld")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
wnt.nodes.clear()
w_bg = wnt.nodes.new("ShaderNodeBackground")
w_bg.inputs["Color"].default_value = (0.58, 0.60, 0.64, 1.0)
w_bg.inputs["Strength"].default_value = 0.6
w_out = wnt.nodes.new("ShaderNodeOutputWorld")
wnt.links.new(w_bg.outputs["Background"], w_out.inputs["Surface"])

sun_data = bpy.data.lights.new(name="SunLight", type="SUN")
sun_data.energy = 3.0
sun_data.color = (1.0, 0.98, 0.94)
sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
bpy.context.collection.objects.link(sun_obj)
sun_obj.location = (-28.0, -32.0, 52.0)
sun_dir = Vector((0.0, 0.0, 18.0)) - sun_obj.location
sun_obj.rotation_euler = sun_dir.to_track_quat("-Z", "Y").to_euler()

cam_data = bpy.data.cameras.new(name="PreviewCam")
cam_data.lens = 29.0
cam_data.sensor_width = 36.0
cam_data.clip_start = 0.1
cam_data.clip_end = 500.0
cam_obj = bpy.data.objects.new(name="PreviewCam", object_data=cam_data)
bpy.context.collection.objects.link(cam_obj)
cam_obj.location = Vector((-38.0, -46.0, 4.5))
look_target = Vector((0.0, 0.0, 21.5))
cam_dir = look_target - cam_obj.location
cam_obj.rotation_euler = cam_dir.to_track_quat("-Z", "Y").to_euler()
scene.camera = cam_obj

scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = preview_path
bpy.ops.render.render(write_still=True)
