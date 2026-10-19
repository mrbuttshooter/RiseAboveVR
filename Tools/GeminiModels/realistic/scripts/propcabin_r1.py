import bpy
import bmesh
import mathutils
import math
import sys
import os


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)
    for img in list(bpy.data.images):
        bpy.data.images.remove(img)
    for light in list(bpy.data.lights):
        bpy.data.lights.remove(light)
    for cam in list(bpy.data.cameras):
        bpy.data.cameras.remove(cam)
    for world in list(bpy.data.worlds):
        bpy.data.worlds.remove(world)


def set_principled(bsdf, name, value):
    if name in bsdf.inputs:
        bsdf.inputs[name].default_value = value


def build_weathered_material(
    name,
    base_col,
    alt_col,
    rust_col=(0.34, 0.14, 0.06, 1.0),
    dirt_col=(0.20, 0.16, 0.11, 1.0),
    roughness=0.55,
    metallic=0.0,
    noise_scale=6.0,
    scratch_scale=45.0,
    bump_strength=0.12,
    dirt_height=0.42,
    dirt_amount=0.85,
    rust_amount=0.35,
    wood_grain=False,
    img_albedo=None,
    img_normal=None,
):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out_node = nodes.new(type="ShaderNodeOutputMaterial")
    out_node.location = (900, 0)

    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.location = (600, 0)
    set_principled(bsdf, "Roughness", roughness)
    set_principled(bsdf, "Metallic", metallic)
    links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])

    geom = nodes.new(type="ShaderNodeNewGeometry")
    geom.location = (-900, 200)

    sep_xyz = nodes.new(type="ShaderNodeSeparateXYZ")
    sep_xyz.location = (-700, 350)
    links.new(geom.outputs["Position"], sep_xyz.inputs["Vector"])

    noise_main = nodes.new(type="ShaderNodeTexNoise")
    noise_main.location = (-650, 50)
    noise_main.inputs["Scale"].default_value = noise_scale
    noise_main.inputs["Detail"].default_value = 6.0
    noise_main.inputs["Roughness"].default_value = 0.65

    if wood_grain:
        mapping = nodes.new(type="ShaderNodeMapping")
        mapping.location = (-820, 50)
        mapping.inputs["Scale"].default_value = (14.0, 1.4, 14.0)
        links.new(geom.outputs["Position"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], noise_main.inputs["Vector"])
    else:
        links.new(geom.outputs["Position"], noise_main.inputs["Vector"])

    mix_base = nodes.new(type="ShaderNodeMixRGB")
    mix_base.location = (-350, 120)
    mix_base.blend_type = "MIX"
    mix_base.inputs["Color1"].default_value = base_col
    mix_base.inputs["Color2"].default_value = alt_col
    links.new(noise_main.outputs["Fac"], mix_base.inputs["Fac"])

    noise_scratch = nodes.new(type="ShaderNodeTexVoronoi")
    noise_scratch.location = (-650, -180)
    noise_scratch.inputs["Scale"].default_value = scratch_scale
    links.new(geom.outputs["Position"], noise_scratch.inputs["Vector"])

    ramp_scratch = nodes.new(type="ShaderNodeValToRGB")
    ramp_scratch.location = (-420, -180)
    ramp_scratch.color_ramp.elements[0].position = 0.02
    ramp_scratch.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
    ramp_scratch.color_ramp.elements[1].position = 0.09
    ramp_scratch.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    links.new(noise_scratch.outputs["Distance"], ramp_scratch.inputs["Fac"])

    math_scratch_mul = nodes.new(type="ShaderNodeMath")
    math_scratch_mul.location = (-200, -180)
    math_scratch_mul.operation = "MULTIPLY"
    math_scratch_mul.inputs[1].default_value = 0.25
    links.new(ramp_scratch.outputs["Color"], math_scratch_mul.inputs[0])

    mix_scratch = nodes.new(type="ShaderNodeMixRGB")
    mix_scratch.location = (-80, 100)
    mix_scratch.inputs["Color2"].default_value = (0.58, 0.60, 0.62, 1.0)
    links.new(math_scratch_mul.outputs["Value"], mix_scratch.inputs["Fac"])
    links.new(mix_base.outputs["Color"], mix_scratch.inputs["Color1"])

    map_rust = nodes.new(type="ShaderNodeMapping")
    map_rust.location = (-820, -400)
    map_rust.inputs["Scale"].default_value = (6.0, 6.0, 1.2)
    links.new(geom.outputs["Position"], map_rust.inputs["Vector"])

    noise_rust = nodes.new(type="ShaderNodeTexNoise")
    noise_rust.location = (-650, -400)
    noise_rust.inputs["Scale"].default_value = 4.5
    noise_rust.inputs["Detail"].default_value = 8.0
    noise_rust.inputs["Roughness"].default_value = 0.7
    links.new(map_rust.outputs["Vector"], noise_rust.inputs["Vector"])

    ramp_rust = nodes.new(type="ShaderNodeValToRGB")
    ramp_rust.location = (-420, -400)
    ramp_rust.color_ramp.elements[0].position = 0.58
    ramp_rust.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp_rust.color_ramp.elements[1].position = 0.76
    ramp_rust.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(noise_rust.outputs["Fac"], ramp_rust.inputs["Fac"])

    math_rust = nodes.new(type="ShaderNodeMath")
    math_rust.location = (-200, -400)
    math_rust.operation = "MULTIPLY"
    math_rust.inputs[1].default_value = rust_amount
    links.new(ramp_rust.outputs["Color"], math_rust.inputs[0])

    mix_rust = nodes.new(type="ShaderNodeMixRGB")
    mix_rust.location = (110, 80)
    mix_rust.inputs["Color2"].default_value = rust_col
    links.new(math_rust.outputs["Value"], mix_rust.inputs["Fac"])
    links.new(mix_scratch.outputs["Color"], mix_rust.inputs["Color1"])

    noise_dirt = nodes.new(type="ShaderNodeTexNoise")
    noise_dirt.location = (-650, 520)
    noise_dirt.inputs["Scale"].default_value = 7.5
    noise_dirt.inputs["Detail"].default_value = 7.0
    noise_dirt.inputs["Roughness"].default_value = 0.75
    links.new(geom.outputs["Position"], noise_dirt.inputs["Vector"])

    math_dirt_splash = nodes.new(type="ShaderNodeMath")
    math_dirt_splash.location = (-450, 480)
    math_dirt_splash.operation = "MULTIPLY"
    math_dirt_splash.inputs[1].default_value = 0.28
    links.new(noise_dirt.outputs["Fac"], math_dirt_splash.inputs[0])

    math_z_mod = nodes.new(type="ShaderNodeMath")
    math_z_mod.location = (-260, 420)
    math_z_mod.operation = "SUBTRACT"
    links.new(sep_xyz.outputs["Z"], math_z_mod.inputs[0])
    links.new(math_dirt_splash.outputs["Value"], math_z_mod.inputs[1])

    math_z_norm = nodes.new(type="ShaderNodeMath")
    math_z_norm.location = (-90, 420)
    math_z_norm.operation = "DIVIDE"
    math_z_norm.inputs[1].default_value = max(0.05, dirt_height)
    links.new(math_z_mod.outputs["Value"], math_z_norm.inputs[0])

    ramp_dirt = nodes.new(type="ShaderNodeValToRGB")
    ramp_dirt.location = (80, 420)
    ramp_dirt.color_ramp.elements[0].position = 0.0
    ramp_dirt.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
    ramp_dirt.color_ramp.elements[1].position = 0.85
    ramp_dirt.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    links.new(math_z_norm.outputs["Value"], ramp_dirt.inputs["Fac"])

    math_dirt_fac = nodes.new(type="ShaderNodeMath")
    math_dirt_fac.location = (290, 350)
    math_dirt_fac.operation = "MULTIPLY"
    math_dirt_fac.inputs[1].default_value = dirt_amount
    links.new(ramp_dirt.outputs["Color"], math_dirt_fac.inputs[0])

    mix_dirt = nodes.new(type="ShaderNodeMixRGB")
    mix_dirt.location = (380, 100)
    mix_dirt.inputs["Color2"].default_value = dirt_col
    links.new(math_dirt_fac.outputs["Value"], mix_dirt.inputs["Fac"])
    links.new(mix_rust.outputs["Color"], mix_dirt.inputs["Color1"])

    links.new(mix_dirt.outputs["Color"], bsdf.inputs["Base Color"])

    math_bump_sum = nodes.new(type="ShaderNodeMath")
    math_bump_sum.location = (180, -250)
    math_bump_sum.operation = "ADD"
    links.new(noise_main.outputs["Fac"], math_bump_sum.inputs[0])
    links.new(math_dirt_fac.outputs["Value"], math_bump_sum.inputs[1])

    bump_node = nodes.new(type="ShaderNodeBump")
    bump_node.location = (380, -220)
    bump_node.inputs["Strength"].default_value = bump_strength
    bump_node.inputs["Distance"].default_value = 0.015
    links.new(math_bump_sum.outputs["Value"], bump_node.inputs["Height"])
    links.new(bump_node.outputs["Normal"], bsdf.inputs["Normal"])

    if img_albedo is not None:
        tex_alb = nodes.new(type="ShaderNodeTexImage")
        tex_alb.name = "Bake_Albedo"
        tex_alb.location = (600, 360)
        tex_alb.image = img_albedo

    if img_normal is not None:
        tex_nrm = nodes.new(type="ShaderNodeTexImage")
        tex_nrm.name = "Bake_Normal"
        tex_nrm.location = (600, 620)
        tex_nrm.image = img_normal

    return mat


