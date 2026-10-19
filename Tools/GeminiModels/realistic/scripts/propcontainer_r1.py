import bpy
import bmesh
import mathutils
from mathutils import Vector, Matrix
import math
import sys
import os

# ---------------------------------------------------------------------------
# 1. CLEAR SCENE & PARSE OUTPUT PATHS
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)

out_arg = "Container20.fbx"
if "--" in sys.argv:
    idx = sys.argv.index("--")
    if idx + 1 < len(sys.argv):
        out_arg = sys.argv[idx + 1]

out_arg = os.path.abspath(out_arg)
base_no_ext, ext = os.path.splitext(out_arg)
if ext.lower() == ".fbx":
    fbx_path = out_arg
    preview_path = base_no_ext + ".png"
elif ext.lower() == ".png":
    preview_path = out_arg
    fbx_path = base_no_ext + ".fbx"
else:
    fbx_path = out_arg + ".fbx"
    preview_path = out_arg + ".png"

out_dir = os.path.dirname(fbx_path)
if out_dir:
    os.makedirs(out_dir, exist_ok=True)

albedo_path = os.path.join(out_dir, "Container20_albedo.png")
normal_path = os.path.join(out_dir, "Container20_normal.png")

scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0

# ---------------------------------------------------------------------------
# 2. GEOMETRY HELPERS (BMESH)
# ---------------------------------------------------------------------------
MAT_BLUE = 0
MAT_DARK_STEEL = 1
MAT_GALV = 2
MAT_RUBBER = 3
MAT_CSC = 4
MAT_WHITE = 5


def add_oriented_face(bm, verts, mat_idx, out_dir=None):
    f = bm.faces.new(verts)
    f.material_index = mat_idx
    f.smooth = False
    if out_dir is not None:
        f.normal_update()
        if f.normal.dot(out_dir) < 0.0:
            f.normal_flip()
    return f


def add_box(bm, x0, x1, y0, y1, z0, z1, mat_idx):
    v000 = bm.verts.new((x0, y0, z0))
    v100 = bm.verts.new((x1, y0, z0))
    v110 = bm.verts.new((x1, y1, z0))
    v010 = bm.verts.new((x0, y1, z0))
    v001 = bm.verts.new((x0, y0, z1))
    v101 = bm.verts.new((x1, y0, z1))
    v111 = bm.verts.new((x1, y1, z1))
    v011 = bm.verts.new((x0, y1, z1))
    faces = [
        ([v000, v010, v110, v100], Vector((0, 0, -1))),
        ([v001, v101, v111, v011], Vector((0, 0, 1))),
        ([v000, v100, v101, v001], Vector((0, -1, 0))),
        ([v110, v010, v011, v111], Vector((0, 1, 0))),
        ([v010, v000, v001, v011], Vector((-1, 0, 0))),
        ([v100, v110, v111, v101], Vector((1, 0, 0))),
    ]
    created = []
    for fverts, nrm in faces:
        created.append(add_oriented_face(bm, fverts, mat_idx, nrm))
    return created


def add_subdivided_box(bm, x0, x1, y0, y1, z0, z1, nx, ny, nz, mat_idx):
    xs = [x0 + (x1 - x0) * i / nx for i in range(nx + 1)]
    ys = [y0 + (y1 - y0) * i / ny for i in range(ny + 1)]
    zs = [z0 + (z1 - z0) * i / nz for i in range(nz + 1)]

    # -Y and +Y faces
    for y_val, nrm_y in ((y0, Vector((0, -1, 0))), (y1, Vector((0, 1, 0)))):
        grid = [[bm.verts.new((x, y_val, z)) for z in zs] for x in xs]
        for i in range(nx):
            for k in range(nz):
                add_oriented_face(bm, [grid[i][k], grid[i + 1][k], grid[i + 1][k + 1], grid[i][k + 1]], mat_idx, nrm_y)

    # -Z and +Z faces
    for z_val, nrm_z in ((z0, Vector((0, 0, -1))), (z1, Vector((0, 0, 1)))):
        grid = [[bm.verts.new((x, y, z_val)) for y in ys] for x in xs]
        for i in range(nx):
            for j in range(ny):
                add_oriented_face(bm, [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]], mat_idx, nrm_z)

    # -X and +X faces
    for x_val, nrm_x in ((x0, Vector((-1, 0, 0))), (x1, Vector((1, 0, 0)))):
        grid = [[bm.verts.new((x_val, y, z)) for z in zs] for y in ys]
        for j in range(ny):
            for k in range(nz):
                add_oriented_face(bm, [grid[j][k], grid[j + 1][k], grid[j + 1][k + 1], grid[j][k + 1]], mat_idx, nrm_x)


def add_cylinder_z(bm, cx, cy, z0, z1, radius, segs, slots_z, mat_idx, cap_ends=True):
    zs = [z0 + (z1 - z0) * k / slots_z for k in range(slots_z + 1)]
    rings = []
    for z in zs:
        ring = []
        for s in range(segs):
            ang = 2.0 * math.pi * s / segs
            ring.append(bm.verts.new((cx + radius * math.cos(ang), cy + radius * math.sin(ang), z)))
        rings.append(ring)
    for k in range(slots_z):
        for s in range(segs):
            s_next = (s + 1) % segs
            v0 = rings[k][s]
            v1 = rings[k][s_next]
            v2 = rings[k + 1][s_next]
            v3 = rings[k + 1][s]
            ang_mid = 2.0 * math.pi * (s + 0.5) / segs
            out_dir = Vector((math.cos(ang_mid), math.sin(ang_mid), 0.0))
            add_oriented_face(bm, [v0, v1, v2, v3], mat_idx, out_dir)
    if cap_ends:
        c_bot = bm.verts.new((cx, cy, z0))
        c_top = bm.verts.new((cx, cy, z1))
        for s in range(segs):
            s_next = (s + 1) % segs
            add_oriented_face(bm, [c_bot, rings[0][s_next], rings[0][s]], mat_idx, Vector((0, 0, -1)))
            add_oriented_face(bm, [c_top, rings[-1][s], rings[-1][s_next]], mat_idx, Vector((0, 0, 1)))


def add_grid_sheet(bm, grid_coords, mat_idx, out_dir):
    ni = len(grid_coords) - 1
    nj = len(grid_coords[0]) - 1
    vgrid = [[bm.verts.new(grid_coords[i][j]) for j in range(nj + 1)] for i in range(ni + 1)]
    for i in range(ni):
        for j in range(nj):
            add_oriented_face(bm, [vgrid[i][j], vgrid[i + 1][j], vgrid[i + 1][j + 1], vgrid[i][j + 1]], mat_idx, out_dir)
    return vgrid


