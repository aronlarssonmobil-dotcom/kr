#!/usr/bin/env python3
# =============================================================================
#  KR-5 "APEX"  —  5-inch freestyle FPV quadcopter
#  Fully parametric 3D build script for Blender 4.x/5.x (bpy)
#
#  Every component is modelled at true real-world scale (millimetres) from
#  the PARAMS table below: carbon frame, 2306.5 brushless motors with
#  visible copper windings, tri-blade 5.1x4.9 propellers generated from a
#  NACA-style airfoil with geometric-pitch twist, 30.5x30.5 FC/ESC stack,
#  digital FPV camera, 6S 1300 mAh LiPo, antennas, wiring looms, hardware.
#
#  Usage:
#     python3 generate_drone.py                 # quick preview renders
#     FULL=1 python3 generate_drone.py          # final renders + .blend/.glb
#     SHOTS=hero,motor python3 generate_drone.py
# =============================================================================

import bpy
import bmesh
import math
import os
import random
from math import pi, sin, cos, tan, atan, atan2, sqrt, radians
from mathutils import Vector, Matrix, Euler

random.seed(11)

MM = 0.001  # scene unit is metres; the model is built in true millimetres
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

FULL = os.environ.get("FULL", "") == "1"
SHOT_FILTER = [s for s in os.environ.get("SHOTS", "").split(",") if s]

# -----------------------------------------------------------------------------
#  PARAMETER TABLE — the entire aircraft is driven from these numbers
# -----------------------------------------------------------------------------
P = dict(
    # frame
    motor_xy        = 79.5,    # motor centre offset on X and Y (=> 224.9 mm WB)
    arm_thick       = 5.0,     # 5 mm carbon arms
    plate_thick     = 2.0,     # 2 mm carbon plates
    bottom_L        = 150.0, bottom_W = 54.0,
    top_L           = 118.0, top_W    = 34.0,
    standoff_h      = 25.0, standoff_d = 5.0,
    standoffs       = [(13.0, -52.0), (-13.0, -52.0), (13.5, -2.0), (-13.5, -2.0)],
    # motors (2306.5 class)
    bell_d          = 28.4, base_d = 28.0,
    motor_holes     = 16.0,    # 16x16 M3 pattern
    n_poles         = 12,
    # props (5.1 x 4.9 tri-blade)
    prop_diam       = 129.5,   # 5.1"
    prop_pitch      = 124.5,   # 4.9" geometric pitch
    prop_blades     = 3,
    hub_d           = 14.0, hub_h = 7.0,
    # stack
    stack_pitch     = 30.5, board = 36.0,
    # battery 6S 1300
    bat_L = 75.0, bat_W = 39.0, bat_H = 48.0, bat_ctr_y = -14.0,
    # z-stackup (from ground)
    z_arm           = 2.0,     # arms 2..7  (bottom plate 0..2)
    z_main          = 7.0,     # main plate 7..9
    z_deck          = 9.0,     # electronics deck
    z_top           = 34.0,    # top plate 34..36
)
P["z_motor"] = P["z_arm"] + P["arm_thick"]          # 7.0
P["z_top_t"] = P["z_top"] + P["plate_thick"]        # 36.0

ACCENT = (1.0, 0.28, 0.03, 1.0)   # anodised orange accent colour

# =============================================================================
#  SCENE / COLLECTION SETUP
# =============================================================================
def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def get_col(name):
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col

def link_obj(obj, colname="DRONE"):
    get_col(colname).objects.link(obj)
    return obj

# =============================================================================
#  GENERIC MESH HELPERS  (bmesh-first: fully headless-safe)
# =============================================================================
def obj_from_bm(name, bm, mat=None, col="DRONE"):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    if mat:
        ob.data.materials.append(mat)
    return link_obj(ob, col)

def shade_smooth(ob, angle_deg=40.0):
    """Smooth shading with sharp edges above the given face angle (4.x/5.x-safe)."""
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
            r2=None, col="DRONE", smooth=True):
    bm = bmesh.new()
    cyl_bm(bm, r * MM, (r2 if r2 is not None else r) * MM, depth * MM, segs=segs)
    ob = obj_from_bm(name, bm, mat, col)
    ob.location = loc
    ob.rotation_euler = Euler(rot)
    if smooth:
        shade_smooth(ob, 40)
    return ob

def add_box(name, sx, sy, sz, loc, mat=None, rot=(0, 0, 0), bevel=0.0,
            col="DRONE", smooth_deg=0):
    """Box with absolute size in metres (pass mm*MM)."""
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

def fillet2d(pts, r, segs=5):
    """Fillet every corner of a closed 2D polygon; r = radius or per-point list."""
    out = []
    n = len(pts)
    for i in range(n):
        p0 = Vector(pts[(i - 1) % n]); p1 = Vector(pts[i]); p2 = Vector(pts[(i + 1) % n])
        rr = r[i] if isinstance(r, (list, tuple)) else r
        v1 = (p0 - p1); v2 = (p2 - p1)
        l1, l2 = v1.length, v2.length
        if l1 < 1e-6 or l2 < 1e-6:
            continue
        v1n, v2n = v1 / l1, v2 / l2
        ang = v1n.angle(v2n)
        if rr <= 0.01 or ang > radians(177):
            out.append((p1.x, p1.y)); continue
        t = min(rr / tan(ang / 2), l1 * 0.45, l2 * 0.45)
        rr2 = t * tan(ang / 2)
        pa = p1 + v1n * t
        pb = p1 + v2n * t
        bis = (v1n + v2n)
        if bis.length < 1e-6:
            out.append((p1.x, p1.y)); continue
        c = p1 + bis.normalized() * (rr2 / sin(ang / 2))
        a0 = atan2(pa.y - c.y, pa.x - c.x)
        a1 = atan2(pb.y - c.y, pb.x - c.x)
        da = a1 - a0
        while da > pi: da -= 2 * pi
        while da < -pi: da += 2 * pi
        for k in range(segs + 1):
            a = a0 + da * k / segs
            out.append((c.x + rr2 * cos(a), c.y + rr2 * sin(a)))
    return out

def dedupe(pts, eps=0.02):
    out = []
    for p in pts:
        if not out or (Vector(p) - Vector(out[-1])).length > eps:
            out.append(p)
    if len(out) > 1 and (Vector(out[0]) - Vector(out[-1])).length < eps:
        out.pop()
    return out

