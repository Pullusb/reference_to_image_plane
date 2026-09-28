import bpy, re
from mathutils import Matrix, Vector



# import importlib
# iap = importlib.import_module('io_import_images_as_planes')

## //--- Function are taken from Import image as plane addon (with some tweaks)
## credits to Florian Meyer (tstscr), mont29, matali, Ted Schundler (SpkyElctrc)

from collections import namedtuple
ImageSpec = namedtuple(
    'ImageSpec',
    ['image', 'size', 'frame_start', 'frame_offset', 'frame_duration'])

def get_prefs():
    '''
    function to read current addon preferences properties
    access with : get_prefs().super_special_option
    '''
    return bpy.context.preferences.addons[__package__].preferences

def clean_node_tree(node_tree):
    """Clear all nodes in a shader node tree except the output.

    Returns the output node (created if missing)
    """
    nodes = node_tree.nodes
    for node in list(nodes):  # copy to avoid altering the loop's data source
        if not node.type == 'OUTPUT_MATERIAL':
            nodes.remove(node)

    if not nodes:
        # Node tree can be empty (e.g. reused material without default nodes)
        return nodes.new('ShaderNodeOutputMaterial')

    # Keep a single output
    for node in list(nodes)[1:]:
        nodes.remove(node)
    return nodes[0]

#### /// can load from IAP
def get_input_nodes(node, links):
    """Get nodes that are a inputs to the given node"""
    # Get all links going to node.
    input_links = {lnk for lnk in links if lnk.to_node == node}
    # Sort those links, get their input nodes (and avoid doubles!).
    sorted_nodes = []
    done_nodes = set()
    for socket in node.inputs:
        done_links = set()
        for link in input_links:
            nd = link.from_node
            if nd in done_nodes:
                # Node already treated!
                done_links.add(link)
            elif link.to_socket == socket:
                sorted_nodes.append(nd)
                done_links.add(link)
                done_nodes.add(nd)
        input_links -= done_links
    return sorted_nodes


def auto_align_nodes(node_tree):
    """Given a shader node tree, arrange nodes neatly relative to the output node."""
    x_gap = 200
    y_gap = 180
    nodes = node_tree.nodes
    links = node_tree.links
    output_node = None
    for node in nodes:
        if node.type == 'OUTPUT_MATERIAL' or node.type == 'GROUP_OUTPUT':
            output_node = node
            break

    else:  # Just in case there is no output
        return

    def align(to_node):
        from_nodes = get_input_nodes(to_node, links)
        for i, node in enumerate(from_nodes):
            node.location.x = min(node.location.x, to_node.location.x - x_gap)
            node.location.y = to_node.location.y
            node.location.y -= i * y_gap
            node.location.y += (len(from_nodes) - 1) * y_gap / (len(from_nodes))
            align(node)

    align(output_node)

def get_socket(sockets, *names):
    """Return first socket found by name, to handle renaming across Blender versions"""
    for name in names:
        socket = sockets.get(name)
        if socket is not None:
            return socket
    raise KeyError(f'None of sockets {names} found')

def is_valid_shadeless_group(node_tree):
    """Check that the shadeless group has the expected output socket connected"""
    for node in node_tree.nodes:
        if node.type == 'GROUP_OUTPUT' and node.inputs and node.inputs[0].is_linked:
            return True
    return False