def add_box(bm, x0, x1, y0, y1, z0, z1, mat_idx, nx=1, ny=1, nz=1, skip_faces=()):
    if x0 > x1:
        x0, x1 = x1, x0
    if y0 > y1:
        y0, y1 = y1, y0
    if z0 > z1:
        z0, z1 = z1, z0

    xs = [x0 + (x1 - x0) * i / nx for i in range(nx + 1)]
    ys = [y0 + (y1 - y0) * i / ny for i in range(ny + 1)]
    zs = [z0 + (z1 - z0) * i / nz for i in range(nz + 1)]

    def make_grid(u_vals, v_vals, coord_fn, flip=False):
        grid = [[bm.verts.new(coord_fn(u, v)) for v in v_vals] for u in u_vals]
        for i in range(len(u_vals) - 1):
            for j in range(len(v_vals) - 1):
                v00 = grid[i][j]
                v10 = grid[i + 1][j]
                v11 = grid[i + 1][j + 1]
                v01 = grid[i][j + 1]
                verts = (v00, v01, v11, v10) if flip else (v00, v10, v11, v01)
                f = bm.faces.new(verts)
                f.material_index = mat_idx
                f.smooth = False

    if "-Z" not in skip_faces:
        make_grid(xs, ys, lambda x, y: (x, y, z0), flip=True)
    if "+Z" not in skip_faces:
        make_grid(xs, ys, lambda x, y: (x, y, z1), flip=False)
    if "-Y" not in skip_faces:
        make_grid(xs, zs, lambda x, z: (x, y0, z), flip=False)
    if "+Y" not in skip_faces:
        make_grid(xs, zs, lambda x, z: (x, y1, z), flip=True)
    if "-X" not in skip_faces:
        make_grid(ys, zs, lambda y, z: (x0, y, z), flip=True)
    if "+X" not in skip_faces:
        make_grid(ys, zs, lambda y, z: (x1, y, z), flip=False)


def add_prism_points(bm, pts_bottom, pts_top, mat_idx, cap_bottom=True, cap_top=True):
    n = len(pts_bottom)
    vb = [bm.verts.new(p) for p in pts_bottom]
    vt = [bm.verts.new(p) for p in pts_top]
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((vb[i], vb[j], vt[j], vt[i]))
        f.material_index = mat_idx
        f.smooth = False
    if cap_bottom and n >= 3:
        fb = bm.faces.new(tuple(reversed(vb)))
        fb.material_index = mat_idx
        fb.smooth = False
    if cap_top and n >= 3:
        ft = bm.faces.new(tuple(vt))
        ft.material_index = mat_idx
        ft.smooth = False


def add_cylinder_along(bm, p0, p1, radius, segments, mat_idx, cap_ends=True):
    v0 = mathutils.Vector(p0)
    v1 = mathutils.Vector(p1)
    axis = v1 - v0
    length = axis.length
    if length < 1e-6:
        return
    axis.normalize()
    up = mathutils.Vector((0.0, 0.0, 1.0))
    if abs(axis.dot(up)) > 0.95:
        up = mathutils.Vector((1.0, 0.0, 0.0))
    t1 = axis.cross(up).normalized()
    t2 = axis.cross(t1).normalized()

    pts0 = []
    pts1 = []
    for i in range(segments):
        ang = 2.0 * math.pi * i / segments
        offset = (t1 * math.cos(ang) + t2 * math.sin(ang)) * radius
        pts0.append(v0 + offset)
        pts1.append(v1 + offset)
    add_prism_points(bm, pts0, pts1, mat_idx, cap_bottom=cap_ends, cap_top=cap_ends)


def add_frame_rect_y(bm, x0, x1, z0, z1, y_front, y_back, border, mat_idx):
    add_box(bm, x0, x1, y_front, y_back, z0, z0 + border, mat_idx)
    add_box(bm, x0, x1, y_front, y_back, z1 - border, z1, mat_idx)
    add_box(bm, x0, x0 + border, y_front, y_back, z0 + border, z1 - border, mat_idx)
    add_box(bm, x1 - border, x1, y_front, y_back, z0 + border, z1 - border, mat_idx)