def add_thick_corrugated_panel_x(bm, x_profile, zs, y_sign, thickness, mat_outer, mat_inner):
    # x_profile is list of (x, y_outer)
    nx = len(x_profile) - 1
    nz = len(zs) - 1
    out_dir = Vector((0.0, float(y_sign), 0.0))
    in_dir = Vector((0.0, -float(y_sign), 0.0))

    outer_grid = [[bm.verts.new((x, y, z)) for z in zs] for (x, y) in x_profile]
    inner_grid = [[bm.verts.new((x, y - y_sign * thickness, z)) for z in zs] for (x, y) in x_profile]

    for i in range(nx):
        for k in range(nz):
            add_oriented_face(
                bm,
                [outer_grid[i][k], outer_grid[i + 1][k], outer_grid[i + 1][k + 1], outer_grid[i][k + 1]],
                mat_outer,
                out_dir,
            )
            add_oriented_face(
                bm,
                [inner_grid[i][k], inner_grid[i + 1][k], inner_grid[i + 1][k + 1], inner_grid[i][k + 1]],
                mat_inner,
                in_dir,
            )

    # Top and bottom closing strips
    for i in range(nx):
        add_oriented_face(
            bm,
            [outer_grid[i][0], inner_grid[i][0], inner_grid[i + 1][0], outer_grid[i + 1][0]],
            mat_outer,
            Vector((0, 0, -1)),
        )
        add_oriented_face(
            bm,
            [outer_grid[i][-1], outer_grid[i + 1][-1], inner_grid[i + 1][-1], inner_grid[i][-1]],
            mat_outer,
            Vector((0, 0, 1)),
        )


# ---------------------------------------------------------------------------
# 3. BUILD 20-FOOT ISO SHIPPING CONTAINER ("Container20")
# ---------------------------------------------------------------------------
# Dimensions:
# Length (X): 6.06 m -> [-3.03, +3.03]
# Width  (Y): 2.44 m -> [-1.22, +1.22] (FRONT faces -Y)
# Height (Z): 2.59 m -> [0.00, +2.59]  (Bottom at Z=0)

L_HALF = 3.03
W_HALF = 1.22
H_FULL = 2.59

# ISO 1161 Corner Casting dimensions: 178 mm (X) x 162 mm (Y) x 118 mm (Z)
CC_X = 0.178
CC_Y = 0.162
CC_Z = 0.118

bm = bmesh.new()

# --- 3A. 8 CORNER CASTINGS WITH TWIST-LOCK APERTURES ---
for sx in (-1, 1):
    for sy in (-1, 1):
        for sz in (0, 1):
            x0 = -L_HALF if sx < 0 else (L_HALF - CC_X)
            x1 = x0 + CC_X
            y0 = -W_HALF if sy < 0 else (W_HALF - CC_Y)
            y1 = y0 + CC_Y
            z0 = 0.0 if sz == 0 else (H_FULL - CC_Z)
            z1 = z0 + CC_Z

            c_faces = add_box(bm, x0, x1, y0, y1, z0, z1, MAT_DARK_STEEL)
            # Identify the 3 exterior faces of this corner casting for twist-lock holes
            ext_faces = []
            for f in c_faces:
                f.normal_update()
                if (sx < 0 and f.normal.x < -0.9) or (sx > 0 and f.normal.x > 0.9):
                    ext_faces.append(f)
                elif (sy < 0 and f.normal.y < -0.9) or (sy > 0 and f.normal.y > 0.9):
                    ext_faces.append(f)
                elif (sz == 0 and f.normal.z < -0.9) or (sz == 1 and f.normal.z > 0.9):
                    ext_faces.append(f)

            bmesh.ops.inset_individual(bm, faces=ext_faces, thickness=0.034, depth=0.0)
            res = bmesh.ops.extrude_discrete_faces(bm, faces=ext_faces)
            for ef in res["faces"]:
                ef.normal_update()
                bmesh.ops.translate(bm, verts=ef.verts, vec=-ef.normal * 0.028)
                ef.material_index = MAT_DARK_STEEL

# --- 3B. 4 VERTICAL CORNER POSTS ---
# Spanning Z from CC_Z (0.118) to H_FULL - CC_Z (2.472)
for sx in (-1, 1):
    for sy in (-1, 1):
        px0 = -L_HALF + 0.004 if sx < 0 else L_HALF - CC_X + 0.004
        px1 = px0 + CC_X - 0.008
        py0 = -W_HALF + 0.004 if sy < 0 else W_HALF - CC_Y + 0.004
        py1 = py0 + CC_Y - 0.008
        add_subdivided_box(bm, px0, px1, py0, py1, CC_Z, H_FULL - CC_Z, 1, 1, 6, MAT_BLUE)

        # Inner J-bar stiffening flange on corner posts
        jx0 = px1 if sx < 0 else px0 - 0.045
        jx1 = px1 + 0.045 if sx < 0 else px0
        jy0 = -W_HALF + 0.012 if sy < 0 else W_HALF - 0.065
        jy1 = -W_HALF + 0.065 if sy < 0 else W_HALF - 0.012
        add_subdivided_box(bm, jx0, jx1, jy0, jy1, CC_Z, H_FULL - CC_Z, 1, 1, 4, MAT_BLUE)

# --- 3C. BOTTOM SIDE RAILS WITH FORKLIFT POCKETS & TOP SIDE RAILS ---
X_PANEL_START = -L_HALF + CC_X
X_PANEL_END = L_HALF - CC_X

# Forklift pocket centers along X: +/- 1.025 m, width 0.36 m
fp_intervals = [
    (X_PANEL_START, -1.205, False),
    (-1.205, -0.845, True),
    (-0.845, 0.845, False),
    (0.845, 1.205, True),
    (1.205, X_PANEL_END, False),
]

for sy in (-1, 1):
    ry0 = -W_HALF + 0.006 if sy < 0 else W_HALF - 0.145
    ry1 = -W_HALF + 0.145 if sy < 0 else W_HALF - 0.006
    for xa, xb, is_pocket in fp_intervals:
        if not is_pocket:
            seg_nx = max(2, int((xb - xa) / 0.35))
            add_subdivided_box(bm, xa, xb, ry0, ry1, 0.018, 0.158, seg_nx, 1, 1, MAT_DARK_STEEL)
        else:
            # Top & bottom flange of forklift pocket + side reinforcing plates
            add_box(bm, xa, xb, ry0 - 0.004, ry1 + 0.004, 0.122, 0.162, MAT_DARK_STEEL)
            add_box(bm, xa, xb, ry0 - 0.004, ry1 + 0.004, 0.012, 0.034, MAT_DARK_STEEL)
            add_box(bm, xa - 0.025, xa + 0.02, ry0 - 0.004, ry1 + 0.004, 0.034, 0.122, MAT_DARK_STEEL)
            add_box(bm, xb - 0.02, xb + 0.025, ry0 - 0.004, ry1 + 0.004, 0.034, 0.122, MAT_DARK_STEEL)

    # Forklift tunnel tubes spanning full width between -Y and +Y rails (create once when sy == -1)
    if sy == -1:
        for px_a, px_b in ((-1.205, -0.845), (0.845, 1.205)):
            add_box(bm, px_a, px_b, -W_HALF + 0.145, W_HALF - 0.145, 0.122, 0.145, MAT_DARK_STEEL)
            add_box(bm, px_a, px_b, -W_HALF + 0.145, W_HALF - 0.145, 0.015, 0.032, MAT_DARK_STEEL)
            add_box(bm, px_a, px_a + 0.02, -W_HALF + 0.145, W_HALF - 0.145, 0.032, 0.122, MAT_DARK_STEEL)
            add_box(bm, px_b - 0.02, px_b, -W_HALF + 0.145, W_HALF - 0.145, 0.032, 0.122, MAT_DARK_STEEL)

    # Top Side Rails (60x60 mm RHS along X)
    ty0 = -W_HALF + 0.006 if sy < 0 else W_HALF - 0.072
    ty1 = -W_HALF + 0.072 if sy < 0 else W_HALF - 0.006
    add_subdivided_box(bm, X_PANEL_START, X_PANEL_END, ty0, ty1, H_FULL - 0.095, H_FULL - 0.004, 16, 1, 1, MAT_BLUE)