def plate(name, outline, z0, z1, holes=(), mat=None, col="DRONE", bevel=0.22):
    """Extruded CNC plate with circular cutouts, chamfered edges."""
    bm = bmesh.new()
    vs = [bm.verts.new((x * MM, y * MM, z0 * MM)) for x, y in dedupe(outline)]
    f = bm.faces.new(vs)
    res = bmesh.ops.extrude_face_region(bm, geom=[f])
    up = [v for v in res["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, (z1 - z0) * MM), verts=up)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = obj_from_bm(name, bm, mat, col)
    if holes:
        cutters = bmesh.new()
        zc = ((z0 + z1) / 2) * MM
        dz = (z1 - z0 + 4) * MM
        for x, y, r in holes:
            cyl_bm(cutters, r * MM, r * MM, dz,
                   Matrix.Translation((x * MM, y * MM, zc)), segs=24)
        cob = obj_from_bm(name + "_cut", cutters, None, col)
        boolean_cut(ob, cob)
    bevel_edges(ob, bevel * MM, angle=35)
    shade_smooth(ob, 40)
    return ob

def make_wire(name, pts_mm, radius, mat, col="DRONE", res=24, cyclic=False):
    """Smooth round-profile cable along control points (Bezier, auto handles)."""
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
              col="DRONE", extrude=0.05):
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

# =============================================================================
#  MATERIALS  (Cycles / Principled BSDF, Blender 4.x/5.x socket names)
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
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    return m, nt, b

def mix_color(node):
    """Return (A, B, Result) colour sockets of a Mix node (index-safe)."""
    node.data_type = 'RGBA'
    a = [s for s in node.inputs if s.name == 'A' and s.type == 'RGBA'][0]
    b = [s for s in node.inputs if s.name == 'B' and s.type == 'RGBA'][0]
    out = [s for s in node.outputs if s.name == 'Result' and s.type == 'RGBA'][0]
    return a, b, out

def mat_carbon(name="carbon_twill", scale=1.0):
    """Procedural 2x2 twill-weave carbon fibre, anisotropic + clearcoat."""
    m, nt, b = base_mat(name)
    n = nt.nodes; l = nt.links
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, radians(45))
    s = 290.0 * scale
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
    ramp.color_ramp.elements[1].color = (0.052, 0.057, 0.065, 1)
    l.new(mout, ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    set_in(b, "Metallic", 0.15)
    set_in(b, "Roughness", 0.32)
    set_in(b, "Anisotropic", 0.7)
    rotm = n.new("ShaderNodeMath"); rotm.operation = 'MULTIPLY'
    l.new(chk.outputs["Fac"], rotm.inputs[0])
    rotm.inputs[1].default_value = 0.25
    if b.inputs.get("Anisotropic Rotation"):
        l.new(rotm.outputs["Value"], b.inputs["Anisotropic Rotation"])
    set_in(b, "Coat Weight", 0.5)
    set_in(b, "Coat Roughness", 0.12)
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    bump.inputs["Distance"].default_value = 0.00002
    l.new(mout, bump.inputs["Height"])
    l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m

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

def mat_tpu(name, color):
    """3D-printed TPU: matte rubber with visible layer lines."""
    m, nt, b = base_mat(name)
    n = nt.nodes; l = nt.links
    set_in(b, "Base Color", color)
    set_in(b, "Roughness", 0.55)
    set_in(b, "Sheen Weight", 0.3)
    tc = n.new("ShaderNodeTexCoord")
    wave = n.new("ShaderNodeTexWave")
    wave.wave_type = 'BANDS'; wave.bands_direction = 'Z'
    wave.inputs["Scale"].default_value = 2600.0
    l.new(tc.outputs["Object"], wave.inputs["Vector"])
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    bump.inputs["Distance"].default_value = 0.00003
    l.new(wave.outputs["Color"], bump.inputs["Height"])
    l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m

def mat_strap(name):
    m, nt, b = base_mat(name)
    n = nt.nodes; l = nt.links
    set_in(b, "Base Color", (0.02, 0.02, 0.022, 1))
    set_in(b, "Roughness", 0.8)
    set_in(b, "Sheen Weight", 0.6)
    tc = n.new("ShaderNodeTexCoord")
    w1 = n.new("ShaderNodeTexWave"); w1.wave_type = 'BANDS'; w1.bands_direction = 'X'
    w1.inputs["Scale"].default_value = 1400.0
    w2 = n.new("ShaderNodeTexWave"); w2.wave_type = 'BANDS'; w2.bands_direction = 'Z'
    w2.inputs["Scale"].default_value = 350.0
    l.new(tc.outputs["Object"], w1.inputs["Vector"])
    l.new(tc.outputs["Object"], w2.inputs["Vector"])
    mx = n.new("ShaderNodeMix")
    ma, mb, mout = mix_color(mx)
    mx.inputs["Factor"].default_value = 0.5
    l.new(w1.outputs["Color"], ma)
    l.new(w2.outputs["Color"], mb)
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.5
    bump.inputs["Distance"].default_value = 0.00004
    l.new(mout, bump.inputs["Height"])
    l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m

def mat_floor(name):
    m, nt, b = base_mat(name)
    n = nt.nodes; l = nt.links
    set_in(b, "Base Color", (0.012, 0.013, 0.015, 1))
    set_in(b, "Coat Weight", 0.4)
    set_in(b, "Coat Roughness", 0.25)
    tc = n.new("ShaderNodeTexCoord")
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 18.0
    noise.inputs["Detail"].default_value = 6.0
    l.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (0.28, 0.28, 0.28, 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (0.45, 0.45, 0.45, 1)
    l.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Roughness"])
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.04
    bump.inputs["Distance"].default_value = 0.0004
    l.new(noise.outputs["Fac"], bump.inputs["Height"])
    l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m

def build_materials():
    MATS["carbon"]      = mat_carbon()
    MATS["carbon_fine"] = mat_carbon("carbon_fine", scale=1.6)
    MATS["alu_gun"]     = mat_simple("alu_gunmetal", (0.16, 0.17, 0.19, 1), 0.32, 1.0, coat=0.15, aniso=0.4)
    MATS["alu_bright"]  = mat_simple("alu_machined", (0.62, 0.64, 0.66, 1), 0.22, 1.0, aniso=0.6)
    MATS["alu_orange"]  = mat_simple("alu_orange", ACCENT, 0.3, 1.0, coat=0.2)
    MATS["steel"]       = mat_simple("steel_screw", (0.28, 0.28, 0.29, 1), 0.38, 1.0)
    MATS["steel_dark"]  = mat_simple("steel_black", (0.06, 0.06, 0.065, 1), 0.42, 1.0)
    MATS["copper"]      = mat_simple("copper_coil", (0.72, 0.32, 0.12, 1), 0.28, 1.0, coat=0.6)
    MATS["magnet"]      = mat_simple("magnet", (0.04, 0.04, 0.045, 1), 0.5, 0.8)
    MATS["pcb"]         = mat_simple("pcb_mask", (0.012, 0.02, 0.014, 1), 0.45, 0.0, coat=0.35, coat_r=0.15)
    MATS["pcb_black"]   = mat_simple("pcb_black", (0.015, 0.015, 0.017, 1), 0.4, 0.0, coat=0.35)
    MATS["chip"]        = mat_simple("chip", (0.02, 0.02, 0.022, 1), 0.35)
    MATS["gold"]        = mat_simple("gold_pad", (0.85, 0.6, 0.2, 1), 0.25, 1.0)
    MATS["solder"]      = mat_simple("solder", (0.55, 0.56, 0.58, 1), 0.28, 1.0)
    MATS["prop"]        = mat_simple("prop_poly", (0.03, 0.032, 0.038, 1), 0.14, 0.0,
                                     coat=0.5, transmission=0.35, ior=1.49)
    MATS["tpu"]         = mat_tpu("tpu_orange", ACCENT)
    MATS["tpu_black"]   = mat_tpu("tpu_black", (0.02, 0.02, 0.022, 1))
    MATS["wire_blk"]    = mat_simple("wire_black", (0.015, 0.015, 0.016, 1), 0.42, sheen=0.2)
    MATS["wire_red"]    = mat_simple("wire_red", (0.42, 0.01, 0.01, 1), 0.42, sheen=0.2)
    MATS["xt60"]        = mat_simple("xt60_nylon", (0.75, 0.55, 0.02, 1), 0.45)
    MATS["lipo"]        = mat_simple("lipo_wrap", (0.028, 0.03, 0.034, 1), 0.22, 0.0, coat=0.6, coat_r=0.1)
    MATS["foam"]        = mat_simple("foam_pad", (0.015, 0.015, 0.016, 1), 0.95)
    MATS["strap"]       = mat_strap("strap_weave")
    MATS["glass"]       = mat_simple("lens_glass", (0.35, 0.4, 0.9, 1), 0.03, 0.0,
                                     coat=1.0, coat_r=0.03, transmission=1.0, ior=1.5)
    MATS["cam_body"]    = mat_simple("cam_body", (0.03, 0.03, 0.032, 1), 0.4, 0.3)
    MATS["antenna_cap"] = mat_simple("antenna_cap", (0.9, 0.32, 0.05, 1), 0.3, 0.0,
                                     transmission=0.7, ior=1.45, coat=0.4)
    MATS["white_nylon"] = mat_simple("white_nylon", (0.8, 0.8, 0.78, 1), 0.5)
    MATS["cap_sleeve"]  = mat_simple("cap_sleeve", (0.16, 0.05, 0.02, 1), 0.35, coat=0.5)
    MATS["led"]         = mat_simple("led_die", ACCENT, 0.2, emis=ACCENT, emis_str=40)
    MATS["led_grn"]     = mat_simple("led_grn", (0.1, 1, 0.2, 1), 0.2, emis=(0.1, 1, 0.2, 1), emis_str=25)
    MATS["led_blu"]     = mat_simple("led_blu", (0.1, 0.3, 1, 1), 0.2, emis=(0.1, 0.3, 1, 1), emis_str=25)
    MATS["text_w"]      = mat_simple("text_white", (0.85, 0.86, 0.88, 1), 0.4)
    MATS["text_o"]      = mat_simple("text_orange", ACCENT, 0.4)
    MATS["floor"]       = mat_floor("studio_floor")
    MATS["backdrop"]    = mat_simple("backdrop", (0.012, 0.013, 0.016, 1), 0.9)

# =============================================================================
#  HARDWARE — button-head screws & nuts (true M3 proportions)
# =============================================================================
def make_screw(name, loc, length=6.0, head_d=5.7, head_h=1.65, thread_d=3.0,
               up=True, mat=None, col="DRONE"):
    """M3 button-head cap screw with hex socket. up=True → head on top."""
    mat = mat or MATS["steel_dark"]
    bm = bmesh.new()
    ret = bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12,
                                    radius=head_d / 2 * MM)
    bmesh.ops.scale(bm, vec=(1, 1, head_h * 2 / head_d), verts=ret["verts"])
    verts_del = [v for v in ret["verts"] if v.co.z < 0.00002]
    bmesh.ops.delete(bm, geom=verts_del, context='VERTS')
    cyl_bm(bm, head_d / 2 * MM, head_d / 2 * MM, 0.35 * MM,
           Matrix.Translation((0, 0, 0.1 * MM)), segs=24)
    cyl_bm(bm, thread_d / 2 * MM, thread_d / 2 * MM, length * MM,
           Matrix.Translation((0, 0, -length / 2 * MM)), segs=18)
    ob = obj_from_bm(name, bm, mat, col)
    ob.location = loc
    if not up:
        ob.rotation_euler = Euler((pi, 0, 0))
    shade_smooth(ob, 35)
    hx = add_cyl(name + "_hex", 1.28, 1.3, (0, 0, 0), MATS["magnet"], segs=6, col=col)
    hx.parent = ob
    hx.location = (0, 0, (head_h - 0.55) * MM)
    return ob

def make_nut(name, loc, w=5.5, h=2.4, mat=None, col="DRONE", nylon=False):
    mat = mat or MATS["steel"]
    bm = bmesh.new()
    cyl_bm(bm, w / sqrt(3) * MM, w / sqrt(3) * MM, h * MM, segs=6)
    ob = obj_from_bm(name, bm, mat, col)
    ob.location = loc
    if nylon:
        ring = add_cyl(name + "_ny", w / sqrt(3) * 0.8, h * 0.4, (0, 0, 0),
                       MATS["white_nylon"], segs=18, col=col)
        ring.parent = ob
        ring.location = (0, 0, h * 0.55 * MM)
    return ob

# =============================================================================
#  FRAME
# =============================================================================
def arm_outline():
    mx = P["motor_xy"] * sqrt(2)          # motor centre distance along arm
    pts = [(12, 8), (12, -8), (60, -7), (mx - 22, -8.6)]
    for k in range(21):                    # motor-end disc, r = 15
        a = -radians(96) + radians(192) * k / 20
        pts.append((mx + 15 * cos(a), 15 * sin(a)))
    pts.append((60, 7))
    radii = [3, 3, 8, 4] + [0] * 21 + [8]
    return fillet2d(pts, radii, segs=4)

def build_arm(idx):
    ang = radians(45 + 90 * idx)
    mx = P["motor_xy"] * sqrt(2)
    holes = [(mx, 0, 4.0)]
    for dx in (-P["motor_holes"] / 2, P["motor_holes"] / 2):
        for dy in (-P["motor_holes"] / 2, P["motor_holes"] / 2):
            holes.append((mx + dx, dy, 1.6))
    holes += [(20, 0, 1.6), (32, 0, 1.6)]
    ob = plate(f"arm_{idx}", arm_outline(), P["z_arm"], P["z_arm"] + P["arm_thick"],
               holes=holes, mat=MATS["carbon"])
    ob.rotation_euler = Euler((0, 0, ang))
    return ob

def octo_outline(L, W, ch):
    h, w = L / 2, W / 2
    pts = [(-w, h - ch), (-w + ch, h), (w - ch, h), (w, h - ch),
           (w, -h + ch), (w - ch, -h), (-w + ch, -h), (-w, -h + ch)]
    return fillet2d(pts, 2.5, segs=4)

def clamp_holes():
    hs = []
    for sx in (1, -1):
        for sy in (1, -1):
            for d in (20, 32):
                r = d / sqrt(2)
                hs.append((sx * r, sy * r, 1.6))
    return hs

def build_plates():
    stack = [(sx * P["stack_pitch"] / 2, sy * P["stack_pitch"] / 2, 1.6)
             for sx in (1, -1) for sy in (1, -1)]
    stand = [(x, y, 1.6) for x, y in P["standoffs"]]
    plate("bottom_plate", octo_outline(P["bottom_L"], P["bottom_W"], 15),
          0.0, P["plate_thick"],
          holes=clamp_holes() + stack + stand, mat=MATS["carbon"])
    plate("main_plate", octo_outline(P["bottom_L"], P["bottom_W"], 15),
          P["z_main"], P["z_main"] + P["plate_thick"],
          holes=clamp_holes() + stack + stand + [(0, 44, 6.0)],
          mat=MATS["carbon"])
    plate("top_plate", octo_outline(P["top_L"], P["top_W"], 12),
          P["z_top"], P["z_top_t"],
          holes=stand + [(0, 46, 1.6), (0, 38, 1.6)],
          mat=MATS["carbon"])
    for i, (x, y, r) in enumerate(clamp_holes()):
        make_screw(f"clamp_screw_{i}",
                   (x * MM, y * MM, (P["z_main"] + P["plate_thick"]) * MM), length=9)

def build_standoffs():
    for i, (x, y) in enumerate(P["standoffs"]):
        add_cyl(f"standoff_{i}", P["standoff_d"] / 2, P["standoff_h"],
                (x * MM, y * MM, (P["z_deck"] + P["standoff_h"] / 2) * MM),
                MATS["alu_gun"], segs=24)
        make_screw(f"so_top_{i}", (x * MM, y * MM, P["z_top_t"] * MM), length=5)
        make_screw(f"so_bot_{i}", (x * MM, y * MM, P["z_main"] * MM), length=5, up=False)

def build_camera_cage():
    """Two carbon side plates + orange alu cross brace holding the FPV cam."""
    for sx in (1, -1):
        outline = fillet2d([(30, 0), (57, 0), (53, 25), (34, 25)], [2, 5, 4, 2], segs=4)
        ob = plate(f"cam_side_{'R' if sx > 0 else 'L'}", outline,
                   0, P["plate_thick"],
                   holes=[(44, 13, 1.1)], mat=MATS["carbon_fine"], bevel=0.18)
        ob.rotation_euler = Euler((pi / 2, 0, pi / 2))
        ob.location = ((11.5 if sx > 0 else -13.5) * MM, 0, P["z_deck"] * MM)
    add_cyl("cage_brace", 2.0, 26.0, (0, 33 * MM, 31 * MM),
            MATS["alu_orange"], rot=(0, pi / 2, 0), segs=24)

# =============================================================================
#  MOTORS  (2306.5 brushless: lathe-spun bell, copper windings, hardware)
# =============================================================================
def spin_profile(name, profile_mm, loc, mat, segs=64, col="DRONE", smooth=35):
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
    shade_smooth(ob, smooth)
    return ob

def build_motor(idx, sx, sy):
    z0 = P["z_motor"]
    cx, cy = sx * P["motor_xy"], sy * P["motor_xy"]
    loc = Vector((cx * MM, cy * MM, z0 * MM))
    R = P["bell_d"] / 2
    a0 = atan2(cy, cx)
    # --- machined base -----------------------------------------------------
    base_prof = [(3.2, 0.0), (13.9, 0.0), (13.9, 1.8), (12.4, 2.2),
                 (12.4, 4.6), (9.0, 5.2), (5.0, 5.2), (3.2, 3.4), (3.2, 0.0)]
    spin_profile(f"m{idx}_base", base_prof, loc, MATS["alu_gun"])
    add_cyl(f"m{idx}_stator", 11.6, 3.4, loc + Vector((0, 0, 7.0 * MM)),
            MATS["magnet"], segs=48)
    # --- copper windings (12 poles, slight cant) ---------------------------
    for p in range(P["n_poles"]):
        a = 2 * pi * p / P["n_poles"]
        px = cx + 10.4 * cos(a); py = cy + 10.4 * sin(a)
        ob = add_cyl(f"m{idx}_coil_{p}", 2.0, 4.6,
                     (px * MM, py * MM, (z0 + 7.0) * MM), MATS["copper"], segs=14)
        ob.rotation_euler = Euler((0, radians(12), a))
    # --- bell (skirt → machined ring → domed top with cooling slots) -------
    bell_prof = [(3.2, 21.0), (5.5, 21.0), (9.5, 19.6), (12.6, 18.2),
                 (R, 16.6), (R, 5.6), (R - 0.7, 5.0), (R - 1.4, 5.6),
                 (R - 1.4, 15.4), (11.6, 16.9), (5.0, 18.6), (3.2, 18.6)]
    bell = spin_profile(f"m{idx}_bell", bell_prof, loc, MATS["steel_dark"], segs=72)
    spin_profile(f"m{idx}_rim", [(R + 0.01, 5.4), (R + 0.01, 7.0),
                                 (R - 0.5, 7.4), (R - 0.5, 5.8), (R + 0.01, 5.4)],
                 loc, MATS["alu_bright"], segs=72)
    bmcut = bmesh.new()
    for k in range(9):
        a = 2 * pi * k / 9
        m = (Matrix.Translation(loc) @ Matrix.Rotation(a, 4, 'Z') @
             Matrix.Translation((8.6 * MM, 0, 19.4 * MM)) @
             Matrix.Rotation(radians(25), 4, 'X') @ Matrix.Rotation(radians(18), 4, 'Y'))
        bmc = bmesh.new()
        bmesh.ops.create_cube(bmc, size=1)
        bmesh.ops.scale(bmc, vec=(5.2 * MM, 2.0 * MM, 3.0 * MM), verts=bmc.verts)
        bmesh.ops.transform(bmc, matrix=m, verts=bmc.verts)
        me_t = bpy.data.meshes.new("mt"); bmc.to_mesh(me_t); bmc.free()
        bmcut.from_mesh(me_t); bpy.data.meshes.remove(me_t)
    cut = obj_from_bm(f"m{idx}_slotcut", bmcut, None)
    boolean_cut(bell, cut)
    shade_smooth(bell, 35)
    spin_profile(f"m{idx}_mag", [(R - 1.45, 6.0), (R - 1.45, 14.0),
                                 (R - 2.6, 14.0), (R - 2.6, 6.0), (R - 1.45, 6.0)],
                 loc, MATS["magnet"], segs=48)
    # shaft + washer + orange low-profile M5 prop nut (above the prop hub)
    add_cyl(f"m{idx}_shaft", 2.5, 19.0, loc + Vector((0, 0, 24 * MM)),
            MATS["alu_bright"], segs=24)
    zn = z0 + 21.0 + P["hub_h"]
    add_cyl(f"m{idx}_washer", 4.6, 0.8, (cx * MM, cy * MM, (zn + 0.4) * MM),
            MATS["alu_bright"], segs=24)
    nut = add_cyl(f"m{idx}_propnut", 4.0, 4.6, (cx * MM, cy * MM, (zn + 3.1) * MM),
                  MATS["alu_orange"], segs=6, smooth=False)
    bevel_edges(nut, 0.5 * MM, 30, 2)
    # spec label printed on the arm next to the motor
    make_text(f"m{idx}_lbl", "KR 2306.5  1750KV", 2.6,
              ((cx - 30 * cos(a0)) * MM, (cy - 30 * sin(a0)) * MM,
               (P["z_arm"] + P["arm_thick"] + 0.06) * MM),
              rot=(0, 0, a0), mat=MATS["text_w"], extrude=0.03)
    # mounting screws from under the arm
    for dx in (-8, 8):
        for dy in (-8, 8):
            v = Vector((dx, dy, 0)); v.rotate(Euler((0, 0, a0)))
            make_screw(f"m{idx}_screw_{dx}_{dy}",
                       ((cx + v.x) * MM, (cy + v.y) * MM, P["z_arm"] * MM),
                       length=6, up=False)
    # three phase wires along the arm to the ESC corner pads
    z_pad = P["z_deck"] + 3.8
    for w in range(3):
        off = (w - 1) * 2.4
        pv = Vector((-off * sin(a0), off * cos(a0), 0))
        p_start = Vector((cx - 12.5 * cos(a0), cy - 12.5 * sin(a0), z0 + 4.5))
        p_mid   = Vector((cx * 0.55, cy * 0.55, z0 + 3.6))
        p_mid2  = Vector((cx * 0.32, cy * 0.32, P["z_deck"] + 3.2))
        p_end   = Vector((sx * (11.2 + 3.1 * w), sy * 15.9, z_pad))
        make_wire(f"m{idx}_pw_{w}",
                  [tuple(p_start + pv), tuple(p_mid + pv), tuple(p_mid2 + pv * 0.4),
                   tuple(p_end)], 0.55, MATS["wire_blk"])

# =============================================================================
#  PROPELLER — parametric tri-blade, NACA section, geometric-pitch twist
# =============================================================================
def naca_section(x, t, m=0.055, p=0.42):
    """Return (camber, half-thickness) at chord fraction x (both x chord)."""
    yt = 5 * t * (0.2969 * sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 +
                  0.2843 * x ** 3 - 0.1036 * x ** 4)
    if x < p:
        yc = m / p ** 2 * (2 * p * x - x ** 2)
    else:
        yc = m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x ** 2)
    return yc, yt