def add_corrugated_wall_x(
    bm,
    x_start,
    x_end,
    z_levels,
    y_base,
    rib_depth,
    n_waves,
    openings,
    mat_idx,
    facing_neg_y=True,
):
    thickness = 0.022 if facing_neg_y else -0.022
    u_pts = []
    wave_len = (x_end - x_start) / n_waves
    profile_fracs = [
        (0.00, 0.0),
        (0.28, 0.0),
        (0.42, 1.0),
        (0.78, 1.0),
    ]
    for w in range(n_waves):
        wx = x_start + w * wave_len
        for frac, d in profile_fracs:
            x_val = wx + frac * wave_len
            y_val = y_base + (-rib_depth * d if facing_neg_y else rib_depth * d)
            u_pts.append((x_val, y_val))
    u_pts.append((x_end, y_base))

    nu = len(u_pts)
    nz = len(z_levels)
    front_grid = [[None] * nz for _ in range(nu)]
    back_grid = [[None] * nz for _ in range(nu)]

    for i, (xv, yv) in enumerate(u_pts):
        for k, zv in enumerate(z_levels):
            front_grid[i][k] = bm.verts.new((xv, yv, zv))
            back_grid[i][k] = bm.verts.new((xv, yv + thickness, zv))

    def is_open(xc, zc):
        for ox0, ox1, oz0, oz1 in openings:
            if ox0 + 0.002 < xc < ox1 - 0.002 and oz0 + 0.002 < zc < oz1 - 0.002:
                return True
        return False

    active = [[False] * (nz - 1) for _ in range(nu - 1)]
    for i in range(nu - 1):
        xc = 0.5 * (u_pts[i][0] + u_pts[i + 1][0])
        for k in range(nz - 1):
            zc = 0.5 * (z_levels[k] + z_levels[k + 1])
            if not is_open(xc, zc):
                active[i][k] = True
                vf00 = front_grid[i][k]
                vf10 = front_grid[i + 1][k]
                vf11 = front_grid[i + 1][k + 1]
                vf01 = front_grid[i][k + 1]

                vb00 = back_grid[i][k]
                vb10 = back_grid[i + 1][k]
                vb11 = back_grid[i + 1][k + 1]
                vb01 = back_grid[i][k + 1]

                if facing_neg_y:
                    f1 = bm.faces.new((vf00, vf10, vf11, vf01))
                    f2 = bm.faces.new((vb00, vb01, vb11, vb10))
                else:
                    f1 = bm.faces.new((vf00, vf01, vf11, vf10))
                    f2 = bm.faces.new((vb00, vb10, vb11, vb01))
                f1.material_index = mat_idx
                f1.smooth = False
                f2.material_index = mat_idx
                f2.smooth = False

    for i in range(nu - 1):
        for k in range(nz - 1):
            if not active[i][k]:
                continue
            if k == 0 or not active[i][k - 1]:
                verts = (
                    (front_grid[i][k], back_grid[i][k], back_grid[i + 1][k], front_grid[i + 1][k])
                    if facing_neg_y
                    else (front_grid[i][k], front_grid[i + 1][k], back_grid[i + 1][k], back_grid[i][k])
                )
                f = bm.faces.new(verts)
                f.material_index = mat_idx
                f.smooth = False
            if k == nz - 2 or not active[i][k + 1]:
                verts = (
                    (front_grid[i][k + 1], front_grid[i + 1][k + 1], back_grid[i + 1][k + 1], back_grid[i][k + 1])
                    if facing_neg_y
                    else (front_grid[i][k + 1], back_grid[i][k + 1], back_grid[i + 1][k + 1], front_grid[i + 1][k + 1])
                )
                f = bm.faces.new(verts)
                f.material_index = mat_idx
                f.smooth = False
            if i == 0 or not active[i - 1][k]:
                verts = (
                    (front_grid[i][k], front_grid[i][k + 1], back_grid[i][k + 1], back_grid[i][k])
                    if facing_neg_y
                    else (front_grid[i][k], back_grid[i][k], back_grid[i][k + 1], front_grid[i][k + 1])
                )
                f = bm.faces.new(verts)
                f.material_index = mat_idx
                f.smooth = False
            if i == nu - 2 or not active[i + 1][k]:
                verts = (
                    (front_grid[i + 1][k], back_grid[i + 1][k], back_grid[i + 1][k + 1], front_grid[i + 1][k + 1])
                    if facing_neg_y
                    else (front_grid[i + 1][k], front_grid[i + 1][k + 1], back_grid[i + 1][k + 1], back_grid[i + 1][k])
                )
                f = bm.faces.new(verts)
                f.material_index = mat_idx
                f.smooth = False


def add_corrugated_wall_y(
    bm,
    y_start,
    y_end,
    z_levels,
    x_base,
    rib_depth,
    n_waves,
    mat_idx,
    facing_neg_x=True,
):
    thickness = 0.022 if facing_neg_x else -0.022
    v_pts = []
    wave_len = (y_end - y_start) / n_waves
    profile_fracs = [
        (0.00, 0.0),
        (0.28, 0.0),
        (0.42, 1.0),
        (0.78, 1.0),
    ]
    for w in range(n_waves):
        wy = y_start + w * wave_len
        for frac, d in profile_fracs:
            y_val = wy + frac * wave_len
            x_val = x_base + (-rib_depth * d if facing_neg_x else rib_depth * d)
            v_pts.append((x_val, y_val))
    v_pts.append((x_base, y_end))

    nv = len(v_pts)
    nz = len(z_levels)
    outer_grid = [[bm.verts.new((xv, yv, zv)) for zv in z_levels] for xv, yv in v_pts]
    inner_grid = [[bm.verts.new((xv + thickness, yv, zv)) for zv in z_levels] for xv, yv in v_pts]

    for i in range(nv - 1):
        for k in range(nz - 1):
            vo00 = outer_grid[i][k]
            vo10 = outer_grid[i + 1][k]
            vo11 = outer_grid[i + 1][k + 1]
            vo01 = outer_grid[i][k + 1]

            vi00 = inner_grid[i][k]
            vi10 = inner_grid[i + 1][k]
            vi11 = inner_grid[i + 1][k + 1]
            vi01 = inner_grid[i][k + 1]

            if facing_neg_x:
                f1 = bm.faces.new((vo00, vo01, vo11, vo10))
                f2 = bm.faces.new((vi00, vi10, vi11, vi01))
            else:
                f1 = bm.faces.new((vo00, vo10, vo11, vo01))
                f2 = bm.faces.new((vi00, vi01, vi11, vi10))
            f1.material_index = mat_idx
            f1.smooth = False
            f2.material_index = mat_idx
            f2.smooth = False


def add_iso_corner(bm, x0, x1, y0, y1, z0, z1, mat_idx):
    add_box(bm, x0, x1, y0, y1, z0, z1, mat_idx)
    cx = 0.5 * (x0 + x1)
    cy = 0.5 * (y0 + y1)
    cz = 0.5 * (z0 + z1)
    y_face = y0 if y0 < 0 else y1
    dy = -0.012 if y0 < 0 else 0.012
    add_frame_rect_y(
        bm,
        cx - 0.045,
        cx + 0.045,
        cz - 0.032,
        cz + 0.032,
        min(y_face, y_face + dy),
        max(y_face, y_face + dy),
        0.014,
        mat_idx,
    )


def add_sign_with_text(bm, mat_yellow, mat_black, mat_metal):
    sx0, sx1 = 0.80, 1.42
    sz0, sz1 = 1.50, 1.82
    sy_back = -1.145
    sy_front = -1.164

    add_box(bm, sx0 - 0.01, sx1 + 0.01, sy_front + 0.006, sy_back, sz0 - 0.01, sz1 + 0.01, mat_metal)
    add_box(bm, sx0, sx1, sy_front, sy_front + 0.008, sz0, sz1, mat_yellow, nx=2, nz=2)
    add_frame_rect_y(bm, sx0 + 0.012, sx1 - 0.012, sz0 + 0.012, sz1 - 0.012, sy_front - 0.004, sy_front + 0.001, 0.010, mat_black)

    for rx in (sx0 + 0.026, sx1 - 0.026):
        for rz in (sz0 + 0.026, sz1 - 0.026):
            add_cylinder_along(bm, (rx, sy_front - 0.006, rz), (rx, sy_front + 0.002, rz), 0.007, 6, mat_metal)

    font = {
        "S": [
            (0, 6, 5, 7),
            (0, 3, 1, 6),
            (0, 3, 5, 4),
            (4, 0, 5, 3),
            (0, 0, 5, 1),
        ],
        "I": [
            (0, 6, 5, 7),
            (2, 1, 3, 6),
            (0, 0, 5, 1),
        ],
        "T": [
            (0, 6, 5, 7),
            (2, 0, 3, 6),
        ],
        "E": [
            (0, 0, 1, 7),
            (1, 6, 5, 7),
            (1, 3, 4, 4),
            (1, 0, 5, 1),
        ],
        "O": [
            (0, 0, 1, 7),
            (4, 0, 5, 7),
            (1, 6, 4, 7),
            (1, 0, 4, 1),
        ],
        "F": [
            (0, 0, 1, 7),
            (1, 6, 5, 7),
            (1, 3, 4, 4),
        ],
        "C": [
            (0, 0, 1, 7),
            (1, 6, 5, 7),
            (1, 0, 5, 1),
        ],
    }

    def draw_word(word, x_center, z_bottom, char_w, char_h, spacing):
        total_w = len(word) * char_w + (len(word) - 1) * spacing
        x_Origin = x_center - 0.5 * total_w
        pw = char_w / 5.0
        ph = char_h / 7.0
        for idx, ch in enumerate(word):
            cx0 = x_Origin + idx * (char_w + spacing)
            for bx0, by0, bx1, by1 in font.get(ch, []):
                add_box(
                    bm,
                    cx0 + bx0 * pw,
                    cx0 + bx1 * pw,
                    sy_front - 0.005,
                    sy_front + 0.001,
                    z_bottom + by0 * ph,
                    z_bottom + by1 * ph,
                    mat_black,
                )

    draw_word("SITE", 1.11, 1.675, 0.068, 0.098, 0.018)
    draw_word("OFFICE", 1.11, 1.545, 0.064, 0.095, 0.015)


