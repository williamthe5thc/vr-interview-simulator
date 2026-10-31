"""Batch 2 of the conference-room dressing (glassware, bookshelf, water cooler, blinds, ...).

Run:  blender -b -P Tools/blender_props2.py -- <out_models_dir> <out_preview_dir>
Reuses the helpers in blender_props.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import math
import random
from mathutils import Vector

import blender_props as bp
from blender_props import reset, lathe, tube, rbox, new_obj, finish, apply_mods, export
import bmesh, bpy

bp.COLORS.update({
    "glass": (0.8, 0.9, 0.95), "water": (0.6, 0.8, 0.95), "plate_metal": (0.7, 0.7, 0.72), "led": (0.2, 0.9, 0.5),
    "shelf_wood": (0.35, 0.22, 0.13), "trophy_gold": (0.85, 0.65, 0.2),
    "book_red": (0.55, 0.1, 0.1), "book_blue": (0.1, 0.2, 0.5), "book_green": (0.12, 0.35, 0.2), "book_tan": (0.7, 0.6, 0.4),
    "book_black": (0.06, 0.06, 0.07), "book_orange": (0.8, 0.4, 0.1), "book_white": (0.85, 0.85, 0.82), "book_teal": (0.1, 0.45, 0.5),
    "cooler_white": (0.9, 0.9, 0.92), "tap_blue": (0.1, 0.3, 0.9), "tap_red": (0.9, 0.15, 0.1), "water_jug": (0.4, 0.6, 0.9),
    "jacket": (0.15, 0.17, 0.22), "bin_metal": (0.35, 0.36, 0.38), "blind": (0.9, 0.88, 0.84), "blind_head": (0.8, 0.8, 0.8),
    "lampshade": (0.95, 0.9, 0.78),
})


def flat_box(name, size, loc, mat_name, rot=(0, 0, 0)):
    """Plain 12-triangle box (cheap, for books and slats)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    ob = new_obj(name, bm)
    ob.location = loc
    ob.rotation_euler = tuple(math.radians(a) for a in rot)
    return finish(ob, mat_name, smooth=False)


def make_glassware():
    reset()
    lathe("tumbler", [(0, 0.0), (0.027, 0.0), (0.03, 0.004), (0.034, 0.1), (0.0345, 0.1), (0.031, 0.1), (0.0285, 0.014), (0, 0.012)], "glass")
    lathe("water", [(0, 0.014), (0.0285, 0.016), (0.0315, 0.07), (0, 0.07)], "water")
    export("WaterGlass")
    reset()
    lathe("carafe", [(0, 0.0), (0.05, 0.0), (0.056, 0.01), (0.058, 0.12), (0.034, 0.17), (0.029, 0.22), (0.033, 0.232), (0.029, 0.232),
                     (0.026, 0.2), (0.05, 0.12), (0.052, 0.014), (0, 0.012)], "glass")
    lathe("water", [(0, 0.014), (0.05, 0.016), (0.0525, 0.1), (0.0345, 0.15), (0, 0.15)], "water")
    lathe("lid", [(0, 0.235), (0.028, 0.235), (0.034, 0.24), (0.034, 0.265), (0.03, 0.272), (0, 0.272)], "glass")
    export("WaterCarafe")