def chord_at(f):
    c = 7.5 + 8.8 * sin(pi * (f ** 0.78) * 0.94)
    if f > 0.88:
        c *= sqrt(max(1 - ((f - 0.88) / 0.12) ** 2 * 0.97, 0.03))
    return c

def blade_grid(hand):
    """Vertex rings for one blade. hand=+1 → CCW prop, -1 → CW (mirrored)."""
    R = P["prop_diam"] / 2
    r0 = 6.4
    NS, NC = 34, 22
    rings = []
    for i in range(NS + 1):
        f = i / NS
        r = r0 + (R - r0) * f
        chord = chord_at(f)
        thick = min(0.22, (1.5 - 0.8 * f) / chord)
        theta = min(atan(P["prop_pitch"] / (2 * pi * r)) * 0.92, radians(62))
        sweep = 3.5 * f * f
        axis_off = 0.5 - 0.18 * min(f / 0.35, 1.0)
        ring = []
        for side in (0, 1):
            for j in range(NC + 1):
                if side == 0:
                    xf = j / NC; zsig = 1
                else:
                    if j == 0 or j == NC:
                        continue
                    xf = 1 - j / NC; zsig = -1
                yc, yt = naca_section(min(max(xf, 1e-4), 1.0), thick)
                cxs = (xf - axis_off) * chord
                czs = (yc + zsig * yt) * chord
                yy = cxs * cos(theta) + czs * sin(theta)
                zz = -cxs * sin(theta) + czs * cos(theta) + 3.5
                ring.append(Vector((r, hand * (-yy - sweep), zz)))
        rings.append(ring)
    return rings