def get_shadeless_node(dest_node_tree):
    """Return a "shadless" cycles/eevee node, creating a node group if nonexistent"""
    node_tree = bpy.data.node_groups.get('IAP_SHADELESS')
    if node_tree and not is_valid_shadeless_group(node_tree):
        # Broken group (e.g. left over from a failed build): rebuild it
        node_tree.name = 'IAP_SHADELESS_invalid'
        node_tree = None

    if node_tree is None:
        # need to build node shadeless node group
        node_tree = bpy.data.node_groups.new('IAP_SHADELESS', 'ShaderNodeTree')

        # Create sockets before in/out nodes so they get them
        if hasattr(node_tree, 'interface'):
            # Blender 4.0+
            node_tree.interface.new_socket('Shader', in_out='OUTPUT', socket_type='NodeSocketShader')
            node_tree.interface.new_socket('Color', in_out='INPUT', socket_type='NodeSocketColor')
        else:
            node_tree.outputs.new('NodeSocketShader', 'Shader')
            node_tree.inputs.new('NodeSocketColor', 'Color')

        output_node = node_tree.nodes.new('NodeGroupOutput')
        input_node = node_tree.nodes.new('NodeGroupInput')

        # This could be faster as a transparent shader, but then no ambient occlusion
        diffuse_shader = node_tree.nodes.new('ShaderNodeBsdfDiffuse')
        node_tree.links.new(diffuse_shader.inputs[0], input_node.outputs[0])

        emission_shader = node_tree.nodes.new('ShaderNodeEmission')
        node_tree.links.new(emission_shader.inputs[0], input_node.outputs[0])

        light_path = node_tree.nodes.new('ShaderNodeLightPath')
        is_glossy_ray = light_path.outputs['Is Glossy Ray']
        is_shadow_ray = light_path.outputs['Is Shadow Ray']
        ray_depth = light_path.outputs['Ray Depth']
        transmission_depth = light_path.outputs['Transmission Depth']

        unrefracted_depth = node_tree.nodes.new('ShaderNodeMath')
        unrefracted_depth.operation = 'SUBTRACT'
        unrefracted_depth.label = 'Bounce Count'
        node_tree.links.new(unrefracted_depth.inputs[0], ray_depth)
        node_tree.links.new(unrefracted_depth.inputs[1], transmission_depth)

        refracted = node_tree.nodes.new('ShaderNodeMath')
        refracted.operation = 'SUBTRACT'
        refracted.label = 'Camera or Refracted'
        refracted.inputs[0].default_value = 1.0
        node_tree.links.new(refracted.inputs[1], unrefracted_depth.outputs[0])

        reflection_limit = node_tree.nodes.new('ShaderNodeMath')
        reflection_limit.operation = 'SUBTRACT'
        reflection_limit.label = 'Limit Reflections'
        reflection_limit.inputs[0].default_value = 2.0
        node_tree.links.new(reflection_limit.inputs[1], ray_depth)

        camera_reflected = node_tree.nodes.new('ShaderNodeMath')
        camera_reflected.operation = 'MULTIPLY'
        camera_reflected.label = 'Camera Ray to Glossy'
        node_tree.links.new(camera_reflected.inputs[0], reflection_limit.outputs[0])
        node_tree.links.new(camera_reflected.inputs[1], is_glossy_ray)

        shadow_or_reflect = node_tree.nodes.new('ShaderNodeMath')
        shadow_or_reflect.operation = 'MAXIMUM'
        shadow_or_reflect.label = 'Shadow or Reflection?'
        node_tree.links.new(shadow_or_reflect.inputs[0], camera_reflected.outputs[0])
        node_tree.links.new(shadow_or_reflect.inputs[1], is_shadow_ray)

        shadow_or_reflect_or_refract = node_tree.nodes.new('ShaderNodeMath')
        shadow_or_reflect_or_refract.operation = 'MAXIMUM'
        shadow_or_reflect_or_refract.label = 'Shadow, Reflect or Refract?'
        node_tree.links.new(shadow_or_reflect_or_refract.inputs[0], shadow_or_reflect.outputs[0])
        node_tree.links.new(shadow_or_reflect_or_refract.inputs[1], refracted.outputs[0])

        mix_shader = node_tree.nodes.new('ShaderNodeMixShader')
        node_tree.links.new(mix_shader.inputs[0], shadow_or_reflect_or_refract.outputs[0])
        node_tree.links.new(mix_shader.inputs[1], diffuse_shader.outputs[0])
        node_tree.links.new(mix_shader.inputs[2], emission_shader.outputs[0])

        node_tree.links.new(output_node.inputs[0], mix_shader.outputs[0])

        auto_align_nodes(node_tree)

    group_node = dest_node_tree.nodes.new("ShaderNodeGroup")
    group_node.node_tree = node_tree

    return group_node

#### above func can be loaded from IAP via import  (below are modified) ///

