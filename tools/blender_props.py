"""Generates the conference-room prop models (FBX) and Workbench previews.

Run:  blender -b -P Tools/blender_props.py -- <out_models_dir> <out_preview_dir>
Z-up in Blender; the FBX exporter converts to Unity's Y-up. Every model has its origin on the floor / base centre
and its front toward Blender -Y. Material slot names (chair_fabric, ...) are remapped to project materials in Unity.
"""
import bpy, bmesh, math, sys, os
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if len(argv) > 0 else os.path.abspath("models")
PREV = argv[1] if len(argv) > 1 else os.path.abspath("previews")
os.makedirs(OUT, exist_ok=True)
os.makedirs(PREV, exist_ok=True)

COLORS = {
    "chair_fabric": (0.10, 0.12, 0.16), "chair_plastic": (0.03, 0.03, 0.035), "chair_metal": (0.7, 0.72, 0.75),
    "leaf": (0.12, 0.4, 0.14), "leaf2": (0.18, 0.48, 0.16), "pot": (0.78, 0.76, 0.72), "soil": (0.08, 0.05, 0.03),
    "stem": (0.2, 0.3, 0.1),
    "laptop_metal": (0.62, 0.63, 0.66), "laptop_dark": (0.04, 0.04, 0.045), "laptop_screen": (0.02, 0.03, 0.05),
    "mug_white": (0.92, 0.92, 0.9), "mug_coffee": (0.12, 0.07, 0.04),
    "table_wood": (0.55, 0.38, 0.22),
}
_mats = {}


def mat(name):
    if name not in _mats:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        bsdf = m.node_tree.nodes["Principled BSDF"]
        c = COLORS.get(name, (0.5, 0.5, 0.5))
        bsdf.inputs["Base Color"].default_value = (c[0], c[1], c[2], 1)
        m.diffuse_color = (c[0], c[1], c[2], 1)
        _mats[name] = m
    return _mats[name]


def reset():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for b in list(bpy.data.meshes):
        bpy.data.meshes.remove(b)


def finish(obj, material, smooth=True, angle=35):
    obj.data.materials.clear()
    obj.data.materials.append(mat(material))
    if smooth:
        for p in obj.data.polygons:
            p.use_smooth = True
        bpy.context.view_layer.objects.active = obj
        try:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(angle))
        except Exception:
            pass
    return obj