def add_sliding_window_with_mesh(bm, wx0, wx1, wz0, wz1, mat_frame, mat_glass, mat_galv, mat_black):
    add_box(bm, wx0 + 0.02, wx1 - 0.02, -1.02, -0.98, wz0 + 0.02, wz1 - 0.02, mat_black)

    add_frame_rect_y(bm, wx0 - 0.03, wx1 + 0.03, wz0 - 0.03, wz1 + 0.03, -1.185, -1.03, 0.045, mat_frame)
    add_box(bm, wx0 - 0.045, wx1 + 0.045, -1.215, -1.14, wz0 - 0.045, wz0 - 0.015, mat_frame, nx=3)

    w_mid = 0.5 * (wx0 + wx1)
    sash_b = 0.038

    lx0, lx1 = wx0 + 0.015, w_mid + 0.018
    lz0, lz1 = wz0 + 0.015, wz1 - 0.015
    add_frame_rect_y(bm, lx0, lx1, lz0, lz1, -1.125, -1.095, sash_b, mat_frame)
    add_frame_rect_y(bm, lx0 + sash_b, lx1 - sash_b, lz0 + sash_b, lz1 - sash_b, -1.120, -1.100, 0.010, mat_black)
    add_box(
        bm,
        lx0 + sash_b + 0.008,
        lx1 - sash_b - 0.008,
        -1.114,
        -1.106,
        lz0 + sash_b + 0.008,
        lz1 - sash_b - 0.008,
        mat_glass,
        nx=2,
        nz=2,
    )

    rx0, rx1 = w_mid - 0.018, wx1 - 0.015
    rz0, rz1 = wz0 + 0.015, wz1 - 0.015
    add_frame_rect_y(bm, rx0, rx1, rz0, rz1, -1.092, -1.062, sash_b, mat_frame)
    add_frame_rect_y(bm, rx0 + sash_b, rx1 - sash_b, rz0 + sash_b, rz1 - sash_b, -1.087, -1.067, 0.010, mat_black)
    add_box(
        bm,
        rx0 + sash_b + 0.008,
        rx1 - sash_b - 0.008,
        -1.081,
        -1.073,
        rz0 + sash_b + 0.008,
        rz1 - sash_b - 0.008,
        mat_glass,
        nx=2,
        nz=2,
    )

    cz = 0.5 * (wz0 + wz1)
    add_box(bm, w_mid - 0.012, w_mid + 0.012, -1.135, -1.095, cz - 0.055, cz + 0.055, mat_black)

    mx0, mx1 = wx0 - 0.015, wx1 + 0.015
    mz0, mz1 = wz0 - 0.010, wz1 + 0.015
    my_front, my_back = -1.238, -1.214

    add_frame_rect_y(bm, mx0, mx1, mz0, mz1, my_front, my_back, 0.024, mat_galv)
    add_box(bm, mx0 + 0.02, mx1 - 0.02, my_front + 0.003, my_back - 0.003, cz - 0.012, cz + 0.012, mat_galv)

    for bx in (mx0 + 0.02, w_mid, mx1 - 0.02):
        for bz in (mz0 + 0.04, mz1 - 0.04):
            add_box(bm, bx - 0.016, bx + 0.016, -1.22, -1.165, bz - 0.016, bz + 0.016, mat_frame)

    n_vbars = 13
    for i in range(1, n_vbars):
        bx = mx0 + (mx1 - mx0) * i / n_vbars
        add_box(bm, bx - 0.0035, bx + 0.0035, my_front + 0.006, my_back - 0.006, mz0 + 0.02, mz1 - 0.02, mat_galv)

    n_hbars = 9
    for j in range(1, n_hbars):
        bz = mz0 + (mz1 - mz0) * j / n_hbars
        add_box(bm, mx0 + 0.02, mx1 - 0.02, my_front + 0.009, my_back - 0.003, bz - 0.0035, bz + 0.0035, mat_galv)


