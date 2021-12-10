import bpy
from . import fn

class RTP_addon_prefs(bpy.types.AddonPreferences):
    bl_idname = __package__ # or  __name__.split('.')[0] # or with: os.path.splitext(__name__)[0]

    collection: bpy.props.StringProperty(name='Collection',
        description='Destination Collection to put generated planes (Nothing = Scene Master Collection)',
        default='Background')

    # Default is 'PRINCIPLED' on import image as plane
    shader: bpy.props.EnumProperty(name="Shader", 
        items=(
                ('PRINCIPLED',"Principled","Principled Shader"),
                ('SHADELESS', "Shadeless", "Only visible to camera and reflections"),
                ('EMISSION', "Emit", "Emission Shader"),
            ), 
        default='SHADELESS', # EMISSION
        description="Default node shader to use")

    use_driver: bpy.props.BoolProperty(name="Create Driver", default=True, 
        description="Create customs properties and driver on object to adjust scale and distance to camera anytime")

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        col = layout.column()

        box = col.box()
        box.label(text='General Settings:')
        box.prop(self, "shader", text='Default Plane Shader')

        ## Cam BG imgs dedicated settings
        box = col.box()
        box.label(text='Camera background images to plane prefs:')
        box.prop(self, "use_driver", text='Toggle Driver Creation On')
        
        bcol = box.column() 
        bcol.prop(self, "collection", text='Destination Collection')
        bcol.label(text='(Empty field = Scene Collection)')
        bcol.label(text='Destination can be overwritten with env variable: "REF_TO_PLANE_COLLECTION"') #, icon='INFO')


def open_addon_prefs():
    '''Open addon prefs windows with focus on current addon'''
    from .__init__ import bl_info
    wm = bpy.context.window_manager
    wm.addon_filter = 'All'
    if not 'COMMUNITY' in  wm.addon_support: # reactivate community
        wm.addon_support = set([i for i in wm.addon_support] + ['COMMUNITY'])
    wm.addon_search = bl_info['name']
    bpy.context.preferences.active_section = 'ADDONS'
    bpy.ops.preferences.addon_expand(module=__package__)
    bpy.ops.screen.userpref_show('INVOKE_DEFAULT')

class RTP_OT_open_addon_prefs(bpy.types.Operator):
    ## Open user preferences window in addon tab and prefill the search with addon name 
    bl_idname = "rtp.open_addon_prefs"
    bl_label = "Open Addon Prefs"
    bl_description = "Access addon preferences"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        open_addon_prefs()
        return {'FINISHED'}

### --- ENV_PROP ---

def set_env_properties():
    import os
    prefs = fn.get_prefs()
    collec = os.getenv('REF_TO_PLANE_COLLECTION')
    prefs.collection = collec if collec else prefs.collection


def register():
    bpy.utils.register_class(RTP_OT_open_addon_prefs)
    bpy.utils.register_class(RTP_addon_prefs)
    set_env_properties()

def unregister():
    bpy.utils.unregister_class(RTP_addon_prefs)
    bpy.utils.unregister_class(RTP_OT_open_addon_prefs)