def new_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def apply_mods(ob):
    bpy.context.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def rbox(name, size, loc, mat_name, rot=(0, 0, 0), bevel=0.01, seg=3, smooth=True):
    """Rounded box, size = (x, y, z) full extents, loc = centre."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    ob = new_obj(name, bm)
    ob.location = loc
    ob.rotation_euler = tuple(math.radians(a) for a in rot)
    mod = ob.modifiers.new("b", "BEVEL")
    mod.width = min(bevel, min(size) * 0.45)
    mod.segments = seg
    mod.limit_method = "ANGLE"
    apply_mods(ob)
    return finish(ob, mat_name, smooth)


def lathe(name, profile, mat_name, loc=(0, 0, 0), steps=24):
    """profile = [(radius, height)...] revolved about Z."""
    bm = bmesh.new()
    rows = []
    for i in range(steps):
        a = 2 * math.pi * i / steps
        ca, sa = math.cos(a), math.sin(a)
        rows.append([bm.verts.new((r * ca, r * sa, h)) for (r, h) in profile])
    for i in range(steps):
        j = (i + 1) % steps
        for k in range(len(profile) - 1):
            try:
                bm.faces.new((rows[i][k], rows[j][k], rows[j][k + 1], rows[i][k + 1]))
            except ValueError:
                pass
    # cap any ring at r == 0
    for end in (0, -1):
        if profile[end][0] > 1e-5:
            try:
                bm.faces.new([rows[i][end] for i in (range(steps) if end == 0 else reversed(range(steps)))])
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = new_obj(name, bm)
    ob.location = loc
    return finish(ob, mat_name)


def tube(name, a, b, r0, r1, mat_name, steps=10):
    a, b = Vector(a), Vector(b)
    d = b - a
    ln = d.length
    bm = bmesh.new()
    rings = []
    for k in range(2):
        r = r0 if k == 0 else r1
        z = 0 if k == 0 else ln
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / steps), r * math.sin(2 * math.pi * i / steps), z)) for i in range(steps)])
    for i in range(steps):
        j = (i + 1) % steps
        bm.faces.new((rings[0][i], rings[0][j], rings[1][j], rings[1][i]))
    bm.faces.new(rings[1])
    bm.faces.new(list(reversed(rings[0])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = new_obj(name, bm)
    ob.location = a
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    return finish(ob, mat_name)


def join_all(name):
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    return ob


def export(name):
    ob = join_all(name)
    # clean-up so Unity gets sane transforms
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    path = os.path.join(OUT, name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_ALL", bake_space_transform=True,
                             axis_forward="-Z", axis_up="Y", mesh_smooth_type="FACE", use_mesh_modifiers=True)
    preview(name)
    print("exported", path, "tris:", sum(len(p.vertices) - 2 for p in ob.data.polygons))


def preview(name):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.render.resolution_x, sc.render.resolution_y = 700, 700
    ob = [o for o in sc.objects if o.type == "MESH"][0]
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    mn = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
    mx = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
    ctr, size = (mn + mx) / 2, max((mx - mn).length, 0.1)
    cam = bpy.data.objects.get("pc") or bpy.data.objects.new("pc", bpy.data.cameras.new("pc"))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    sc.camera = cam
    for i, direction in enumerate([Vector((-0.8, -1, 0.7)), Vector((0.9, 0.9, 0.5))]):
        cam.location = ctr + direction.normalized() * size * 1.5
        look = (ctr - cam.location).to_track_quat("-Z", "Y")
        cam.rotation_euler = look.to_euler()
        sc.render.filepath = os.path.join(PREV, f"{name}_{i}.png")
        bpy.ops.render.render(write_still=True)


# ------------------------------------------------------------------ chair

def make_chair():
    reset()
    seat_top = 0.47
    # 5-star base
    for i in range(5):
        a = i * 72
        rot = math.radians(a)
        d = Vector((math.cos(rot), math.sin(rot), 0))
        tube("leg", (0, 0, 0.085) , tuple(d * 0.31 + Vector((0, 0, 0.06))), 0.022, 0.014, "chair_plastic")
        caster_pos = d * 0.31
        lathe("caster", [(0, 0.0), (0.022, 0.0), (0.028, 0.02), (0.028, 0.04), (0.02, 0.05), (0, 0.05)], "chair_plastic",
              (caster_pos.x, caster_pos.y, 0.0))
    lathe("hub", [(0, 0.075), (0.05, 0.075), (0.06, 0.09), (0.05, 0.105), (0, 0.105)], "chair_plastic")
    # gas lift
    lathe("lift", [(0, 0.1), (0.03, 0.1), (0.03, 0.30), (0.022, 0.30), (0.022, 0.38), (0, 0.38)], "chair_metal")
    lathe("cover", [(0.034, 0.28), (0.05, 0.28), (0.044, 0.40), (0.034, 0.40)], "chair_plastic")
    # seat mechanism + cushion
    rbox("mech", (0.28, 0.26, 0.05), (0, 0.0, 0.405), "chair_plastic", bevel=0.015)
    rbox("seat", (0.52, 0.5, 0.085), (0, -0.01, seat_top - 0.0425), "chair_fabric", bevel=0.03, seg=4)
    rbox("seat_pad", (0.46, 0.44, 0.02), (0, -0.02, seat_top - 0.005), "chair_fabric", bevel=0.01)
    # backrest: spine + curved panel
    rbox("spine", (0.07, 0.04, 0.26), (0, 0.22, 0.58), "chair_plastic", rot=(-12, 0, 0), bevel=0.012)
    back = rbox("back", (0.48, 0.075, 0.52), (0, 0.255, 0.80), "chair_fabric", rot=(-10, 0, 0), bevel=0.03, seg=4)
    # bend the panel slightly around its vertical axis for a lumbar curve
    bpy.context.view_layer.objects.active = back
    for v in back.data.vertices:
        v.co.y += -0.5 * (v.co.x ** 2) * 1.2
    back.data.update()
    rbox("back_rim", (0.5, 0.03, 0.54), (0, 0.285, 0.80), "chair_plastic", rot=(-10, 0, 0), bevel=0.012)
    # armrests
    for s in (-1, 1):
        rbox("arm_post", (0.04, 0.05, 0.2), (0.27 * s, 0.02, 0.57), "chair_plastic", bevel=0.01)
        rbox("arm_pad", (0.07, 0.30, 0.04), (0.27 * s, -0.04, 0.68), "chair_plastic", bevel=0.015)
        rbox("arm_join", (0.05, 0.12, 0.05), (0.26 * s, 0.1, 0.50), "chair_plastic", bevel=0.01)
    export("OfficeChair")


# ------------------------------------------------------------------ plant

def leaf(name, base, direction, length, width, droop, mat_name, twist=0.0):
    """A folded, drooping leaf blade. direction = unit vector of the leaf's initial heading."""
    seg = 7
    bm = bmesh.new()
    d = Vector(direction).normalized()
    side = d.cross(Vector((0, 0, 1)))
    if side.length < 1e-4:
        side = Vector((1, 0, 0))
    side.normalize()
    up = side.cross(d).normalized()
    pts = []
    pos = Vector(base)
    heading = d.copy()
    ring = []
    for i in range(seg + 1):
        t = i / seg
        w = width * math.sin(math.pi * min(1.0, 0.18 + t * 0.82)) * (1 - 0.15 * t)
        fold = 0.18 * w
        # centre vertex lifted (a fold along the midrib), edges drooped
        cvert = bm.verts.new(pos + up * fold)
        lvert = bm.verts.new(pos - side * w * 0.5)
        rvert = bm.verts.new(pos + side * w * 0.5)
        ring.append((lvert, cvert, rvert))
        step = length / seg
        heading = (heading + Vector((0, 0, -droop * step))).normalized()
        pos = pos + heading * step
    for i in range(seg):
        (l0, c0, r0), (l1, c1, r1) = ring[i], ring[i + 1]
        bm.faces.new((l0, c0, c1, l1))
        bm.faces.new((c0, r0, r1, c1))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = new_obj(name, bm)
    # double sided: add a solidify so back faces are lit properly
    mod = ob.modifiers.new("s", "SOLIDIFY")
    mod.thickness = 0.004
    apply_mods(ob)
    return finish(ob, mat_name, True, 60)