def add_door_and_stairs(bm, mat_frame, mat_door, mat_galv, mat_glass, mat_black):
    dx0, dx1 = 1.48, 2.44
    dz0, dz1 = 0.26, 2.28

    add_box(bm, dx0 + 0.03, dx1 - 0.03, -1.03, -0.99, dz0 + 0.02, dz1 - 0.02, mat_black)

    add_frame_rect_y(bm, dx0 - 0.035, dx1 + 0.035, dz0, dz1 + 0.035, -1.19, -1.04, 0.055, mat_frame)
    add_box(bm, dx0 - 0.04, dx1 + 0.04, -1.205, -1.04, dz0 - 0.018, dz0 + 0.015, mat_galv, nx=3)

    lx0, lx1 = dx0 + 0.02, dx1 - 0.02
    lz0, lz1 = dz0 + 0.015, dz1 - 0.02
    add_box(bm, lx0, lx1, -1.135, -1.085, lz0, lz1, mat_door, nx=4, nz=5)

    add_box(bm, lx0 + 0.015, lx1 - 0.015, -1.142, -1.132, lz0 + 0.01, lz0 + 0.23, mat_galv, nx=3)

    for px in (lx0 + 0.08, 0.5 * (lx0 + lx1), lx1 - 0.08):
        add_box(bm, px - 0.006, px + 0.006, -1.140, -1.132, lz0 + 0.26, 1.38, mat_frame)

    wx0, wx1 = 1.73, 2.19
    wz0, wz1 = 1.46, 2.02
    add_frame_rect_y(bm, wx0, wx1, wz0, wz1, -1.152, -1.075, 0.032, mat_black)
    add_box(bm, wx0 + 0.028, wx1 - 0.028, -1.125, -1.105, wz0 + 0.028, wz1 - 0.028, mat_glass, nx=2, nz=2)
    for b_idx in range(3):
        bx = wx0 + 0.115 * (b_idx + 1)
        add_box(bm, bx - 0.004, bx + 0.004, -1.145, -1.135, wz0 + 0.025, wz1 - 0.025, mat_galv)

    hx = lx0 + 0.075
    hz = 1.18
    add_box(bm, hx - 0.022, hx + 0.022, -1.152, -1.135, hz - 0.095, hz + 0.095, mat_galv)
    add_box(bm, hx - 0.012, hx + 0.012, -1.188, -1.148, hz + 0.015, hz + 0.038, mat_galv)
    add_box(bm, hx - 0.012, hx + 0.115, -1.192, -1.172, hz + 0.014, hz + 0.038, mat_galv)
    add_cylinder_along(bm, (hx, -1.158, hz - 0.045), (hx, -1.135, hz - 0.045), 0.013, 8, mat_black)

    for h_z in (0.52, 1.26, 2.00):
        add_cylinder_along(bm, (lx1 + 0.006, -1.152, h_z - 0.045), (lx1 + 0.006, -1.152, h_z + 0.045), 0.013, 8, mat_galv)

    add_box(bm, dx0 - 0.06, dx1 + 0.06, -1.28, -1.14, dz1 + 0.035, dz1 + 0.062, mat_door, nx=3)
    add_box(bm, dx0 - 0.06, dx1 + 0.06, -1.28, -1.26, dz1 + 0.012, dz1 + 0.035, mat_door)

    add_box(bm, 1.24, 1.38, -1.18, -1.14, 2.12, 2.21, mat_black)
    add_box(bm, 1.255, 1.365, -1.205, -1.175, 2.132, 2.198, mat_glass)

    sx0, sx1 = 1.44, 2.48
    sy_wall = -1.18
    sy_land = -1.46
    sy_end = -2.06

    add_box(bm, sx0 + 0.025, sx1 - 0.025, sy_land, sy_wall, 0.225, 0.258, mat_galv, nx=4, ny=2)
    for r in range(5):
        ry = sy_land + 0.03 + r * 0.052
        add_box(bm, sx0 + 0.035, sx1 - 0.035, ry - 0.007, ry + 0.007, 0.258, 0.265, mat_galv, nx=2)

    steps = [
        (-1.66, -1.46, 0.190),
        (-1.86, -1.66, 0.125),
        (-2.06, -1.86, 0.060),
    ]
    for y_front, y_back, z_top in steps:
        add_box(bm, sx0 + 0.025, sx1 - 0.025, y_front, y_back, z_top - 0.030, z_top, mat_galv, nx=4, ny=2)
        for r in range(4):
            ry = y_front + 0.025 + r * 0.048
            add_box(bm, sx0 + 0.035, sx1 - 0.035, ry - 0.006, ry + 0.006, z_top, z_top + 0.007, mat_galv, nx=2)

    for side_x in (sx0 + 0.012, sx1 - 0.012):
        add_box(bm, side_x - 0.014, side_x + 0.014, sy_land - 0.02, sy_wall, 0.15, 0.265, mat_frame)
        pts_b = [
            (side_x - 0.014, sy_end, 0.00),
            (side_x + 0.014, sy_end, 0.00),
            (side_x + 0.014, sy_end, 0.085),
            (side_x - 0.014, sy_end, 0.085),
        ]
        pts_t = [
            (side_x - 0.014, sy_land, 0.175),
            (side_x + 0.014, sy_land, 0.175),
            (side_x + 0.014, sy_land, 0.265),
            (side_x - 0.014, sy_land, 0.265),
        ]
        add_prism_points(bm, pts_b, pts_t, mat_frame)
        add_box(bm, side_x - 0.045, side_x + 0.045, sy_end - 0.03, sy_end + 0.06, 0.00, 0.016, mat_frame)
        add_box(bm, side_x - 0.045, side_x + 0.045, sy_wall - 0.08, sy_wall, 0.00, 0.225, mat_frame)

        r_tube = 0.019
        p_bot_base = (side_x, sy_end + 0.04, 0.06)
        p_bot_top = (side_x, sy_end + 0.04, 0.96)
        p_bot_mid = (side_x, sy_end + 0.04, 0.54)

        p_land_base = (side_x, sy_land + 0.02, 0.25)
        p_land_top = (side_x, sy_land + 0.02, 1.15)
        p_land_mid = (side_x, sy_land + 0.02, 0.73)

        p_wall_top = (side_x, sy_wall + 0.01, 1.15)
        p_wall_mid = (side_x, sy_wall + 0.01, 0.73)

        add_cylinder_along(bm, p_bot_base, p_bot_top, r_tube, 8, mat_galv)
        add_cylinder_along(bm, p_land_base, p_land_top, r_tube, 8, mat_galv)
        add_cylinder_along(bm, p_bot_top, p_land_top, r_tube, 8, mat_galv)
        add_cylinder_along(bm, p_land_top, p_wall_top, r_tube, 8, mat_galv)
        add_cylinder_along(bm, p_bot_mid, p_land_mid, r_tube * 0.8, 8, mat_galv)
        add_cylinder_along(bm, p_land_mid, p_wall_mid, r_tube * 0.8, 8, mat_galv)

        add_box(bm, side_x - 0.035, side_x + 0.035, -1.195, -1.155, 1.11, 1.19, mat_frame)
        add_box(bm, side_x - 0.035, side_x + 0.035, -1.195, -1.155, 0.69, 0.77, mat_frame)


