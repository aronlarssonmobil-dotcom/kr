#!/usr/bin/env python3
# =============================================================================
#  KRAFT GT-K1 — mid-engine sports GT, fully parametric Blender build (bpy)
#
#  The whole car is generated from numbers: a lofted body shell (Catmull-Rom
#  cross-sections), boolean panel seams and wheel arches, parametric wheels
#  (tyres, 10-spoke rims, drilled brake discs, radial calipers), double-
#  wishbone front suspension with coil-over springs, steerable front axle,
#  glass canopy, lights, swan-neck wing, diffuser and cockpit — all in true
#  millimetre scale, rendered with Cycles.
#
#  Usage:
#     python3 generate_car.py                 # quick preview renders
#     FULL=1 python3 generate_car.py          # final renders + .blend/.glb
#     SHOTS=hero,wheel python3 generate_car.py
#     STEER=14 python3 generate_car.py        # front-wheel steering angle
# =============================================================================

import bpy
import bmesh
import os
import random
from math import pi, sin, cos, tan, atan, atan2, sqrt, radians
from mathutils import Vector, Matrix, Euler

random.seed(7)

MM = 0.001
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

FULL = os.environ.get("FULL", "") == "1"
SHOT_FILTER = [s for s in os.environ.get("SHOTS", "").split(",") if s]
STEER = radians(float(os.environ.get("STEER", "13")))

# -----------------------------------------------------------------------------
#  MASTER PARAMETERS
# -----------------------------------------------------------------------------
P = dict(
    length     = 4500.0,
    width      = 2020.0,
    height     = 1170.0,
    axle_f     = -1400.0,  axle_r = 1450.0,
    z_axle_f   = 322.0,    z_axle_r = 335.0,
    tire_f     = (650.0, 275.0),   # OD, width
    tire_r     = (680.0, 305.0),
    rim_d      = 508.0,            # 20"
    track_f    = 780.0,            # wheel centre |y|
    track_r    = 800.0,
    arch_r_f   = 385.0, arch_r_r = 400.0,
)

ACCENT = (1.0, 0.28, 0.03, 1.0)

# =============================================================================
#  GENERIC HELPERS (shared design system with the KR-5 drone script)
# =============================================================================
def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def get_col(name):
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col

def link_obj(obj, colname="CAR"):
    get_col(colname).objects.link(obj)
    return obj

def obj_from_bm(name, bm, mat=None, col="CAR"):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    if mat:
        ob.data.materials.append(mat)
    return link_obj(ob, col)

def shade_smooth(ob, angle_deg=40.0):
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    thr = radians(angle_deg)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2:
            try:
                if e.calc_face_angle() > thr:
                    e.smooth = False
            except ValueError:
                pass
        else:
            e.smooth = False
    bm.to_mesh(me)
    bm.free()

def bake_modifiers(ob):
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(deps), depsgraph=deps)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)

def boolean_cut(ob, cutter):
    md = ob.modifiers.new("cut", "BOOLEAN")
    md.operation = "DIFFERENCE"
    md.solver = "EXACT"
    md.object = cutter
    bake_modifiers(ob)
    me = cutter.data
    bpy.data.objects.remove(cutter, do_unlink=True)
    if me.users == 0:
        bpy.data.meshes.remove(me)

def bevel_edges(ob, width=0.00025, angle=30.0, segments=1):
    try:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        thr = radians(angle)
        edges = []
        for e in bm.edges:
            if len(e.link_faces) == 2:
                try:
                    if e.calc_face_angle() > thr:
                        edges.append(e)
                except ValueError:
                    pass
        if edges:
            bmesh.ops.bevel(bm, geom=edges, offset=width, segments=segments,
                            profile=0.7, affect="EDGES", clamp_overlap=True)
        bm.to_mesh(ob.data)
        bm.free()
    except Exception as ex:
        print("bevel skipped on", ob.name, ex)

def cyl_bm(bm, r1, r2, depth, mat=Matrix.Identity(4), segs=48, caps=True):
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=segs,
                          radius1=r1, radius2=r2, depth=depth, matrix=mat)

def add_cyl(name, r, depth, loc, mat=None, rot=(0, 0, 0), segs=48,
            r2=None, col="CAR", smooth=True):
    bm = bmesh.new()
    cyl_bm(bm, r * MM, (r2 if r2 is not None else r) * MM, depth * MM, segs=segs)
    ob = obj_from_bm(name, bm, mat, col)
    ob.location = loc
    ob.rotation_euler = Euler(rot)
    if smooth:
        shade_smooth(ob, 40)
    return ob

def add_box(name, sx, sy, sz, loc, mat=None, rot=(0, 0, 0), bevel=0.0,
            col="CAR", smooth_deg=0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=2,
                        profile=0.72, affect="EDGES", clamp_overlap=True)
    ob = obj_from_bm(name, bm, mat, col)
    ob.location = loc
    ob.rotation_euler = Euler(rot)
    if bevel > 0:
        shade_smooth(ob, smooth_deg or 40)
    return ob