# --- 3D. END SILLS, HEADERS & UNDERFLOOR CROSS-MEMBERS ---
# Door End Sill (-X) and Header (-X)
add_subdivided_box(bm, -L_HALF + 0.005, -L_HALF + CC_X, -W_HALF + CC_Y, W_HALF - CC_Y, 0.015, 0.142, 1, 8, 1, MAT_DARK_STEEL)
add_subdivided_box(bm, -L_HALF + 0.005, -L_HALF + CC_X, -W_HALF + CC_Y, W_HALF - CC_Y, H_FULL - 0.118, H_FULL - 0.004, 1, 8, 1, MAT_BLUE)
# Rain drip lip above cargo doors at -X
add_subdivided_box(bm, -L_HALF - 0.016, -L_HALF + 0.005, -W_HALF + CC_Y + 0.05, W_HALF - CC_Y - 0.05, H_FULL - 0.032, H_FULL - 0.008, 1, 6, 1, MAT_BLUE)

# Rear End Sill (+X) and Header (+X)
add_subdivided_box(bm, L_HALF - CC_X, L_HALF - 0.005, -W_HALF + CC_Y, W_HALF - CC_Y, 0.015, 0.142, 1, 8, 1, MAT_DARK_STEEL)
add_subdivided_box(bm, L_HALF - CC_X, L_HALF - 0.005, -W_HALF + CC_Y, W_HALF - CC_Y, H_FULL - 0.118, H_FULL - 0.004, 1, 8, 1, MAT_BLUE)

# 14 Transverse Underfloor Cross-Members + Floor Deck
num_cross = 14
for i in range(num_cross):
    cx = X_PANEL_START + (X_PANEL_END - X_PANEL_START) * (i + 0.5) / num_cross
    if abs(abs(cx) - 1.025) > 0.24:
        add_box(bm, cx - 0.022, cx + 0.022, -W_HALF + 0.145, W_HALF - 0.145, 0.035, 0.142, MAT_DARK_STEEL)

# Floor underside / interior floor plate
add_subdivided_box(bm, X_PANEL_START, X_PANEL_END, -W_HALF + 0.14, W_HALF - 0.14, 0.142, 0.165, 10, 4, 1, MAT_DARK_STEEL)

# --- 3E. TRAPEZOIDAL CORRUGATED SIDE PANELS (-Y FRONT AND +Y BACK) ---
# 20 trapezoidal waves along X from X_PANEL_START (-2.852) to X_PANEL_END (+2.852)
N_WAVES = 20
PANEL_LEN = X_PANEL_END - X_PANEL_START  # 5.704 m
WAVE_LEN = PANEL_LEN / N_WAVES           # 0.2852 m
# Fractions within one trapezoidal period:
# 0.00 -> 0.26 : outer crest
# 0.26 -> 0.50 : angled web to valley
# 0.50 -> 0.76 : inner valley
# 0.76 -> 1.00 : angled web back to crest
Y_OUTER_MAG = W_HALF - 0.008             # 1.212 m
Y_INNER_MAG = W_HALF - 0.044             # 1.176 m (36 mm real corrugation depth)


def eval_side_corrugation_y(x_val, sy_sign):
    if x_val <= X_PANEL_START:
        return sy_sign * Y_OUTER_MAG
    if x_val >= X_PANEL_END:
        return sy_sign * Y_OUTER_MAG
    u = (x_val - X_PANEL_START) / WAVE_LEN
    frac = u - math.floor(u)
    if frac < 0.26:
        mag = Y_OUTER_MAG
    elif frac < 0.50:
        t = (frac - 0.26) / 0.24
        mag = Y_OUTER_MAG * (1.0 - t) + Y_INNER_MAG * t
    elif frac < 0.76:
        mag = Y_INNER_MAG
    else:
        t = (frac - 0.76) / 0.24
        mag = Y_INNER_MAG * (1.0 - t) + Y_OUTER_MAG * t
    return sy_sign * mag


zs_side = [0.158 + (H_FULL - 0.095 - 0.158) * k / 9 for k in range(10)]

for sy in (-1, 1):
    x_prof = []
    for w in range(N_WAVES):
        x_base = X_PANEL_START + w * WAVE_LEN
        x_prof.append((x_base, sy * Y_OUTER_MAG))
        x_prof.append((x_base + 0.26 * WAVE_LEN, sy * Y_OUTER_MAG))
        x_prof.append((x_base + 0.50 * WAVE_LEN, sy * Y_INNER_MAG))
        x_prof.append((x_base + 0.76 * WAVE_LEN, sy * Y_INNER_MAG))
    x_prof.append((X_PANEL_END, sy * Y_OUTER_MAG))

    add_thick_corrugated_panel_x(bm, x_prof, zs_side, sy, 0.012, MAT_BLUE, MAT_BLUE)

    # Ventilation louver boxes near top-left and top-right of each side wall
    for vx in (-2.56, 2.56):
        vy0 = sy * (Y_OUTER_MAG - 0.002)
        vy1 = sy * (Y_OUTER_MAG + 0.014)
        ymin_v, ymax_v = min(vy0, vy1), max(vy0, vy1)
        add_box(bm, vx - 0.09, vx + 0.09, ymin_v, ymax_v, 2.12, 2.38, MAT_BLUE)
        for lz in (2.16, 2.21, 2.26, 2.31):
            vy_louver = sy * (Y_OUTER_MAG + 0.018)
            add_box(bm, vx - 0.07, vx + 0.07, min(vy1, vy_louver), max(vy1, vy_louver), lz, lz + 0.018, MAT_DARK_STEEL)

# --- 3F. TRAPEZOIDAL CORRUGATED ROOF PANEL ---
# Roof spans X_PANEL_START to X_PANEL_END, Y from -(W_HALF - 0.072) to +(W_HALF - 0.072)
ROOF_Y_MAX = W_HALF - 0.072
ys_roof = [-ROOF_Y_MAX + 2.0 * ROOF_Y_MAX * j / 6 for j in range(7)]
x_roof_prof = []
for w in range(N_WAVES):
    x_base = X_PANEL_START + w * WAVE_LEN
    x_roof_prof.append((x_base, H_FULL - 0.004))
    x_roof_prof.append((x_base + 0.26 * WAVE_LEN, H_FULL - 0.004))
    x_roof_prof.append((x_base + 0.50 * WAVE_LEN, H_FULL - 0.024))
    x_roof_prof.append((x_base + 0.76 * WAVE_LEN, H_FULL - 0.024))
x_roof_prof.append((X_PANEL_END, H_FULL - 0.004))

roof_grid_top = []
roof_grid_bot = []
for x_val, z_wave in x_roof_prof:
    row_top = []
    row_bot = []
    for j, y_val in enumerate(ys_roof):
        # Die-stamped flat border where roof meets top side rails
        z_actual = (H_FULL - 0.016) if (j == 0 or j == len(ys_roof) - 1) else z_wave
        row_top.append((x_val, y_val, z_actual))
        row_bot.append((x_val, y_val, z_actual - 0.010))
    roof_grid_top.append(row_top)
    roof_grid_bot.append(row_bot)