def apply_texture_options(texture, img_spec):
        image_user = texture.image_user
        # image_user.use_auto_refresh = True # self.use_auto_refresh
        image_user.frame_start = img_spec.frame_start
        image_user.frame_offset = img_spec.frame_offset
        image_user.frame_duration = img_spec.frame_duration

        # Image sequences need auto refresh to display reliably
        # if img_spec.image.source == 'SEQUENCE':
        if img_spec.image.source in {'SEQUENCE', 'MOVIE'}:
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
        # Fallback on image name for images without filepath (generated/packed)
        name_compat = bpy.path.display_name_from_filepath(image.filepath) or image.name
        material = None
        if overwrite_material:
            for mat in bpy.data.materials:
                if mat.name == name_compat:
                    material = mat
        if not material:
            material = bpy.data.materials.new(name=name_compat)

        if bpy.app.version < (5, 0, 0):
            # Always True from 5.0 (use_nodes deprecated)
            material.use_nodes = True
        # if selfuse_transparency:
        if hasattr(material, 'surface_render_method'):
            # Blender 4.2+ (EEVEE Next)
            material.surface_render_method = 'BLENDED'
        else:
            material.blend_method = 'BLEND'
        node_tree = material.node_tree
        out_node = clean_node_tree(node_tree)

        tex_image = create_cycles_texnode(context, node_tree, img_spec)

        if shader == 'PRINCIPLED':
            core_shader = node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        elif shader == 'SHADELESS':
            # core_shader = iap.get_shadeless_node(node_tree)
            core_shader = get_shadeless_node(node_tree)
        elif shader == 'EMISSION':
            core_shader = node_tree.nodes.new('ShaderNodeBsdfPrincipled')
            core_shader.inputs['Emission Strength'].default_value = 1.0#emit_strength
            core_shader.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
            get_socket(core_shader.inputs, 'Specular IOR Level', 'Specular').default_value = 0.0

        # Connect color from texture
        if shader in {'PRINCIPLED', 'SHADELESS'}:
            node_tree.links.new(core_shader.inputs[0], tex_image.outputs['Color'])
        elif shader == 'EMISSION':
            node_tree.links.new(get_socket(core_shader.inputs, 'Emission Color', 'Emission'), tex_image.outputs['Color'])

        if use_transparency:
            if shader in {'PRINCIPLED', 'EMISSION'}:
                node_tree.links.new(core_shader.inputs['Alpha'], tex_image.outputs['Alpha'])
            else:
                bsdf_transparent = node_tree.nodes.new('ShaderNodeBsdfTransparent')

                mix_shader = node_tree.nodes.new('ShaderNodeMixShader')
                node_tree.links.new(mix_shader.inputs[0], tex_image.outputs['Alpha'])
                node_tree.links.new(mix_shader.inputs[1], bsdf_transparent.outputs['BSDF'])
                node_tree.links.new(mix_shader.inputs[2], core_shader.outputs[0])
                core_shader = mix_shader

        node_tree.links.new(out_node.inputs['Surface'], core_shader.outputs[0])

        # iap.auto_align_nodes(node_tree)
        auto_align_nodes(node_tree)
        return material

 ## Import image as plane addon function ---//


