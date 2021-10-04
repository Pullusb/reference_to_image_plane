import bpy
from bpy.types import Operator
from . import fn

class RTP_OT_convert_to_mesh(Operator):
    bl_idname = "ref_to_image_plane.convert_to_mesh"
    bl_label = "Convert References To Image Planes"
    bl_description = "Convert selected reference images to textured plane"
    bl_options = {"REGISTER", "UNDO"}


    SHADERS = (
        ('PRINCIPLED',"Principled","Principled Shader"),
        ('SHADELESS', "Shadeless", "Only visible to camera and reflections"),
        ('EMISSION', "Emit", "Emission Shader"),
    )
    
    # Default is 'PRINCIPLED' on import image as plane
    shader: bpy.props.EnumProperty(name="Shader", items=SHADERS, default='EMISSION', description="Node shader to use")
    
    NAME_RULE = (
        ('OBJECT',"Source Object","Name after object source with a suffix"),
        ('IMAGE', "Image", "name from laoded image"),
    )
    
    name_from: bpy.props.EnumProperty(name="Name After", items=NAME_RULE, default='IMAGE', description="Name to give new object")
    
    del_ref: bpy.props.BoolProperty(name="Delete Reference Object", default=True, description="Delete empty image object refernece once texture plane is created")



    @classmethod
    def poll(cls, context):
        return True
        # return context.object and context.object.type == 'EMPTY'\
        #     and context.object.empty_display_type == 'IMAGE' and context.object.data

    @staticmethod
    def _is_ref(o):
        return o and o.type == 'EMPTY' and o.empty_display_type == 'IMAGE' and o.data

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self) # , width=450

    def execute(self, context):

        converted = 0
        for o in context.selected_objects:
            if not self._is_ref(o):
                continue
            fn.convert_empty_image_to_mesh(context, o, name_from=self.name_from, delete_ref=self.del_ref, shader=self.shader)
            converted += 1

        if not converted:
            self.report({'ERROR'}, 'Nothing converted')
            return {"CANCELLED"}

        self.report({'INFO'}, f'{converted} converted to mesh plane')
        return {"FINISHED"}


classes=(
RTP_OT_convert_to_mesh,
)

def register(): 
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)