def fan_cap(bm, verts, reverse=False):
    ctr = Vector((0, 0, 0))
    for v in verts:
        ctr += v.co
    ctr /= len(verts)
    vc = bm.verts.new(ctr)
    n = len(verts)
    for k in range(n):
        a, b = verts[k], verts[(k + 1) % n]
        try:
            bm.faces.new((a, b, vc) if not reverse else (b, a, vc))
        except ValueError:
            pass

def build_prop(idx, sx, sy, hand, phase_deg):
    cx, cy = sx * P["motor_xy"], sy * P["motor_xy"]
    zh = P["z_motor"] + 21.0
    bm = bmesh.new()
    for b in range(P["prop_blades"]):
        ang = 2 * pi * b / P["prop_blades"]
        rot = Matrix.Rotation(ang, 4, 'Z')
        rings = blade_grid(hand)
        first = prev = None
        for ring in rings:
            vs = [bm.verts.new(rot @ (v * MM)) for v in ring]
            if prev:
                n = len(vs)
                for k in range(n):
                    try:
                        bm.faces.new((prev[k], prev[(k + 1) % n],
                                      vs[(k + 1) % n], vs[k]))
                    except ValueError:
                        pass
            else:
                first = vs
            prev = vs
        fan_cap(bm, prev)
        fan_cap(bm, first, reverse=True)
    cyl_bm(bm, P["hub_d"] / 2 * MM, P["hub_d"] / 2 * 0.95 * MM, P["hub_h"] * MM,
           Matrix.Translation((0, 0, P["hub_h"] / 2 * MM)), segs=40)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = obj_from_bm(f"prop_{idx}", bm, MATS["prop"])
    bore = add_cyl(f"prop_{idx}_bore", 2.55, 12, (0, 0, P["hub_h"] / 2 * MM),
                   None, segs=24)
    boolean_cut(ob, bore)
    shade_smooth(ob, 46)
    ob.location = (cx * MM, cy * MM, zh * MM)
    ob.rotation_euler = Euler((0, 0, radians(phase_deg)))
    return ob

