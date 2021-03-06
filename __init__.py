bl_info = {
    "name": "Reference To Image Plane",
    "description": "Convert a reference image or camera background ref to a textured plane",
    "author": "Samuel Bernou",
    "version": (0, 4, 1),
    "blender": (2, 93, 0),
    "location": "Object Menu > Convert & Cam Data Properties > Background Images",
    "warning": "",
    "doc_url": "https://github.com/Pullusb/reference_to_image_plane",
    "tracker_url": "https://github.com/Pullusb/reference_to_image_plane/issues/new",
    "category": "Object" }

from . import OP_ref_to_image_plane
from . import ui
from . import prefs
from . import OP_cam_bg_img_to_plane

import bpy

def register():
    if bpy.app.background:
        return
    prefs.register()
    OP_ref_to_image_plane.register()
    OP_cam_bg_img_to_plane.register()
    ui.register()

def unregister():
    if bpy.app.background:
        return
    ui.unregister()
    OP_cam_bg_img_to_plane.unregister()
    OP_ref_to_image_plane.unregister()
    prefs.unregister()

if __name__ == "__main__":
    register()
