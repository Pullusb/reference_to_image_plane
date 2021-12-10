import collections
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
    shader: bpy.props.EnumProperty(name="Shader", 
        items=SHADERS, 
        default='SHADELESS', # EMISSION
        description="Node shader to use")
    
    STATES = (
        ('HIDE', "Hide", "Hide camera reference that have genereted texutre plane"),
        ('DELETE', "Delete", "Delete camera ref after conversion"),
        ('NONE',"Do nothing","Don't do anything to the camera ref"),
    )

    post_state: bpy.props.EnumProperty(name="Ref Post Action", items=STATES, default='HIDE', description="What to do with camera refs once converted")
    
    distance: bpy.props.FloatProperty(name="Distance", default=10.0, description="Distance to place image plane relative to camera")
    
    use_driver: bpy.props.BoolProperty(name="Create Driver", default=True, 
    description="Create customs properties and driver on object to adjust scale and distance to camera anytime")

    collection: bpy.props.StringProperty(
        name='Destination Collection',
        description='Collection to put generated planes, create if necessary (Nothing = Scene Master Collection)',
        default='Background')

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        self.collection = fn.get_prefs().collection.strip()
        self.shader = fn.get_prefs().shader
        self.use_driver = fn.get_prefs().use_driver
        return context.window_manager.invoke_props_dialog(self, width=350)

    ## optional draw (just to add open addon pref button)
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        col = layout.column(align=False)
        col.prop(self, 'shader')
        col.prop(self, 'post_state')
        col.prop(self, 'distance')
        col.prop(self, 'use_driver')
        col.prop(self, 'collection')
        col.separator()
        row = col.row(align=True)
        row.label(text='') # 'Change Default Settings:'
        row.operator("rtp.open_addon_prefs", text="", icon='PREFERENCES')

    def execute(self, context):
        fn.convert_cam_bg_image_to_mesh(
            context,
            shader=self.shader,
            distance=self.distance,
            use_driver=self.use_driver,
            post_state=self.post_state,
            col_name=self.collection
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