# =============================================================================
#  ELECTRONICS STACK  (4-in-1 ESC + F7 FC + digital VTX)
# =============================================================================
def pcb_with_pads(name, size, z_mm, mat):
    b = P["stack_pitch"] / 2
    return plate(name, fillet2d([(-size / 2, -size / 2), (size / 2, -size / 2),
                                 (size / 2, size / 2), (-size / 2, size / 2)], 4.5, 5),
                 z_mm, z_mm + 1.5,
                 holes=[(sx * b, sy * b, 1.55) for sx in (1, -1) for sy in (1, -1)],
                 mat=mat, bevel=0.12)

def build_stack():
    zd = P["z_deck"]
    bq = P["stack_pitch"] / 2
    # ---- 4-in-1 ESC 60A ---------------------------------------------------
    z_esc = zd + 2.0
    pcb_with_pads("esc_board", P["board"], z_esc, MATS["pcb_black"])
    for i, (sx, sy) in enumerate([(1, 1), (1, -1), (-1, 1), (-1, -1)]):
        for k in range(2):
            add_box(f"esc_fet_{i}_{k}", 6.2 * MM, 5.0 * MM, 1.6 * MM,
                    (sx * (9.5 - k * 7.2) * MM, sy * 11.0 * MM, (z_esc + 2.3) * MM),
                    MATS["chip"], bevel=0.15 * MM)
        for w in range(3):
            px, py = sx * (11.2 + 3.1 * w), sy * 15.9
            add_cyl(f"esc_pad_{i}_{w}", 1.2, 0.3, (px * MM, py * MM, (z_esc + 1.6) * MM),
                    MATS["gold"], segs=16)
            add_cyl(f"esc_blob_{i}_{w}", 0.95, 1.0, (px * MM, py * MM, (z_esc + 2.0) * MM),
                    MATS["solder"], segs=12)
    add_box("esc_mcu", 7 * MM, 7 * MM, 1.2 * MM, (0, -6 * MM, (z_esc + 2.1) * MM),
            MATS["chip"], bevel=0.12 * MM)
    for i, (sx, sy) in enumerate([(1, 1), (1, -1), (-1, 1), (-1, -1)]):
        add_cyl(f"gummy_{i}", 3.3, 2.0, (sx * bq * MM, sy * bq * MM, (zd + 1.0) * MM),
                MATS["tpu_black"], segs=20)
        add_cyl(f"gummy2_{i}", 3.3, 2.5, (sx * bq * MM, sy * bq * MM, (z_esc + 2.8) * MM),
                MATS["tpu_black"], segs=20)
    # ---- F7 flight controller ---------------------------------------------
    z_fc = z_esc + 4.2
    pcb_with_pads("fc_board", P["board"], z_fc, MATS["pcb"])
    add_box("fc_mcu", 10 * MM, 10 * MM, 1.1 * MM, (0, 2 * MM, (z_fc + 2.05) * MM),
            MATS["chip"], bevel=0.12 * MM)
    make_text("fc_mcu_txt", "KR-F722", 1.7, (0, 2 * MM, (z_fc + 2.64) * MM),
              mat=MATS["text_w"], extrude=0.02)
    add_box("fc_gyro", 3 * MM, 3 * MM, 0.9 * MM, (8 * MM, -7 * MM, (z_fc + 1.95) * MM),
            MATS["chip"])
    add_box("fc_usbc", 7.4 * MM, 9 * MM, 3.2 * MM, (-9 * MM, -16.5 * MM, (z_fc + 3.1) * MM),
            MATS["alu_bright"], bevel=0.9 * MM, smooth_deg=25)
    for i in range(4):
        add_box(f"fc_jst_{i}", 5.8 * MM, 3 * MM, 3 * MM,
                ((-9 + i * 6) * MM, P["board"] / 2 * MM - 2.4 * MM, (z_fc + 3.0) * MM),
                MATS["white_nylon"], bevel=0.3 * MM)
    placed = 0
    while placed < 10:
        px, py = random.uniform(-13, 13), random.uniform(-13, 9)
        if abs(px) < 7 and abs(py - 2) < 7:
            continue
        add_box(f"fc_passive_{placed}", 1.6 * MM, 0.9 * MM, 0.5 * MM,
                (px * MM, py * MM, (z_fc + 1.75) * MM), MATS["chip"],
                rot=(0, 0, random.choice([0, pi / 2])))
        placed += 1
    add_cyl("fc_led", 0.8, 0.5, (-6 * MM, -13 * MM, (z_fc + 1.7) * MM), MATS["led_blu"], segs=12)
    add_cyl("fc_led2", 0.8, 0.5, (-3.5 * MM, -13 * MM, (z_fc + 1.7) * MM), MATS["led_grn"], segs=12)
    # ---- digital VTX with finned heatsink ----------------------------------
    z_vtx = z_fc + 4.4
    pcb_with_pads("vtx_board", 30.5, z_vtx, MATS["pcb_black"])
    add_box("vtx_heatsink", 24 * MM, 24 * MM, 2.2 * MM, (0, 0, (z_vtx + 2.6) * MM),
            MATS["alu_gun"], bevel=0.3 * MM)
    for i in range(7):
        add_box(f"vtx_fin_{i}", 24 * MM, 2.0 * MM, 3.4 * MM,
                (0, (-9.6 + i * 3.2) * MM, (z_vtx + 5.0) * MM),
                MATS["alu_gun"], bevel=0.25 * MM)
    make_text("vtx_txt", "KR AIR ONE", 2.4, (0, -13.4 * MM, (z_vtx + 1.58) * MM),
              mat=MATS["text_o"], extrude=0.02)
    # ---- stack bolts + nylon nuts ------------------------------------------
    for i, (sx, sy) in enumerate([(1, 1), (1, -1), (-1, 1), (-1, -1)]):
        x, y = sx * bq * MM, sy * bq * MM
        add_cyl(f"stack_bolt_{i}", 1.5, 19, (x, y, (zd + 8.5) * MM),
                MATS["steel_dark"], segs=16)
        make_nut(f"stack_nut_{i}", (x, y, (z_vtx + 6.3) * MM), w=5.5, h=3.2, nylon=True)
    # ---- 1000 µF low-ESR cap on a TPU saddle at the rear -------------------
    cap_loc = Vector((0, -30 * MM, (zd + 5.5) * MM))
    add_box("cap_saddle", 14 * MM, 10 * MM, 4 * MM, cap_loc + Vector((0, 1 * MM, -3.2 * MM)),
            MATS["tpu"], bevel=1.2 * MM)
    add_cyl("cap_body", 5.0, 21, cap_loc, MATS["cap_sleeve"], rot=(pi / 2, 0, 0), segs=32)
    add_cyl("cap_top", 4.6, 0.8, cap_loc + Vector((0, -10.8 * MM, 0)),
            MATS["alu_bright"], rot=(pi / 2, 0, 0), segs=32)
    make_text("cap_txt", "1000uF 35V", 1.8, cap_loc + Vector((0, -2 * MM, 5.02 * MM)),
              rot=(0, 0, pi / 2), mat=MATS["text_w"], extrude=0.02)
    make_wire("cap_lead_p", [(2.2, -22, zd + 6.5), (4.5, -17.5, zd + 4.4), (5, -15.5, zd + 3.6)],
              0.7, MATS["wire_red"])
    make_wire("cap_lead_n", [(-2.2, -22, zd + 6.5), (-4.5, -17.5, zd + 4.4), (-5, -15.5, zd + 3.6)],
              0.7, MATS["wire_blk"])
    # ---- ELRS receiver ------------------------------------------------------
    add_box("rx_board", 11 * MM, 16 * MM, 2.4 * MM, (12 * MM, -26 * MM, (zd + 4) * MM),
            MATS["pcb"], bevel=0.2 * MM)