add_grid_sheet(bm, roof_grid_top, MAT_BLUE, Vector((0, 0, 1)))
add_grid_sheet(bm, roof_grid_bot, MAT_BLUE, Vector((0, 0, -1)))

# --- 3G. CORRUGATED REAR END WALL (+X) ---
REAR_Y_MIN = -W_HALF + CC_Y
REAR_Y_MAX = W_HALF - CC_Y
REAR_WAVES = 7
REAR_WAVE_W = (REAR_Y_MAX - REAR_Y_MIN) / REAR_WAVES
y_rear_prof = []
for w in range(REAR_WAVES):
    yb = REAR_Y_MIN + w * REAR_WAVE_W
    y_rear_prof.append((yb, L_HALF - 0.022))
    y_rear_prof.append((yb + 0.25 * REAR_WAVE_W, L_HALF - 0.022))
    y_rear_prof.append((yb + 0.50 * REAR_WAVE_W, L_HALF - 0.062))
    y_rear_prof.append((yb + 0.75 * REAR_WAVE_W, L_HALF - 0.062))
y_rear_prof.append((REAR_Y_MAX, L_HALF - 0.022))

zs_rear = [0.142 + (H_FULL - 0.118 - 0.142) * k / 7 for k in range(8)]
rear_out = [[(x_val, y_val, z_val) for z_val in zs_rear] for (y_val, x_val) in y_rear_prof]
rear_in = [[(x_val - 0.012, y_val, z_val) for z_val in zs_rear] for (y_val, x_val) in y_rear_prof]
add_grid_sheet(bm, rear_out, MAT_BLUE, Vector((1, 0, 0)))
add_grid_sheet(bm, rear_in, MAT_BLUE, Vector((-1, 0, 0)))

# --- 3H. DOUBLE CARGO DOORS ON -X END ---
# Door opening Y: [-1.058, +1.058], Z: [0.142, 2.472]
DOOR_X_OUT = -L_HALF + 0.038
DOOR_X_IN = -L_HALF + 0.068
DOOR_Z_MIN = 0.148
DOOR_Z_MAX = H_FULL - 0.124

for door_side in (-1, 1):
    dy0 = -1.052 if door_side < 0 else 0.008
    dy1 = -0.008 if door_side < 0 else 1.052

    # Perimeter rubber EPDM gasket around door leaf
    g_thick = 0.018
    # Outer vertical gasket, center vertical gasket, bottom gasket, top gasket
    add_box(bm, DOOR_X_OUT - 0.008, DOOR_X_OUT + 0.012, dy0 - 0.008, dy0 + g_thick, DOOR_Z_MIN - 0.006, DOOR_Z_MAX + 0.006, MAT_RUBBER)
    add_box(bm, DOOR_X_OUT - 0.008, DOOR_X_OUT + 0.012, dy1 - g_thick, dy1 + 0.008, DOOR_Z_MIN - 0.006, DOOR_Z_MAX + 0.006, MAT_RUBBER)
    add_box(bm, DOOR_X_OUT - 0.008, DOOR_X_OUT + 0.012, dy0, dy1, DOOR_Z_MIN - 0.006, DOOR_Z_MIN + g_thick, MAT_RUBBER)
    add_box(bm, DOOR_X_OUT - 0.008, DOOR_X_OUT + 0.012, dy0, dy1, DOOR_Z_MAX - g_thick, DOOR_Z_MAX + 0.006, MAT_RUBBER)

    # Steel perimeter door stile & rail frame
    frame_w = 0.065
    add_subdivided_box(bm, DOOR_X_OUT, DOOR_X_IN, dy0 + 0.01, dy0 + frame_w, DOOR_Z_MIN + 0.01, DOOR_Z_MAX - 0.01, 1, 1, 6, MAT_BLUE)
    add_subdivided_box(bm, DOOR_X_OUT, DOOR_X_IN, dy1 - frame_w, dy1 - 0.01, DOOR_Z_MIN + 0.01, DOOR_Z_MAX - 0.01, 1, 1, 6, MAT_BLUE)
    add_subdivided_box(bm, DOOR_X_OUT, DOOR_X_IN, dy0 + frame_w, dy1 - frame_w, DOOR_Z_MIN + 0.01, DOOR_Z_MIN + 0.12, 1, 4, 1, MAT_BLUE)
    add_subdivided_box(bm, DOOR_X_OUT, DOOR_X_IN, dy0 + frame_w, dy1 - frame_w, DOOR_Z_MAX - 0.12, DOOR_Z_MAX - 0.01, 1, 4, 1, MAT_BLUE)

    # Corrugated central door panel (5 pressed horizontal trapezoidal ribs, flat upper section for stencil markings)
    pz0 = DOOR_Z_MIN + 0.12
    pz1 = DOOR_Z_MAX - 0.12
    z_door_prof = [(pz0, DOOR_X_OUT)]
    rib_zone_h = (pz1 - pz0) * 0.72
    n_ribs = 5
    rib_h = rib_zone_h / n_ribs
    for r in range(n_ribs):
        zb = pz0 + r * rib_h
        z_door_prof.append((zb + 0.18 * rib_h, DOOR_X_OUT))
        z_door_prof.append((zb + 0.36 * rib_h, DOOR_X_IN - 0.004))
        z_door_prof.append((zb + 0.68 * rib_h, DOOR_X_IN - 0.004))
        z_door_prof.append((zb + 0.86 * rib_h, DOOR_X_OUT))
    # Upper flat section for owner codes / decals
    z_door_prof.append((pz0 + rib_zone_h + 0.08, DOOR_X_OUT))
    z_door_prof.append((pz1 - 0.08, DOOR_X_OUT))
    z_door_prof.append((pz1, DOOR_X_OUT))

    ys_door_panel = [dy0 + frame_w + (dy1 - dy0 - 2.0 * frame_w) * j / 5 for j in range(6)]
    door_grid_out = [[(x_p, y_p, z_p) for z_p, x_p in z_door_prof] for y_p in ys_door_panel]
    door_grid_in = [[(x_p + 0.010, y_p, z_p) for z_p, x_p in z_door_prof] for y_p in ys_door_panel]
    add_grid_sheet(bm, door_grid_out, MAT_BLUE, Vector((-1, 0, 0)))
    add_grid_sheet(bm, door_grid_in, MAT_BLUE, Vector((1, 0, 0)))

# Center overlapping astragal weather strip between left and right doors
add_subdivided_box(bm, DOOR_X_OUT - 0.012, DOOR_X_OUT + 0.002, -0.022, 0.022, DOOR_Z_MIN, DOOR_Z_MAX, 1, 1, 8, MAT_BLUE)