def add_wall_ac_unit(bm, mat_ac, mat_frame, mat_galv, mat_black):
    ax_outer = -3.32
    ax_inner = -2.96
    ay0, ay1 = -0.58, 0.34
    az0, az1 = 1.28, 1.88

    for by in (ay0 + 0.12, ay1 - 0.12):
        add_box(bm, -2.98, -2.94, by - 0.025, by + 0.025, 0.94, 1.30, mat_galv)
        add_box(bm, ax_outer + 0.02, -2.95, by - 0.025, by + 0.025, 1.24, 1.28, mat_galv)
        pts_b = [
            (-2.96, by - 0.018, 0.98),
            (-2.96, by + 0.018, 0.98),
            (-2.96, by + 0.018, 1.02),
            (-2.96, by - 0.018, 1.02),
        ]
        pts_t = [
            (ax_outer + 0.08, by - 0.018, 1.24),
            (ax_outer + 0.08, by + 0.018, 1.24),
            (ax_outer + 0.08, by + 0.018, 1.26),
            (ax_outer + 0.08, by - 0.018, 1.26),
        ]
        add_prism_points(bm, pts_b, pts_t, mat_galv)
        add_box(bm, ax_outer + 0.05, ax_outer + 0.11, by - 0.03, by + 0.03, 1.275, 1.295, mat_black)
        add_box(bm, -3.06, -3.00, by - 0.03, by + 0.03, 1.275, 1.295, mat_black)

    add_box(bm, ax_outer, ax_inner, ay0, ay1, az0, az1, mat_ac, nx=2, ny=4, nz=3)
    add_box(bm, ax_outer - 0.015, ax_inner + 0.005, ay0 - 0.015, ay1 + 0.015, az1, az1 + 0.028, mat_ac, ny=3)

    fcy = -0.25
    fcz = 1.58
    f_rad = 0.21

    add_cylinder_along(bm, (ax_outer - 0.006, fcy, fcz), (ax_outer + 0.025, fcy, fcz), f_rad, 16, mat_black)
    add_cylinder_along(bm, (ax_outer - 0.010, fcy, fcz), (ax_outer - 0.002, fcy, fcz), 0.052, 10, mat_galv)

    for b in range(5):
        ang = 2.0 * math.pi * b / 5.0 + 0.3
        ang2 = ang + 0.72
        p1 = (ax_outer - 0.008, fcy + math.cos(ang) * 0.045, fcz + math.sin(ang) * 0.045)
        p2 = (ax_outer - 0.004, fcy + math.cos(ang) * 0.185, fcz + math.sin(ang) * 0.185)
        p3 = (ax_outer - 0.012, fcy + math.cos(ang2) * 0.185, fcz + math.sin(ang2) * 0.185)
        p4 = (ax_outer - 0.008, fcy + math.cos(ang2) * 0.045, fcz + math.sin(ang2) * 0.045)
        pts_back = [(p[0] + 0.008, p[1], p[2]) for p in (p1, p2, p3, p4)]
        add_prism_points(bm, [p1, p2, p3, p4], pts_back, mat_black)

    for ring_r in (0.08, 0.145, 0.21):
        segs = 12
        for s in range(segs):
            a0 = 2.0 * math.pi * s / segs
            a1 = 2.0 * math.pi * (s + 1) / segs
            q0 = (ax_outer - 0.016, fcy + math.cos(a0) * ring_r, fcz + math.sin(a0) * ring_r)
            q1 = (ax_outer - 0.016, fcy + math.cos(a1) * ring_r, fcz + math.sin(a1) * ring_r)
            add_cylinder_along(bm, q0, q1, 0.0045, 4, mat_galv, cap_ends=False)

    for s in range(8):
        ang = 2.0 * math.pi * s / 8.0
        q0 = (ax_outer - 0.018, fcy + math.cos(ang) * 0.02, fcz + math.sin(ang) * 0.02)
        q1 = (ax_outer - 0.015, fcy + math.cos(ang) * 0.22, fcz + math.sin(ang) * 0.22)
        add_cylinder_along(bm, q0, q1, 0.0045, 4, mat_galv)

    add_box(bm, ax_outer - 0.008, ax_outer + 0.002, 0.03, 0.042, az0 + 0.02, az1 - 0.02, mat_frame)
    for l_idx in range(11):
        lz = az0 + 0.06 + l_idx * 0.044
        add_box(bm, ax_outer - 0.012, ax_outer + 0.002, 0.075, 0.285, lz - 0.008, lz + 0.008, mat_frame)

    for s_idx in range(8):
        lz = az0 + 0.12 + s_idx * 0.048
        add_box(bm, ax_outer + 0.05, ax_inner - 0.05, ay0 - 0.008, ay0 + 0.002, lz - 0.008, lz + 0.008, mat_frame)

    add_box(bm, -3.14, -2.94, 0.34, 0.44, 1.36, 1.54, mat_frame)
    add_cylinder_along(bm, (-3.08, 0.42, 1.46), (-3.08, 0.62, 1.46), 0.018, 8, mat_black)
    add_cylinder_along(bm, (-3.08, 0.62, 1.46), (-2.94, 0.62, 1.46), 0.018, 8, mat_black)
    add_cylinder_along(bm, (-3.04, 0.42, 1.41), (-3.04, 0.58, 1.41), 0.014, 8, mat_black)
    add_cylinder_along(bm, (-3.04, 0.58, 1.41), (-2.94, 0.58, 1.41), 0.014, 8, mat_black)
    add_box(bm, -3.02, -2.93, 0.53, 0.67, 1.36, 1.52, mat_frame)

    add_cylinder_along(bm, (-3.00, 0.25, 1.28), (-2.97, 0.25, 0.22), 0.009, 6, mat_ac)

    add_box(bm, -3.04, -2.94, 0.72, 0.92, 1.22, 1.52, mat_frame, ny=2, nz=2)
    add_cylinder_along(bm, (-3.06, 0.82, 1.18), (-2.99, 0.82, 1.24), 0.026, 8, mat_Sign_or_AC := mat_ac)