# =============================================================================
#  FPV CAMERA  (19 mm digital micro, tilted 25°)
# =============================================================================
def build_fpv_cam():
    tilt = radians(25)
    root = bpy.data.objects.new("fpv_cam_root", None)
    link_obj(root)
    root.location = (0, 44 * MM, 22 * MM)
    root.rotation_euler = Euler((tilt, 0, 0))
    def put(ob, off, rot=None):
        ob.parent = root
        ob.location = Vector(off) * MM
        if rot:
            ob.rotation_euler = Euler(rot)
        return ob
    body = add_box("cam_body", 19 * MM, 14 * MM, 19 * MM, (0, 0, 0),
                   MATS["cam_body"], bevel=1.4 * MM, smooth_deg=30)
    put(body, (0, -3, 0))
    put(add_cyl("cam_barrel", 7.2, 10, (0, 0, 0), MATS["cam_body"], segs=36),
        (0, 9, 0), (pi / 2, 0, 0))
    put(add_cyl("cam_ring", 7.8, 3.2, (0, 0, 0), MATS["alu_orange"], segs=36),
        (0, 12.4, 0), (pi / 2, 0, 0))
    for k in range(24):
        a = 2 * pi * k / 24
        put(add_cyl(f"cam_knurl_{k}", 0.45, 3.0, (0, 0, 0), MATS["alu_orange"], segs=8),
            (7.8 * cos(a), 12.4, 7.8 * sin(a)), (pi / 2, 0, 0))
    put(add_cyl("cam_lens", 5.6, 1.6, (0, 0, 0), MATS["glass"], segs=48),
        (0, 14.2, 0), (pi / 2, 0, 0))
    put(add_cyl("cam_lens_inner", 4.2, 1.0, (0, 0, 0), MATS["magnet"], segs=32),
        (0, 13.6, 0), (pi / 2, 0, 0))
    t = make_text("cam_txt", "KR NANO", 1.6, (0, 0, 0), mat=MATS["text_w"], extrude=0.02)
    put(t, (0, -3, 9.56))
    for sxx in (1, -1):
        sc = make_screw(f"cam_screw_{sxx}", (0, 0, 0), length=4, head_d=4.2, head_h=1.3)
        sc.parent = root
        sc.location = (sxx * 13.5 * MM, 0, 0)
        sc.rotation_euler = Euler((0, sxx * pi / 2, 0))
    make_wire("cam_coax", [(0, 40, 18), (0, 34, 15.5), (0, 24, 17.5), (-3, 20, 20.5),
                           (-3, 17.5, 20.8)], 0.6, MATS["wire_blk"])

