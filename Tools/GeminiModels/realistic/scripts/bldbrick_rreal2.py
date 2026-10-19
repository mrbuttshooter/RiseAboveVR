import bpy
import bmesh
import math
import sys
import os
from mathutils import Vector, Matrix


def clear_scene():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
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
        for block in list(col):
            col.remove(block)


def add_box(bm, cx, cy, cz, sx, sy, sz, mat_idx, omit_faces=(), smooth=False):
    hx = sx * 0.5
    hy = sy * 0.5
    hz = sz * 0.5
    coords = [
        (cx - hx, cy - hy, cz - hz),
        (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz),
        (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz),
        (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz),
        (cx - hx, cy + hy, cz + hz),
    ]
    verts = [bm.verts.new(c) for c in coords]
    face_defs = [
        ('-Y', (0, 1, 5, 4)),
        ('+Y', (2, 3, 7, 6)),
        ('-X', (3, 0, 4, 7)),
        ('+X', (1, 2, 6, 5)),
        ('-Z', (3, 2, 1, 0)),
        ('+Z', (4, 5, 6, 7)),
    ]
    created_faces = []
    for tag, idxs in face_defs:
        if tag in omit_faces:
            continue
        f = bm.faces.new([verts[i] for i in idxs])
        f.material_index = mat_idx
        f.smooth = smooth
        created_faces.append(f)
    return created_faces