def build_site_cabin(materials):
    mat_wall = 0
    mat_frame = 1
    mat_door = 2
    mat_galv = 3
    mat_glass = 4
    mat_timber = 5
    mat_ac = 6
    mat_yellow = 7
    mat_black = 8

    bm = bmesh.new()

    sleeper_xs = (-2.55, -0.85, 0.85, 2.55)
    for sx in sleeper_xs:
        add_box(bm, sx - 0.12, sx + 0.12, -1.24, 1.24, 0.00, 0.14, mat_timber, nx=2, ny=8, nz=2)
        for sy in (-1.13, 1.13):
            add_box(bm, sx - 0.135, sx + 0.135, sy - 0.09, sy + 0.09, 0.138, 0.156, mat_frame, nx=2, ny=2)
            for bx in (sx - 0.095, sx + 0.095):
                for by in (sy - 0.055, sy + 0.055):
                    add_cylinder_along(bm, (bx, by, 0.155), (bx, by, 0.172), 0.011, 6, mat_galv)

    for sy in (-1.14, 1.14):
        add_box(bm, -2.84, 2.84, sy - 0.055, sy + 0.055, 0.15, 0.265, mat_frame, nx=12, nz=2)
    for fx in (-1.15, 1.15):
        add_frame_rect_y(bm, fx - 0.11, fx + 0.11, 0.155, 0.255, -1.208, -1.08, 0.018, mat_galv)

    for cx in (-2.92, -1.90, -0.85, 0.00, 0.85, 1.90, 2.92):
        add_box(bm, cx - 0.04, cx + 0.04, -1.09, 1.09, 0.16, 0.255, mat_frame, ny=4)

    add_box(bm, -2.92, 2.92, -1.14, 1.14, 0.245, 0.268, mat_frame, nx=6, ny=3)

    for sx_0, sx_1 in ((-3.00, -2.82), (2.82, 3.00)):
        for sy_0, sy_1 in ((-1.20, -1.02), (1.02, 1.20)):
            add_iso_corner(bm, sx_0, sx_1, sy_0, sy_1, 0.14, 0.28, mat_frame)
            add_iso_corner(bm, sx_0, sx_1, sy_0, sy_1, 2.44, 2.60, mat_frame)

    corners = [
        (-2.98, -2.84, -1.18, -1.04),
        (2.84, 2.98, -1.18, -1.04),
        (-2.98, -2.84, 1.04, 1.18),
        (2.84, 2.98, 1.04, 1.18),
    ]
    for cx0, cx1, cy0, cy1 in corners:
        add_box(bm, cx0, cx1, cy0, cy1, 0.28, 2.44, mat_frame, nz=6)

    for ry in (-1.15, 1.15):
        add_box(bm, -2.84, 2.84, ry - 0.05, ry + 0.05, 2.44, 2.595, mat_frame, nx=12, nz=2)
    for rx in (-2.93, 2.93):
        add_box(bm, rx - 0.05, rx + 0.05, -1.04, 1.04, 2.44, 2.595, mat_frame, ny=6, nz=2)

    for gy_sign in (-1, 1):
        gy0 = gy_sign * 1.195
        gy1 = gy_sign * 1.232
        add_box(bm, -3.01, 3.01, min(gy0, gy1), max(gy0, gy1), 2.435, 2.465, mat_frame, nx=10)
        add_box(bm, -3.01, 3.01, gy1 - 0.006, gy1 + 0.006, 2.465, 2.525, mat_frame, nx=10)

    for d_y in (-1.225, 1.225):
        add_cylinder_along(bm, (-2.94, d_y, 0.18), (-2.94, d_y, 2.46), 0.028, 8, mat_frame)
        y_dir = -1.0 if d_y < 0 else 1.0
        add_cylinder_along(bm, (-2.94, d_y, 0.18), (-2.94, d_y + y_dir * 0.07, 0.11), 0.028, 8, mat_frame)
        for clip_z in (0.45, 1.10, 1.75, 2.32):
            add_box(bm, -2.975, -2.905, min(d_y, d_y - y_dir * 0.05), max(d_y, d_y - y_dir * 0.05), clip_z - 0.015, clip_z + 0.015, mat_galv)

    add_box(bm, -2.86, 2.86, -1.12, 1.12, 2.54, 2.575, mat_galv, nx=12, ny=4)
    for r_i in range(15):
        rx = -2.66 + r_i * 0.38
        add_box(bm, rx - 0.022, rx + 0.022, -1.11, 1.11, 2.575, 2.598, mat_galv, ny=3)

    front_openings = [
        (-2.24, -1.04, 1.04, 2.08),
        (-0.48, 0.72, 1.04, 2.08),
        (1.48, 2.44, 0.26, 2.28),
    ]
    z_front = [0.26, 0.42, 0.74, 1.04, 1.56, 2.08, 2.28, 2.44]
    add_corrugated_wall_x(
        bm,
        x_start=-2.84,
        x_end=2.84,
        z_levels=z_front,
        y_base=-1.135,
        rib_depth=0.026,
        n_waves=36,
        openings=front_openings,
        mat_idx=mat_wall,
        facing_neg_y=True,
    )

    z_other = [0.26, 0.42, 1.15, 1.85, 2.44]
    add_corrugated_wall_x(
        bm,
        x_start=-2.84,
        x_end=2.84,
        z_levels=z_other,
        y_base=1.135,
        rib_depth=0.026,
        n_waves=36,
        openings=[],
        mat_idx=mat_wall,
        facing_neg_y=False,
    )

    add_corrugated_wall_y(
        bm,
        y_start=-1.04,
        y_end=1.04,
        z_levels=z_other,
        x_base=-2.935,
        rib_depth=0.024,
        n_waves=14,
        mat_idx=mat_wall,
        facing_neg_x=True,
    )

    add_corrugated_wall_y(
        bm,
        y_start=-1.04,
        y_end=1.04,
        z_levels=z_other,
        x_base=2.935,
        rib_depth=0.024,
        n_waves=14,
        mat_idx=mat_wall,
        facing_neg_x=False,
    )

    add_sliding_window_with_mesh(bm, -2.24, -1.04, 1.04, 2.08, mat_frame, mat_glass, mat_galv, mat_black)
    add_sliding_window_with_mesh(bm, -0.48, 0.72, 1.04, 2.08, mat_frame, mat_glass, mat_galv, mat_black)

    add_door_and_stairs(bm, mat_frame, mat_door, mat_galv, mat_glass, mat_black)
    add_wall_ac_unit(bm, mat_ac, mat_frame, mat_galv, mat_black)
    add_sign_with_text(bm, mat_yellow, mat_black, mat_galv)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = False
    for e in bm.edges:
        e.smooth = False

    bmesh.ops.triangulate(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new("SiteCabin")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("SiteCabin", mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = (0.0, 0.0, 0.0)

    for mat in materials:
        obj.data.materials.append(mat)

    return obj


def set_active_bake_image(materials, node_name):
    for mat in materials:
        if not mat or not mat.use_nodes:
            continue
        nodes = mat.node_tree.nodes
        target = nodes.get(node_name)
        for n in nodes:
            n.select = False
        if target is not None:
            target.select = True
            nodes.active = target


def setup_final_material(obj, img_albedo, img_normal):
    final_mat = bpy.data.materials.new(name="SiteCabin_Mat")
    final_mat.use_nodes = True
    nodes = final_mat.node_tree.nodes
    links = final_mat.node_tree.links
    nodes.clear()

    out_node = nodes.new(type="ShaderNodeOutputMaterial")
    out_node.location = (500, 0)

    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.location = (200, 0)
    set_principled(bsdf, "Roughness", 0.6)
    set_principled(bsdf, "Metallic", 0.0)
    links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])

    tex_alb = nodes.new(type="ShaderNodeTexImage")
    tex_alb.location = (-350, 180)
    tex_alb.image = img_albedo
    links.new(tex_alb.outputs["Color"], bsdf.inputs["Base Color"])

    tex_nrm = nodes.new(type="ShaderNodeTexImage")
    tex_nrm.location = (-350, -180)
    tex_nrm.image = img_normal
    tex_nrm.image.colorspace_settings.name = "Non-Color"

    nrm_map = nodes.new(type="ShaderNodeNormalMap")
    nrm_map.location = (-60, -180)
    nrm_map.inputs["Strength"].default_value = 1.0
    links.new(tex_nrm.outputs["Color"], nrm_map.inputs["Color"])
    links.new(nrm_map.outputs["Normal"], bsdf.inputs["Normal"])

    obj.data.materials.clear()
    obj.data.materials.append(final_mat)
    for poly in obj.data.polygons:
        poly.material_index = 0