# --- 3I. 8 HEAVY-DUTY DOOR HINGES (4 PER DOOR) ---
hinge_zs = [0.34, 0.96, 1.66, 2.28]
for sy in (-1, 1):
    hy_pin = sy * (W_HALF - CC_Y + 0.016)
    hx_pin = -L_HALF + 0.018
    for hz in hinge_zs:
        # Upper & lower hinge cheek lugs welded to corner post
        add_box(bm, hx_pin - 0.012, -L_HALF + 0.048, hy_pin - 0.022, hy_pin + 0.022, hz - 0.062, hz - 0.036, MAT_DARK_STEEL)
        add_box(bm, hx_pin - 0.012, -L_HALF + 0.048, hy_pin - 0.022, hy_pin + 0.022, hz + 0.036, hz + 0.062, MAT_DARK_STEEL)
        # Hinge pin cylinder
        add_cylinder_z(bm, hx_pin, hy_pin, hz - 0.068, hz + 0.068, 0.013, 8, 2, MAT_GALV, cap_ends=True)
        # Hinge blade strap extending onto door frame
        by0 = hy_pin if sy < 0 else hy_pin - 0.165
        by1 = hy_pin + 0.165 if sy < 0 else hy_pin
        add_box(bm, DOOR_X_OUT - 0.016, DOOR_X_OUT + 0.002, by0, by1, hz - 0.034, hz + 0.034, MAT_GALV)
        # 3 bolt heads on each hinge strap
        for b_idx in range(3):
            by_bolt = hy_pin - sy * (0.045 + b_idx * 0.048)
            add_box(bm, DOOR_X_OUT - 0.023, DOOR_X_OUT - 0.016, by_bolt - 0.009, by_bolt + 0.009, hz - 0.009, hz + 0.009, MAT_GALV)

# --- 3J. 4 VERTICAL LOCKING BARS, CAMS, KEEPERS, BRACKETS & HANDLES ---
locking_bar_ys = [-0.74, -0.26, 0.26, 0.74]
BAR_X = -L_HALF + 0.006
BAR_Z_MIN = 0.115
BAR_Z_MAX = H_FULL - 0.095
bracket_zs = [0.46, 0.88, 1.68, 2.14]

for idx_bar, by in enumerate(locking_bar_ys):
    # Main cylindrical locking rod
    add_cylinder_z(bm, BAR_X, by, BAR_Z_MIN, BAR_Z_MAX, 0.017, 10, 8, MAT_GALV, cap_ends=True)

    # Top and bottom locking cams & cam retainer keepers on sill/header
    for cam_z, keeper_z0, keeper_z1 in (
        (BAR_Z_MIN + 0.015, 0.075, 0.145),
        (BAR_Z_MAX - 0.015, H_FULL - 0.120, H_FULL - 0.050),
    ):
        # Cam lug on rod
        add_box(bm, BAR_X - 0.022, BAR_X + 0.028, by - 0.026, by + 0.026, cam_z - 0.025, cam_z + 0.025, MAT_GALV)
        # Cam keeper block welded to sill/header
        add_box(bm, BAR_X - 0.030, -L_HALF + 0.042, by - 0.042, by - 0.018, keeper_z0, keeper_z1, MAT_DARK_STEEL)
        add_box(bm, BAR_X - 0.030, -L_HALF + 0.042, by + 0.018, by + 0.042, keeper_z0, keeper_z1, MAT_DARK_STEEL)

    # 4 Guide bearing brackets along each locking rod
    for bz in bracket_zs:
        # Saddle wrapping around rod
        add_box(bm, BAR_X - 0.024, DOOR_X_OUT + 0.002, by - 0.024, by + 0.024, bz - 0.026, bz + 0.026, MAT_GALV)
        # Mounting flanges bolted to door
        add_box(bm, DOOR_X_OUT - 0.010, DOOR_X_OUT + 0.002, by - 0.056, by + 0.056, bz - 0.024, bz + 0.024, MAT_GALV)
        for s_bolt in (-1, 1):
            add_box(bm, DOOR_X_OUT - 0.017, DOOR_X_OUT - 0.010, by + s_bolt * 0.038 - 0.008, by + s_bolt * 0.038 + 0.008, bz - 0.008, bz + 0.008, MAT_GALV)

    # Forged Locking Handle at Z = 1.08 m
    hz_handle = 1.08
    h_dir = 1 if by < 0 else -1  # Left doors swing handle toward center, right doors toward center
    # Hinge hub welded to locking rod
    add_box(bm, BAR_X - 0.032, BAR_X + 0.012, by - 0.024, by + 0.024, hz_handle - 0.032, hz_handle + 0.032, MAT_GALV)
    # Forged lever arm + grip extending horizontally by 0.22 m
    hy_end = by + h_dir * 0.22
    hy_min, hy_max = min(by, hy_end), max(by, hy_end)
    add_subdivided_box(bm, BAR_X - 0.036, BAR_X - 0.022, hy_min, hy_max, hz_handle - 0.016, hz_handle + 0.016, 1, 3, 1, MAT_GALV)
    # Cylindrical handle grip at tip
    hy_grip_end = hy_end + h_dir * 0.08
    add_box(bm, BAR_X - 0.040, BAR_X - 0.018, min(hy_end, hy_grip_end), max(hy_end, hy_grip_end), hz_handle - 0.020, hz_handle + 0.020, MAT_GALV)
    # Retainer catch plate & rotating security latch on door behind handle tip
    add_box(bm, BAR_X - 0.022, DOOR_X_OUT + 0.002, hy_end - 0.030, hy_end + 0.030, hz_handle - 0.042, hz_handle + 0.042, MAT_GALV)
    add_box(bm, BAR_X - 0.044, BAR_X - 0.022, hy_end - 0.018, hy_end + 0.018, hz_handle + 0.016, hz_handle + 0.052, MAT_GALV)

# --- 3K. CSC SAFETY APPROVAL PLATE (ON LEFT CARGO DOOR) ---
csc_y0, csc_y1 = -0.64, -0.38
csc_z0, csc_z1 = 0.68, 0.86
csc_x = DOOR_X_OUT - 0.006
add_subdivided_box(bm, csc_x - 0.005, DOOR_X_OUT + 0.002, csc_y0, csc_y1, csc_z0, csc_z1, 1, 3, 3, MAT_CSC)
# Raised embossed data sub-plates and 4 corner rivets
add_box(bm, csc_x - 0.008, csc_x - 0.005, csc_y0 + 0.018, csc_y1 - 0.018, csc_z1 - 0.045, csc_z1 - 0.015, MAT_CSC)
add_box(bm, csc_x - 0.008, csc_x - 0.005, csc_y0 + 0.018, csc_y1 - 0.018, csc_z0 + 0.018, csc_z1 - 0.055, MAT_CSC)
for ry in (csc_y0 + 0.010, csc_y1 - 0.010):
    for rz in (csc_z0 + 0.010, csc_z1 - 0.010):
        add_box(bm, csc_x - 0.011, csc_x - 0.005, ry - 0.005, ry + 0.005, rz - 0.005, rz + 0.005, MAT_GALV)