def spin_profile(name, profile_mm, loc, mat, segs=64, col="CAR", smooth=35,
                 rot=(0, 0, 0)):
    bm = bmesh.new()
    vs = [bm.verts.new((r * MM, 0, z * MM)) for r, z in profile_mm]
    for i in range(len(vs) - 1):
        bm.edges.new((vs[i], vs[i + 1]))
    bmesh.ops.spin(bm, geom=list(bm.verts) + list(bm.edges),
                   cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * pi,
                   steps=segs, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = obj_from_bm(name, bm, mat, col)
    ob.location = loc
    ob.rotation_euler = Euler(rot)
    shade_smooth(ob, smooth)
    return ob

def make_wire(name, pts_mm, radius, mat, col="CAR", res=24, cyclic=False):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.resolution_u = res
    cu.bevel_depth = radius * MM
    cu.bevel_resolution = 6
    cu.use_fill_caps = True
    sp = cu.splines.new('BEZIER')
    sp.bezier_points.add(len(pts_mm) - 1)
    for bp, p in zip(sp.bezier_points, pts_mm):
        bp.co = Vector(p) * MM
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    sp.use_cyclic_u = cyclic
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(mat)
    return link_obj(ob, col)

def make_text(name, body, size, loc, rot=(0, 0, 0), mat=None, align='CENTER',
              col="CAR", extrude=0.4):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.size = size * MM
    cu.extrude = extrude * MM
    cu.align_x = align
    cu.align_y = 'CENTER'
    ob = bpy.data.objects.new(name, cu)
    if mat:
        ob.data.materials.append(mat)
    ob.location = loc
    ob.rotation_euler = Euler(rot)
    return link_obj(ob, col)

def catmull(pts, n):
    """Sample n points along a Catmull-Rom spline through pts (list of Vector)."""
    pts = [Vector(p) for p in pts]
    ext = [pts[0] + (pts[0] - pts[1])] + pts + [pts[-1] + (pts[-1] - pts[-2])]
    out = []
    segs = len(pts) - 1
    for i in range(n):
        t = i / (n - 1) * segs
        k = min(int(t), segs - 1)
        u = t - k
        p0, p1, p2, p3 = ext[k], ext[k + 1], ext[k + 2], ext[k + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * u +
                          (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u +
                          (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u))
    return out

# =============================================================================
#  MATERIALS
# =============================================================================
MATS = {}

def set_in(node, name, value):
    s = node.inputs.get(name)
    if s is not None:
        try:
            s.default_value = value
        except Exception:
            pass

def base_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree, m.node_tree.nodes.get("Principled BSDF")

def mix_color(node):
    node.data_type = 'RGBA'
    a = [s for s in node.inputs if s.name == 'A' and s.type == 'RGBA'][0]
    b = [s for s in node.inputs if s.name == 'B' and s.type == 'RGBA'][0]
    out = [s for s in node.outputs if s.name == 'Result' and s.type == 'RGBA'][0]
    return a, b, out

def mat_simple(name, color, rough=0.5, metal=0.0, coat=0.0, coat_r=0.1,
               emis=None, emis_str=0.0, transmission=0.0, ior=1.45,
               sheen=0.0, aniso=0.0):
    m, nt, b = base_mat(name)
    set_in(b, "Base Color", color)
    set_in(b, "Roughness", rough)
    set_in(b, "Metallic", metal)
    set_in(b, "Coat Weight", coat)
    set_in(b, "Coat Roughness", coat_r)
    set_in(b, "Transmission Weight", transmission)
    set_in(b, "IOR", ior)
    set_in(b, "Sheen Weight", sheen)
    set_in(b, "Anisotropic", aniso)
    if emis:
        set_in(b, "Emission Color", emis)
        set_in(b, "Emission Strength", emis_str)
    return m

def mat_paint(name, color):
    """Metallic car paint: base + micro-flake sparkle + deep clearcoat."""
    m, nt, b = base_mat(name)
    n = nt.nodes; l = nt.links
    set_in(b, "Base Color", color)
    set_in(b, "Metallic", 0.55)
    set_in(b, "Roughness", 0.38)
    set_in(b, "Coat Weight", 1.0)
    set_in(b, "Coat Roughness", 0.03)
    tc = n.new("ShaderNodeTexCoord")
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9000.0
    noise.inputs["Detail"].default_value = 2.0
    l.new(tc.outputs["Object"], noise.inputs["Vector"])
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = 0.000004
    l.new(noise.outputs["Fac"], bump.inputs["Height"])
    l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m

def mat_carbon(name="carbon_twill", scale=1.0):
    m, nt, b = base_mat(name)
    n = nt.nodes; l = nt.links
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, radians(45))
    s = 55.0 * scale
    mp.inputs["Scale"].default_value = (s, s, s)
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    chk = n.new("ShaderNodeTexChecker")
    chk.inputs["Scale"].default_value = 1.0
    l.new(mp.outputs["Vector"], chk.inputs["Vector"])
    wx = n.new("ShaderNodeTexWave"); wx.wave_type = 'BANDS'
    wx.bands_direction = 'X'; wx.inputs["Scale"].default_value = 7.0
    wx.inputs["Distortion"].default_value = 0.5
    l.new(mp.outputs["Vector"], wx.inputs["Vector"])
    wy = n.new("ShaderNodeTexWave"); wy.wave_type = 'BANDS'
    wy.bands_direction = 'Y'; wy.inputs["Scale"].default_value = 7.0
    wy.inputs["Distortion"].default_value = 0.5
    l.new(mp.outputs["Vector"], wy.inputs["Vector"])
    mixw = n.new("ShaderNodeMix")
    ma, mb, mout = mix_color(mixw)
    l.new(chk.outputs["Fac"], mixw.inputs["Factor"])
    l.new(wx.outputs["Color"], ma)
    l.new(wy.outputs["Color"], mb)
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.008, 0.009, 0.011, 1)
    ramp.color_ramp.elements[1].position = 0.9
    ramp.color_ramp.elements[1].color = (0.05, 0.055, 0.062, 1)
    l.new(mout, ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    set_in(b, "Metallic", 0.15)
    set_in(b, "Roughness", 0.3)
    set_in(b, "Anisotropic", 0.6)
    set_in(b, "Coat Weight", 0.7)
    set_in(b, "Coat Roughness", 0.08)
    return m

def mat_tire(name):
    m, nt, b = base_mat(name)
    n = nt.nodes; l = nt.links
    set_in(b, "Base Color", (0.012, 0.012, 0.013, 1))
    set_in(b, "Roughness", 0.72)
    set_in(b, "Sheen Weight", 0.25)
    tc = n.new("ShaderNodeTexCoord")
    wave = n.new("ShaderNodeTexWave")
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Z'
    wave.inputs["Scale"].default_value = 260.0
    wave.inputs["Distortion"].default_value = 1.2
    l.new(tc.outputs["Object"], wave.inputs["Vector"])
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.0006
    l.new(wave.outputs["Color"], bump.inputs["Height"])
    l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m

def mat_floor(name):
    m, nt, b = base_mat(name)
    n = nt.nodes; l = nt.links
    set_in(b, "Base Color", (0.012, 0.013, 0.015, 1))
    set_in(b, "Coat Weight", 0.35)
    set_in(b, "Coat Roughness", 0.22)
    tc = n.new("ShaderNodeTexCoord")
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 6.0
    l.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (0.3, 0.3, 0.3, 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (0.46, 0.46, 0.46, 1)
    l.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Roughness"])
    return m

def build_materials():
    MATS["paint"]     = mat_paint("paint_kraft_orange", (0.62, 0.13, 0.015, 1))
    MATS["paint_blk"] = mat_paint("paint_gloss_black", (0.008, 0.008, 0.009, 1))
    MATS["carbon"]    = mat_carbon()
    MATS["glass"]     = mat_simple("glass_smoke", (0.02, 0.022, 0.026, 1), 0.02, 0.0,
                                   coat=1.0, coat_r=0.02, transmission=1.0, ior=1.45)
    MATS["glass_hl"]  = mat_simple("glass_clear", (0.85, 0.87, 0.9, 1), 0.02, 0.0,
                                   coat=1.0, transmission=1.0, ior=1.5)
    MATS["tire"]      = mat_tire("tire_rubber")
    MATS["rim"]       = mat_simple("rim_gunmetal", (0.13, 0.14, 0.155, 1), 0.3, 1.0, coat=0.3, aniso=0.4)
    MATS["rim_lip"]   = mat_simple("rim_lip", (0.7, 0.72, 0.74, 1), 0.18, 1.0, aniso=0.6)
    MATS["disc"]      = mat_simple("brake_disc", (0.38, 0.39, 0.4, 1), 0.42, 1.0, aniso=0.85)
    MATS["disc_hat"]  = mat_simple("disc_hat", (0.05, 0.05, 0.055, 1), 0.5, 1.0)
    MATS["caliper"]   = mat_simple("caliper", ACCENT, 0.32, 0.35, coat=0.6)
    MATS["alu"]       = mat_simple("alu", (0.55, 0.57, 0.59, 1), 0.3, 1.0)
    MATS["steel_dk"]  = mat_simple("steel_dark", (0.08, 0.08, 0.085, 1), 0.45, 1.0)
    MATS["spring"]    = mat_simple("spring", ACCENT, 0.35, 1.0, coat=0.3)
    MATS["black_tr"]  = mat_simple("trim_black", (0.015, 0.015, 0.016, 1), 0.55)
    MATS["black_gl"]  = mat_simple("trim_gloss", (0.01, 0.01, 0.011, 1), 0.12, coat=0.8)
    MATS["mesh"]      = mat_simple("grille_mesh", (0.01, 0.01, 0.011, 1), 0.7, 0.6)
    MATS["interior"]  = mat_simple("interior_alcantara", (0.03, 0.03, 0.033, 1), 0.85, sheen=0.5)
    MATS["seat_o"]    = mat_simple("seat_accent", ACCENT, 0.6, sheen=0.4)
    MATS["drl"]       = mat_simple("drl", (1, 1, 1, 1), 0.2, emis=(0.9, 0.95, 1, 1), emis_str=30)
    MATS["tail_led"]  = mat_simple("tail_led", (1, 0.05, 0.02, 1), 0.2,
                                   emis=(1, 0.04, 0.015, 1), emis_str=22)
    MATS["proj"]      = mat_simple("projector", (0.6, 0.65, 0.75, 1), 0.08, 1.0,
                                   emis=(0.8, 0.9, 1, 1), emis_str=4)
    MATS["exh"]       = mat_simple("exhaust_ti", (0.45, 0.42, 0.4, 1), 0.3, 1.0, aniso=0.7)
    MATS["text_w"]    = mat_simple("text_white", (0.85, 0.86, 0.88, 1), 0.4)
    MATS["floor"]     = mat_floor("studio_floor")
    MATS["backdrop"]  = mat_simple("backdrop", (0.012, 0.013, 0.016, 1), 0.9)

# =============================================================================
#  BODY — lofted shell from cross-sections
# =============================================================================
# station: (x, [(y,z) x6 half-profile bottom-centre → outer → top-centre])
BODY = [
    (-2250, [(0, 260), (150, 265), (280, 300), (330, 370), (250, 430), (0, 470)]),
    (-2100, [(0, 190), (380, 200), (520, 300), (560, 400), (430, 490), (0, 540)]),
    (-1850, [(0, 145), (620, 160), (760, 300), (800, 430), (620, 560), (0, 615)]),
    (-1400, [(0, 135), (700, 150), (860, 330), (900, 480), (700, 640), (0, 680)]),
    (-950,  [(0, 130), (730, 145), (880, 320), (920, 500), (720, 670), (0, 700)]),
    (-450,  [(0, 130), (750, 145), (900, 310), (930, 520), (750, 690), (0, 715)]),
    (0,     [(0, 130), (750, 145), (900, 310), (925, 520), (745, 700), (0, 720)]),
    (450,   [(0, 130), (770, 148), (920, 320), (950, 540), (770, 715), (0, 730)]),
    (950,   [(0, 135), (800, 155), (960, 350), (990, 570), (800, 750), (0, 760)]),
    (1450,  [(0, 150), (820, 175), (990, 420), (1010, 620), (820, 790), (0, 810)]),
    (1850,  [(0, 190), (740, 230), (900, 450), (930, 630), (740, 790), (0, 815)]),
    (2120,  [(0, 240), (620, 290), (800, 470), (820, 640), (640, 780), (0, 800)]),
    (2250,  [(0, 300), (380, 340), (600, 480), (620, 630), (500, 760), (0, 780)]),
]

CANOPY = [
    (-950, [(0, 712), (380, 702), (600, 686)]),
    (-350, [(0, 1150), (320, 1105), (520, 980)]),
    (250,  [(0, 1170), (330, 1120), (540, 990)]),
    (800,  [(0, 1050), (320, 1010), (530, 900)]),
    (1300, [(0, 848), (300, 832), (500, 802)]),
]

def loft(name, stations, su, sv, mat, close_caps=True):
    """Loft mirrored half-sections into a closed shell."""
    ringed = []
    for x, pts in stations:
        half = catmull([Vector((p[0], p[1], 0)) for p in pts], su)
        ring = []
        for v in half:
            ring.append(Vector((x, v.x, v.y)))
        for v in reversed(half[1:-1]):
            ring.append(Vector((x, -v.x, v.y)))
        ringed.append(ring)
    # resample along length
    nrings = len(ringed)
    cols = []
    m = len(ringed[0])
    for j in range(m):
        chain = [ringed[i][j] for i in range(nrings)]
        cols.append(catmull(chain, sv))
    bm = bmesh.new()
    grid = []
    for i in range(sv):
        ring = [bm.verts.new(cols[j][i] * MM) for j in range(m)]
        grid.append(ring)
    for i in range(sv - 1):
        for j in range(m):
            a = grid[i][j]; b = grid[i][(j + 1) % m]
            c = grid[i + 1][(j + 1) % m]; d = grid[i + 1][j]
            try:
                bm.faces.new((a, b, c, d))
            except ValueError:
                pass
    if close_caps:
        for ring, rev in ((grid[0], True), (grid[-1], False)):
            ctr = Vector((0, 0, 0))
            for v in ring:
                ctr += v.co
            ctr /= len(ring)
            vc = bm.verts.new(ctr)
            n = len(ring)
            for k in range(n):
                a, b = ring[k], ring[(k + 1) % n]
                try:
                    bm.faces.new((b, a, vc) if rev else (a, b, vc))
                except ValueError:
                    pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = obj_from_bm(name, bm, mat)
    shade_smooth(ob, 42)
    return ob

def build_body():
    body = loft("body_shell", BODY, 26, 110, MATS["paint"])
    # ---- wheel arches -------------------------------------------------------
    cut = bmesh.new()
    for x, z, r in ((P["axle_f"], P["z_axle_f"], P["arch_r_f"]),
                    (P["axle_r"], P["z_axle_r"], P["arch_r_r"])):
        for sy in (1, -1):
            m = (Matrix.Translation((x * MM, sy * 0.87, z * MM)) @
                 Matrix.Rotation(pi / 2, 4, 'X'))
            cyl_bm(cut, r * MM, r * MM, 0.55, m, segs=48)
    cob = obj_from_bm("arch_cut", cut, None)
    boolean_cut(body, cob)
    # ---- panel seams (doors, frunk, engine cover) --------------------------
    seams = bmesh.new()
    def seam_box(sx, sy, sz, loc, rot=(0, 0, 0)):
        bmc = bmesh.new()
        bmesh.ops.create_cube(bmc, size=1)
        bmesh.ops.scale(bmc, vec=(sx * MM, sy * MM, sz * MM), verts=bmc.verts)
        mtx = (Matrix.Translation((loc[0] * MM, loc[1] * MM, loc[2] * MM)) @
               Euler(rot).to_matrix().to_4x4())
        bmesh.ops.transform(bmc, matrix=mtx, verts=bmc.verts)
        me_t = bpy.data.meshes.new("st"); bmc.to_mesh(me_t); bmc.free()
        seams.from_mesh(me_t)
        bpy.data.meshes.remove(me_t)
    for sy in (1, -1):
        seam_box(3, 120, 560, (-450, sy * 900, 460))     # door front cut
        seam_box(3, 120, 560, (430, sy * 930, 470))      # door rear cut
        seam_box(1700, 3, 130, (0, sy * 935, 745), (radians(-6 * sy), 0, 0))  # belt seam
    seam_box(3, 1450, 120, (-950, 0, 690))               # frunk rear seam
    seam_box(3, 1000, 140, (-1900, 0, 585))              # nose panel seam
    seam_box(3, 1250, 130, (650, 0, 745))                # engine cover front
    for sy in (1, -1):
        seam_box(1050, 3, 130, (1170, sy * 420, 800), (0, radians(4), 0))
    sob = obj_from_bm("seam_cut", seams, None)
    boolean_cut(body, sob)
    shade_smooth(body, 42)
    # ---- inner arch drums (hide interior through gaps) ----------------------
    for x, z, r, w in ((P["axle_f"], P["z_axle_f"], P["arch_r_f"] - 12, 340),
                       (P["axle_r"], P["z_axle_r"], P["arch_r_r"] - 12, 370)):
        for sy in (1, -1):
            add_cyl(f"arch_drum_{x}_{sy}", r, w,
                    (x * MM, sy * (870 - w / 2 - 60) * MM, z * MM),
                    MATS["black_tr"], rot=(pi / 2, 0, 0), segs=40)
    # ---- belly pan ----------------------------------------------------------
    add_box("belly", 3600 * MM, 1500 * MM, 30 * MM, (0, 0, 120 * MM),
            MATS["carbon"], bevel=8 * MM)
    # ---- canopy glass -------------------------------------------------------
    loft("canopy", CANOPY, 14, 40, MATS["glass"])
    return body

# =============================================================================
#  AERO & TRIM
# =============================================================================
def build_aero():
    # front splitter
    add_box("splitter", 700 * MM, 1780 * MM, 26 * MM, (-2160 * MM, 0, 150 * MM),
            MATS["carbon"], bevel=8 * MM)
    # rear diffuser (angled plate + strakes)
    dif = add_box("diffuser", 720 * MM, 1500 * MM, 26 * MM,
                  (1965 * MM, 0, 215 * MM), MATS["carbon"],
                  rot=(0, radians(-13), 0), bevel=6 * MM)
    for i in range(5):
        y = -600 + i * 300
        add_box(f"strake_{i}", 620 * MM, 14 * MM, 150 * MM,
                (1985 * MM, y * MM, 260 * MM), MATS["carbon"],
                rot=(0, radians(-13), 0), bevel=3 * MM)
    # swan-neck wing
    bm = bmesh.new()
    span, chord = 1500, 260
    NS, NC = 24, 16
    for i in range(NS + 1):
        fy = (i / NS - 0.5) * span
        pass
    # (wing surface via simple symmetric airfoil sweep)
    rings = []
    for i in range(NS + 1):
        fy = (i / NS - 0.5)
        y = fy * span
        c = chord * (1.0 - 0.18 * abs(fy) ** 2.5)
        ring = []
        for side in (0, 1):
            for j in range(NC + 1):
                if side == 1 and (j == 0 or j == NC):
                    continue
                xf = j / NC if side == 0 else 1 - j / NC
                zsig = 1 if side == 0 else -1
                yt = 0.055 * 5 * (0.2969 * sqrt(max(xf, 1e-4)) - 0.126 * xf -
                                  0.3516 * xf ** 2 + 0.2843 * xf ** 3 - 0.1036 * xf ** 4)
                camb = -0.05 * sin(pi * xf ** 0.9)      # inverted (downforce)
                px = (xf - 0.3) * c
                pz = (camb + zsig * yt) * c
                a = radians(-8)                          # angle of attack
                ring.append(Vector((px * cos(a) - pz * sin(a),
                                    y, px * sin(a) + pz * cos(a))))
        rings.append(ring)
    prev = None
    first = None
    for ring in rings:
        vs = [bm.verts.new((v + Vector((2050, 0, 1010))) * MM) for v in ring]
        if prev:
            n = len(vs)
            for k in range(n):
                try:
                    bm.faces.new((prev[k], prev[(k + 1) % n], vs[(k + 1) % n], vs[k]))
                except ValueError:
                    pass
        else:
            first = vs
        prev = vs
    for ring, rev in ((first, True), (prev, False)):
        ctr = Vector((0, 0, 0))
        for v in ring:
            ctr += v.co
        ctr /= len(ring)
        vc = bm.verts.new(ctr)
        n = len(ring)
        for k in range(n):
            a, b = ring[k], ring[(k + 1) % n]
            try:
                bm.faces.new((b, a, vc) if rev else (a, b, vc))
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    wing = obj_from_bm("wing", bm, MATS["carbon"])
    shade_smooth(wing, 45)
    for sy in (1, -1):
        add_box(f"endplate_{sy}", 300 * MM, 12 * MM, 190 * MM,
                (2060 * MM, sy * 755 * MM, 1000 * MM), MATS["carbon"], bevel=3 * MM)
        make_wire(f"pylon_{sy}", [(1930, sy * 330, 810), (1990, sy * 330, 900),
                                  (2060, sy * 330, 1005)], 16, MATS["carbon"])
    # mirrors
    for sy in (1, -1):
        make_wire(f"mir_stalk_{sy}", [(-420, sy * 900, 720), (-450, sy * 990, 780)],
                  14, MATS["paint_blk"])
        bmm = bmesh.new()
        bmesh.ops.create_uvsphere(bmm, u_segments=24, v_segments=14, radius=1)
        bmesh.ops.scale(bmm, vec=(95 * MM, 65 * MM, 55 * MM), verts=bmm.verts)
        mo = obj_from_bm(f"mirror_{sy}", bmm, MATS["paint"])
        mo.location = (-430 * MM, sy * 1010 * MM, 795 * MM)
        shade_smooth(mo, 40)
        add_cyl(f"mir_glass_{sy}", 52, 4, (-395 * MM, sy * 1012 * MM, 795 * MM),
                MATS["black_gl"], rot=(0, pi / 2, 0), segs=28)

def build_lights():
    for sy in (1, -1):
        # headlight blister: dark gloss housing + two projectors + DRL blade
        hb = add_box(f"hl_house_{sy}", 340 * MM, 300 * MM, 130 * MM,
                     (-1965 * MM, sy * 520 * MM, 555 * MM), MATS["black_gl"],
                     rot=(radians(-8 * sy) * 0, radians(-14), radians(18 * sy)),
                     bevel=32 * MM, smooth_deg=30)
        for k in range(2):
            add_cyl(f"hl_proj_{sy}_{k}", 42, 60,
                    ((-2065 + k * 60) * MM, sy * (455 + k * 105) * MM, (560 + k * 8) * MM),
                    MATS["proj"], rot=(0, radians(-80), radians(10 * sy)), segs=28)
        make_wire(f"drl_{sy}", [(-1990, sy * 380, 610), (-1935, sy * 560, 628),
                                (-1860, sy * 668, 622)], 7, MATS["drl"])
    # full-width tail LED bar
    add_box("tail_bar", 26 * MM, 1330 * MM, 34 * MM, (2242 * MM, 0, 700 * MM),
            MATS["tail_led"], bevel=8 * MM)
    for sy in (1, -1):
        add_box(f"tail_wrap_{sy}", 120 * MM, 60 * MM, 34 * MM,
                (2195 * MM, sy * 690 * MM, 698 * MM), MATS["tail_led"],
                rot=(0, 0, radians(-30 * sy)), bevel=8 * MM)
    make_text("badge", "K R A F T", 62, (2258 * MM, 0, 622 * MM),
              rot=(pi / 2, 0, -pi / 2), mat=MATS["text_w"], extrude=3)
    make_text("badge2", "GT-K1", 40, (2258 * MM, -430 * MM, 622 * MM),
              rot=(pi / 2, 0, -pi / 2), mat=MATS["text_w"], extrude=3)
    # grille mesh + intakes
    add_box("grille", 60 * MM, 900 * MM, 130 * MM, (-2225 * MM, 0, 330 * MM),
            MATS["mesh"], bevel=15 * MM)
    for sy in (1, -1):
        add_box(f"side_intake_{sy}", 320 * MM, 90 * MM, 200 * MM,
                (620 * MM, sy * 905 * MM, 480 * MM), MATS["mesh"],
                rot=(0, 0, radians(-14 * sy)), bevel=25 * MM, smooth_deg=30)
    # exhausts
    for sy in (1, -1):
        add_cyl(f"exh_{sy}", 44, 90, (2230 * MM, sy * 150 * MM, 420 * MM),
                MATS["exh"], rot=(0, pi / 2, 0), segs=28)
        add_cyl(f"exh_in_{sy}", 36, 92, (2233 * MM, sy * 150 * MM, 420 * MM),
                MATS["black_tr"], rot=(0, pi / 2, 0), segs=24)
    # engine-deck louvres
    for i in range(6):
        add_box(f"louvre_{i}", 60 * MM, 640 * MM, 10 * MM,
                ((940 + i * 105) * MM, 0, (792 - i * 4) * MM),
                MATS["black_tr"], rot=(0, radians(24), 0), bevel=3 * MM)

# =============================================================================
#  WHEELS, BRAKES, SUSPENSION
# =============================================================================
def make_disc_template():
    """Drilled + inner-vaned brake disc, built once, reused per corner."""
    disc = spin_profile("disc_tpl", [(60, -16), (188, -16), (192, -12), (192, 12),
                                     (188, 16), (60, 16), (60, -16)],
                        (0, 0, 0), MATS["disc"], segs=64)
    cut = bmesh.new()
    for k in range(20):
        a = 2 * pi * k / 20
        cyl_bm(cut, 7 * MM, 7 * MM, 60 * MM,
               Matrix.Translation((150 * cos(a) * MM, 150 * sin(a) * MM, 0)), segs=10)
    cob = obj_from_bm("disc_holes", cut, None)
    boolean_cut(disc, cob)
    shade_smooth(disc, 40)
    hat = spin_profile("hat_tpl", [(0, 14), (58, 14), (62, 10), (62, -6), (52, -8),
                                   (0, -8), (0, 14)], (0, 0, 0), MATS["disc_hat"], segs=40)
    hat.parent = disc
    return disc

def make_wheel_template(od, width):
    """Tyre + 10-spoke rim as one template object tree (axis = +Z)."""
    R, w = od / 2, width / 2
    root = bpy.data.objects.new(f"wheel_tpl_{od}", None)
    link_obj(root)
    # tyre via spin: tread + shoulders + sidewalls + bead
    prof = [(R - 4, -w * 0.55), (R, -w * 0.72), (R, w * 0.72), (R - 4, w * 0.55),
            (R, w * 0.86)]
    prof = [(254, -w), (R - 30, -w * 0.94), (R - 6, -w * 0.72), (R, -w * 0.5),
            (R, w * 0.5), (R - 6, w * 0.72), (R - 30, w * 0.94), (254, w)]
    tyre = spin_profile("tyre", prof, (0, 0, 0), MATS["tire"], segs=72)
    tyre.parent = root
    tyre.rotation_euler = Euler((0, pi / 2, 0))     # axis → X, will re-aim later
    # rim barrel + lip
    rim_prof = [(150, w * 0.6), (240, w * 0.75), (252, w * 0.8), (252, -w * 0.8),
                (236, -w * 0.75), (236, w * 0.55), (150, w * 0.6)]
    rim = spin_profile("rim_barrel", rim_prof, (0, 0, 0), MATS["rim"], segs=64)
    rim.parent = root
    rim.rotation_euler = Euler((0, pi / 2, 0))
    lip = spin_profile("rim_lip", [(252.5, w * 0.68), (252.5, w * 0.8),
                                   (244, w * 0.82), (244, w * 0.7), (252.5, w * 0.68)],
                       (0, 0, 0), MATS["rim_lip"], segs=64)
    lip.parent = root
    lip.rotation_euler = Euler((0, pi / 2, 0))
    # 10 spokes (paired Y-style) + centre + bolts
    for k in range(10):
        a = 2 * pi * k / 10
        sp = add_box(f"spoke_{k}", 30 * MM, 170 * MM, 34 * MM, (0, 0, 0),
                     MATS["rim"], bevel=6 * MM)
        sp.parent = root
        sp.location = (w * 0.55 * MM * 0 + 0.0 - 0 * MM,
                       0, 0)
        sp.location = (0, cos(a) * 150 * MM, sin(a) * 150 * MM)
        sp.rotation_euler = Euler((a + pi / 2 + radians(6), 0, 0))
        sp.location.x = w * 0.42 * MM
    hub = add_cyl("hub_face", 78, 40, (0, 0, 0), MATS["rim"], segs=32)
    hub.parent = root
    hub.location = (w * 0.5 * MM, 0, 0)
    hub.rotation_euler = Euler((0, pi / 2, 0))
    cap = add_cyl("hub_cap", 30, 8, (0, 0, 0), MATS["black_gl"], segs=24)
    cap.parent = root
    cap.location = ((w * 0.5 + 20) * MM, 0, 0)
    cap.rotation_euler = Euler((0, pi / 2, 0))
    for k in range(5):
        a = 2 * pi * k / 5
        bolt = add_cyl(f"bolt_{k}", 9, 12, (0, 0, 0), MATS["steel_dk"], segs=6, smooth=False)
        bolt.parent = root
        bolt.location = ((w * 0.5 + 16) * MM, cos(a) * 52 * MM, sin(a) * 52 * MM)
        bolt.rotation_euler = Euler((0, pi / 2, 0))
    return root

def copy_tree(root, name):
    new_root = root.copy()
    new_root.name = name
    link_obj(new_root)
    for ch in root.children_recursive:
        c = ch.copy()
        c.name = f"{name}_{ch.name}"
        c.parent = new_root if ch.parent == root else None
        link_obj(c)
    # fix nested parents (only one level used besides root)
    for ch in root.children_recursive:
        pass
    return new_root

def build_wheels():
    disc_tpl = make_disc_template()
    tpl_f = make_wheel_template(*P["tire_f"])
    tpl_r = make_wheel_template(*P["tire_r"])
    corners = [
        ("FL", P["axle_f"], +P["track_f"], P["z_axle_f"], tpl_f, STEER),
        ("FR", P["axle_f"], -P["track_f"], P["z_axle_f"], tpl_f, STEER),
        ("RL", P["axle_r"], +P["track_r"], P["z_axle_r"], tpl_r, 0.0),
        ("RR", P["axle_r"], -P["track_r"], P["z_axle_r"], tpl_r, 0.0),
    ]
    for name, x, y, z, tpl, steer in corners:
        side = 1 if y > 0 else -1
        w = tpl.copy()
        w.name = f"wheel_{name}"
        link_obj(w)
        for ch in tpl.children_recursive:
            c = ch.copy()
            c.name = f"{name}_{c.name}"
            if ch.parent == tpl:
                c.parent = w
            link_obj(c)
        w.location = (x * MM, y * MM, z * MM)
        rz = (pi / 2 if side > 0 else -pi / 2) + steer * (1 if True else 1) * (-side)
        w.rotation_euler = Euler((0, 0, (pi / 2 * side) + (-steer if x < 0 else 0)))
        w.rotation_euler.x = radians(random.uniform(0, 36))   # random wheel phase
        # brake disc + caliper (inboard of rim face)
        d = disc_tpl.copy(); d.name = f"disc_{name}"
        link_obj(d)
        for ch in disc_tpl.children:
            c = ch.copy(); c.name = f"{name}_hat"; c.parent = d; link_obj(c)
        d.location = (x * MM, (y - side * 40) * MM, z * MM)
        d.rotation_euler = Euler((pi / 2, 0, 0))
        cal = add_box(f"caliper_{name}", 130 * MM, 60 * MM, 110 * MM,
                      ((x - 148 if x < 0 else x + 148) * MM * 0 + (x - 150) * MM,
                       (y - side * 46) * MM, (z + 88) * MM),
                      MATS["caliper"], rot=(0, radians(-32), 0), bevel=16 * MM,
                      smooth_deg=30)
        make_text(f"cal_txt_{name}", "KRAFT", 30,
                  ((x - 168) * MM, (y - side * 46 + side * 34) * MM, (z + 92) * MM),
                  rot=(pi / 2, radians(-30), 0 if side > 0 else pi),
                  mat=MATS["text_w"], extrude=1.2)
        # suspension: lower wishbone + coil-over
        make_wire(f"wb_{name}", [(x + 260, side * 300, z - 90),
                                 (x, side * (abs(y) - 120), z - 100),
                                 (x - 260, side * 300, z - 90)], 22, MATS["steel_dk"])
        make_wire(f"damper_{name}", [(x, side * (abs(y) - 130), z - 60),
                                     (x - 40, side * (abs(y) - 260), z + 240)],
                  24, MATS["alu"])
        helix = []
        for t in range(60):
            u = t / 59
            a = u * 2 * pi * 6
            cx = x + (-40 * u)
            cyy = side * ((abs(y) - 130) + (-130 * u))
            cz = (z - 40) + 280 * u
            helix.append((cx + 42 * cos(a), cyy + 42 * sin(a) * 0.8, cz))
        make_wire(f"spring_{name}", helix, 9, MATS["spring"], res=8)
    # hide templates
    for tpl in (tpl_f, tpl_r, disc_tpl):
        tpl.hide_render = True
        tpl.hide_viewport = True
        for ch in tpl.children_recursive:
            ch.hide_render = True
            ch.hide_viewport = True

# =============================================================================
#  INTERIOR (visible through smoke glass)
# =============================================================================
def build_interior():
    add_box("tub", 1900 * MM, 1350 * MM, 320 * MM, (-50 * MM, 0, 320 * MM),
            MATS["interior"], bevel=40 * MM)
    add_box("dash", 340 * MM, 1330 * MM, 200 * MM, (-780 * MM, 0, 620 * MM),
            MATS["interior"], rot=(0, radians(-12), 0), bevel=45 * MM, smooth_deg=30)
    for sy in (1, -1):
        add_box(f"seat_base_{sy}", 520 * MM, 480 * MM, 180 * MM,
                (120 * MM, sy * 360 * MM, 420 * MM), MATS["interior"],
                bevel=45 * MM, smooth_deg=30)
        add_box(f"seat_back_{sy}", 200 * MM, 460 * MM, 620 * MM,
                (330 * MM, sy * 360 * MM, 700 * MM), MATS["interior"],
                rot=(0, radians(18), 0), bevel=50 * MM, smooth_deg=30)
        add_box(f"seat_stripe_{sy}", 205 * MM, 120 * MM, 600 * MM,
                (330 * MM, sy * 360 * MM, 705 * MM), MATS["seat_o"],
                rot=(0, radians(18), 0), bevel=48 * MM, smooth_deg=30)
    # steering wheel on column (LHD)
    swc = Vector((-620 * MM, 360 * MM, 640 * MM))
    add_cyl("column", 30, 260, tuple(swc + Vector((60 * MM, 0, -40 * MM))),
            MATS["black_tr"], rot=(0, radians(65), 0), segs=20)
    rim = add_cyl("sw_rim", 170, 30, tuple(swc), MATS["black_tr"], segs=40)
    rim.rotation_euler = Euler((0, radians(65), 0))
    bm = bmesh.new()
    tor = bmesh.ops.create_circle(bm, cap_ends=False, radius=1, segments=8)
    bm.free()
    for k, a in enumerate((0, radians(120), radians(-120))):
        make_wire(f"sw_spoke_{k}",
                  [tuple(Vector((swc.x / MM, swc.y / MM, swc.z / MM))),
                   (swc.x / MM - 150 * sin(a) * 0.42, swc.y / MM + cos(a) * 150,
                    swc.z / MM + sin(a) * 150 * 0.9)], 16, MATS["black_tr"])

# =============================================================================
#  STUDIO & CAMERAS
# =============================================================================
def build_studio():
    col = "STUDIO"
    add_box("floor", 30.0, 30.0, 0.05, (0, 0, -0.025), MATS["floor"], col=col)
    add_box("wall_n", 30.0, 0.1, 8.0, (0, -8.0, 3.2), MATS["backdrop"], col=col)
    add_box("wall_s", 30.0, 0.1, 8.0, (0, 8.0, 3.2), MATS["backdrop"], col=col)
    add_box("wall_w", 0.1, 30.0, 8.0, (-9.0, 0, 3.2), MATS["backdrop"], col=col)
    add_box("wall_e", 0.1, 30.0, 8.0, (9.0, 0, 3.2), MATS["backdrop"], col=col)
    def area(name, size_x, size_y, loc, target, power, color=(1, 1, 1)):
        li = bpy.data.lights.new(name, 'AREA')
        li.shape = 'RECTANGLE'
        li.size = size_x; li.size_y = size_y
        li.energy = power; li.color = color
        ob = bpy.data.objects.new(name, li)
        link_obj(ob, col)
        ob.location = loc
        d = Vector(target) - Vector(loc)
        ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        return ob
    area("key",  2.6, 2.6, ( 2.4,  3.4, 3.4), (0, 0, 0.5), 950, (1.0, 0.97, 0.92))
    area("fill", 3.0, 3.0, (-3.6,  2.6, 1.8), (0, 0, 0.5), 260, (0.9, 0.94, 1.0))
    area("rim1", 0.5, 5.5, (-2.8, -3.6, 2.6), (0, 0, 0.6), 700, (0.8, 0.88, 1.0))
    area("rim2", 0.5, 5.5, ( 3.2, -3.2, 2.2), (0, 0, 0.6), 500, (1.0, 0.85, 0.7))
    # long overhead strip → the classic roof streak
    area("strip", 0.7, 9.0, (0.4, 0.0, 4.2), (0.2, 0, 0), 900)
    w = bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.002, 0.0025, 0.004, 1)
    bg.inputs[1].default_value = 1.0

SHOTS = {}

def add_camera(name, loc_mm, look_mm, lens=50, fstop=5.6, focus_mm=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36
    cd.clip_start = 0.01
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = fstop
    ob = bpy.data.objects.new(name, cd)
    link_obj(ob, "STUDIO")
    ob.location = Vector(loc_mm) * MM
    d = Vector(look_mm) * MM - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    tgt = bpy.data.objects.new(name + "_focus", None)
    link_obj(tgt, "STUDIO")
    tgt.location = Vector(focus_mm or look_mm) * MM
    cd.dof.focus_object = tgt
    SHOTS[name] = ob
    return ob

def build_cameras():
    add_camera("hero",  (-4600, 3400, 1050), (0, 0, 480), lens=42, fstop=5.6)
    add_camera("rear",  (4300, -3300, 1150), (0, 0, 520), lens=45, fstop=5.6)
    add_camera("side",  (150, 5200, 560),    (0, 0, 520), lens=60, fstop=6.3)
    add_camera("front", (-5400, 250, 520),   (0, 0, 500), lens=70, fstop=6.3)
    add_camera("wheel", (-2500, 2100, 420),  (-1400, 780, 330), lens=85, fstop=3.5,
               focus_mm=(-1400, 830, 330))
    add_camera("deck",  (2500, 1500, 1750),  (900, 0, 750), lens=55, fstop=5.6)

# =============================================================================
#  RENDER / EXPORT
# =============================================================================
def setup_render():
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 256 if FULL else 40
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.015 if FULL else 0.05
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.cycles.max_bounces = 8
    sc.cycles.transparent_max_bounces = 12
    sc.render.resolution_x = 1920 if FULL else 860
    sc.render.resolution_y = 1200 if FULL else 540
    sc.render.image_settings.file_format = 'PNG'
    sc.view_settings.view_transform = 'AgX'
    for look in ('AgX - Punchy', 'Punchy'):
        try:
            sc.view_settings.look = look
            break
        except Exception:
            pass

def render_all():
    sc = bpy.context.scene
    tag = "full" if FULL else "prev"
    for name, cam in SHOTS.items():
        if SHOT_FILTER and name not in SHOT_FILTER:
            continue
        sc.camera = cam
        if name == "hero" and FULL:
            sc.render.resolution_x, sc.render.resolution_y = 2304, 1440
        else:
            sc.render.resolution_x = 1920 if FULL else 860
            sc.render.resolution_y = 1200 if FULL else 540
        sc.render.filepath = os.path.join(OUT, f"{name}_{tag}.png")
        print(f"--- rendering {name} ...", flush=True)
        bpy.ops.render.render(write_still=True)

def export_assets():
    for ob in bpy.data.objects:
        ob.select_set(False)
    for ob in get_col("CAR").objects:
        if not ob.hide_render:
            ob.select_set(True)
    try:
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "kraft_gt_k1.glb"),
                                  use_selection=True, export_apply=True)
        print("GLB exported")
    except Exception as ex:
        print("GLB export failed:", ex)
    try:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "kraft_gt_k1.blend"))
        print("Blend saved")
    except Exception as ex:
        print("blend save failed:", ex)

def main():
    clean_scene()
    get_col("CAR"); get_col("STUDIO")
    build_materials()
    build_body()
    build_aero()
    build_lights()
    build_wheels()
    build_interior()
    build_studio()
    build_cameras()
    setup_render()
    if FULL:
        export_assets()
    render_all()
    print("DONE. objects:", len(bpy.data.objects))

main()