def main():
    out_arg = "SiteCabin.fbx"
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if idx + 1 < len(sys.argv):
            out_arg = sys.argv[idx + 1]

    out_arg = os.path.abspath(out_arg)
    out_dir = os.path.dirname(out_arg)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if out_arg.lower().endswith(".fbx"):
        fbx_path = out_arg
        preview_path = out_arg[:-4] + ".png"
    else:
        fbx_path = out_arg + ".fbx"
        preview_path = out_arg + ".png"

    albedo_path = os.path.join(out_dir, "SiteCabin_albedo.png")
    normal_path = os.path.join(out_dir, "SiteCabin_normal.png")

    clear_scene()

    img_albedo = bpy.data.images.new("SiteCabin_albedo", width=2048, height=2048, alpha=False)
    img_albedo.colorspace_settings.name = "sRGB"

    img_normal = bpy.data.images.new("SiteCabin_normal", width=2048, height=2048, alpha=False)
    img_normal.colorspace_settings.name = "Non-Color"

    mat_wall = build_weathered_material(
        "WallPanel_Mat",
        base_col=(0.83, 0.82, 0.78, 1.0),
        alt_col=(0.74, 0.73, 0.68, 1.0),
        rust_col=(0.38, 0.17, 0.08, 1.0),
        dirt_col=(0.22, 0.17, 0.12, 1.0),
        roughness=0.52,
        noise_scale=5.5,
        scratch_scale=50.0,
        bump_strength=0.10,
        dirt_height=0.42,
        dirt_amount=0.88,
        rust_amount=0.28,
        img_albedo=img_albedo,
        img_normal=img_normal,
    )
    mat_frame = build_weathered_material(
        "FrameSteel_Mat",
        base_col=(0.16, 0.18, 0.20, 1.0),
        alt_col=(0.23, 0.25, 0.27, 1.0),
        rust_col=(0.36, 0.15, 0.06, 1.0),
        dirt_col=(0.21, 0.17, 0.12, 1.0),
        roughness=0.58,
        noise_scale=7.0,
        scratch_scale=42.0,
        bump_strength=0.14,
        dirt_height=0.42,
        dirt_amount=0.82,
        rust_amount=0.38,
        img_albedo=img_albedo,
        img_normal=img_normal,
    )
    mat_door = build_weathered_material(
        "DoorPanel_Mat",
        base_col=(0.25, 0.27, 0.30, 1.0),
        alt_col=(0.20, 0.22, 0.24, 1.0),
        rust_col=(0.35, 0.15, 0.07, 1.0),
        dirt_col=(0.22, 0.18, 0.13, 1.0),
        roughness=0.54,
        noise_scale=6.5,
        scratch_scale=48.0,
        bump_strength=0.11,
        dirt_height=0.42,
        dirt_amount=0.80,
        rust_amount=0.30,
        img_albedo=img_albedo,
        img_normal=img_normal,
    )
    mat_galv = build_weathered_material(
        "GalvMetal_Mat",
        base_col=(0.54, 0.56, 0.58, 1.0),
        alt_col=(0.41, 0.43, 0.45, 1.0),
        rust_col=(0.37, 0.17, 0.08, 1.0),
        dirt_col=(0.23, 0.18, 0.12, 1.0),
        roughness=0.48,
        noise_scale=12.0,
        scratch_scale=60.0,
        bump_strength=0.15,
        dirt_height=0.40,
        dirt_amount=0.78,
        rust_amount=0.34,
        img_albedo=img_albedo,
        img_normal=img_normal,
    )
    mat_glass = build_weathered_material(
        "WindowGlass_Mat",
        base_col=(0.09, 0.14, 0.18, 1.0),
        alt_col=(0.15, 0.21, 0.25, 1.0),
        rust_col=(0.20, 0.20, 0.20, 1.0),
        dirt_col=(0.28, 0.25, 0.21, 1.0),
        roughness=0.18,
        noise_scale=4.0,
        scratch_scale=35.0,
        bump_strength=0.02,
        dirt_height=0.25,
        dirt_amount=0.25,
        rust_amount=0.05,
        img_albedo=img_albedo,
        img_normal=img_normal,
    )
    mat_timber = build_weathered_material(
        "TimberSleeper_Mat",
        base_col=(0.24, 0.15, 0.08, 1.0),
        alt_col=(0.14, 0.09, 0.05, 1.0),
        rust_col=(0.18, 0.11, 0.06, 1.0),
        dirt_col=(0.16, 0.12, 0.08, 1.0),
        roughness=0.82,
        noise_scale=8.0,
        scratch_scale=30.0,
        bump_strength=0.24,
        dirt_height=0.35,
        dirt_amount=0.75,
        rust_amount=0.20,
        wood_grain=True,
        img_albedo=img_albedo,
        img_normal=img_normal,
    )
    mat_ac = build_weathered_material(
        "ACUnit_Mat",
        base_col=(0.73, 0.71, 0.66, 1.0),
        alt_col=(0.62, 0.60, 0.55, 1.0),
        rust_col=(0.39, 0.18, 0.08, 1.0),
        dirt_col=(0.24, 0.20, 0.15, 1.0),
        roughness=0.52,
        noise_scale=8.0,
        scratch_scale=45.0,
        bump_strength=0.12,
        dirt_height=0.40,
        dirt_amount=0.60,
        rust_amount=0.32,
        img_albedo=img_albedo,
        img_normal=img_normal,
    )
    mat_yellow = build_weathered_material(
        "SignYellow_Mat",
        base_col=(0.93, 0.73, 0.05, 1.0),
        alt_col=(0.84, 0.64, 0.04, 1.0),
        rust_col=(0.42, 0.22, 0.08, 1.0),
        dirt_col=(0.30, 0.25, 0.18, 1.0),
        roughness=0.44,
        noise_scale=9.0,
        scratch_scale=50.0,
        bump_strength=0.05,
        dirt_height=0.30,
        dirt_amount=0.20,
        rust_amount=0.08,
        img_albedo=img_albedo,
        img_normal=img_normal,
    )
    mat_black = build_weathered_material(
        "SignBlack_Mat",
        base_col=(0.04, 0.04, 0.05, 1.0),
        alt_col=(0.08, 0.08, 0.09, 1.0),
        rust_col=(0.15, 0.10, 0.07, 1.0),
        dirt_col=(0.18, 0.15, 0.11, 1.0),
        roughness=0.62,
        noise_scale=10.0,
        scratch_scale=45.0,
        bump_strength=0.05,
        dirt_height=0.35,
        dirt_amount=0.35,
        rust_amount=0.08,
        img_albedo=img_albedo,
        img_normal=img_normal,
    )

    materials = [
        mat_wall,
        mat_frame,
        mat_door,
        mat_galv,
        mat_glass,
        mat_timber,
        mat_ac,
        mat_yellow,
        mat_black,
    ]

    cabin_obj = build_site_cabin(materials)

    bpy.ops.object.select_all(action="DESELECT")
    cabin_obj.select_set(True)
    bpy.context.view_layer.objects.active = cabin_obj

    if not cabin_obj.data.uv_layers:
        cabin_obj.data.uv_layers.new(name="UVMap")
    cabin_obj.data.uv_layers.active_index = 0

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.context.scene.tool_settings.use_uv_select_sync = True
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.01)
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(margin=0.01)
    bpy.ops.object.mode_set(mode="OBJECT")

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.render.bake.margin = 8

    set_active_bake_image(materials, "Bake_Albedo")
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=8)

    img_albedo.filepath_raw = albedo_path
    img_albedo.file_format = "PNG"
    img_albedo.save()
    img_albedo.filepath = albedo_path

    set_active_bake_image(materials, "Bake_Normal")
    scene.render.bake.normal_space = "TANGENT"
    bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", margin=8)

    img_normal.filepath_raw = normal_path
    img_normal.file_format = "PNG"
    img_normal.save()
    img_normal.filepath = normal_path

    setup_final_material(cabin_obj, img_albedo, img_normal)

    bpy.ops.object.select_all(action="DESELECT")
    cabin_obj.select_set(True)
    bpy.context.view_layer.objects.active = cabin_obj

    bpy.ops.export_scene.fbx(
        filepath=fbx_path,
        use_selection=True,
        bake_space_transform=True,
        axis_forward="-Z",
        axis_up="Y",
        path_mode="COPY",
        embed_textures=True,
    )

    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    w_nodes = world.node_tree.nodes
    w_links = world.node_tree.links
    w_nodes.clear()
    w_out = w_nodes.new(type="ShaderNodeOutputWorld")
    w_bg = w_nodes.new(type="ShaderNodeBackground")
    w_bg.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1.0)
    w_bg.inputs["Strength"].default_value = 0.6
    w_links.new(w_bg.outputs["Background"], w_out.inputs["Surface"])

    sun_data = bpy.data.lights.new(name="SunLight", type="SUN")
    sun_data.energy = 3.0
    sun_data.color = (1.0, 0.98, 0.94)
    sun_obj = bpy.data.objects.new(name="SunLight", object_data=sun_data)
    bpy.context.collection.objects.link(sun_obj)
    sun_obj.location = (-6.0, -7.0, 8.0)
    sun_dir = mathutils.Vector((0.0, 0.0, 1.2)) - sun_obj.location
    sun_obj.rotation_euler = sun_dir.to_track_quat("-Z", "Y").to_euler()

    cam_data = bpy.data.cameras.new(name="PreviewCamera")
    cam_data.lens = 33.0
    cam_obj = bpy.data.objects.new(name="PreviewCamera", object_data=cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = mathutils.Vector((-5.1, -6.1, 1.7))
    cam_target = mathutils.Vector((-0.05, -0.15, 1.28))
    cam_dir = cam_target - cam_obj.location
    cam_obj.rotation_euler = cam_dir.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    engine_keys = list(scene.render.bl_rna.properties["engine"].enum_items.keys())
    if "BLENDER_EEVEE_NEXT" in engine_keys:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    elif "BLENDER_EEVEE" in engine_keys:
        scene.render.engine = "BLENDER_EEVEE"
    else:
        for k in engine_keys:
            if "EEVEE" in k:
                scene.render.engine = k
                break

    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = preview_path
    bpy.ops.render.render(write_still=True)

    cabin_obj.data.calc_loop_triangles()
    n_tris = len(cabin_obj.data.loop_triangles)
    print("TRIS", n_tris)


if __name__ == "__main__":
    main()