# --- 3L. WHITE OWNER CODE "RAVU 204518 2" & "22G1" STENCIL MARKINGS ---
FONT_5X7 = {
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "2": ["01110", "10001", "00001", "00110", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}


def add_stencil_text_side(bm, text, x_start, z_top, char_w, char_h, char_gap, sy_sign, mat_idx):
    # Places conformal 3D stencil quads along the corrugated Y side wall
    cw = char_w / 5.0
    ch = char_h / 7.0
    out_dir = Vector((0.0, float(sy_sign), 0.0))
    offset_y = sy_sign * 0.0025

    for idx_c, ch_char in enumerate(text):
        rows = FONT_5X7.get(ch_char, FONT_5X7[" "])
        cx0 = x_start + idx_c * (char_w + char_gap)
        for r_idx, row_str in enumerate(rows):
            z1 = z_top - r_idx * ch
            z0 = z1 - ch
            col = 0
            while col < 5:
                if row_str[col] == "1":
                    col_end = col + 1
                    while col_end < 5 and row_str[col_end] == "1":
                        col_end += 1
                    xa = cx0 + col * cw
                    xb = cx0 + col_end * cw
                    ya = eval_side_corrugation_y(xa, sy_sign) + offset_y
                    yb = eval_side_corrugation_y(xb, sy_sign) + offset_y
                    v0 = bm.verts.new((xa, ya, z0))
                    v1 = bm.verts.new((xb, yb, z0))
                    v2 = bm.verts.new((xb, yb, z1))
                    v3 = bm.verts.new((xa, ya, z1))
                    add_oriented_face(bm, [v0, v1, v2, v3], mat_idx, out_dir)
                    col = col_end
                else:
                    col += 1


def add_stencil_text_door(bm, text, y_start, z_top, char_w, char_h, char_gap, x_plane, mat_idx):
    cw = char_w / 5.0
    ch = char_h / 7.0
    out_dir = Vector((-1.0, 0.0, 0.0))
    for idx_c, ch_char in enumerate(text):
        rows = FONT_5X7.get(ch_char, FONT_5X7[" "])
        cy0 = y_start + idx_c * (char_w + char_gap)
        for r_idx, row_str in enumerate(rows):
            z1 = z_top - r_idx * ch
            z0 = z1 - ch
            col = 0
            while col < 5:
                if row_str[col] == "1":
                    col_end = col + 1
                    while col_end < 5 and row_str[col_end] == "1":
                        col_end += 1
                    ya = cy0 + col * cw
                    yb = cy0 + col_end * cw
                    v0 = bm.verts.new((x_plane, ya, z0))
                    v1 = bm.verts.new((x_plane, yb, z0))
                    v2 = bm.verts.new((x_plane, yb, z1))
                    v3 = bm.verts.new((x_plane, ya, z1))
                    add_oriented_face(bm, [v0, v1, v2, v3], mat_idx, out_dir)
                    col = col_end
                else:
                    col += 1


# Owner code "RAVU 204518 2" and ISO type "22G1" on Front (-Y) side wall
add_stencil_text_side(bm, "RAVU 204518 2", 0.95, 2.28, 0.088, 0.135, 0.024, -1, MAT_WHITE)
add_stencil_text_side(bm, "22G1", 1.52, 2.08, 0.075, 0.105, 0.022, -1, MAT_WHITE)

# Owner code "RAVU 204518 2" and ISO type "22G1" on Back (+Y) side wall
add_stencil_text_side(bm, "RAVU 204518 2", -2.35, 2.28, 0.088, 0.135, 0.024, 1, MAT_WHITE)
add_stencil_text_side(bm, "22G1", -1.78, 2.08, 0.075, 0.105, 0.022, 1, MAT_WHITE)

# Owner code "RAVU 204518 2" and "22G1" on Right Cargo Door (-X end)
add_stencil_text_door(bm, "RAVU 204518 2", 0.09, 2.25, 0.052, 0.095, 0.015, DOOR_X_OUT - 0.003, MAT_WHITE)
add_stencil_text_door(bm, "22G1", 0.34, 2.11, 0.048, 0.080, 0.015, DOOR_X_OUT - 0.003, MAT_WHITE)
# Check digit box frame around the "2" on side and door
add_box(bm, 2.27, 2.41, -Y_OUTER_MAG - 0.004, -Y_OUTER_MAG - 0.001, 2.13, 2.14, MAT_WHITE)
add_box(bm, 2.27, 2.41, -Y_OUTER_MAG - 0.004, -Y_OUTER_MAG - 0.001, 2.29, 2.30, MAT_WHITE)

# Finalize BMesh into Mesh Object "Container20"
mesh = bpy.data.meshes.new("Container20")
bm.to_mesh(mesh)
bm.free()

container_obj = bpy.data.objects.new("Container20", mesh)
scene.collection.objects.link(container_obj)
bpy.context.view_layer.objects.active = container_obj
container_obj.select_set(True)

# ---------------------------------------------------------------------------
# 4. PROCEDURAL MATERIALS WITH WEAR (RUST STREAKS, SCRATCHES, GROUND DIRT)
# ---------------------------------------------------------------------------
def mix_rgba(nt, fac, col1, col2, blend_type='MIX'):
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = 'RGBA'
    m.blend_type = blend_type
    m.clamp_factor = True
    val_in = [s for s in m.inputs if s.type == 'VALUE'][0]
    rgba_ins = [s for s in m.inputs if s.type == 'RGBA']
    rgba_out = [s for s in m.outputs if s.type == 'RGBA'][0]

    if isinstance(fac, (int, float)):
        val_in.default_value = float(fac)
    else:
        nt.links.new(fac, val_in)

    if isinstance(col1, tuple):
        rgba_ins[0].default_value = col1
    else:
        nt.links.new(col1, rgba_ins[0])

    if isinstance(col2, tuple):
        rgba_ins[1].default_value = col2
    else:
        nt.links.new(col2, rgba_ins[1])

    return rgba_out


def add_math(nt, op, a, b, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    if isinstance(a, (int, float)):
        n.inputs[0].default_value = float(a)
    else:
        nt.links.new(a, n.inputs[0])
    if isinstance(b, (int, float)):
        n.inputs[1].default_value = float(b)
    else:
        nt.links.new(b, n.inputs[1])
    return n.outputs[0]


def add_ramp(nt, fac_socket, stops):
    r = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(fac_socket, r.inputs["Fac"])
    cr = r.color_ramp
    cr.elements[0].position = stops[0][0]
    cr.elements[0].color = stops[0][1]
    cr.elements[1].position = stops[1][0]
    cr.elements[1].color = stops[1][1]
    for pos, col in stops[2:]:
        el = cr.elements.new(pos)
        el.color = col
    return r.outputs["Color"]


def build_weathered_material(name, base_col_a, base_col_b, rust_amount, dirt_amount, scratch_amount, bump_strength, roughness_val):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out_node = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    # Note: Keep Metallic at 0.0 during DIFFUSE (COLOR) bake so all base colors bake cleanly without turning black
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = roughness_val
    nt.links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])

    tex_coord = nt.nodes.new("ShaderNodeTexCoord")
    sep_xyz = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tex_coord.outputs["Object"], sep_xyz.inputs["Vector"])

    # 1. Base paint blotchiness / sun fading
    noise_base = nt.nodes.new("ShaderNodeTexNoise")
    noise_base.inputs["Scale"].default_value = 2.8
    noise_base.inputs["Detail"].default_value = 5.0
    noise_base.inputs["Roughness"].default_value = 0.6
    nt.links.new(tex_coord.outputs["Object"], noise_base.inputs["Vector"])
    base_mix = mix_rgba(nt, noise_base.outputs["Fac"], base_col_a, base_col_b)

    # 2. Rust streaks from corners, top/bottom rails and panel seams
    map_streak = nt.nodes.new("ShaderNodeMapping")
    map_streak.inputs["Scale"].default_value = (10.0, 10.0, 1.4)
    nt.links.new(tex_coord.outputs["Object"], map_streak.inputs["Vector"])

    noise_rust = nt.nodes.new("ShaderNodeTexNoise")
    noise_rust.inputs["Scale"].default_value = 4.2
    noise_rust.inputs["Detail"].default_value = 8.0
    noise_rust.inputs["Roughness"].default_value = 0.65
    noise_rust.inputs["Distortion"].default_value = 0.35
    nt.links.new(map_streak.outputs["Vector"], noise_rust.inputs["Vector"])

    # Proximity to top rail (Z near 2.59) and bottom sill (Z near 0.0)
    z_norm = add_math(nt, 'DIVIDE', sep_xyz.outputs["Z"], 2.59, clamp=True)
    top_prox = add_math(nt, 'SUBTRACT', z_norm, 0.65, clamp=True)
    top_prox = add_math(nt, 'MULTIPLY', top_prox, 2.6, clamp=True)
    bot_prox = add_math(nt, 'SUBTRACT', 0.28, z_norm, clamp=True)
    bot_prox = add_math(nt, 'MULTIPLY', bot_prox, 3.2, clamp=True)
    z_edge = add_math(nt, 'MAXIMUM', top_prox, bot_prox, clamp=True)

    # Proximity to X ends (corners at |X| -> 3.03)
    abs_x = nt.nodes.new("ShaderNodeMath")
    abs_x.operation = 'ABSOLUTE'
    nt.links.new(sep_xyz.outputs["X"], abs_x.inputs[0])
    x_prox = add_math(nt, 'SUBTRACT', abs_x.outputs[0], 2.35, clamp=True)
    x_prox = add_math(nt, 'MULTIPLY', x_prox, 1.5, clamp=True)

    edge_bias = add_math(nt, 'MAXIMUM', z_edge, x_prox, clamp=True)
    edge_bias = add_math(nt, 'ADD', edge_bias, 0.25, clamp=True)

    rust_raw = add_math(nt, 'MULTIPLY', noise_rust.outputs["Fac"], edge_bias, clamp=True)
    rust_raw = add_math(nt, 'MULTIPLY', rust_raw, rust_amount, clamp=True)
    rust_mask = add_ramp(nt, rust_raw, [
        (0.32, (0.0, 0.0, 0.0, 1.0)),
        (0.58, (1.0, 1.0, 1.0, 1.0)),
    ])
    rust_col = mix_rgba(
        nt,
        noise_rust.outputs["Fac"],
        (0.14, 0.045, 0.018, 1.0),
        (0.34, 0.11, 0.032, 1.0),
    )
    after_rust = mix_rgba(nt, rust_mask, base_mix, rust_col)

    # 3. Scratches (stretched high-frequency noise)
    map_scratch = nt.nodes.new("ShaderNodeMapping")
    map_scratch.inputs["Scale"].default_value = (3.5, 16.0, 14.0)
    nt.links.new(tex_coord.outputs["Object"], map_scratch.inputs["Vector"])

    noise_scr = nt.nodes.new("ShaderNodeTexNoise")
    noise_scr.inputs["Scale"].default_value = 18.0
    noise_scr.inputs["Detail"].default_value = 10.0
    noise_scr.inputs["Roughness"].default_value = 0.75
    nt.links.new(map_scratch.outputs["Vector"], noise_scr.inputs["Vector"])

    scr_scaled = add_math(nt, 'MULTIPLY', noise_scr.outputs["Fac"], scratch_amount, clamp=True)
    scr_mask = add_ramp(nt, scr_scaled, [
        (0.62, (0.0, 0.0, 0.0, 1.0)),
        (0.74, (1.0, 1.0, 1.0, 1.0)),
    ])
    after_scratch = mix_rgba(nt, scr_mask, after_rust, (0.36, 0.38, 0.40, 1.0))

    # 4. Dirt and dust near the ground (Z gradient + noise)
    noise_dirt = nt.nodes.new("ShaderNodeTexNoise")
    noise_dirt.inputs["Scale"].default_value = 5.5
    noise_dirt.inputs["Detail"].default_value = 6.0
    nt.links.new(tex_coord.outputs["Object"], noise_dirt.inputs["Vector"])

    ground_grad = add_math(nt, 'SUBTRACT', 0.42, z_norm, clamp=True)
    ground_grad = add_math(nt, 'MULTIPLY', ground_grad, 2.5, clamp=True)
    dirt_combined = add_math(nt, 'MULTIPLY', ground_grad, noise_dirt.outputs["Fac"], clamp=True)
    dirt_combined = add_math(nt, 'ADD', dirt_combined, add_math(nt, 'MULTIPLY', ground_grad, 0.45, clamp=True), clamp=True)
    dirt_combined = add_math(nt, 'MULTIPLY', dirt_combined, dirt_amount, clamp=True)

    dirt_col = mix_rgba(
        nt,
        noise_dirt.outputs["Fac"],
        (0.16, 0.13, 0.095, 1.0),
        (0.28, 0.24, 0.18, 1.0),
    )
    final_col = mix_rgba(nt, dirt_combined, after_scratch, dirt_col)
    nt.links.new(final_col, bsdf.inputs["Base Color"])

    # 5. Procedural Bump (scratches + rust pitting + surface grain) -> Normal
    bump_mix = add_math(nt, 'ADD', add_math(nt, 'MULTIPLY', rust_mask, 0.6), add_math(nt, 'MULTIPLY', scr_mask, 0.4), clamp=True)
    bump_height = add_math(nt, 'ADD', bump_mix, add_math(nt, 'MULTIPLY', noise_base.outputs["Fac"], 0.25))
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = bump_strength
    bump.inputs["Distance"].default_value = 0.005
    nt.links.new(bump_height, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


# Create the 6 surface materials
# 0: Faded RAL 5010 Gentian Blue container paint
mat_blue = build_weathered_material(
    "BluePaint_Mat",
    (0.018, 0.105, 0.285, 1.0),
    (0.042, 0.175, 0.395, 1.0),
    rust_amount=1.05,
    dirt_amount=1.0,
    scratch_amount=0.95,
    bump_strength=0.45,
    roughness_val=0.58,
)
# 1: Dark weathered steel / corner castings / sills / cross-members
mat_dark_steel = build_weathered_material(
    "DarkSteel_Mat",
    (0.015, 0.075, 0.195, 1.0),
    (0.11, 0.07, 0.055, 1.0),
    rust_amount=1.35,
    dirt_amount=1.25,
    scratch_amount=1.05,
    bump_strength=0.60,
    roughness_val=0.68,
)
# 2: Galvanized steel locking bars, hinges, handles
mat_galv = build_weathered_material(
    "GalvSteel_Mat",
    (0.38, 0.40, 0.42, 1.0),
    (0.52, 0.54, 0.56, 1.0),
    rust_amount=0.70,
    dirt_amount=0.80,
    scratch_amount=1.10,
    bump_strength=0.35,
    roughness_val=0.45,
)
# 3: Black EPDM rubber door gaskets
mat_rubber = build_weathered_material(
    "RubberSeal_Mat",
    (0.025, 0.026, 0.028, 1.0),
    (0.055, 0.055, 0.060, 1.0),
    rust_amount=0.15,
    dirt_amount=0.90,
    scratch_amount=0.30,
    bump_strength=0.25,
    roughness_val=0.78,
)
# 4: CSC stainless data plate
mat_csc = build_weathered_material(
    "CSCPlate_Mat",
    (0.44, 0.45, 0.43, 1.0),
    (0.22, 0.23, 0.24, 1.0),
    rust_amount=0.35,
    dirt_amount=0.60,
    scratch_amount=0.85,
    bump_strength=0.40,
    roughness_val=0.48,
)
# 5: White stencil markings ("RAVU 204518 2")
mat_white = build_weathered_material(
    "DecalWhite_Mat",
    (0.78, 0.80, 0.77, 1.0),
    (0.88, 0.89, 0.86, 1.0),
    rust_amount=0.55,
    dirt_amount=0.70,
    scratch_amount=0.80,
    bump_strength=0.30,
    roughness_val=0.55,
)

for m in (mat_blue, mat_dark_steel, mat_galv, mat_rubber, mat_csc, mat_white):
    container_obj.data.materials.append(m)

# ---------------------------------------------------------------------------
# 5. UV UNWRAP
# ---------------------------------------------------------------------------
bpy.ops.object.select_all(action='DESELECT')
container_obj.select_set(True)
bpy.context.view_layer.objects.active = container_obj

if not container_obj.data.uv_layers:
    container_obj.data.uv_layers.new(name="UVMap")

bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.01)
bpy.ops.uv.average_islands_scale()
bpy.ops.uv.pack_islands(margin=0.01)
bpy.ops.object.mode_set(mode='OBJECT')

