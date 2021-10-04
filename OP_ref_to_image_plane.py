import bpy
import re
from bpy.types import Operator
from mathutils import Vector

# from . import fn

## import methods from import img as plane addon (adapted some locally)
## credits to those goes to Florian Meyer (tstscr), mont29, matali, Ted Schundler (SpkyElctrc)
import importlib
iap = importlib.import_module('io_import_images_as_planes')

from collections import namedtuple
ImageSpec = namedtuple(
    'ImageSpec',
    ['image', 'size', 'frame_start', 'frame_offset', 'frame_duration'])


def apply_texture_options(texture, img_spec):
        image_user = texture.image_user
        # image_user.use_auto_refresh = False # self.use_auto_refresh
        # image_user.frame_start = img_spec.frame_start
        # image_user.frame_offset = img_spec.frame_offset
        # image_user.frame_duration = img_spec.frame_duration

        # Image sequences need auto refresh to display reliably
        if img_spec.image.source == 'SEQUENCE':
            image_user.use_auto_refresh = True

        texture.extension = 'CLIP'  # Default of "Repeat" can cause artifacts

def create_cycles_texnode(context, node_tree, img_spec):
        tex_image = node_tree.nodes.new('ShaderNodeTexImage')
        tex_image.image = img_spec.image
        tex_image.show_texture = True
        apply_texture_options(tex_image, img_spec)
        return tex_image

def create_cycles_material(context, img_spec, shader='EMISSION', overwrite_material=True, use_transparency=True):
        image = img_spec.image
        name_compat = bpy.path.display_name_from_filepath(image.filepath)
        material = None
        if overwrite_material:
            for mat in bpy.data.materials:
                if mat.name == name_compat:
                    material = mat
        if not material:
            material = bpy.data.materials.new(name=name_compat)

        material.use_nodes = True
        # if selfuse_transparency:
        material.blend_method = 'BLEND'
        node_tree = material.node_tree
        out_node = iap.clean_node_tree(node_tree)

        tex_image = create_cycles_texnode(context, node_tree, img_spec)

        if shader == 'PRINCIPLED':
            core_shader = node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        elif shader == 'SHADELESS':
            core_shader = iap.get_shadeless_node(node_tree)
        elif shader == 'EMISSION':
            core_shader = node_tree.nodes.new('ShaderNodeBsdfPrincipled')
            core_shader.inputs['Emission Strength'].default_value = 1.0#emit_strength
            core_shader.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
            core_shader.inputs['Specular'].default_value = 0.0

        # Connect color from texture
        if shader in {'PRINCIPLED', 'SHADELESS'}:
            node_tree.links.new(core_shader.inputs[0], tex_image.outputs['Color'])
        elif shader == 'EMISSION':
            node_tree.links.new(core_shader.inputs['Emission'], tex_image.outputs['Color'])

        if use_transparency:
            if shader in {'PRINCIPLED', 'EMISSION'}:
                node_tree.links.new(core_shader.inputs['Alpha'], tex_image.outputs['Alpha'])
            else:
                bsdf_transparent = node_tree.nodes.new('ShaderNodeBsdfTransparent')

                mix_shader = node_tree.nodes.new('ShaderNodeMixShader')
                node_tree.links.new(mix_shader.inputs['Fac'], tex_image.outputs['Alpha'])
                node_tree.links.new(mix_shader.inputs[1], bsdf_transparent.outputs['BSDF'])
                node_tree.links.new(mix_shader.inputs[2], core_shader.outputs[0])
                core_shader = mix_shader

        node_tree.links.new(out_node.inputs['Surface'], core_shader.outputs[0])

        iap.auto_align_nodes(node_tree)
        return material


def create_image_plane(coords, img):
    name = img.name
    fac = [(0, 1, 3, 2)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(coords, [], fac)
    plane = bpy.data.objects.new(name, me)

    col = bpy.context.collection
    col.objects.link(plane)

    me.uv_layers.new(name='UVMap')
    return plane


def get_ref_object_space_coord(o):
    size = o.empty_display_size
    x,y = o.empty_image_offset
    img = o.data

    res_x, res_y = img.size
    scaling = 1 / max(res_x, res_y)

    # 3----2
    # |    |
    # 0----1 

    corners = [
        Vector((0,0)),
        Vector((res_x, 0)),
        Vector((0, res_y)),
        Vector((res_x, res_y)),
        ]

    obj_space_corners = []
    for co in corners:
        nco_x = ((co.x + (x * res_x)) * size) * scaling
        nco_y = ((co.y + (y * res_y)) * size) * scaling
        obj_space_corners.append(Vector((nco_x, nco_y, 0)))
    return obj_space_corners

def convert_empty_image_to_mesh(context, o, delete_ref=True, shader='EMISSION'):
    """shader in ['EMISSION', 'PRINCIPLED', 'SHADELESS']"""
    img = o.data  
    print(f'\nConvert object: {o.name} -> Image: {img.name}')
    
    # ifp = img.filepath
    obj_space_corners = get_ref_object_space_coord(o)
    plane = create_image_plane(obj_space_corners, img)

    # link in same collection
    o.users_collection[0].objects.link(plane)

    # img_spec = ImageSpec(img, tuple(img.size), 0, 0, 0)
    img_spec = ImageSpec(img, (0,0), 0, 0, 0)
    material = create_cycles_material(context, img_spec)
    plane.data.materials.append(material)

    plane.parent = o.parent
    plane.matrix_local = o.matrix_local
    plane.matrix_parent_inverse = o.matrix_parent_inverse

    if delete_ref:
        bpy.data.objects.remove(o)

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
    # default is 'PRINCIPLED' on import image as plane
    shader: bpy.props.EnumProperty(name="Shader", items=SHADERS, default='EMISSION', description="Node shader to use")
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
            convert_empty_image_to_mesh(context, o, delete_ref=self.del_ref, shader=self.shader)
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