def make_plant():
    reset()
    lathe("pot", [(0.0, 0.0), (0.15, 0.0), (0.19, 0.04), (0.235, 0.46), (0.255, 0.48), (0.255, 0.5), (0.225, 0.5), (0.215, 0.46), (0.0, 0.46)], "pot")
    lathe("soil", [(0, 0.44), (0.21, 0.44), (0.21, 0.46), (0, 0.47)], "soil")
    import random
    rnd = random.Random(11)
    for i in range(40):
        a = rnd.random() * math.tau
        tilt = 0.35 + rnd.random() * 0.8
        h = 0.18 + rnd.random() * 0.5
        base = Vector((rnd.uniform(-0.06, 0.06), rnd.uniform(-0.06, 0.06), 0.46))
        outward = Vector((math.cos(a), math.sin(a), 0))
        tip = base + outward * (0.06 + tilt * 0.34) + Vector((0, 0, h))
        tube("stem", tuple(base), tuple(tip), 0.009, 0.005, "stem", steps=6)
        lead = (outward * 0.8 + Vector((0, 0, 0.5))).normalized()
        leaf("leaf", tuple(tip), tuple(lead), 0.26 + rnd.random() * 0.14, 0.15 + rnd.random() * 0.06, 1.2 + rnd.random() * 1.0,
             "leaf" if i % 2 else "leaf2")
    export("PottedPlant")


# ------------------------------------------------------------------ laptop