def create_image_plane(coords, name):
    '''Create an a mesh plane with a defaut UVmap from passed coordinate
    object and mesh get passed name
    
    return plane object
    '''
    fac = [(0, 1, 3, 2)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(coords, [], fac)
    plane = bpy.data.objects.new(name, me)
    # col = bpy.context.collection
    # col.objects.link(plane)

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

def convert_empty_image_to_mesh(context, o, name_from='IMAGE', delete_ref=True, shader='EMISSION'):
    """shader in ['EMISSION', 'PRINCIPLED', 'SHADELESS']"""
    img = o.data  
    img_user = o.image_user
    col = o.users_collection[0]
    
    if name_from == 'IMAGE':
        name = bpy.path.display_name(img.name, title_case=False)
    if name_from == 'OBJECT':
        name = re.sub(r'.\d{3}$', '', o.name) + '_texplane'
    
    ## increment if needed (ifommitted, blender will do it)
    new_name = name
    i=0
    while new_name in [ob.name for ob in col.all_objects]:
        i+=1
        new_name = f'{name}.{i:03d}'
    name = new_name

    print(f'\nConvert ref to mesh: {o.name} -> {name}')
    # ifp = img.filepath
    obj_space_corners = get_ref_object_space_coord(o)
    plane = create_image_plane(obj_space_corners, name=name)

    # link in same collection
    col.objects.link(plane)
    
    ## img_spec :: 'image', 'size', 'frame_start', 'frame_offset', 'frame_duration'
    # if img.source == 'FILE':
    #     img_spec = ImageSpec(img, (0,0), 0, 0, 1) # just to match IAP norm to send... (lazy mode)

    img_spec = ImageSpec(img, (img.size[0], img.size[1]), img_user.frame_start, img_user.frame_offset, img_user.frame_duration)
    material = create_cycles_material(context, img_spec, shader=shader)
    plane.data.materials.append(material)

    plane.parent = o.parent
    plane.matrix_local = o.matrix_local
    plane.matrix_parent_inverse = o.matrix_parent_inverse

    if delete_ref:
        bpy.data.objects.remove(o)


#### ----
## FROM CAM REFS
#### ----

def set_collection(ob, collection, unlink=True) :
    ''' link an object in a collection and create it if necessary, if unlink object is removed from other collections'''
    scn     = bpy.context.scene
    col     = None
    visible = False
    linked  = False

    # check if collection exist or create it
    for c in bpy.data.collections :
        if c.name == collection : col = c
    if not col : col = bpy.data.collections.new(name=collection)

    # link the collection to the scene's collection if necessary
    for c in scn.collection.children :
        if c.name == col.name : visible = True
    if not visible : scn.collection.children.link(col)

    # check if the object is already in the collection and link it if necessary
    for o in col.objects :
        if o == ob : linked = True
    if not linked : col.objects.link(ob)

    # remove object from scene's collection
    for o in scn.collection.objects :
        if o == ob : scn.collection.objects.unlink(ob)

    # if unlink flag we remove the object from other collections
    if unlink :
        for c in ob.users_collection :
            if c.name != collection : c.objects.unlink(ob)

def get_cam_fit_axis(cam, scene=None):
    '''Return the frame axis driven by camera angle/ortho_scale and shift:
    0 for width, 1 for height (resolves 'AUTO' sensor fit with render aspect)'''
    fit = cam.data.sensor_fit
    if fit == 'HORIZONTAL':
        return 0
    if fit == 'VERTICAL':
        return 1
    scene = scene or bpy.context.scene
    render = scene.render
    width = render.resolution_x * render.pixel_aspect_x
    height = render.resolution_y * render.pixel_aspect_y
    return 0 if width >= height else 1

def get_bg_image_frame_rect(scene, cam, bg):
    """Rect of a camera background image as drawn in camera view (without rotation):
    (center_x, center_y, width, height), relative to camera frame center,
    in frame units where camera fit axis size is 1.

    Mirror of Blender overlay image_camera_background_matrix_get
    (source/blender/draw/engines/overlay/overlay_camera.hh)
    """
    corners = cam.data.view_frame(scene=scene)
    cam_width = abs(corners[0].x - corners[3].x)
    cam_height = abs(corners[0].y - corners[1].y)
    cam_aspect = cam_width / cam_height

    img = bg.image
    image_aspect = (img.size[0] * img.display_aspect[0]) / (img.size[1] * img.display_aspect[1])

    if bg.frame_method == 'CROP':
        if image_aspect > cam_aspect:
            width, height = cam_height * image_aspect, cam_height
        else:
            width, height = cam_width, cam_width / image_aspect
    elif bg.frame_method == 'FIT':
        if image_aspect > cam_aspect:
            width, height = cam_width, cam_width / image_aspect
        else:
            width, height = cam_height * image_aspect, cam_height
    else: # STRETCH
        width, height = cam_width, cam_height

    width *= bg.scale
    height *= bg.scale

    offset_x, offset_y = bg.offset
    if cam.data.type == 'ORTHO':
        offset_x *= cam.data.ortho_scale
        offset_y *= cam.data.ortho_scale
    # Blender 2.80 behavior kept in overlay
    offset_x *= min(1.0, cam_aspect)
    offset_y /= max(1.0, cam_aspect) * (image_aspect / cam_aspect)

    fit_size = cam_width if get_cam_fit_axis(cam, scene) == 0 else cam_height
    return (offset_x / fit_size, offset_y / fit_size, width / fit_size, height / fit_size)

def set_bg_image_frame_rect(scene, cam, bg, center_x, center_y, width):
    """Set background image 'FIT' mode, scale and offset so the image is drawn
    at given rect (inverse of get_bg_image_frame_rect, same units, no rotation)"""
    corners = cam.data.view_frame(scene=scene)
    cam_width = abs(corners[0].x - corners[3].x)
    cam_height = abs(corners[0].y - corners[1].y)
    cam_aspect = cam_width / cam_height
    fit_size = cam_width if get_cam_fit_axis(cam, scene) == 0 else cam_height

    img = bg.image
    image_aspect = (img.size[0] * img.display_aspect[0]) / (img.size[1] * img.display_aspect[1])

    bg.frame_method = 'FIT'
    base_width = cam_width if image_aspect > cam_aspect else cam_height * image_aspect
    bg.scale = width * fit_size / base_width

    offset_x = center_x * fit_size / min(1.0, cam_aspect)
    offset_y = center_y * fit_size * max(1.0, cam_aspect) * (image_aspect / cam_aspect)
    if cam.data.type == 'ORTHO':
        offset_x /= cam.data.ortho_scale
        offset_y /= cam.data.ortho_scale
    bg.offset = (offset_x, offset_y)

def get_frame_size_factor(cam):
    '''Frame size (along fit axis) as a factor of plane distance for perspective,
    absolute size for orthographic'''
    from math import tan
    if cam.data.type == 'ORTHO':
        return cam.data.ortho_scale
    return tan(cam.data.angle / 2) * 2

def setup_transform_from_dist(cam, plane, distance):
    plane.parent = cam

    size = get_frame_size_factor(cam)
    if cam.data.type != 'ORTHO':
        size *= distance

    shift_x = cam.data.shift_x
    shift_y = cam.data.shift_y

    plane.location.x = size * shift_x
    plane.location.y = size * shift_y
    plane.location.z = -distance
    
    for axis in range(2):
        plane.scale[axis] = size # * scale/100.0
    
    # unparent from cam after ?

def create_plane_driver(cam, plane, distance=None):
    '''Setup custom prop and drivers on object transform to fit in cam frustum
    Code from les Fées spéciale
    https://gitlab.com/lfs.coop/blender/camera-plane
    '''

    if not plane.get("camera_plane_distance"):
        plane["camera_plane_distance"] = 10
    if not plane.get("camera_plane_scale"):
        plane["camera_plane_scale"] = 100
    
    plane.parent = cam
    # plane.show_wire = True
    # plane.matrix_world = cam.matrix_world # Already created with init transform
    plane.lock_location = (True,)*3
    plane.lock_rotation = (True,)*3
    plane.lock_scale =    (True,)*3

    ## Frame size variable: FOV in perspective, ortho scale in orthographic
    is_ortho = cam.data.type == 'ORTHO'
    frame_size = "ortho" if is_ortho else "tan(FOV/2) * distance*2"

    def add_frame_size_var(driver):
        var = driver.driver.variables.new()
        var.type = 'SINGLE_PROP'
        var.targets[0].id_type = "OBJECT"
        var.targets[0].id = cam
        if is_ortho:
            var.name = "ortho"
            var.targets[0].data_path = 'data.ortho_scale'
        else:
            var.name = "FOV"
            var.targets[0].data_path = 'data.angle'

    ## LOC X AND Y (shift) ##
    for axis in range(2):
        driver = plane.driver_add('location', axis)

        # Driver type
        driver.driver.type = 'SCRIPTED'

        # Variable DISTANCE
        var = driver.driver.variables.new()
        var.name = "distance"
        var.type = 'SINGLE_PROP'
        var.targets[0].id = plane
        var.targets[0].data_path = '["camera_plane_distance"]'

        # Variable FOV (or ortho scale)
        add_frame_size_var(driver)

        # Variable scale
        var = driver.driver.variables.new()
        var.name = "shift"
        var.type = 'SINGLE_PROP'
        var.targets[0].id = cam
        var.targets[0].data_path = 'data.shift_' + ('x' if axis == 0 else 'y')

        # Expression
        driver.driver.expression = f"{frame_size} * shift"

    ## DISTANCE ##
    driver = plane.driver_add('location', 2)
    # Driver type
    driver.driver.type = 'SCRIPTED'
    # Variable
    var = driver.driver.variables.new()
    var.name = "distance"
    var.type = 'SINGLE_PROP'
    var.targets[0].id = plane
    var.targets[0].data_path = '["camera_plane_distance"]'

    # Expression
    driver.driver.expression = "-distance"

    ## SCALE X AND Y ##
    for axis in range(2):
        driver = plane.driver_add('scale', axis)

        # Driver type
        driver.driver.type = 'SCRIPTED'

        # Variable DISTANCE
        var = driver.driver.variables.new()
        var.name = "distance"
        var.type = 'SINGLE_PROP'
        var.targets[0].id = plane
        var.targets[0].data_path = '["camera_plane_distance"]'

        # Variable FOV (or ortho scale)
        add_frame_size_var(driver)

        # Variable scale
        var = driver.driver.variables.new()
        var.name = "scale"
        var.type = 'SINGLE_PROP'
        var.targets[0].id = plane
        var.targets[0].data_path = '["camera_plane_scale"]'

        # Expression
        driver.driver.expression = f"{frame_size} * scale/100.0"
    
    # Set init distance if given
    if distance:
        plane["camera_plane_distance"] = distance
    

def create_plane_from_cam_bg(context, cam, bg, shader='EMISSION', distance=10, use_driver=False, col_name='Background'):
    '''Create an image plane matching a camera background image frame
    return plane object (None if background has no image)'''
    img = bg.image
    if not img:
        return

    name = img.name
    res_x, res_y = img.size

    # create plane coords matching the background image as drawn in camera view,
    # in frame units where camera fit axis size is 1
    # (the axis on which camera angle/ortho_scale and shift apply)
    center_x, center_y, width, height = get_bg_image_frame_rect(context.scene, cam, bg)
    flip_x = -1 if bg.use_flip_x else 1
    flip_y = -1 if bg.use_flip_y else 1
    rot = Matrix.Rotation(-bg.rotation, 2)

    # 3----2
    # |    |
    # 0----1 

    corners = [
        Vector((-0.5, -0.5)),
        Vector((0.5, -0.5)),
        Vector((-0.5, 0.5)),
        Vector((0.5, 0.5)),
        ]

    fit_based_corners = []
    for co in corners:
        local = rot @ Vector((co.x * width * flip_x, co.y * height * flip_y))
        fit_based_corners.append(Vector((center_x + local.x, center_y + local.y, 0)))

    plane = create_image_plane(fit_based_corners, name)
    
    ## 'image', 'size', 'frame_start', 'frame_offset', 'frame_duration'
    img_spec = ImageSpec(img, (res_x, res_y), bg.image_user.frame_start, bg.image_user.frame_offset, bg.image_user.frame_duration)
    material = create_cycles_material(context, img_spec, shader=shader)
    plane.data.materials.append(material)

    # context.scene.collection.objects.link(plane) # scene collection
    if not col_name:
        context.scene.collection.objects.link(plane)
    else:
        set_collection(plane, col_name)

    # create ctrl driver
    if use_driver:
        create_plane_driver(cam, plane, distance)
    else:
        setup_transform_from_dist(cam, plane, distance)

    print(f'Generated image plane {plane.name}')
    return plane

def convert_cam_bg_image_to_mesh(context, shader='EMISSION', distance=10, use_driver=False, post_state='HIDE', col_name='Background'):
    cam = context.object
    if not cam or cam.type != 'CAMERA':
        # fallback to scene active camera if no cam selected
        cam = context.scene.camera
    if not cam:
        return

    offset = 0
    for bg in reversed(cam.data.background_images):
        if not bg.show_background_image:
            continue

        plane = create_plane_from_cam_bg(context, cam, bg,
            shader=shader, distance=distance + offset, use_driver=use_driver, col_name=col_name)
        if not plane:
            continue

        if post_state == 'HIDE':
            bg.show_background_image = False
        elif post_state == 'DELETE':
            cam.data.background_images.remove(bg)
        
        offset += 2 # offset when mulitple ref to generate