def add_strut(bm, p0, p1, radius, mat_idx, cap_ends=False):
    v0 = Vector(p0)
    v1 = Vector(p1)
    diff = v1 - v0
    if diff.length < 1e-5:
        return []
    tangent = diff.normalized()
    ref = Vector((0.0, 0.0, 1.0)) if abs(tangent.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    side_u = tangent.cross(ref).normalized() * radius
    side_v = tangent.cross(side_u).normalized() * radius
    c0 = [
        bm.verts.new(v0 - side_u - side_v),
        bm.verts.new(v0 + side_u - side_v),
        bm.verts.new(v0 + side_u + side_v),
        bm.verts.new(v0 - side_u + side_v),
    ]
    c1 = [
        bm.verts.new(v1 - side_u - side_v),
        bm.verts.new(v1 + side_u - side_v),
        bm.verts.new(v1 + side_u + side_v),
        bm.verts.new(v1 - side_u + side_v),
    ]
    faces = []
    for i in range(4):
        ni = (i + 1) % 4
        f = bm.faces.new((c0[i], c0[ni], c1[ni], c1[i]))
        f.material_index = mat_idx
        f.smooth = False
        faces.append(f)
    if cap_ends:
        fb = bm.faces.new((c0[3], c0[2], c0[1], c0[0]))
        fb.material_index = mat_idx
        fb.smooth = False
        ft = bm.faces.new((c1[0], c1[1], c1[2], c1[3]))
        ft.material_index = mat_idx
        ft.smooth = False
        faces.extend([fb, ft])
    return faces


def add_cylinder_z(bm, cx, cy, z0, z1, r0, r1, segs, mat_idx, cap_bottom=False, cap_top=True, smooth_sides=False):
    faces = []
    ring0 = []
    for i in range(segs):
        ang = (2.0 * math.pi * i) / segs
        ring0.append(bm.verts.new((cx + math.cos(ang) * r0, cy + math.sin(ang) * r0, z0)))
    if r1 <= 1e-5:
        apex = bm.verts.new((cx, cy, z1))
        for i in range(segs):
            ni = (i + 1) % segs
            f = bm.faces.new((ring0[i], ring0[ni], apex))
            f.material_index = mat_idx
            f.smooth = smooth_sides
            faces.append(f)
        if cap_bottom:
            fb = bm.faces.new(list(reversed(ring0)))
            fb.material_index = mat_idx
            fb.smooth = False
            faces.append(fb)
        return faces
    ring1 = []
    for i in range(segs):
        ang = (2.0 * math.pi * i) / segs
        ring1.append(bm.verts.new((cx + math.cos(ang) * r1, cy + math.sin(ang) * r1, z1)))
    for i in range(segs):
        ni = (i + 1) % segs
        f = bm.faces.new((ring0[i], ring0[ni], ring1[ni], ring1[i]))
        f.material_index = mat_idx
        f.smooth = smooth_sides
        faces.append(f)
    if cap_bottom:
        fb = bm.faces.new(list(reversed(ring0)))
        fb.material_index = mat_idx
        fb.smooth = False
        faces.append(fb)
    if cap_top:
        ft = bm.faces.new(ring1)
        ft.material_index = mat_idx
        ft.smooth = False
        faces.append(ft)
    return faces


def add_wrap_band(bm, z0, z1, overhang, mat_idx):
    cz = 0.5 * (z0 + z1)
    sz = z1 - z0
    w_outer = 14.0 + 2.0 * overhang
    d_band = overhang
    hy_mid = 7.0 + 0.5 * overhang
    add_box(bm, 0.0, -hy_mid, cz, w_outer, d_band, sz, mat_idx, omit_faces=('+Y',))
    add_box(bm, 0.0, hy_mid, cz, w_outer, d_band, sz, mat_idx, omit_faces=('-Y',))
    add_box(bm, -hy_mid, 0.0, cz, d_band, 14.0, sz, mat_idx, omit_faces=('+X', '-Y', '+Y'))
    add_box(bm, hy_mid, 0.0, cz, d_band, 14.0, sz, mat_idx, omit_faces=('-X', '-Y', '+Y'))


def snap_face_opening(face, axis_u, u_min, u_max, z_min, z_max):
    u_mid = 0.5 * (u_min + u_max)
    z_mid = 0.5 * (z_min + z_max)
    for v in face.verts:
        if axis_u == 'X':
            v.co.x = u_min if v.co.x < u_mid else u_max
        else:
            v.co.y = u_min if v.co.y < u_mid else u_max
        v.co.z = z_min if v.co.z < z_mid else z_max


def build_recessed_window_bay(
    bm,
    f_bay,
    facade_tag,
    u_center,
    z_floor,
    win_w,
    win_h,
    sill_rel_z,
    recess_depth,
    frame_w,
    wall_mat,
    frame_mat,
    glass_mat,
    stone_mat,
    add_sill=True,
    add_lintel=True,
    add_pediment=False,
    add_upper_mullion=False,
):
    f_bay.material_index = wall_mat
    res_wall = bmesh.ops.inset_individual(bm, faces=[f_bay], thickness=0.12, depth=0.0)
    for rf in res_wall['faces']:
        rf.material_index = wall_mat
        rf.smooth = False

    axis_u = 'X' if facade_tag in ('FRONT', 'BACK') else 'Y'
    u0 = u_center - 0.5 * win_w
    u1 = u_center + 0.5 * win_w
    z0 = z_floor + sill_rel_z
    z1 = z0 + win_h
    snap_face_opening(f_bay, axis_u, u0, u1, z0, z1)

    res_rev = bmesh.ops.inset_individual(bm, faces=[f_bay], thickness=0.0, depth=-recess_depth)
    for rf in res_rev['faces']:
        rf.material_index = wall_mat
        rf.smooth = False

    res_frm = bmesh.ops.inset_individual(bm, faces=[f_bay], thickness=frame_w, depth=-0.025)
    for rf in res_frm['faces']:
        rf.material_index = frame_mat
        rf.smooth = False

    f_bay.material_index = glass_mat
    f_bay.smooth = False

    inner_w = max(0.2, win_w - 2.0 * frame_w)
    z_mid = z0 + 0.50 * win_h

    if facade_tag == 'FRONT':
        wall_pos = -7.0
        n_sign = -1.0
        back_face = '+Y'
        end_faces = ('-X', '+X', '+Y', '-Z')
        mull_omit = ('-X', '+X', '+Y', '-Z', '+Z')
    elif facade_tag == 'BACK':
        wall_pos = 7.0
        n_sign = 1.0
        back_face = '-Y'
        end_faces = ('-X', '+X', '-Y', '-Z')
        mull_omit = ('-X', '+X', '-Y', '-Z', '+Z')
    elif facade_tag == 'LEFT':
        wall_pos = -7.0
        n_sign = -1.0
        back_face = '+X'
        end_faces = ('-Y', '+Y', '+X', '-Z')
        mull_omit = ('-Y', '+Y', '+X', '-Z', '+Z')
    else:
        wall_pos = 7.0
        n_sign = 1.0
        back_face = '-X'
        end_faces = ('-Y', '+Y', '-X', '-Z')
        mull_omit = ('-Y', '+Y', '-X', '-Z', '+Z')

    sash_pos = wall_pos - n_sign * (recess_depth + 0.005)
    if axis_u == 'X':
        add_box(bm, u_center, sash_pos, z_mid, inner_w, 0.04, 0.045, frame_mat, omit_faces=end_faces)
        if add_upper_mullion:
            z_up_mid = 0.5 * (z_mid + (z1 - frame_w))
            up_h = (z1 - frame_w) - z_mid
            add_box(bm, u_center, sash_pos, z_up_mid, 0.035, 0.035, up_h, frame_mat, omit_faces=mull_omit)
    else:
        add_box(bm, sash_pos, u_center, z_mid, 0.04, inner_w, 0.045, frame_mat, omit_faces=end_faces)
        if add_upper_mullion:
            z_up_mid = 0.5 * (z_mid + (z1 - frame_w))
            up_h = (z1 - frame_w) - z_mid
            add_box(bm, sash_pos, u_center, z_up_mid, 0.035, 0.035, up_h, frame_mat, omit_faces=mull_omit)

    if add_sill:
        sill_w = win_w + 0.18
        sill_h = 0.12
        sill_proj = 0.09
        sill_z = z0 - 0.5 * sill_h + 0.02
        sill_d_pos = wall_pos + n_sign * (0.5 * sill_proj)
        if axis_u == 'X':
            add_box(bm, u_center, sill_d_pos, sill_z, sill_w, sill_proj, sill_h, stone_mat, omit_faces=(back_face,))
        else:
            add_box(bm, sill_d_pos, u_center, sill_z, sill_proj, sill_w, sill_h, stone_mat, omit_faces=(back_face,))

    if add_lintel:
        lintel_w = win_w + 0.22
        lintel_h = 0.21
        lintel_proj = 0.075
        lintel_z = z1 + 0.5 * lintel_h - 0.01
        lintel_d_pos = wall_pos + n_sign * (0.5 * lintel_proj)
        lintel_omit = (back_face, '-Z')
        if axis_u == 'X':
            add_box(bm, u_center, lintel_d_pos, lintel_z, lintel_w, lintel_proj, lintel_h, stone_mat, omit_faces=lintel_omit)
            if add_pediment:
                cap_z = z1 + lintel_h + 0.035 - 0.01
                cap_pos = wall_pos + n_sign * 0.06
                add_box(bm, u_center, cap_pos, cap_z, lintel_w + 0.10, 0.12, 0.07, stone_mat, omit_faces=(back_face, '-Z'))
        else:
            add_box(bm, lintel_d_pos, u_center, lintel_z, lintel_proj, lintel_w, lintel_h, stone_mat, omit_faces=lintel_omit)
            if add_pediment:
                cap_z = z1 + lintel_h + 0.035 - 0.01
                cap_pos = wall_pos + n_sign * 0.06
                add_box(bm, cap_pos, u_center, cap_z, 0.12, lintel_w + 0.10, 0.07, stone_mat, omit_faces=(back_face, '-Z'))


def build_building_geometry():
    MAT_BRICK = 0
    MAT_STONE = 1
    MAT_STUCCO = 2
    MAT_FRAME = 3
    MAT_GLASS = 4
    MAT_DARK_METAL = 5
    MAT_ROOF = 6
    MAT_WOOD = 7
    MAT_AWNING = 8

    bm = bmesh.new()

    xs = [-7.0, -6.0, -3.6, -1.2, 1.2, 3.6, 6.0, 7.0]
    ys = [-7.0, -6.0, -3.6, -1.2, 1.2, 3.6, 6.0, 7.0]
    zs = [0.0, 0.55, 3.65, 3.95, 6.95, 9.95, 12.95, 15.95, 18.95, 19.85]

    perim_xy = []
    for i in range(7):
        perim_xy.append((xs[i], -7.0, 'FRONT', i))
    for i in range(7):
        perim_xy.append((7.0, ys[i], 'RIGHT', i))
    for i in range(7):
        perim_xy.append((xs[7 - i], 7.0, 'BACK', i))
    for i in range(7):
        perim_xy.append((-7.0, ys[7 - i], 'LEFT', i))

    n_perim = len(perim_xy)
    n_z = len(zs)

    grid_verts = []
    for kz in range(n_z):
        z_val = zs[kz]
        ring = []
        for p_idx in range(n_perim):
            px, py, _, _ = perim_xy[p_idx]
            ring.append(bm.verts.new((px, py, z_val)))
        grid_verts.append(ring)

    bay_faces = {}
    for kz in range(n_z - 1):
        for p_idx in range(n_perim):
            np_idx = (p_idx + 1) % n_perim
            _, _, fac_tag, col_idx = perim_xy[p_idx]
            v00 = grid_verts[kz][p_idx]
            v10 = grid_verts[kz][np_idx]
            v11 = grid_verts[kz + 1][np_idx]
            v01 = grid_verts[kz + 1][p_idx]
            f = bm.faces.new((v00, v10, v11, v01))
            f.smooth = False
            if kz == 0:
                f.material_index = MAT_STONE
            elif kz == 1:
                f.material_index = MAT_STUCCO if fac_tag in ('FRONT', 'LEFT', 'RIGHT') else MAT_BRICK
            elif kz == 2:
                f.material_index = MAT_STONE
            else:
                f.material_index = MAT_BRICK
            bay_faces[(fac_tag, kz, col_idx)] = f

    f_bottom = bm.faces.new(list(reversed(grid_verts[0])))
    f_bottom.material_index = MAT_STONE
    f_bottom.smooth = False

    f_roof_top = bm.faces.new(grid_verts[-1])
    f_roof_top.material_index = MAT_ROOF
    f_roof_top.smooth = False

    res_parapet = bmesh.ops.inset_region(bm, faces=[f_roof_top], thickness=0.38, depth=0.0, use_even_offset=True)
    parapet_ring_faces = res_parapet['faces']
    for pf in parapet_ring_faces:
        pf.material_index = MAT_BRICK
        pf.smooth = False

    ext_parapet = bmesh.ops.extrude_face_region(bm, geom=parapet_ring_faces)
    ext_p_verts = [e for e in ext_parapet['geom'] if isinstance(e, bmesh.types.BMVert)]
    ext_p_faces = [e for e in ext_parapet['geom'] if isinstance(e, bmesh.types.BMFace)]
    bmesh.ops.translate(bm, verts=ext_p_verts, vec=(0.0, 0.0, 0.70))
    bmesh.ops.delete(bm, geom=parapet_ring_faces, context='FACES')
    for pf in ext_p_faces:
        pf.material_index = MAT_STONE
        pf.smooth = False

    for f in bm.faces:
        if abs(f.normal.z) < 0.5 and f.calc_center_median().z > 19.90:
            f.material_index = MAT_BRICK
            f.smooth = False

    bay_centers = [-4.8, -2.4, 0.0, 2.4, 4.8]

    for kz in range(3, 8):
        z_fl = zs[kz]
        for fac_tag in ('FRONT', 'BACK', 'LEFT', 'RIGHT'):
            for col_idx in range(1, 6):
                f_bay = bay_faces[(fac_tag, kz, col_idx)]
                u_c = bay_centers[col_idx - 1]
                if fac_tag in ('BACK', 'LEFT'):
                    u_c = -u_c
                is_front = (fac_tag == 'FRONT')
                build_recessed_window_bay(
                    bm=bm,
                    f_bay=f_bay,
                    facade_tag=fac_tag,
                    u_center=u_c,
                    z_floor=z_fl,
                    win_w=1.18,
                    win_h=1.84,
                    sill_rel_z=0.52,
                    recess_depth=0.20,
                    frame_w=0.075,
                    wall_mat=MAT_BRICK,
                    frame_mat=MAT_FRAME,
                    glass_mat=MAT_GLASS,
                    stone_mat=MAT_STONE,
                    add_sill=True,
                    add_lintel=True,
                    add_pediment=(is_front and kz in (3, 7)),
                    add_upper_mullion=is_front,
                )

    for fac_tag in ('LEFT', 'RIGHT', 'BACK'):
        w_mat = MAT_STUCCO if fac_tag in ('LEFT', 'RIGHT') else MAT_BRICK
        for col_idx in range(1, 6):
            f_bay = bay_faces[(fac_tag, 1, col_idx)]
            u_c = bay_centers[col_idx - 1]
            if fac_tag in ('BACK', 'LEFT'):
                u_c = -u_c
            if fac_tag == 'BACK' and col_idx == 3:
                build_recessed_window_bay(
                    bm=bm,
                    f_bay=f_bay,
                    facade_tag='BACK',
                    u_center=0.0,
                    z_floor=0.55,
                    win_w=1.20,
                    win_h=2.35,
                    sill_rel_z=0.02,
                    recess_depth=0.26,
                    frame_w=0.08,
                    wall_mat=MAT_BRICK,
                    frame_mat=MAT_DARK_METAL,
                    glass_mat=MAT_WOOD,
                    stone_mat=MAT_STONE,
                    add_sill=False,
                    add_lintel=True,
                    add_pediment=False,
                    add_upper_mullion=False,
                )
            else:
                build_recessed_window_bay(
                    bm=bm,
                    f_bay=f_bay,
                    facade_tag=fac_tag,
                    u_center=u_c,
                    z_floor=0.55,
                    win_w=1.18,
                    win_h=1.92,
                    sill_rel_z=0.52,
                    recess_depth=0.20,
                    frame_w=0.075,
                    wall_mat=w_mat,
                    frame_mat=MAT_FRAME,
                    glass_mat=MAT_GLASS,
                    stone_mat=MAT_STONE,
                    add_sill=True,
                    add_lintel=True,
                    add_pediment=False,
                    add_upper_mullion=False,
                )

    for col_idx in (1, 2, 3):
        f_shop = bay_faces[('FRONT', 1, col_idx)]
        u_c = bay_centers[col_idx - 1]
        build_recessed_window_bay(
            bm=bm,
            f_bay=f_shop,
            facade_tag='FRONT',
            u_center=u_c,
            z_floor=0.55,
            win_w=2.04,
            win_h=2.12,
            sill_rel_z=0.28,
            recess_depth=0.22,
            frame_w=0.07,
            wall_mat=MAT_STUCCO,
            frame_mat=MAT_DARK_METAL,
            glass_mat=MAT_GLASS,
            stone_mat=MAT_STONE,
            add_sill=True,
            add_lintel=False,
            add_pediment=False,
            add_upper_mullion=False,
        )

    f_shop_door = bay_faces[('FRONT', 1, 4)]
    build_recessed_window_bay(
        bm=bm,
        f_bay=f_shop_door,
        facade_tag='FRONT',
        u_center=2.4,
        z_floor=0.55,
        win_w=1.56,
        win_h=2.40,
        sill_rel_z=0.0,
        recess_depth=0.30,
        frame_w=0.08,
        wall_mat=MAT_STUCCO,
        frame_mat=MAT_DARK_METAL,
        glass_mat=MAT_GLASS,
        stone_mat=MAT_STONE,
        add_sill=False,
        add_lintel=False,
        add_pediment=False,
        add_upper_mullion=False,
    )
    add_box(bm, 2.4, -6.72, 1.50, 0.07, 0.05, 1.90, MAT_DARK_METAL, omit_faces=('+Y', '-Z', '+Z'))
    add_box(bm, 2.4, -6.72, 2.45, 1.40, 0.06, 0.07, MAT_DARK_METAL, omit_faces=('+Y', '-X', '+X'))
    add_box(bm, 2.4, -7.08, 0.28, 1.72, 0.18, 0.56, MAT_STONE, omit_faces=('+Y', '-Z'))

    f_main_ent = bay_faces[('FRONT', 1, 5)]
    f_main_ent.material_index = MAT_STUCCO
    res_ent1 = bmesh.ops.inset_individual(bm, faces=[f_main_ent], thickness=0.14, depth=0.0)
    for rf in res_ent1['faces']:
        rf.material_index = MAT_STUCCO
        rf.smooth = False
    snap_face_opening(f_main_ent, 'X', 4.02, 5.58, 0.55, 3.12)
    res_ent2 = bmesh.ops.inset_individual(bm, faces=[f_main_ent], thickness=0.0, depth=-0.38)
    for rf in res_ent2['faces']:
        rf.material_index = MAT_STONE
        rf.smooth = False
    res_ent3 = bmesh.ops.inset_individual(bm, faces=[f_main_ent], thickness=0.09, depth=-0.03)
    for rf in res_ent3['faces']:
        rf.material_index = MAT_WOOD
        rf.smooth = False
    f_main_ent.material_index = MAT_WOOD
    f_main_ent.smooth = False

    add_box(bm, 4.80, -6.64, 1.48, 0.07, 0.05, 1.72, MAT_WOOD, omit_faces=('+Y', '-Z', '+Z'))
    add_box(bm, 4.80, -6.63, 2.38, 1.38, 0.07, 0.09, MAT_WOOD, omit_faces=('+Y', '-X', '+X'))
    add_box(bm, 4.80, -6.64, 2.72, 1.34, 0.03, 0.56, MAT_GLASS, omit_faces=('+Y', '-X', '+X', '-Z', '+Z'))
    add_box(bm, 3.88, -7.07, 1.65, 0.26, 0.14, 3.10, MAT_STONE, omit_faces=('+Y', '-Z'))
    add_box(bm, 5.72, -7.07, 1.65, 0.26, 0.14, 3.10, MAT_STONE, omit_faces=('+Y', '-Z'))
    add_box(bm, 4.80, -7.14, 3.32, 2.26, 0.28, 0.26, MAT_STONE, omit_faces=('+Y',))
    add_box(bm, 4.80, -7.14, 0.28, 1.96, 0.28, 0.56, MAT_STONE, omit_faces=('+Y', '-Z'))
    add_box(bm, 4.80, -7.38, 0.14, 2.16, 0.22, 0.28, MAT_STONE, omit_faces=('+Y', '-Z'))

    add_box(bm, -1.20, -7.05, 3.26, 9.75, 0.10, 0.44, MAT_DARK_METAL, omit_faces=('+Y',))

    aw_x0 = -6.12
    aw_x1 = 3.72
    aw_y_wall = -7.00
    aw_y_front = -8.25
    aw_z_top = 3.44
    aw_z_front = 2.66
    aw_z_valance = 2.40
    aw_thick = 0.04

    v_aw_tl0 = bm.verts.new((aw_x0, aw_y_wall, aw_z_top))
    v_aw_tr0 = bm.verts.new((aw_x1, aw_y_wall, aw_z_top))
    v_aw_fl0 = bm.verts.new((aw_x0, aw_y_front, aw_z_front))
    v_aw_fr0 = bm.verts.new((aw_x1, aw_y_front, aw_z_front))
    v_aw_vl0 = bm.verts.new((aw_x0, aw_y_front, aw_z_valance))
    v_aw_vr0 = bm.verts.new((aw_x1, aw_y_front, aw_z_valance))
    v_aw_bl0 = bm.verts.new((aw_x0, aw_y_wall, aw_z_front))
    v_aw_br0 = bm.verts.new((aw_x1, aw_y_wall, aw_z_front))

    v_aw_tl1 = bm.verts.new((aw_x0, aw_y_wall, aw_z_top - aw_thick))
    v_aw_tr1 = bm.verts.new((aw_x1, aw_y_wall, aw_z_top - aw_thick))
    v_aw_fl1 = bm.verts.new((aw_x0, aw_y_front + aw_thick, aw_z_front - aw_thick))
    v_aw_fr1 = bm.verts.new((aw_x1, aw_y_front + aw_thick, aw_z_front - aw_thick))
    v_aw_vl1 = bm.verts.new((aw_x0, aw_y_front + aw_thick, aw_z_valance))
    v_aw_vr1 = bm.verts.new((aw_x1, aw_y_front + aw_thick, aw_z_valance))

    aw_faces = [
        bm.faces.new((v_aw_fl0, v_aw_fr0, v_aw_tr0, v_aw_tl0)),
        bm.faces.new((v_aw_tl1, v_aw_tr1, v_aw_fr1, v_aw_fl1)),
        bm.faces.new((v_aw_vl0, v_aw_vr0, v_aw_fr0, v_aw_fl0)),
        bm.faces.new((v_aw_fl1, v_aw_fr1, v_aw_vr1, v_aw_vl1)),
        bm.faces.new((v_aw_vl0, v_aw_vl1, v_aw_vr1, v_aw_vr0)),
        bm.faces.new((v_aw_bl0, v_aw_fl0, v_aw_tl0)),
        bm.faces.new((v_aw_tl1, v_aw_fl1, v_aw_bl0)),
        bm.faces.new((v_aw_fr0, v_aw_br0, v_aw_tr0)),
        bm.faces.new((v_aw_tr1, v_aw_br0, v_aw_fl1 if False else v_aw_fr1)),
    ]
    for af in aw_faces:
        af.material_index = MAT_AWNING
        af.smooth = False

    for sx in (-6.05, -3.60, -1.20, 1.20, 3.65):
        add_strut(bm, (sx, -7.00, 2.08), (sx, aw_y_front + 0.05, aw_z_front - 0.02), 0.018, MAT_DARK_METAL)

    add_wrap_band(bm, 0.48, 0.60, 0.07, MAT_STONE)
    add_wrap_band(bm, 3.62, 3.75, 0.10, MAT_STONE)
    add_wrap_band(bm, 3.75, 3.98, 0.20, MAT_STONE)
    add_wrap_band(bm, 6.86, 7.00, 0.07, MAT_STONE)
    add_wrap_band(bm, 15.86, 16.00, 0.07, MAT_STONE)

    add_wrap_band(bm, 18.90, 19.04, 0.10, MAT_STONE)
    add_wrap_band(bm, 19.46, 19.70, 0.36, MAT_STONE)
    add_wrap_band(bm, 19.70, 19.86, 0.44, MAT_STONE)
    add_wrap_band(bm, 20.52, 20.66, 0.08, MAT_STONE)

    for i in range(16):
        bx = -6.50 + i * (13.0 / 15.0)
        add_box(bm, bx, -7.15, 19.25, 0.14, 0.30, 0.40, MAT_STONE, omit_faces=('+Y', '+Z'))
    for i in range(8):
        by = -6.00 + i * (12.0 / 7.0)
        add_box(bm, -7.15, by, 19.25, 0.30, 0.14, 0.40, MAT_STONE, omit_faces=('+X', '+Z'))
        add_box(bm, 7.15, by, 19.25, 0.30, 0.14, 0.40, MAT_STONE, omit_faces=('-X', '+Z'))

    for q_idx in range(10):
        qz = 4.30 + q_idx * 1.48
        q_w = 0.48 if (q_idx % 2 == 0) else 0.32
        add_box(bm, -7.0 + 0.5 * q_w, -7.03, qz, q_w, 0.06, 0.42, MAT_STONE, omit_faces=('+Y', '+X'))
        add_box(bm, 7.0 - 0.5 * q_w, -7.03, qz, q_w, 0.06, 0.42, MAT_STONE, omit_faces=('+Y', '-X'))

    fe_x0 = -3.72
    fe_x1 = 1.32
    fe_xc = 0.5 * (fe_x0 + fe_x1)
    fe_w = fe_x1 - fe_x0
    fe_y_wall = -7.00
    fe_y_out = -8.16
    fe_ym = 0.5 * (fe_y_wall + fe_y_out)
    fe_d = fe_y_wall - fe_y_out
    fe_levels = [4.42, 7.42, 10.42, 13.42, 16.42]

    for lvl_idx, fz in enumerate(fe_levels):
        add_box(bm, fe_xc, fe_y_out + 0.03, fz, fe_w, 0.06, 0.08, MAT_DARK_METAL)
        add_box(bm, fe_x0 + 0.03, fe_ym, fz, 0.06, fe_d, 0.08, MAT_DARK_METAL, omit_faces=('+Y',))
        add_box(bm, fe_x1 - 0.03, fe_ym, fz, 0.06, fe_d, 0.08, MAT_DARK_METAL, omit_faces=('+Y',))

        for s_idx in range(5):
            sy = fe_y_wall - 0.16 - s_idx * 0.21
            if lvl_idx > 0 and s_idx in (1, 2, 3):
                add_box(bm, -3.18, sy, fz, 0.96, 0.05, 0.03, MAT_DARK_METAL, omit_faces=('-X', '+X'))
                add_box(bm, 0.48, sy, fz, 1.56, 0.05, 0.03, MAT_DARK_METAL, omit_faces=('-X', '+X'))
            else:
                add_box(bm, fe_xc, sy, fz, fe_w - 0.12, 0.05, 0.03, MAT_DARK_METAL, omit_faces=('-X', '+X'))

        for bx in (-3.62, -1.20, 1.22):
            add_strut(bm, (bx, fe_y_wall, fz - 0.72), (bx, fe_y_out + 0.08, fz - 0.03), 0.024, MAT_DARK_METAL)

        rz_top = fz + 0.92
        rz_bot = fz + 0.14
        rz_mid = 0.5 * (rz_top + rz_bot)
        rh = rz_top - rz_bot

        add_box(bm, fe_xc, fe_y_out + 0.03, rz_top, fe_w, 0.045, 0.045, MAT_DARK_METAL)
        add_box(bm, fe_xc, fe_y_out + 0.03, rz_bot, fe_w, 0.035, 0.035, MAT_DARK_METAL)
        add_box(bm, fe_x0 + 0.03, fe_ym, rz_top, 0.045, fe_d, 0.045, MAT_DARK_METAL, omit_faces=('+Y',))
        add_box(bm, fe_x1 - 0.03, fe_ym, rz_top, 0.045, fe_d, 0.045, MAT_DARK_METAL, omit_faces=('+Y',))

        for px in (fe_x0 + 0.03, -1.20, fe_x1 - 0.03):
            add_box(bm, px, fe_y_out + 0.03, fz + 0.48, 0.045, 0.045, 0.94, MAT_DARK_METAL, omit_faces=('-Z', '+Z'))

        for p_idx in range(8):
            px = fe_x0 + 0.42 + p_idx * ((fe_w - 0.84) / 7.0)
            add_box(bm, px, fe_y_out + 0.03, rz_mid, 0.022, 0.022, rh, MAT_DARK_METAL, omit_faces=('-Z', '+Z'))

    for fl_idx in range(4):
        z_a = fe_levels[fl_idx]
        z_b = fe_levels[fl_idx + 1]
        if fl_idx % 2 == 0:
            x_start, x_end = -2.65, -0.35
        else:
            x_start, x_end = -0.35, -2.65
        y_st0 = -7.36
        y_st1 = -7.80
        add_strut(bm, (x_start, y_st0, z_a), (x_end, y_st0, z_b), 0.024, MAT_DARK_METAL)
        add_strut(bm, (x_start, y_st1, z_a), (x_end, y_st1, z_b), 0.024, MAT_DARK_METAL)
        add_strut(bm, (x_start, y_st1, z_a + 0.86), (x_end, y_st1, z_b + 0.86), 0.020, MAT_DARK_METAL)
        n_steps = 7
        for s_i in range(1, n_steps + 1):
            t = s_i / (n_steps + 1.0)
            sx = x_start + (x_end - x_start) * t
            sz = z_a + (z_b - z_a) * t
            add_box(bm, sx, 0.5 * (y_st0 + y_st1), sz, 0.22, 0.44, 0.028, MAT_DARK_METAL, omit_faces=('-Y', '+Y'))

    dl_x0 = -3.52
    dl_x1 = -3.14
    dl_y = -8.14
    add_box(bm, dl_x0, dl_y, 3.45, 0.03, 0.03, 3.60, MAT_DARK_METAL)
    add_box(bm, dl_x1, dl_y, 3.45, 0.03, 0.03, 3.60, MAT_DARK_METAL)
    for r_i in range(8):
        rz = 1.85 + r_i * 0.42
        add_box(bm, 0.5 * (dl_x0 + dl_x1), dl_y, rz, 0.38, 0.024, 0.024, MAT_DARK_METAL, omit_faces=('-X', '+X'))

    rl_x0 = 0.78
    rl_x1 = 1.18
    rl_y = -7.56
    add_box(bm, rl_x0, rl_y, 18.80, 0.032, 0.032, 4.70, MAT_DARK_METAL)
    add_box(bm, rl_x1, rl_y, 18.80, 0.032, 0.032, 4.70, MAT_DARK_METAL)
    add_box(bm, rl_x0, -7.02, 21.14, 0.032, 1.10, 0.032, MAT_DARK_METAL)
    add_box(bm, rl_x1, -7.02, 21.14, 0.032, 1.10, 0.032, MAT_DARK_METAL)
    for r_i in range(10):
        rz = 16.80 + r_i * 0.44
        add_box(bm, 0.5 * (rl_x0 + rl_x1), rl_y, rz, 0.40, 0.024, 0.024, MAT_DARK_METAL, omit_faces=('-X', '+X'))

    wt_cx = -3.10
    wt_cy = 2.35
    wt_z_roof = 19.85
    wt_z_deck = 22.85
    wt_z_top = 26.05
    wt_z_peak = 27.10

    leg_bot_offs = [(-1.18, -1.18), (1.18, -1.18), (1.18, 1.18), (-1.18, 1.18)]
    leg_top_offs = [(-0.96, -0.96), (0.96, -0.96), (0.96, 0.96), (-0.96, 0.96)]
    leg_bot_pts = []
    leg_mid_pts = []
    leg_top_pts = []

    for i in range(4):
        bx = wt_cx + leg_bot_offs[i][0]
        by = wt_cy + leg_bot_offs[i][1]
        tx = wt_cx + leg_top_offs[i][0]
        ty = wt_cy + leg_top_offs[i][1]
        add_box(bm, bx, by, wt_z_roof + 0.14, 0.48, 0.48, 0.28, MAT_STONE, omit_faces=('-Z',))
        p_bot = (bx, by, wt_z_roof + 0.28)
        p_top = (tx, ty, wt_z_deck)
        p_mid = (0.5 * (bx + tx), 0.5 * (by + ty), 0.5 * (wt_z_roof + 0.28 + wt_z_deck))
        leg_bot_pts.append(p_bot)
        leg_mid_pts.append(p_mid)
        leg_top_pts.append(p_top)
        add_strut(bm, p_bot, p_top, 0.105, MAT_WOOD)

    for i in range(4):
        ni = (i + 1) % 4
        add_strut(bm, leg_mid_pts[i], leg_mid_pts[ni], 0.06, MAT_WOOD)
        add_strut(bm, leg_top_pts[i], leg_top_pts[ni], 0.075, MAT_WOOD)
        add_strut(bm, leg_bot_pts[i], leg_mid_pts[ni], 0.035, MAT_DARK_METAL)
        add_strut(bm, leg_bot_pts[ni], leg_mid_pts[i], 0.035, MAT_DARK_METAL)
        add_strut(bm, leg_mid_pts[i], leg_top_pts[ni], 0.035, MAT_DARK_METAL)
        add_strut(bm, leg_mid_pts[ni], leg_top_pts[i], 0.035, MAT_DARK_METAL)

    add_cylinder_z(bm, wt_cx, wt_cy, wt_z_roof, wt_z_deck, 0.22, 0.22, 8, MAT_WOOD, cap_bottom=False, cap_top=False)
    add_cylinder_z(bm, wt_cx, wt_cy, wt_z_deck, wt_z_deck + 0.16, 1.78, 1.78, 12, MAT_WOOD, cap_bottom=True, cap_top=True)
    add_cylinder_z(bm, wt_cx, wt_cy, wt_z_deck + 0.16, wt_z_top, 1.56, 1.50, 12, MAT_WOOD, cap_bottom=False, cap_top=True)

    for hz in (23.22, 23.88, 24.62, 25.42):
        t_h = (hz - (wt_z_deck + 0.16)) / (wt_z_top - (wt_z_deck + 0.16))
        hr = (1.56 * (1.0 - t_h) + 1.50 * t_h) + 0.025
        add_cylinder_z(bm, wt_cx, wt_cy, hz - 0.025, hz + 0.025, hr, hr, 12, MAT_DARK_METAL, cap_bottom=False, cap_top=False)

    add_cylinder_z(bm, wt_cx, wt_cy, wt_z_top - 0.04, wt_z_peak, 1.74, 0.0, 12, MAT_WOOD, cap_bottom=True, cap_top=False)
    add_cylinder_z(bm, wt_cx, wt_cy, wt_z_peak - 0.05, wt_z_peak + 0.42, 0.04, 0.01, 6, MAT_DARK_METAL, cap_bottom=False, cap_top=True)

    wt_lx0 = wt_cx - 0.18
    wt_lx1 = wt_cx + 0.18
    wt_ly = wt_cy - 1.64
    add_box(bm, wt_lx0, wt_ly, 23.05, 0.03, 0.03, 6.20, MAT_DARK_METAL)
    add_box(bm, wt_lx1, wt_ly, 23.05, 0.03, 0.03, 6.20, MAT_DARK_METAL)
    for r_i in range(11):
        rz = 20.20 + r_i * 0.54
        add_box(bm, wt_cx, wt_ly, rz, 0.36, 0.024, 0.024, MAT_DARK_METAL, omit_faces=('-X', '+X'))

    bh_cx = 3.10
    bh_cy = 2.20
    bh_w = 3.20
    bh_d = 3.80
    bh_h = 2.85
    add_box(bm, bh_cx, bh_cy, wt_z_roof + 0.5 * bh_h, bh_w, bh_d, bh_h, MAT_BRICK, omit_faces=('-Z',))
    add_box(bm, bh_cx, bh_cy, wt_z_roof + bh_h + 0.08, bh_w + 0.24, bh_d + 0.24, 0.16, MAT_STONE)
    add_box(bm, bh_cx, bh_cy - 0.5 * bh_d - 0.02, wt_z_roof + 1.12, 1.05, 0.06, 2.05, MAT_DARK_METAL, omit_faces=('+Y', '-Z'))
    add_box(bm, bh_cx, bh_cy - 0.5 * bh_d - 0.18, wt_z_roof + 0.07, 1.25, 0.36, 0.14, MAT_STONE, omit_faces=('+Y', '-Z'))

    for ac_y in (-2.50, -4.20):
        ac_x = 2.85
        add_box(bm, ac_x, ac_y, wt_z_roof + 0.06, 1.38, 0.98, 0.12, MAT_STONE, omit_faces=('-Z',))
        add_box(bm, ac_x, ac_y, wt_z_roof + 0.58, 1.26, 0.86, 0.92, MAT_DARK_METAL, omit_faces=('-Z',))
        add_cylinder_z(bm, ac_x - 0.26, ac_y, wt_z_roof + 1.04, wt_z_roof + 1.12, 0.28, 0.28, 8, MAT_DARK_METAL, cap_bottom=False, cap_top=True)
        add_cylinder_z(bm, ac_x + 0.28, ac_y, wt_z_roof + 1.04, wt_z_roof + 1.12, 0.28, 0.28, 8, MAT_DARK_METAL, cap_bottom=False, cap_top=True)

    for ch_x, ch_y in ((-6.32, 0.60), (6.32, -1.10)):
        add_box(bm, ch_x, ch_y, wt_z_roof + 1.05, 0.62, 1.42, 2.10, MAT_BRICK, omit_faces=('-Z',))
        add_box(bm, ch_x, ch_y, wt_z_roof + 2.16, 0.74, 1.54, 0.12, MAT_STONE)
        add_cylinder_z(bm, ch_x, ch_y - 0.32, wt_z_roof + 2.22, wt_z_roof + 2.52, 0.14, 0.14, 8, MAT_STONE, cap_bottom=False, cap_top=True)
        add_cylinder_z(bm, ch_x, ch_y + 0.32, wt_z_roof + 2.22, wt_z_roof + 2.52, 0.14, 0.14, 8, MAT_STONE, cap_bottom=False, cap_top=True)

    for vx, vy in ((-1.10, -3.40), (-2.60, -3.40), (0.60, 3.80)):
        add_cylinder_z(bm, vx, vy, wt_z_roof, wt_z_roof + 0.72, 0.11, 0.11, 8, MAT_DARK_METAL, cap_bottom=False, cap_top=False)
        add_cylinder_z(bm, vx, vy, wt_z_roof + 0.72, wt_z_roof + 0.88, 0.20, 0.04, 8, MAT_DARK_METAL, cap_bottom=True, cap_top=False)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    for edge in bm.edges:
        if len(edge.link_faces) == 2:
            ang = edge.calc_face_angle(0.0)
            if ang > math.radians(28.0):
                edge.smooth = False
        else:
            edge.smooth = False

    mesh = bpy.data.meshes.new("BldgBrick")
    bm.to_mesh(mesh)
    bm.free()

    if hasattr(mesh, "use_auto_smooth"):
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = math.radians(35.0)

    obj = bpy.data.objects.new("BldgBrick", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = (0.0, 0.0, 0.0)
    return obj


def add_grime_modulation(nt, base_color_socket, sep_xyz_node, tex_coord_node, grime_strength=0.42):
    noise_streak = nt.nodes.new("ShaderNodeTexNoise")
    noise_streak.inputs["Scale"].default_value = 1.0
    noise_streak.inputs["Detail"].default_value = 6.0
    noise_streak.inputs["Roughness"].default_value = 0.65

    mapping_streak = nt.nodes.new("ShaderNodeMapping")
    mapping_streak.inputs["Scale"].default_value = (2.8, 2.8, 0.32)
    nt.links.new(tex_coord_node.outputs["Object"], mapping_streak.inputs["Vector"])
    nt.links.new(mapping_streak.outputs["Vector"], noise_streak.inputs["Vector"])

    ground_div = nt.nodes.new("ShaderNodeMath")
    ground_div.operation = 'DIVIDE'
    ground_div.inputs[1].default_value = 3.8
    ground_div.use_clamp = True
    nt.links.new(sep_xyz_node.outputs["Z"], ground_div.inputs[0])

    ground_inv = nt.nodes.new("ShaderNodeMath")
    ground_inv.operation = 'SUBTRACT'
    ground_inv.inputs[0].default_value = 1.0
    ground_inv.use_clamp = True
    nt.links.new(ground_div.outputs["Value"], ground_inv.inputs[1])

    sill_wave = nt.nodes.new("ShaderNodeTexWave")
    sill_wave.wave_type = 'BANDS'
    sill_wave.bands_direction = 'Z'
    sill_wave.wave_profile = 'SAW'
    sill_wave.inputs["Scale"].default_value = 1.05
    sill_wave.inputs["Distortion"].default_value = 1.6
    nt.links.new(tex_coord_node.outputs["Object"], sill_wave.inputs["Vector"])

    sill_mul = nt.nodes.new("ShaderNodeMath")
    sill_mul.operation = 'MULTIPLY'
    nt.links.new(sill_wave.outputs["Fac"], sill_mul.inputs[0])
    nt.links.new(noise_streak.outputs["Fac"], sill_mul.inputs[1])

    grime_sum = nt.nodes.new("ShaderNodeMath")
    grime_sum.operation = 'MAXIMUM'
    grime_sum.use_clamp = True
    nt.links.new(ground_inv.outputs["Value"], grime_sum.inputs[0])
    nt.links.new(sill_mul.outputs["Value"], grime_sum.inputs[1])

    grime_scale = nt.nodes.new("ShaderNodeMath")
    grime_scale.operation = 'MULTIPLY'
    grime_scale.inputs[1].default_value = grime_strength
    grime_scale.use_clamp = True
    nt.links.new(grime_sum.outputs["Value"], grime_scale.inputs[0])

    mix_grime = nt.nodes.new("ShaderNodeMix")
    mix_grime.data_type = 'RGBA'
    mix_grime.blend_type = 'MULTIPLY'
    mix_grime.inputs["B"].default_value = (0.20, 0.18, 0.16, 1.0)
    nt.links.new(grime_scale.outputs["Value"], mix_grime.inputs["Factor"])
    nt.links.new(base_color_socket, mix_grime.inputs["A"])
    return mix_grime.outputs["Result"]


def create_wall_coord_socket(nt, tex_coord_node):
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tex_coord_node.outputs["Object"], sep.inputs["Vector"])
    add_xy = nt.nodes.new("ShaderNodeMath")
    add_xy.operation = 'ADD'
    nt.links.new(sep.outputs["X"], add_xy.inputs[0])
    nt.links.new(sep.outputs["Y"], add_xy.inputs[1])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(add_xy.outputs["Value"], comb.inputs["X"])
    nt.links.new(sep.outputs["Z"], comb.inputs["Y"])
    nt.links.new(sep.outputs["Z"], comb.inputs["Z"])
    return comb.outputs["Vector"], sep


def create_procedural_materials(obj):
    mats = []

    mat_brick = bpy.data.materials.new("Proc_Brick")
    mat_brick.use_nodes = True
    nt = mat_brick.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.78
    bsdf.inputs["Metallic"].default_value = 0.0
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")
    wall_vec, sep_xyz = create_wall_coord_socket(nt, tc)

    brick_tex = nt.nodes.new("ShaderNodeTexBrick")
    brick_tex.offset = 0.5
    brick_tex.offset_frequency = 2
    brick_tex.squash = 1.0
    brick_tex.squash_frequency = 2
    brick_tex.inputs["Scale"].default_value = 4.2
    brick_tex.inputs["Mortar Size"].default_value = 0.022
    brick_tex.inputs["Mortar Smooth"].default_value = 0.15
    brick_tex.inputs["Bias"].default_value = -0.12
    brick_tex.inputs["Brick Width"].default_value = 0.24
    brick_tex.inputs["Row Height"].default_value = 0.082
    brick_tex.inputs["Color1"].default_value = (0.43, 0.14, 0.09, 1.0)
    brick_tex.inputs["Color2"].default_value = (0.21, 0.065, 0.045, 1.0)
    brick_tex.inputs["Mortar"].default_value = (0.54, 0.50, 0.45, 1.0)
    nt.links.new(wall_vec, brick_tex.inputs["Vector"])

    noise_var = nt.nodes.new("ShaderNodeTexNoise")
    noise_var.inputs["Scale"].default_value = 6.5
    noise_var.inputs["Detail"].default_value = 5.0
    nt.links.new(tc.outputs["Object"], noise_var.inputs["Vector"])

    mix_var = nt.nodes.new("ShaderNodeMix")
    mix_var.data_type = 'RGBA'
    mix_var.blend_type = 'OVERLAY'
    mix_var.inputs["Factor"].default_value = 0.25
    nt.links.new(brick_tex.outputs["Color"], mix_var.inputs["A"])
    nt.links.new(noise_var.outputs["Color"], mix_var.inputs["B"])

    col_grimed = add_grime_modulation(nt, mix_var.outputs["Result"], sep_xyz, tc, grime_strength=0.45)
    nt.links.new(col_grimed, bsdf.inputs["Base Color"])

    bump_mix = nt.nodes.new("ShaderNodeMath")
    bump_mix.operation = 'MULTIPLY_ADD'
    bump_mix.inputs[1].default_value = 0.20
    nt.links.new(noise_var.outputs["Fac"], bump_mix.inputs[0])
    nt.links.new(brick_tex.outputs["Fac"], bump_mix.inputs[2])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.invert = True
    bump.inputs["Strength"].default_value = 0.45
    bump.inputs["Distance"].default_value = 0.015
    nt.links.new(bump_mix.outputs["Value"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats.append(mat_brick)

    mat_stone = bpy.data.materials.new("Proc_Stone")
    mat_stone.use_nodes = True
    nt = mat_stone.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.72
    bsdf.inputs["Metallic"].default_value = 0.0
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")
    wall_vec, sep_xyz = create_wall_coord_socket(nt, tc)

    stone_blocks = nt.nodes.new("ShaderNodeTexBrick")
    stone_blocks.inputs["Scale"].default_value = 1.6
    stone_blocks.inputs["Mortar Size"].default_value = 0.012
    stone_blocks.inputs["Brick Width"].default_value = 0.65
    stone_blocks.inputs["Row Height"].default_value = 0.35
    stone_blocks.inputs["Color1"].default_value = (0.68, 0.64, 0.56, 1.0)
    stone_blocks.inputs["Color2"].default_value = (0.58, 0.54, 0.47, 1.0)
    stone_blocks.inputs["Mortar"].default_value = (0.38, 0.35, 0.31, 1.0)
    nt.links.new(wall_vec, stone_blocks.inputs["Vector"])

    stone_noise = nt.nodes.new("ShaderNodeTexNoise")
    stone_noise.inputs["Scale"].default_value = 14.0
    stone_noise.inputs["Detail"].default_value = 8.0
    nt.links.new(tc.outputs["Object"], stone_noise.inputs["Vector"])

    stone_mix = nt.nodes.new("ShaderNodeMix")
    stone_mix.data_type = 'RGBA'
    stone_mix.blend_type = 'MULTIPLY'
    stone_mix.inputs["Factor"].default_value = 0.18
    nt.links.new(stone_blocks.outputs["Color"], stone_mix.inputs["A"])
    nt.links.new(stone_noise.outputs["Color"], stone_mix.inputs["B"])

    stone_grimed = add_grime_modulation(nt, stone_mix.outputs["Result"], sep_xyz, tc, grime_strength=0.38)
    nt.links.new(stone_grimed, bsdf.inputs["Base Color"])

    stone_bump_add = nt.nodes.new("ShaderNodeMath")
    stone_bump_add.operation = 'MULTIPLY_ADD'
    stone_bump_add.inputs[1].default_value = 0.35
    nt.links.new(stone_noise.outputs["Fac"], stone_bump_add.inputs[0])
    nt.links.new(stone_blocks.outputs["Fac"], stone_bump_add.inputs[2])

    stone_bump = nt.nodes.new("ShaderNodeBump")
    stone_bump.invert = True
    stone_bump.inputs["Strength"].default_value = 0.30
    stone_bump.inputs["Distance"].default_value = 0.012
    nt.links.new(stone_bump_add.outputs["Value"], stone_bump.inputs["Height"])
    nt.links.new(stone_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats.append(mat_stone)

    mat_stucco = bpy.data.materials.new("Proc_Stucco")
    mat_stucco.use_nodes = True
    nt = mat_stucco.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.76
    bsdf.inputs["Metallic"].default_value = 0.0
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")
    _, sep_xyz = create_wall_coord_socket(nt, tc)

    stucco_noise = nt.nodes.new("ShaderNodeTexNoise")
    stucco_noise.inputs["Scale"].default_value = 9.0
    stucco_noise.inputs["Detail"].default_value = 8.0
    stucco_noise.inputs["Roughness"].default_value = 0.7
    nt.links.new(tc.outputs["Object"], stucco_noise.inputs["Vector"])

    rust_wave = nt.nodes.new("ShaderNodeTexWave")
    rust_wave.wave_type = 'BANDS'
    rust_wave.bands_direction = 'Z'
    rust_wave.inputs["Scale"].default_value = 4.5
    nt.links.new(tc.outputs["Object"], rust_wave.inputs["Vector"])

    stucco_mix = nt.nodes.new("ShaderNodeMix")
    stucco_mix.data_type = 'RGBA'
    stucco_mix.inputs["A"].default_value = (0.56, 0.52, 0.45, 1.0)
    stucco_mix.inputs["B"].default_value = (0.45, 0.41, 0.35, 1.0)
    nt.links.new(stucco_noise.outputs["Fac"], stucco_mix.inputs["Factor"])

    stucco_grimed = add_grime_modulation(nt, stucco_mix.outputs["Result"], sep_xyz, tc, grime_strength=0.48)
    nt.links.new(stucco_grimed, bsdf.inputs["Base Color"])

    stucco_bump_math = nt.nodes.new("ShaderNodeMath")
    stucco_bump_math.operation = 'MULTIPLY_ADD'
    stucco_bump_math.inputs[1].default_value = 0.15
    nt.links.new(rust_wave.outputs["Fac"], stucco_bump_math.inputs[0])
    nt.links.new(stucco_noise.outputs["Fac"], stucco_bump_math.inputs[2])

    stucco_bump = nt.nodes.new("ShaderNodeBump")
    stucco_bump.inputs["Strength"].default_value = 0.28
    stucco_bump.inputs["Distance"].default_value = 0.01
    nt.links.new(stucco_bump_math.outputs["Value"], stucco_bump.inputs["Height"])
    nt.links.new(stucco_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats.append(mat_stucco)

    mat_frame = bpy.data.materials.new("Proc_Frame")
    mat_frame.use_nodes = True
    nt = mat_frame.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.42
    bsdf.inputs["Metallic"].default_value = 0.0
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")
    _, sep_xyz = create_wall_coord_socket(nt, tc)

    frm_noise = nt.nodes.new("ShaderNodeTexNoise")
    frm_noise.inputs["Scale"].default_value = 18.0
    frm_noise.inputs["Detail"].default_value = 5.0
    nt.links.new(tc.outputs["Object"], frm_noise.inputs["Vector"])

    frm_mix = nt.nodes.new("ShaderNodeMix")
    frm_mix.data_type = 'RGBA'
    frm_mix.inputs["A"].default_value = (0.86, 0.85, 0.81, 1.0)
    frm_mix.inputs["B"].default_value = (0.74, 0.72, 0.67, 1.0)
    nt.links.new(frm_noise.outputs["Fac"], frm_mix.inputs["Factor"])

    frm_grimed = add_grime_modulation(nt, frm_mix.outputs["Result"], sep_xyz, tc, grime_strength=0.25)
    nt.links.new(frm_grimed, bsdf.inputs["Base Color"])

    frm_bump = nt.nodes.new("ShaderNodeBump")
    frm_bump.inputs["Strength"].default_value = 0.12
    frm_bump.inputs["Distance"].default_value = 0.005
    nt.links.new(frm_noise.outputs["Fac"], frm_bump.inputs["Height"])
    nt.links.new(frm_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats.append(mat_frame)

    mat_glass = bpy.data.materials.new("Proc_Glass")
    mat_glass.use_nodes = True
    nt = mat_glass.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.12
    bsdf.inputs["Metallic"].default_value = 0.0
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")
    wall_vec, _ = create_wall_coord_socket(nt, tc)

    curtain_wave = nt.nodes.new("ShaderNodeTexWave")
    curtain_wave.wave_type = 'BANDS'
    curtain_wave.bands_direction = 'X'
    curtain_wave.inputs["Scale"].default_value = 6.2
    curtain_wave.inputs["Distortion"].default_value = 2.4
    nt.links.new(wall_vec, curtain_wave.inputs["Vector"])

    room_noise = nt.nodes.new("ShaderNodeTexNoise")
    room_noise.inputs["Scale"].default_value = 1.4
    room_noise.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], room_noise.inputs["Vector"])

    glass_mix1 = nt.nodes.new("ShaderNodeMix")
    glass_mix1.data_type = 'RGBA'
    glass_mix1.inputs["A"].default_value = (0.04, 0.06, 0.09, 1.0)
    glass_mix1.inputs["B"].default_value = (0.14, 0.18, 0.22, 1.0)
    nt.links.new(room_noise.outputs["Fac"], glass_mix1.inputs["Factor"])

    glass_mix2 = nt.nodes.new("ShaderNodeMix")
    glass_mix2.data_type = 'RGBA'
    glass_mix2.inputs["B"].default_value = (0.20, 0.18, 0.15, 1.0)
    nt.links.new(curtain_wave.outputs["Fac"], glass_mix2.inputs["Factor"])
    nt.links.new(glass_mix1.outputs["Result"], glass_mix2.inputs["A"])
    nt.links.new(glass_mix2.outputs["Result"], bsdf.inputs["Base Color"])

    glass_bump = nt.nodes.new("ShaderNodeBump")
    glass_bump.inputs["Strength"].default_value = 0.05
    glass_bump.inputs["Distance"].default_value = 0.003
    nt.links.new(room_noise.outputs["Fac"], glass_bump.inputs["Height"])
    nt.links.new(glass_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats.append(mat_glass)

    mat_metal = bpy.data.materials.new("Proc_DarkMetal")
    mat_metal.use_nodes = True
    nt = mat_metal.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.45
    bsdf.inputs["Metallic"].default_value = 0.05
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")
    metal_noise = nt.nodes.new("ShaderNodeTexNoise")
    metal_noise.inputs["Scale"].default_value = 14.0
    metal_noise.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], metal_noise.inputs["Vector"])

    metal_mix = nt.nodes.new("ShaderNodeMix")
    metal_mix.data_type = 'RGBA'
    metal_mix.inputs["A"].default_value = (0.11, 0.12, 0.13, 1.0)
    metal_mix.inputs["B"].default_value = (0.21, 0.13, 0.09, 1.0)
    nt.links.new(metal_noise.outputs["Fac"], metal_mix.inputs["Factor"])
    nt.links.new(metal_mix.outputs["Result"], bsdf.inputs["Base Color"])

    metal_bump = nt.nodes.new("ShaderNodeBump")
    metal_bump.inputs["Strength"].default_value = 0.22
    metal_bump.inputs["Distance"].default_value = 0.008
    nt.links.new(metal_noise.outputs["Fac"], metal_bump.inputs["Height"])
    nt.links.new(metal_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats.append(mat_metal)

    mat_roof = bpy.data.materials.new("Proc_Roof")
    mat_roof.use_nodes = True
    nt = mat_roof.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.88
    bsdf.inputs["Metallic"].default_value = 0.0
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")
    roof_noise = nt.nodes.new("ShaderNodeTexNoise")
    roof_noise.inputs["Scale"].default_value = 26.0
    roof_noise.inputs["Detail"].default_value = 9.0
    nt.links.new(tc.outputs["Object"], roof_noise.inputs["Vector"])

    roof_mix = nt.nodes.new("ShaderNodeMix")
    roof_mix.data_type = 'RGBA'
    roof_mix.inputs["A"].default_value = (0.15, 0.15, 0.16, 1.0)
    roof_mix.inputs["B"].default_value = (0.25, 0.24, 0.22, 1.0)
    nt.links.new(roof_noise.outputs["Fac"], roof_mix.inputs["Factor"])
    nt.links.new(roof_mix.outputs["Result"], bsdf.inputs["Base Color"])

    roof_bump = nt.nodes.new("ShaderNodeBump")
    roof_bump.inputs["Strength"].default_value = 0.35
    roof_bump.inputs["Distance"].default_value = 0.01
    nt.links.new(roof_noise.outputs["Fac"], roof_bump.inputs["Height"])
    nt.links.new(roof_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats.append(mat_roof)

    mat_wood = bpy.data.materials.new("Proc_Wood")
    mat_wood.use_nodes = True
    nt = mat_wood.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.68
    bsdf.inputs["Metallic"].default_value = 0.0
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")
    wood_wave = nt.nodes.new("ShaderNodeTexWave")
    wood_wave.wave_type = 'BANDS'
    wood_wave.bands_direction = 'X'
    wood_wave.inputs["Scale"].default_value = 9.5
    wood_wave.inputs["Distortion"].default_value = 4.2
    wood_wave.inputs["Detail"].default_value = 5.0
    nt.links.new(tc.outputs["Object"], wood_wave.inputs["Vector"])

    wood_mix = nt.nodes.new("ShaderNodeMix")
    wood_mix.data_type = 'RGBA'
    wood_mix.inputs["A"].default_value = (0.36, 0.20, 0.11, 1.0)
    wood_mix.inputs["B"].default_value = (0.21, 0.11, 0.06, 1.0)
    nt.links.new(wood_wave.outputs["Fac"], wood_mix.inputs["Factor"])
    nt.links.new(wood_mix.outputs["Result"], bsdf.inputs["Base Color"])

    wood_bump = nt.nodes.new("ShaderNodeBump")
    wood_bump.inputs["Strength"].default_value = 0.32
    wood_bump.inputs["Distance"].default_value = 0.01
    nt.links.new(wood_wave.outputs["Fac"], wood_bump.inputs["Height"])
    nt.links.new(wood_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats.append(mat_wood)

    mat_awning = bpy.data.materials.new("Proc_Awning")
    mat_awning.use_nodes = True
    nt = mat_awning.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.82
    bsdf.inputs["Metallic"].default_value = 0.0
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")
    aw_wave = nt.nodes.new("ShaderNodeTexWave")
    aw_wave.wave_type = 'BANDS'
    aw_wave.bands_direction = 'X'
    aw_wave.inputs["Scale"].default_value = 5.0
    nt.links.new(tc.outputs["Object"], aw_wave.inputs["Vector"])

    aw_noise = nt.nodes.new("ShaderNodeTexNoise")
    aw_noise.inputs["Scale"].default_value = 45.0
    nt.links.new(tc.outputs["Object"], aw_noise.inputs["Vector"])

    aw_mix = nt.nodes.new("ShaderNodeMix")
    aw_mix.data_type = 'RGBA'
    aw_mix.inputs["A"].default_value = (0.08, 0.22, 0.14, 1.0)
    aw_mix.inputs["B"].default_value = (0.04, 0.12, 0.08, 1.0)
    nt.links.new(aw_wave.outputs["Fac"], aw_mix.inputs["Factor"])
    nt.links.new(aw_mix.outputs["Result"], bsdf.inputs["Base Color"])

    aw_bump = nt.nodes.new("ShaderNodeBump")
    aw_bump.inputs["Strength"].default_value = 0.20
    aw_bump.inputs["Distance"].default_value = 0.006
    nt.links.new(aw_noise.outputs["Fac"], aw_bump.inputs["Height"])
    nt.links.new(aw_bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats.append(mat_awning)

    obj.data.materials.clear()
    for m in mats:
        obj.data.materials.append(m)

    return mats


def unwrap_and_bake(obj, out_dir):
    scene = bpy.context.scene
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.01)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(margin=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')

    img_albedo = bpy.data.images.new("BldgBrick_albedo", width=2048, height=2048, alpha=False)
    img_albedo.colorspace_settings.name = 'sRGB'
    img_normal = bpy.data.images.new("BldgBrick_normal", width=2048, height=2048, alpha=False)
    img_normal.colorspace_settings.name = 'Non-Color'

    bake_nodes = []
    for mat in obj.data.materials:
        nt = mat.node_tree
        tex_node = nt.nodes.new("ShaderNodeTexImage")
        tex_node.name = "BakeTarget"
        bake_nodes.append((nt, tex_node))

    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 16
    scene.cycles.use_adaptive_sampling = True
    scene.render.bake.margin = 8

    for nt, tex_node in bake_nodes:
        tex_node.image = img_albedo
        for n in nt.nodes:
            n.select = False
        tex_node.select = True
        nt.nodes.active = tex_node

    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    scene.render.bake.use_pass_color = True
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=8, use_clear=True)

    albedo_path = os.path.join(out_dir, "BldgBrick_albedo.png")
    img_albedo.filepath_raw = albedo_path
    img_albedo.file_format = 'PNG'
    img_albedo.save()
    img_albedo.filepath = albedo_path

    for nt, tex_node in bake_nodes:
        tex_node.image = img_normal
        for n in nt.nodes:
            n.select = False
        tex_node.select = True
        nt.nodes.active = tex_node

    scene.render.bake.normal_space = 'TANGENT'
    bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', margin=8, use_clear=True)

    normal_path = os.path.join(out_dir, "BldgBrick_normal.png")
    img_normal.filepath_raw = normal_path
    img_normal.file_format = 'PNG'
    img_normal.save()
    img_normal.filepath = normal_path

    final_mat = bpy.data.materials.new("BldgBrick_Mat")
    final_mat.use_nodes = True
    fnt = final_mat.node_tree
    fnt.nodes.clear()

    out_node = fnt.nodes.new("ShaderNodeOutputMaterial")
    bsdf_node = fnt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf_node.inputs["Roughness"].default_value = 0.7
    bsdf_node.inputs["Metallic"].default_value = 0.0
    fnt.links.new(bsdf_node.outputs["BSDF"], out_node.inputs["Surface"])

    alb_node = fnt.nodes.new("ShaderNodeTexImage")
    alb_node.image = img_albedo
    fnt.links.new(alb_node.outputs["Color"], bsdf_node.inputs["Base Color"])

    nrm_tex_node = fnt.nodes.new("ShaderNodeTexImage")
    nrm_tex_node.image = img_normal
    nrm_map_node = fnt.nodes.new("ShaderNodeNormalMap")
    fnt.links.new(nrm_tex_node.outputs["Color"], nrm_map_node.inputs["Color"])
    fnt.links.new(nrm_map_node.outputs["Normal"], bsdf_node.inputs["Normal"])

    obj.data.materials.clear()
    obj.data.materials.append(final_mat)
    for poly in obj.data.polygons:
        poly.material_index = 0


def export_and_render(obj, out_fbx):
    scene = bpy.context.scene
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.export_scene.fbx(
        filepath=out_fbx,
        use_selection=True,
        bake_space_transform=True,
        axis_forward='-Z',
        axis_up='Y',
        path_mode='COPY',
        embed_textures=True,
    )

    engine_keys = list(scene.render.bl_rna.properties['engine'].enum_items.keys())
    if 'BLENDER_EEVEE_NEXT' in engine_keys:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    elif 'BLENDER_EEVEE' in engine_keys:
        scene.render.engine = 'BLENDER_EEVEE'
    else:
        scene.render.engine = engine_keys[0]

    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node is None:
        bg_node = world.node_tree.nodes.new("ShaderNodeBackground")
    bg_node.inputs["Color"].default_value = (0.46, 0.48, 0.52, 1.0)
    bg_node.inputs["Strength"].default_value = 0.6

    sun_data = bpy.data.lights.new(name="Sun", type='SUN')
    sun_data.energy = 3.0
    sun_data.color = (1.0, 0.97, 0.92)
    sun_obj = bpy.data.objects.new(name="Sun", object_data=sun_data)
    scene.collection.objects.link(sun_obj)
    sun_obj.location = (-18.0, -24.0, 30.0)
    sun_dir = Vector((0.0, 0.0, 10.0)) - sun_obj.location
    sun_obj.rotation_euler = sun_dir.to_track_quat('-Z', 'Y').to_euler()

    cam_data = bpy.data.cameras.new(name="Camera")
    cam_data.lens = 35.0
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.1
    cam_data.clip_end = 500.0
    cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (-23.5, -27.5, 3.2)
    look_target = Vector((-0.4, 0.0, 12.2))
    cam_dir = look_target - cam_obj.location
    cam_obj.rotation_euler = cam_dir.to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'

    preview_primary = os.path.splitext(out_fbx)[0] + ".png"
    scene.render.filepath = preview_primary
    bpy.ops.render.render(write_still=True)

    preview_alt = out_fbx + ".png"
    if os.path.abspath(preview_primary) != os.path.abspath(preview_alt) and os.path.exists(preview_primary):
        with open(preview_primary, "rb") as f_src:
            png_bytes = f_src.read()
        with open(preview_alt, "wb") as f_dst:
            f_dst.write(png_bytes)

    tri_count = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    print("TRIS", tri_count)


def main():
    out_fbx = "BldgBrick.fbx"
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if idx + 1 < len(sys.argv):
            out_fbx = sys.argv[idx + 1]
    out_fbx = os.path.abspath(out_fbx)
    out_dir = os.path.dirname(out_fbx)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    else:
        out_dir = os.getcwd()

    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0

    obj = build_building_geometry()
    create_procedural_materials(obj)
    unwrap_and_bake(obj, out_dir)
    export_and_render(obj, out_fbx)


if __name__ == "__main__":
    main()
