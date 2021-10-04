bl_info = {
    "name": "Ref to image plane",
    "description": "convert a reference image to image plane (textured quad mesh)",
    "author": "Samuel Bernou",
    "version": (0, 2, 0),
    "blender": (2, 93, 0),
    "location": "View3D",
    "warning": "",
    "doc_url": "https://github.com/Pullusb/ref_to_image_plane",
    "tracker_url": "https://github.com/Pullusb/gp_draw_transform/issues/new",
    "category": "Object" }

from . import OP_ref_to_image_plane

import bpy

def register():
    if bpy.app.background:
        return
    OP_ref_to_image_plane.register()

def unregister():
    if bpy.app.background:
        return
    OP_ref_to_image_plane.unregister()

if __name__ == "__main__":
    register()