def make_laptop():
    reset()
    w, d, t = 0.31, 0.215, 0.015
    rbox("base", (w, d, t), (0, 0, t / 2), "laptop_metal", bevel=0.005)
    rbox("deck", (w - 0.012, d - 0.012, 0.002), (0, 0, t + 0.0005), "laptop_dark", bevel=0.0006, seg=1, smooth=False)
    # keys 14 x 5
    kw, kd = 0.0185, 0.0165
    for r in range(5):
        for c in range(14):
            x = (c - 6.5) * (kw + 0.0025)
            y = d / 2 - 0.045 - r * (kd + 0.003)
            rbox("key", (kw, kd, 0.003), (x, y, t + 0.0027), "laptop_dark", bevel=0.0008, seg=1, smooth=False)
    rbox("pad", (0.1, 0.065, 0.001), (0, -d / 2 + 0.05, t + 0.0013), "laptop_metal", bevel=0.0004, seg=1, smooth=False)
    # lid: hinge on the back edge, opened 105 degrees. Built closed (flat, extending toward -Y), then rotated about the hinge.
    ang = math.radians(105)
    lid_th, lid_h = 0.007, d
    M = Matrix.Translation((0, d / 2, t)) @ Matrix.Rotation(-ang, 4, "X")
    for nm, size, z, matname, bev, sm in (("lid", (w, lid_h, lid_th), lid_th / 2, "laptop_metal", 0.003, True),
                                         ("screen", (w - 0.014, lid_h - 0.016, 0.001), -0.0004, "laptop_screen", 0.0004, False)):
        ob = rbox(nm, size, (0, -lid_h / 2, z), matname, bevel=bev, seg=2 if sm else 1, smooth=sm)
        ob.data.transform(M @ Matrix.Translation(ob.location))
        ob.location = (0, 0, 0)
    export("Laptop")


# ------------------------------------------------------------------ mug

def make_mug():
    reset()
    lathe("mug", [(0, 0), (0.036, 0), (0.04, 0.004), (0.042, 0.09), (0.04, 0.092), (0.035, 0.09), (0.035, 0.012), (0, 0.012)], "mug_white")
    lathe("coffee", [(0, 0.075), (0.035, 0.075), (0.035, 0.077), (0, 0.077)], "mug_coffee")
    # handle: half torus
    bm = bmesh.new()
    n_arc, n_circ, R, r = 12, 6, 0.028, 0.0045
    rings = []
    for i in range(n_arc + 1):
        a = -math.pi / 2 + math.pi * i / n_arc
        cx, cz = 0.04 + R * math.cos(a) * 0.9, 0.047 + R * math.sin(a) * 1.35
        ring = []
        for j in range(n_circ):
            b = math.tau * j / n_circ
            ring.append(bm.verts.new((cx + r * math.cos(b) * math.cos(a), r * math.sin(b), cz + r * math.cos(b) * math.sin(a))))
        rings.append(ring)
    for i in range(n_arc):
        for j in range(n_circ):
            k = (j + 1) % n_circ
            bm.faces.new((rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    finish(new_obj("handle", bm), "mug_white")
    export("Mug")


# ------------------------------------------------------------------ table top

def make_tabletop():
    reset()
    length, width, th, bevel = 3.0, 1.3, 0.05, 0.007   # straight part length, width, thickness
    r = width / 2
    bm = bmesh.new()
    pts = []
    arc = 20
    for i in range(arc + 1):   # right end, from -90 to +90
        a = -math.pi / 2 + math.pi * i / arc
        pts.append((length / 2 + r * math.cos(a), r * math.sin(a)))
    for i in range(arc + 1):   # left end
        a = math.pi / 2 + math.pi * i / arc
        pts.append((-length / 2 + r * math.cos(a), r * math.sin(a)))
    top = [bm.verts.new((x, y, th / 2)) for x, y in pts]
    bot = [bm.verts.new((x, y, -th / 2)) for x, y in pts]
    n = len(pts)
    ft = bm.faces.new(top)
    fb = bm.faces.new(list(reversed(bot)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((top[i], bot[i], bot[j], top[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # planar UVs across the whole top, normalised to 0..1 so the project's tiling applies (like the old box)
    uv = bm.loops.layers.uv.new("UVMap")
    span_x, span_y = length + width, width
    for f in bm.faces:
        for l in f.loops:
            l.vert.co
            l[uv].uv = ((l.vert.co.x + span_x / 2) / span_x, (l.vert.co.y + span_y / 2) / span_y)
    ob = new_obj("TableTop", bm)
    mod = ob.modifiers.new("b", "BEVEL")
    mod.width = bevel
    mod.segments = 2
    mod.limit_method = "ANGLE"
    apply_mods(ob)
    finish(ob, "table_wood", True, 50)
    export("TableTop")


if __name__ == "__main__":
    make_chair()
    make_plant()
    make_laptop()
    make_mug()
    make_tabletop()