# ---------------------------------------------------------------------------
# 6. BAKE ALBEDO & NORMAL MAPS (2048x2048, CYCLES CPU, 16 SAMPLES)
# ---------------------------------------------------------------------------
img_albedo = bpy.data.images.new("Container20_albedo", width=2048, height=2048, alpha=False)
img_normal = bpy.data.images.new("Container20_normal", width=2048, height=2048, alpha=False)
img_normal.colorspace_settings.name = 'Non-Color'


def activate_bake_image_in_all_materials(obj, target_img):
    for mat in obj.data.materials:
        nt = mat.node_tree
        tex_node = nt.nodes.get("BakeTargetNode")
        if tex_node is None:
            tex_node = nt.nodes.new("ShaderNodeTexImage")
            tex_node.name = "BakeTargetNode"
        tex_node.image = target_img
        for n in nt.nodes:
            n.select = False
        tex_node.select = True
        nt.nodes.active = tex_node


scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 16
scene.render.bake.margin = 8
scene.render.bake.use_selected_to_active = False

# Bake 1: DIFFUSE (COLOR) -> Container20_albedo
activate_bake_image_in_all_materials(container_obj, img_albedo)
scene.render.bake.use_pass_direct = False
scene.render.bake.use_pass_indirect = False
scene.render.bake.use_pass_color = True
bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=8)