# =============================================================================
#  BATTERY  (6S 1300 mAh) + strap + XT60 + leads
# =============================================================================
def build_battery():
    zb = P["z_top_t"] + 3.0
    cy = P["bat_ctr_y"]
    ctr = Vector((0, cy * MM, (zb + P["bat_H"] / 2) * MM))
    yf = cy + P["bat_L"] / 2          # front face y = 23.5
    add_box("bat_pad", 30 * MM, 70 * MM, 3.2 * MM, (0, -17 * MM, (P["z_top_t"] + 1.5) * MM),
            MATS["foam"], bevel=0.8 * MM)
    add_box("battery", P["bat_W"] * MM, P["bat_L"] * MM, P["bat_H"] * MM,
            ctr, MATS["lipo"], bevel=3.2 * MM, smooth_deg=30)
    add_box("bat_stripe", (P["bat_W"] + 0.7) * MM, 22 * MM, (P["bat_H"] + 0.7) * MM,
            ctr + Vector((0, -24 * MM, 0)), MATS["text_o"], bevel=3.0 * MM, smooth_deg=30)
    for sxx, rz in ((1, pi / 2), (-1, -pi / 2)):
        make_text(f"bat_txt_a{sxx}", "KRAFTCELL", 5.5,
                  ctr + Vector((sxx * (P["bat_W"] / 2 + 0.75) * MM, -24 * MM, 6 * MM)),
                  rot=(pi / 2, 0, rz), mat=MATS["text_w"], extrude=0.06)
        make_text(f"bat_txt_b{sxx}", "6S 1300mAh 120C", 3.0,
                  ctr + Vector((sxx * (P["bat_W"] / 2 + 0.75) * MM, -24 * MM, -2.5 * MM)),
                  rot=(pi / 2, 0, rz), mat=MATS["text_w"], extrude=0.06)
    # --- battery strap: flat ribbon swept around battery + top plate --------
    prof = bpy.data.curves.new("strap_prof", 'CURVE')
    prof.dimensions = '2D'
    sp = prof.splines.new('POLY')
    sp.points.add(3)
    w, t = 8.0 * MM, 0.75 * MM
    for pt, (x, y) in zip(sp.points, [(-w, -t), (w, -t), (w, t), (-w, t)]):
        pt.co = (x, y, 0, 1)
    sp.use_cyclic_u = True
    prof_ob = bpy.data.objects.new("strap_prof", prof)
    link_obj(prof_ob, "HELPERS")
    cu = bpy.data.curves.new("strap", 'CURVE')
    cu.dimensions = '3D'; cu.resolution_u = 32
    cu.bevel_mode = 'OBJECT'; cu.bevel_object = prof_ob
    cu.use_fill_caps = True
    sp = cu.splines.new('BEZIER')
    hw = P["bat_W"] / 2 + 1.6
    z_lo = P["z_top"] - 1.6
    z_hi = zb + P["bat_H"] + 1.6
    ys = -20.0
    ring = [(hw + 2.5, ys, z_lo + 8), (hw + 3.5, ys, (z_lo + z_hi) / 2),
            (hw + 2.5, ys, z_hi - 8), (hw - 6, ys, z_hi + 1.2), (0, ys, z_hi + 2.2),
            (-hw + 6, ys, z_hi + 1.2), (-hw - 2.5, ys, z_hi - 8),
            (-hw - 3.5, ys, (z_lo + z_hi) / 2), (-hw - 2.5, ys, z_lo + 8),
            (-hw + 6, ys, z_lo - 1.4), (0, ys, z_lo - 2.4), (hw - 6, ys, z_lo - 1.4)]
    sp.bezier_points.add(len(ring) - 1)
    for bp, p in zip(sp.bezier_points, ring):
        bp.co = Vector(p) * MM
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    sp.use_cyclic_u = True
    strap = bpy.data.objects.new("bat_strap", cu)
    strap.data.materials.append(MATS["strap"])
    link_obj(strap)
    add_box("strap_buckle", 4 * MM, 11 * MM, 18 * MM,
            ((hw + 4.2) * MM, ys * MM, (z_lo + z_hi) / 2 * MM),
            MATS["alu_gun"], bevel=0.8 * MM)
    # --- mated XT60 pair beside the stack, leads with natural sag -----------
    xt = Vector((13 * MM, 22 * MM, 17 * MM))
    b1 = add_box("xt60_f", 15.5 * MM, 8.2 * MM, 8.2 * MM, xt, MATS["xt60"],
                 rot=(0, 0, pi / 2), bevel=0.7 * MM)
    b2 = add_box("xt60_m", 15 * MM, 7.6 * MM, 7.6 * MM, (0, 0, 0), MATS["xt60"],
                 bevel=0.6 * MM)
    b2.parent = b1
    b2.location = (-14 * MM, 0, 0)
    make_wire("bat_lead_r", [(6, yf, 50), (11, yf + 4, 38), (14.5, yf + 6.5, 24),
                             (15, yf + 6.8, 18)], 1.7, MATS["wire_red"])
    make_wire("bat_lead_b", [(-1, yf, 48), (6, yf + 5, 36), (11.5, yf + 7.5, 24),
                             (11, yf + 6.8, 18)], 1.7, MATS["wire_blk"])
    make_wire("esc_pig_r", [(4, -17, 12.8), (10, -8, 13.5), (15, -1, 15.5), (15, 0.8, 16.8)],
              1.7, MATS["wire_red"])
    make_wire("esc_pig_b", [(-4, -17, 12.8), (6, -6, 13.0), (11, -1, 15.0), (11, 0.8, 16.8)],
              1.7, MATS["wire_blk"])
    # balance lead tucked along the left flank
    make_wire("bal_lead", [(-8, yf, 46), (-21.5, yf - 8, 44), (-22.5, -2, 50)],
              1.1, MATS["wire_blk"])
    add_box("bal_jst", 8 * MM, 6 * MM, 4 * MM, (-22.5 * MM, -8 * MM, 51 * MM),
            MATS["white_nylon"], rot=(0, 0, pi / 2), bevel=0.4 * MM)

