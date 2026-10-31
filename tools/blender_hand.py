"""Candidate hand v2: a smooth, glove-like hand built from metaballs (soft organic blends instead of boxes and tubes).

Run:  blender -b -P Tools/blender_hand.py -- <out_models_dir> <out_preview_dir>
Right hand, Blender axes: fingers point -Y, thumb +Z, palm faces +X. (Unity: fingers +z, thumb +y, palm -x.) The left hand is a mirrored copy in Unity.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector, Quaternion

import blender_props as bp
from blender_props import reset, export, finish, tube, lathe

bp.COLORS["glove"] = (0.60, 0.66, 0.74)
bp.COLORS["sleeve"] = (0.14, 0.17, 0.24)


def capsule(mb, a, b, radius, stiffness=2.0):
    a, b = Vector(a), Vector(b)
    el = mb.elements.new(type="CAPSULE")
    el.co = (a + b) / 2
    el.radius = radius
    el.stiffness = stiffness
    el.size_x = (b - a).length / 2
    el.rotation = Vector((1, 0, 0)).rotation_difference((b - a).normalized())
    return el


def ellipsoid(mb, c, size, radius, stiffness=2.0):
    el = mb.elements.new(type="ELLIPSOID")
    el.co = c
    el.radius = radius
    el.stiffness = stiffness
    el.size_x, el.size_y, el.size_z = size
    return el


def make_glove_hand():
    reset()
    mbdata = bpy.data.metaballs.new("hand")
    mbdata.resolution = 0.004
    mbdata.render_resolution = 0.004
    mbdata.threshold = 0.55
    mbobj = bpy.data.objects.new("hand", mbdata)
    bpy.context.collection.objects.link(mbobj)
    mb = mbdata

    R = 0.0135   # finger thickness driver
    # palm: a soft plate
    for y, r in ((-0.032, 0.026), (-0.006, 0.030), (0.022, 0.027)):
        capsule(mb, (0.0, y, -0.030), (0.0, y, 0.032), r)
    # wrist
    capsule(mb, (0.0, 0.03, 0.0), (0.0, 0.085, 0.0), 0.027)
    # fingers curl toward the palm side (+x) a little, like holding a controller grip
    front = -0.045
    specs = [("index", 0.032, (0.042, 0.027, 0.021), (22, 36, 30), 1.0),
             ("middle", 0.011, (0.046, 0.030, 0.022), (26, 40, 32), 1.06),
             ("ring", -0.010, (0.042, 0.028, 0.021), (30, 40, 32), 1.0),
             ("little", -0.029, (0.033, 0.021, 0.018), (34, 40, 30), 0.88)]
    for name, z, lengths, curls, thick in specs:
        pos = Vector((0.0, front, z))
        angle = 0.0
        for ln, curl in zip(lengths, curls):
            angle += math.radians(curl)
            d = Vector((math.sin(angle), -math.cos(angle), 0.0))
            end = pos + d * ln
            capsule(mb, pos, end, R * thick * 1.15)
            pos = end
    # thumb from the upper palm, forward and slightly up
    pos = Vector((0.004, -0.014, 0.036))
    for d, ln in (((0.25, -0.55, 0.8), 0.034), ((0.4, -0.8, 0.45), 0.030)):
        d = Vector(d).normalized()
        end = pos + d * ln
        capsule(mb, pos, end, R * 1.25)
        pos = end

    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    mbobj.select_set(True)
    bpy.context.view_layer.objects.active = mbobj
    bpy.ops.object.convert(target="MESH")
    hand = bpy.context.view_layer.objects.active
    dec = hand.modifiers.new("d", "DECIMATE")
    dec.ratio = 0.28
    bpy.ops.object.modifier_apply(modifier=dec.name)
    for p in hand.data.polygons:
        p.use_smooth = True
    finish(hand, "glove", True, 70)

    # sleeve cuff at the wrist so the hand does not end in a bare cut-off tube
    lathe("cuff", [(0.0, 0.0), (0.027, 0.0), (0.030, 0.008), (0.031, 0.06), (0.0, 0.06)], "sleeve", (0, 0, 0))
    cuff = bpy.data.objects["cuff"]
    cuff.rotation_euler = (math.radians(-90), 0, 0)   # lathe axis Z -> +Y (toward the forearm)
    cuff.location = (0.0, 0.08, 0.0)
    bpy.context.view_layer.objects.active = cuff
    bpy.ops.object.select_all(action="DESELECT")
    cuff.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    export("VRHandRight")


if __name__ == "__main__":
    make_glove_hand()
