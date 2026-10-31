"""Simple Quest 1 (Touch) controller models for the candidate's hands to hold: TouchControllerRight.fbx and TouchControllerLeft.fbx.

Run:  blender -b -P Tools/blender_controller.py -- <out_models_dir> <out_preview_dir>
Blender axes: front (pointing direction) = -Y, up = +Z, the right-hand controller's palm side = +X. (Unity: front +z, up +y.)
Origin = middle of the handle, which is where the XR "grip" pose of the controller sits, so the model drops straight onto the XR controller object.
The thumbstick, two face buttons and grip button are separate shapes joined into one mesh (materials ctrl_body / ctrl_ring / ctrl_stick / ctrl_btn).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import blender_props as bp
from blender_props import reset, export, finish, tube, rbox

bp.COLORS["ctrl_body"] = (0.035, 0.035, 0.040)
bp.COLORS["ctrl_ring"] = (0.09, 0.09, 0.10)
bp.COLORS["ctrl_stick"] = (0.012, 0.012, 0.014)
bp.COLORS["ctrl_btn"] = (0.20, 0.20, 0.22)


def make_controller(name, side):
    """side = +1 for the right-hand controller (palm side +X), -1 for the left."""
    s = side
    reset()
    # handle: slightly tapered, leaning forward at the top (about 23 degrees)
    tube("handle", (0.0, 0.030, -0.058), (0.0, -0.012, 0.046), 0.0170, 0.0188, "ctrl_body", 16)
    # head housing at the top of the handle
    rbox("head", (0.040, 0.054, 0.032), (0.0, -0.016, 0.060), "ctrl_body", rot=(math.radians(-23), 0, 0), bevel=0.012, seg=4)
    # thumbstick
    tube("stick", (0.0, -0.023, 0.070), (0.0, -0.028, 0.086), 0.0075, 0.0105, "ctrl_stick", 14)
    # two face buttons beside the stick (A/B on the right controller, X/Y on the left)
    tube("btn1", (s * 0.0125, -0.006, 0.072), (s * 0.0125, -0.008, 0.077), 0.0070, 0.0070, "ctrl_btn", 14)
    tube("btn2", (s * 0.0150, -0.026, 0.070), (s * 0.0150, -0.028, 0.075), 0.0070, 0.0070, "ctrl_btn", 14)
    # trigger on the front of the handle, under the head
    rbox("trigger", (0.017, 0.013, 0.036), (0.0, -0.034, 0.024), "ctrl_btn", rot=(math.radians(-23), 0, 0), bevel=0.005, seg=3)
    # grip button on the palm side of the handle
    rbox("gripbtn", (0.008, 0.016, 0.062), (s * 0.0195, 0.012, 0.004), "ctrl_btn", rot=(math.radians(-23), 0, 0), bevel=0.003, seg=3)
    # tracking ring: arches up and back from the head, over the top of the hand
    bpy.ops.mesh.primitive_torus_add(major_radius=0.047, minor_radius=0.0072, major_segments=40, minor_segments=10,
                                     location=(0.0, 0.040, 0.078), rotation=(math.radians(62), 0, 0))
    ring = bpy.context.view_layer.objects.active
    ring.name = "ring"
    finish(ring, "ctrl_ring", True, 60)
    export(name)


if __name__ == "__main__":
    # side +1 puts the face buttons on the +X side and the grip button on the palm side; the right-hand controller's palm side is Unity +x = Blender -X
    make_controller("TouchControllerRight", -1)
    make_controller("TouchControllerLeft", +1)
