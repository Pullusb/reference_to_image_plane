bl_info = {
    "name": "Ref to image plane",
    "description": "convert a reference image to image plane (textured quad mesh)",
    "author": "Samuel Bernou",
    "version": (0, 1, 0),
    "blender": (2, 93, 0),
    "location": "View3D",
    "warning": "",
    "doc_url": "", #https://github.com/Pullusb/PROJ_name
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