img_albedo.filepath_raw = albedo_path
img_albedo.file_format = 'PNG'
img_albedo.save()

# Bake 2: NORMAL (TANGENT) -> Container20_normal
activate_bake_image_in_all_materials(container_obj, img_normal)
scene.render.bake.normal_space = 'TANGENT'
bpy.ops.object.bake(type='NORMAL', margin=8, normal_space='TANGENT')

img_normal.filepath_raw = normal_path
img_normal.file_format = 'PNG'
img_normal.save()

# ---------------------------------------------------------------------------
# 7. REPLACE ALL SLOTS WITH ONE MATERIAL "Container20_Mat"
# ---------------------------------------------------------------------------
final_mat = bpy.data.materials.new(name="Container20_Mat")
final_mat.use_nodes = True
fnt = final_mat.node_tree
fnt.nodes.clear()

f_out = fnt.nodes.new("ShaderNodeOutputMaterial")
f_bsdf = fnt.nodes.new("ShaderNodeBsdfPrincipled")
f_bsdf.inputs["Roughness"].default_value = 0.6

f_tex_albedo = fnt.nodes.new("ShaderNodeTexImage")
f_tex_albedo.image = img_albedo

f_tex_normal = fnt.nodes.new("ShaderNodeTexImage")
f_tex_normal.image = img_normal
img_normal.colorspace_settings.name = 'Non-Color'

f_norm_map = fnt.nodes.new("ShaderNodeNormalMap")
f_norm_map.space = 'TANGENT'

fnt.links.new(f_tex_albedo.outputs["Color"], f_bsdf.inputs["Base Color"])
fnt.links.new(f_tex_normal.outputs["Color"], f_norm_map.inputs["Color"])
fnt.links.new(f_norm_map.outputs["Normal"], f_bsdf.inputs["Normal"])
fnt.links.new(f_bsdf.outputs["BSDF"], f_out.inputs["Surface"])

container_obj.data.materials.clear()
container_obj.data.materials.append(final_mat)
for poly in container_obj.data.polygons:
    poly.material_index = 0

# ---------------------------------------------------------------------------
# 8. EXPORT FBX
# ---------------------------------------------------------------------------
bpy.ops.object.select_all(action='DESELECT')
container_obj.select_set(True)
bpy.context.view_layer.objects.active = container_obj
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bpy.ops.export_scene.fbx(
    filepath=fbx_path,
    use_selection=True,
    apply_scale_options='FBX_SCALE_ALL',
    bake_space_transform=True,
    axis_forward='-Z',
    axis_up='Y',
    path_mode='COPY',
    embed_textures=True,
)

# ---------------------------------------------------------------------------
# 9. RENDER PREVIEW PNG (900x900, EEVEE, WORLD, SUN, 1.7m 3/4 CAMERA)
# ---------------------------------------------------------------------------
engine_keys = list(scene.render.bl_rna.properties['engine'].enum_items.keys())
for ek in engine_keys:
    if 'EEVEE' in ek:
        scene.render.engine = ek
        break

# Grey sky world strength 0.6
world = bpy.data.worlds.new("PreviewWorld")
scene.world = world
world.use_nodes = True
w_nt = world.node_tree
bg_node = w_nt.nodes.get("Background")
if bg_node is None:
    bg_node = w_nt.nodes.new("ShaderNodeBackground")
bg_node.inputs["Color"].default_value = (0.46, 0.48, 0.50, 1.0)
bg_node.inputs["Strength"].default_value = 0.6

# Sun strength 3 from front-left-above (-X, -Y, +Z)
sun_data = bpy.data.lights.new(name="Sun", type='SUN')
sun_data.energy = 3.0
sun_obj = bpy.data.objects.new(name="Sun", object_data=sun_data)
scene.collection.objects.link(sun_obj)
sun_obj.location = (-6.0, -5.5, 8.0)
sun_target = Vector((0.0, 0.0, 1.2))
sun_dir = sun_target - sun_obj.location
sun_obj.rotation_euler = sun_dir.to_track_quat('-Z', 'Y').to_euler()

# Camera at 1.7 m height in a front 3/4 view framing the whole object
cam_data = bpy.data.cameras.new(name="Camera")
cam_data.lens = 30.0
cam_data.sensor_width = 36.0
cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

cam_obj.location = (-5.75, -5.15, 1.70)
cam_target = Vector((0.05, 0.0, 1.26))
cam_dir = cam_target - cam_obj.location
cam_obj.rotation_euler = cam_dir.to_track_quat('-Z', 'Y').to_euler()

scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = preview_path
bpy.ops.render.render(write_still=True)

tris = sum(len(p.vertices) - 2 for p in container_obj.data.polygons)
print("TRIS", tris)
