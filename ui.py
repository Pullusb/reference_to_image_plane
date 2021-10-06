import bpy
# from bpy.types import Panel

def plane_from_cam_bg_ui(self, context):
    """Append to DATA_PT_camera_background_image in cam data"""
    layout = self.layout

    layout.operator("ref_to_image_plane.cam_bg_img_to_mesh",
    text='Image plane from visible refs', icon='IMAGE_PLANE')


def plane_from_empty_reference_ui(self, context):
    layout = self.layout
    # Context data return image when image is loaded (else None)
    if context.object and context.object.type == 'EMPTY' and context.object.data:
        self.layout.operator_context = 'INVOKE_DEFAULT'
        layout.operator('ref_to_image_plane.convert_to_mesh', text='Mesh From Empty Image', icon='IMAGE_REFERENCE')

# classes=(
# PROJ_PT_proj_panel,
# )

def register(): 
    # for cls in classes:
    #     bpy.utils.register_class(cls)
    bpy.types.DATA_PT_camera_background_image.append(plane_from_cam_bg_ui)
    bpy.types.VIEW3D_MT_object_convert.append(plane_from_empty_reference_ui)

def unregister():
    bpy.types.DATA_PT_camera_background_image.remove(plane_from_cam_bg_ui)
    bpy.types.VIEW3D_MT_object_convert.remove(plane_from_empty_reference_ui)
    # for cls in reversed(classes):
    #     bpy.utils.unregister_class(cls)