import bpy
from bpy.types import Operator
from . import fn

class RTP_OT_cam_bg_img_to_mesh(Operator):
    bl_idname = "ref_to_image_plane.cam_bg_img_to_mesh"
    bl_label = "Camera Bg Images To Image Planes"
    bl_description = "Generate image plane from visible camera background images"
    bl_options = {"REGISTER", "UNDO"}


    SHADERS = (
        ('PRINCIPLED',"Principled","Principled Shader"),
        ('SHADELESS', "Shadeless", "Only visible to camera and reflections"),
        ('EMISSION', "Emit", "Emission Shader"),
    )
    
    # Default is 'PRINCIPLED' on import image as plane
    shader: bpy.props.EnumProperty(name="Shader", items=SHADERS, default='EMISSION', description="Node shader to use")
    
    STATES = (
        ('HIDE', "Hide", "Hide camera reference that have genereted texutre plane"),
        ('DELETE', "Delete", "Delete camera ref after conversion"),
        ('NONE',"Do nothing","Don't do anything to the camera ref"),
    )

    post_state: bpy.props.EnumProperty(name="Ref Post Action", items=STATES, default='HIDE', description="What to do with camera refs once converted")
    
    distance: bpy.props.FloatProperty(name="Distance", default=10.0, description="Distance to place image plane relative to camera")
    
    use_driver: bpy.props.BoolProperty(name="Create Driver", default=False, 
    description="Create customs properties and driver on object to adjust scale and distance to camera anytime")

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def execute(self, context):
        fn.convert_cam_bg_image_to_mesh(
            context,
            shader=self.shader,
            distance=self.distance,
            use_driver=self.use_driver,
            post_state=self.post_state,
            )

        return {"FINISHED"}


classes=(
RTP_OT_cam_bg_img_to_mesh,
)

def register(): 
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)