# =============================================================================
#  VTX ANTENNA (RHCP lollipop on TPU mount), RX antenna, LED bar, HD cam
# =============================================================================
def build_antenna():
    add_box("ant_mount", 30 * MM, 8 * MM, 9 * MM,
            (0, -56.5 * MM, (P["z_top_t"] + 3.5) * MM), MATS["tpu"], bevel=2.2 * MM,
            rot=(radians(-8), 0, 0))
    d = Vector((0, -sin(radians(38)), cos(radians(38))))
    p0 = Vector((0, -57, P["z_top_t"] + 5))
    pts = [tuple(p0 + d * t) for t in (0, 18, 36, 54)]
    make_wire("ant_coax", pts, 1.35, MATS["wire_blk"])
    tip = p0 + d * 56
    head = add_cyl("ant_head", 11.0, 7.5, tuple(tip * MM), MATS["antenna_cap"],
                   rot=(radians(38), 0, 0), segs=40)
    bevel_edges(head, 1.8 * MM, 25, 3)
    shade_smooth(head, 40)
    for k in range(3):
        a = 2 * pi * k / 3
        lobe = add_cyl(f"ant_lobe_{k}", 3.6, 0.9, (0, 0, 0), MATS["copper"], segs=24)
        lobe.parent = head
        lobe.location = (5.2 * cos(a) * MM, 5.2 * sin(a) * MM, 0.5 * MM)
        lobe.rotation_euler = Euler((radians(30) * sin(a), radians(30) * cos(a), 0))
    add_cyl("ant_sma", 3.1, 8, tuple((p0 + d * 3) * MM), MATS["gold"],
            rot=(radians(38), 0, 0), segs=6, smooth=False)
    # ELRS dipole angled out behind the battery
    make_wire("rx_ant_coax", [(12, -32, 14), (14, -48, 20), (12, -62, 36)],
              0.55, MATS["wire_blk"])
    axis = Vector((0.139, -0.654, 0.743))
    base = Vector((12, -65, 40))
    c1 = base + axis * 20
    add_cyl("rx_ant_tube", 1.0, 40, tuple(c1 * MM), MATS["tpu_black"],
            rot=(radians(42), 0, radians(12)), segs=14)
    c2 = base + axis * 47
    add_cyl("rx_ant_tip", 1.3, 14, tuple(c2 * MM), MATS["tpu"],
            rot=(radians(42), 0, radians(12)), segs=14)

def build_led_bar():
    add_box("led_bar", 26 * MM, 2 * MM, 7 * MM, (0, -72.6 * MM, 4.0 * MM),
            MATS["pcb_black"], bevel=0.3 * MM)
    for i in range(4):
        add_box(f"led_{i}", 4 * MM, 1.2 * MM, 4 * MM,
                ((-9 + i * 6) * MM, -73.4 * MM, 4.0 * MM), MATS["led"])

def build_hdcam():
    """Naked HD action cam in a printed TPU cradle on the nose."""
    add_box("hd_mount", 30 * MM, 26 * MM, 9 * MM, (0, 41.5 * MM, 40.2 * MM),
            MATS["tpu"], bevel=2.5 * MM, smooth_deg=30)
    tilt = radians(22)
    root = bpy.data.objects.new("hdcam_root", None)
    link_obj(root)
    root.location = (0, 42 * MM, 45 * MM)
    root.rotation_euler = Euler((tilt, 0, 0))
    def put(ob, off, rot=None):
        ob.parent = root
        ob.location = Vector(off) * MM
        if rot:
            ob.rotation_euler = Euler(rot)
        return ob
    put(add_box("hd_body", 27 * MM, 15 * MM, 22 * MM, (0, 0, 0), MATS["cam_body"],
                bevel=2.2 * MM, smooth_deg=30), (0, 0, 5))
    lens = add_cyl("hd_lens_sq", 8.5, 5, (0, 0, 0), MATS["cam_body"], segs=4, smooth=False)
    put(lens, (0, 8.5, 8), (pi / 2, radians(45), 0))
    bevel_edges(lens, 1.2 * MM, 25, 2)
    put(add_cyl("hd_glass", 6.2, 1.4, (0, 0, 0), MATS["glass"], segs=42),
        (0, 11.6, 8), (pi / 2, 0, 0))
    t = make_text("hd_txt", "KR CAM 4K", 2.0, (0, 0, 0), mat=MATS["text_w"], extrude=0.02)
    put(t, (0, 0, 16.15))

# =============================================================================
#  STUDIO — floor, walls, softboxes, cameras
# =============================================================================
def build_studio():
    col = "STUDIO"
    add_box("floor", 6.0, 6.0, 0.02, (0, 0, -0.01), MATS["floor"], col=col)
    add_box("wall_n", 6.0, 0.05, 3.0, (0, -1.9, 1.2), MATS["backdrop"], col=col)
    add_box("wall_s", 6.0, 0.05, 3.0, (0, 1.9, 1.2), MATS["backdrop"], col=col)
    add_box("wall_w", 0.05, 6.0, 3.0, (-1.9, 0, 1.2), MATS["backdrop"], col=col)
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
    area("key",   0.9, 0.9,  ( 0.55,  0.75, 0.85), (0, 0, 0.04), 60, (1.0, 0.97, 0.92))
    area("fill",  0.9, 0.9,  (-0.85,  0.55, 0.35), (0, 0, 0.05), 14, (0.9, 0.94, 1.0))
    area("rim_l", 0.15, 1.4, (-0.75, -0.85, 0.55), (0, 0, 0.05), 38, (0.75, 0.85, 1.0))
    area("rim_r", 0.15, 1.4, ( 0.85, -0.70, 0.45), (0, 0, 0.05), 28, (1.0, 0.85, 0.7))
    area("top_strip", 0.25, 2.2, (0.35, -0.2, 1.5), (0.05, 0, 0), 32)
    w = bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.002, 0.0025, 0.004, 1)
    bg.inputs[1].default_value = 1.0

SHOTS = {}

def add_camera(name, loc_mm, look_mm, lens=50, fstop=4.0, focus_mm=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36
    cd.clip_start = 0.002
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
    add_camera("hero",   (330, 430, 235),   (0, 6, 38),      lens=50, fstop=5.0)
    add_camera("front",  (30, 470, 80),     (0, 30, 52),     lens=85, fstop=4.5)
    add_camera("top",    (60, -40, 800),    (0, -6, 0),      lens=50, fstop=8.0)
    add_camera("motor",  (215, 275, 95),    (79.5, 79.5, 34), lens=100, fstop=4.5,
               focus_mm=(79.5, 79.5, 30))
    add_camera("rear",   (-120, -430, 150), (0, -30, 45),    lens=70, fstop=4.0,
               focus_mm=(0, -58, 60))
    add_camera("side",   (560, 30, 95),     (0, 0, 52),      lens=70, fstop=5.6)

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
    sc.view_settings.exposure = 0.0

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
    for ob in get_col("DRONE").objects:
        ob.select_set(True)
    try:
        bpy.ops.export_scene.gltf(
            filepath=os.path.join(OUT, "kr5_apex.glb"),
            use_selection=True, export_apply=True)
        print("GLB exported")
    except Exception as ex:
        print("GLB export failed:", ex)
    try:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "kr5_apex.blend"))
        print("Blend saved")
    except Exception as ex:
        print("blend save failed:", ex)

# =============================================================================
#  BUILD IT
# =============================================================================
def main():
    clean_scene()
    get_col("DRONE"); get_col("STUDIO"); get_col("HELPERS")
    build_materials()
    build_plates()
    for i in range(4):
        build_arm(i)
    build_standoffs()
    build_camera_cage()
    # motor order/direction: FR CCW, FL CW, RL CCW, RR CW (Betaflight standard)
    dirs = {0: ((+1, +1), +1, 12), 1: ((-1, +1), -1, 74),
            2: ((-1, -1), +1, 41), 3: ((+1, -1), -1, 103)}
    for idx, ((sx, sy), hand, phase) in dirs.items():
        build_motor(idx, sx, sy)
        build_prop(idx, sx, sy, hand, phase)
    build_stack()
    build_fpv_cam()
    build_battery()
    build_antenna()
    build_led_bar()
    build_hdcam()
    build_studio()
    build_cameras()
    setup_render()
    prof = bpy.data.objects.get("strap_prof")
    if prof:
        prof.hide_render = True
    if FULL:
        export_assets()
    render_all()
    print("DONE. objects:", len(bpy.data.objects))

main()