def make_nameplate():
    reset()
    bm = bmesh.new()
    w, d, h = 0.22, 0.06, 0.05
    pts = [(-w / 2, -d / 2, 0), (w / 2, -d / 2, 0), (w / 2, d / 2, 0), (-w / 2, d / 2, 0), (-w / 2, -d / 2, h), (w / 2, -d / 2, h)]
    v = [bm.verts.new(p) for p in pts]
    bm.faces.new((v[0], v[3], v[2], v[1]))
    bm.faces.new((v[0], v[1], v[5], v[4]))
    bm.faces.new((v[3], v[4], v[5], v[2]))
    bm.faces.new((v[0], v[4], v[3]))
    bm.faces.new((v[1], v[2], v[5]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = new_obj("plate", bm)
    mod = ob.modifiers.new("b", "BEVEL"); mod.width = 0.004; mod.segments = 2
    apply_mods(ob)
    finish(ob, "plate_metal", True, 40)
    export("Nameplate")


def make_speakerphone():
    reset()
    lathe("body", [(0, 0.0), (0.085, 0.0), (0.095, 0.006), (0.095, 0.02), (0.08, 0.03), (0.05, 0.032), (0, 0.032)], "laptop_dark")
    lathe("ring", [(0.05, 0.032), (0.058, 0.0325), (0.058, 0.035), (0.05, 0.035)], "led")
    for i in range(3):
        a = math.radians(90 + i * 120)
        rbox("pad", (0.03, 0.022, 0.004), (0.065 * math.cos(a), 0.065 * math.sin(a), 0.033), "laptop_metal",
             rot=(0, 0, math.degrees(a)), bevel=0.002, seg=1)
    export("Speakerphone")


BOOK_MATS = ["book_red", "book_blue", "book_green", "book_tan", "book_black", "book_orange", "book_white", "book_teal"]


def make_bookshelf():
    reset()
    w, d, h, t = 0.95, 0.3, 1.9, 0.025
    wood = "shelf_wood"
    rbox("side_l", (t, d, h), (-w / 2 + t / 2, 0, h / 2), wood, bevel=0.004, seg=1)
    rbox("side_r", (t, d, h), (w / 2 - t / 2, 0, h / 2), wood, bevel=0.004, seg=1)
    rbox("back", (w, 0.01, h), (0, d / 2 - 0.005, h / 2), wood, bevel=0.002, seg=1)
    levels = [0.08, 0.46, 0.84, 1.22, 1.60, h - t / 2]
    for z in levels:
        rbox("shelf", (w - 2 * t, d, t), (0, 0, z), wood, bevel=0.004, seg=1)
    rnd = random.Random(5)
    for si, z in enumerate(levels[:-1]):
        x = -w / 2 + t + 0.015
        limit = w / 2 - t - 0.015
        top = levels[si + 1]
        stop = limit - 0.05 if si != 2 else 0.0
        while x < stop:
            bw = rnd.uniform(0.022, 0.05)
            bh = rnd.uniform(0.2, min(0.33, top - z - 0.05))
            bd = rnd.uniform(0.18, 0.24)
            lean = rnd.choice([0, 0, 0, 0, 0, 7])
            flat_box("book", (bw, bd, bh), (x + bw / 2, -0.02, z + t / 2 + bh / 2), rnd.choice(BOOK_MATS), rot=(0, lean, 0))
            x += bw + 0.002
        if si == 2:
            for k in range(4):
                flat_box("flat", (0.2, 0.15, 0.03), (0.2, -0.02, z + t / 2 + 0.015 + k * 0.031), rnd.choice(BOOK_MATS),
                         rot=(0, 0, rnd.uniform(-6, 6)))
            lathe("trophy", [(0, 0), (0.04, 0), (0.04, 0.02), (0.012, 0.03), (0.012, 0.1), (0.045, 0.16), (0.04, 0.2), (0, 0.2)],
                  "trophy_gold", (-0.2, -0.02, z + t / 2))
    export("Bookshelf")


def make_watercooler():
    reset()
    rbox("body", (0.32, 0.34, 0.92), (0, 0, 0.46), "cooler_white", bevel=0.02, seg=3)
    rbox("recess", (0.2, 0.04, 0.2), (0, -0.172, 0.62), "plate_metal", bevel=0.005, seg=1)
    rbox("tap_blue", (0.035, 0.03, 0.05), (-0.05, -0.19, 0.64), "tap_blue", bevel=0.005, seg=1)
    rbox("tap_red", (0.035, 0.03, 0.05), (0.05, -0.19, 0.64), "tap_red", bevel=0.005, seg=1)
    rbox("drip", (0.2, 0.06, 0.012), (0, -0.19, 0.5), "plate_metal", bevel=0.003, seg=1)
    lathe("jug", [(0, 0.92), (0.12, 0.92), (0.14, 0.97), (0.145, 1.2), (0.13, 1.3), (0.06, 1.38), (0.05, 1.45), (0, 1.45)], "water_jug")
    export("WaterCooler")


def make_coatstand():
    reset()
    lathe("base", [(0, 0), (0.22, 0), (0.24, 0.015), (0.2, 0.04), (0.04, 0.06), (0, 0.06)], "chair_plastic")
    tube("pole", (0, 0, 0.05), (0, 0, 1.75), 0.018, 0.014, "chair_plastic")
    for i in range(5):
        a = math.radians(i * 72)
        d = Vector((math.cos(a), math.sin(a), 0))
        tube("hook", (0, 0, 1.68), tuple(Vector((0, 0, 1.78)) + d * 0.14), 0.01, 0.008, "chair_plastic")
        tube("hook2", (0, 0, 1.52), tuple(Vector((0, 0, 1.6)) + d * 0.12), 0.009, 0.007, "chair_plastic")
    lathe("cap", [(0, 1.75), (0.025, 1.75), (0.022, 1.8), (0, 1.8)], "chair_metal")
    rbox("jacket", (0.34, 0.1, 0.62), (0.0, -0.13, 1.42), "jacket", bevel=0.04, seg=3)
    export("CoatStand")


def make_bin():
    reset()
    lathe("bin", [(0, 0), (0.12, 0), (0.15, 0.02), (0.17, 0.3), (0.175, 0.31), (0.16, 0.31), (0.155, 0.29), (0.115, 0.03), (0, 0.025)], "bin_metal")
    export("WasteBin")


def make_blinds():
    reset()
    w, h = 3.55, 1.1
    rbox("head", (w + 0.04, 0.05, 0.05), (0, 0, h + 0.02), "blind_head", bevel=0.006, seg=1)
    n = 36
    for i in range(n):
        z = h - i * (h / n)
        flat_box("slat", (w, 0.045, 0.004), (0, 0.006 * (i % 2), z), "blind", rot=(14, 0, 0))
    for x in (-w / 2 + 0.2, w / 2 - 0.2):
        tube("cord", (x, 0.02, h), (x, 0.02, 0.0), 0.002, 0.002, "blind_head", steps=4)
    rbox("bottom", (w, 0.03, 0.02), (0, 0, -0.01), "blind_head", bevel=0.004, seg=1)
    export("Blinds")


def make_coffeemachine():
    reset()
    rbox("base", (0.22, 0.3, 0.04), (0, 0, 0.02), "chair_plastic", bevel=0.008, seg=2)
    rbox("back", (0.22, 0.1, 0.34), (0, 0.1, 0.19), "chair_plastic", bevel=0.01, seg=2)
    rbox("top", (0.22, 0.28, 0.07), (0, 0.01, 0.35), "chair_plastic", bevel=0.01, seg=2)
    rbox("head", (0.16, 0.1, 0.05), (0, -0.06, 0.3), "laptop_metal", bevel=0.006, seg=2)
    rbox("tray", (0.16, 0.12, 0.012), (0, -0.07, 0.06), "laptop_metal", bevel=0.003, seg=1)
    lathe("cup", [(0, 0.062), (0.03, 0.062), (0.036, 0.135), (0.0, 0.135)], "mug_white", (0, -0.07, 0.0))
    rbox("led", (0.012, 0.004, 0.008), (0.08, -0.108, 0.355), "led", bevel=0.001, seg=1)
    export("CoffeeMachine")


def make_floorlamp():
    reset()
    lathe("base", [(0, 0), (0.15, 0), (0.15, 0.02), (0, 0.03)], "chair_plastic")
    tube("pole", (0, 0, 0.02), (0, 0, 1.55), 0.012, 0.012, "chair_metal")
    lathe("shade", [(0.1, 1.45), (0.17, 1.45), (0.12, 1.75), (0.1, 1.75)], "lampshade")
    export("FloorLamp")


if __name__ == "__main__":
    make_glassware()
    make_nameplate()
    make_speakerphone()
    make_bookshelf()
    make_watercooler()
    make_coatstand()
    make_bin()
    make_blinds()
    make_coffeemachine()
    make_floorlamp()


# ------------------------------------------------------------------ candidate hand (right; the left one is a mirrored copy in Unity)

def sphere_at(name, center, r, mat_name, seg=8, rings=6):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    for v in bm.verts:
        v.co += Vector(center)
    return finish(new_obj(name, bm), mat_name)


def finger(name, base, z, lengths, curls, radius, mat_name="skin"):
    """A finger starting at palm-front point (x, y) with segments curling toward +x (the palm side)."""
    x, y = base
    pos = Vector((x, y, z))
    angle = 0.0
    sphere_at(name + "_k0", tuple(pos), radius, mat_name)
    for i, (ln, curl) in enumerate(zip(lengths, curls)):
        angle += math.radians(curl)
        d = Vector((math.sin(angle), -math.cos(angle), 0.0))
        end = pos + d * ln
        tube(f"{name}_s{i}", tuple(pos), tuple(end), radius, radius * 0.92, mat_name, steps=8)
        sphere_at(f"{name}_k{i + 1}", tuple(end), radius * 0.92, mat_name)
        pos = end


def make_hand():
    bp.COLORS["skin"] = (0.74, 0.55, 0.42)
    reset()
    rbox("palm", (0.032, 0.095, 0.088), (0, 0, 0), "skin", bevel=0.012, seg=3)
    tube("wrist", (0, 0.04, 0), (0, 0.14, 0), 0.03, 0.026, "skin", steps=10)
    front = -0.047
    specs = [("index", 0.033, (0.04, 0.026, 0.022), (28, 38, 28), 0.0095),
             ("middle", 0.011, (0.044, 0.028, 0.023), (32, 40, 30), 0.0098),
             ("ring", -0.010, (0.04, 0.027, 0.022), (36, 40, 30), 0.0092),
             ("little", -0.029, (0.031, 0.02, 0.019), (40, 40, 30), 0.0082)]
    for nm, z, lengths, curls, r in specs:
        finger(nm, (0.002, front), z, lengths, curls, r)
    # thumb: from the upper palm, pointing forward and up, slightly across the palm
    pos = Vector((0.006, -0.012, 0.046))
    sphere_at("thumb_k0", tuple(pos), 0.0115, "skin")
    for i, (d, ln, r) in enumerate((((0.25, -0.55, 0.8), 0.036, 0.0112), ((0.4, -0.8, 0.45), 0.03, 0.0102))):
        d = Vector(d).normalized()
        end = pos + d * ln
        tube(f"thumb_s{i}", tuple(pos), tuple(end), r, r * 0.9, "skin", steps=8)
        sphere_at(f"thumb_k{i + 1}", tuple(end), r * 0.9, "skin")
        pos = end
    export("VRHandRight")


if __name__ == "__main__":
    make_hand()
