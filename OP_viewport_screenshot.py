"""Viewport screenshot stored as a camera background image, optionally an image plane.

UI is hidden, then a timer lets the event loop run for a few ticks
before taking the screenshot, then everything is restored.

Whole viewport (default): the full viewport is captured, background image
scale and offset are set so the image matches the view around camera frame.
Otherwise, the capture is cropped to the camera frame, the image then
fits the frame exactly (background image in 'Stretch' mode).
In free view, a new camera matching the view is created to hold the image.
"""

import os
import tempfile

import bpy
import numpy as np
from bpy.types import Operator
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector

from . import fn


# Space visibility toggle -> region type it controls
REGION_TOGGLE_TYPES = {
    "show_region_ui": 'UI',
    "show_region_toolbar": 'TOOLS',
    "show_region_header": 'HEADER',
    "show_region_tool_header": 'TOOL_HEADER',
    "show_region_asset_shelf": 'ASSET_SHELF',
}

# Timer interval (s) and number of ticks to wait for region hide to be applied
TICK = 0.05
HIDE_WAIT_TICKS = 6
# Extra ticks to wait after a camera view zoom change
ZOOM_WAIT_TICKS = 2
# Name of camera created from free view
SCREENSHOT_CAM_NAME = 'ScreenshotCam'
# Custom property set on generated image planes, holding the screenshot image name
PLANE_TAG = 'rtp_screenshot'

# Inset (px at UI scale 1) of viewport capture, to cut editor border, rounded corners
# 20 to also cut the small arrow tabs drawn at the edges for hidden regions (sidebar, toolbar)
VIEW_MARGIN = 10


def get_view_camera(context, space):
    """Camera object used by camera view of this viewport"""
    if getattr(space, 'use_local_camera', False) and space.camera:
        return space.camera
    return context.scene.camera


def get_render_aspect(scene):
    render = scene.render
    return (render.resolution_x * render.pixel_aspect_x) / (render.resolution_y * render.pixel_aspect_y)


def get_camera_frame_rect(scene, cam, region, rv3d):
    """Camera frame bounds in region coordinates: (x, y, width, height)"""
    frame = [cam.matrix_world @ co for co in cam.data.view_frame(scene=scene)]
    coords = [view3d_utils.location_3d_to_region_2d(region, rv3d, co) for co in frame]
    if any(c is None for c in coords):
        return None
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def rect_inside_region(rect, region, tolerance=1.0):
    x, y, w, h = rect
    return (x >= -tolerance and y >= -tolerance
            and x + w <= region.width + tolerance
            and y + h <= region.height + tolerance)


def fit_rect_to_aspect(width, height, aspect):
    """Largest centered rect of given aspect inside width x height: (x, y, w, h)"""
    if width / height > aspect:
        w, h = height * aspect, height
    else:
        w, h = width, width / aspect
    return ((width - w) / 2, (height - h) / 2, w, h)


def create_camera_from_view(context, space, region, rv3d, crop_rect, name=SCREENSHOT_CAM_NAME, cam=None):
    """Create a camera matching the free view, framing crop_rect (region coordinates).
    If cam is given, update this camera object instead of creating a new one.

    Uses the view projection matrix directly, so it matches whatever the viewport
    settings are (lens, ortho, zoom). Camera uses horizontal sensor fit, crop_rect
    must have the render aspect ratio.
    """
    wm = rv3d.window_matrix
    is_ortho = not rv3d.is_perspective

    x, y, w, h = crop_rect
    # Crop bounds to NDC
    ndc_l = 2 * x / region.width - 1
    ndc_r = 2 * (x + w) / region.width - 1
    ndc_b = 2 * y / region.height - 1
    ndc_t = 2 * (y + h) / region.height - 1

    # NDC to view space: at depth 1 for perspective, in world units for ortho
    if is_ortho:
        def to_view(ndc, axis):
            return (ndc - wm[axis][3]) / wm[axis][axis]
    else:
        def to_view(ndc, axis):
            return (ndc + wm[axis][2]) / wm[axis][axis]

    left, right = to_view(ndc_l, 0), to_view(ndc_r, 0)
    bottom, top = to_view(ndc_b, 1), to_view(ndc_t, 1)
    width = right - left

    cam_data = cam.data if cam else bpy.data.cameras.new(name)
    cam_data.sensor_fit = 'HORIZONTAL'
    # Shift is in units of the fit axis (width)
    cam_data.shift_x = (left + right) / 2 / width
    cam_data.shift_y = (bottom + top) / 2 / width

    view_matrix = rv3d.view_matrix.inverted()
    if is_ortho:
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = width
        # Ortho viewport clips on both sides of view center, move camera back
        cam_data.clip_start = 0.001
        cam_data.clip_end = space.clip_end
        back = view_matrix.to_3x3() @ Vector((0, 0, space.clip_end / 2))
        view_matrix = Matrix.Translation(back) @ view_matrix
    else:
        cam_data.type = 'PERSP'
        cam_data.lens = cam_data.sensor_width / width
        cam_data.clip_start = space.clip_start
        cam_data.clip_end = space.clip_end

    if cam is None:
        cam = bpy.data.objects.new(name, cam_data)
    if cam.name not in context.scene.objects:
        context.scene.collection.objects.link(cam)
    # Reset parenting/transform, cam may be an existing camera
    cam.parent = None
    cam.matrix_world = view_matrix.normalized()
    return cam


def image_from_screenshot(tmp_path, window, region, rect, name):
    """Create a packed image datablock from a window screenshot file,
    cropped to rect (region coordinates).
    Return image and the rect actually used after pixel rounding (region coordinates)"""
    shot = bpy.data.images.load(tmp_path)
    try:
        iw, ih = shot.size
        # region coords and window size share the same space,
        # saved image may be larger on HiDPI displays
        sx = iw / window.width
        sy = ih / window.height
        rx, ry, rw, rh = rect
        x0 = max(0, round((region.x + rx) * sx))
        y0 = max(0, round((region.y + ry) * sy))
        w = min(round(rw * sx), iw - x0)
        h = min(round(rh * sy), ih - y0)
        if w <= 0 or h <= 0:
            return None, None
        used_rect = (x0 / sx - region.x, y0 / sy - region.y, w / sx, h / sy)

        px = np.empty(iw * ih * 4, dtype=np.float32)
        shot.pixels.foreach_get(px)
        # Image pixels are stored bottom-up, same as region coords
        crop = px.reshape(ih, iw, 4)[y0:y0 + h, x0:x0 + w].copy()
        crop[..., 3] = 1.0
    finally:
        bpy.data.images.remove(shot)

    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(crop.ravel())
    # Pack so pixels are kept in the blend file
    img.pack()
    return img, used_rect


def remove_existing_screenshot(name):
    """Remove screenshot image with this name, the camera background images using it
    and the image planes generated from it"""
    img = bpy.data.images.get(name)

    for ob in list(bpy.data.objects):
        if ob.get(PLANE_TAG) != name:
            continue
        mesh = ob.data
        print(f'Screenshot to camera: remove previous image plane "{ob.name}"')
        bpy.data.objects.remove(ob)
        if mesh and mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    if img is None:
        return

    for cam_data in bpy.data.cameras:
        for bg in reversed(list(cam_data.background_images)):
            if bg.image == img:
                cam_data.background_images.remove(bg)

    print(f'Screenshot to camera: remove previous image "{img.name}"')
    bpy.data.images.remove(img)


class RTP_OT_viewport_screenshot_to_cam(Operator):
    bl_idname = "ref_to_image_plane.viewport_screenshot_to_cam"
    bl_label = "Viewport Screenshot To Camera Background"
    bl_description = ("Take a clean screenshot of the viewport (without overlays and UI)\n"
        "and set it as camera background image, matching the current view.\n"
        "In camera view: use the active camera\n"
        "In free view: create a camera matching the view\n"
        "Optionally generate an image plane from it")
    bl_options = {"REGISTER"} # Undo pushed manually once capture is done

    SHADERS = (
        ('PRINCIPLED',"Principled","Principled Shader"),
        ('SHADELESS', "Shadeless", "Only visible to camera and reflections"),
        ('EMISSION', "Emit", "Emission Shader"),
    )

    STATES = (
        ('HIDE', "Hide", "Hide camera background image once the image plane is generated"),
        ('DELETE', "Delete", "Delete camera background image once the image plane is generated"),
        ('NONE',"Do nothing","Keep camera background image visible"),
    )

    FIT_MODES = (
        ('CROP', "Crop To Render Ratio", "Crop screenshot to render resolution aspect ratio (scene settings untouched)"),
        ('RESOLUTION', "Change Resolution", "Keep the whole view, change scene render resolution height to match view aspect ratio"),
    )

    replace_existing: bpy.props.BoolProperty(name="Replace Existing", default=True,
        description="Replace previous screenshot of the same camera: remove previous image,\n"
        "its camera background images and generated image planes.\n"
        "In free view, update existing screenshot camera instead of creating a new one")

    opacity: bpy.props.FloatProperty(name="Opacity", default=0.5, min=0.0, max=1.0,
        subtype='FACTOR', description="Opacity of the camera background image")

    whole_viewport: bpy.props.BoolProperty(name="Whole Viewport", default=True,
        description="Capture the whole viewport instead of camera frame only.\n"
        "Background image scale and offset are set to match the view around camera frame")

    fit_camera_view: bpy.props.BoolProperty(name="Fit Camera Frame", default=True,
        description="When capturing camera frame only, temporarily zoom to fit camera frame in viewport\n"
        "before capture to get the maximum resolution (always done if frame is not fully visible)")

    free_view_fit: bpy.props.EnumProperty(name="Free View Fit", items=FIT_MODES, default='CROP',
        description="How to match free view aspect ratio with the new camera frame")

    create_plane: bpy.props.BoolProperty(name="Create Image Plane", default=False,
        description="Also generate an image plane from the screenshot, in camera frustum")

    shader: bpy.props.EnumProperty(name="Shader", items=SHADERS, default='SHADELESS',
        description="Node shader to use")

    post_state: bpy.props.EnumProperty(name="Background Post Action", items=STATES, default='HIDE',
        description="What to do with camera background image once image plane is generated")

    distance: bpy.props.FloatProperty(name="Distance", default=10.0, min=0.0,
        description="Distance to place image plane relative to camera")

    use_driver: bpy.props.BoolProperty(name="Create Driver", default=True,
        description="Create customs properties and driver on object to adjust scale and distance to camera anytime")

    collection: bpy.props.StringProperty(
        name='Destination Collection',
        description='Collection to put generated planes, create if necessary (Nothing = Scene Master Collection)',
        default='Background')

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'VIEW_3D'

    def get_view_area(self, context):
        """Viewport area: current one, else the one stored at invoke (dialog context)"""
        if context.area and context.area.type == 'VIEW_3D':
            return context.area
        return getattr(self, '_area', None)

    def invoke(self, context, event):
        self._area = context.area
        prefs = fn.get_prefs()
        self.collection = prefs.collection.strip()
        self.shader = prefs.shader
        self.use_driver = prefs.use_driver
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        col = layout.column(align=False)

        area = self.get_view_area(context)
        space = area.spaces.active if area else None
        if space is None:
            col.label(text='No viewport found', icon='ERROR')
        elif space.region_3d.view_perspective == 'CAMERA':
            cam = get_view_camera(context, space)
            col.label(text=f'Camera: {cam.name if cam else "None"}', icon='CAMERA_DATA')
            col.prop(self, 'whole_viewport')
            sub = col.column()
            sub.active = not self.whole_viewport
            sub.prop(self, 'fit_camera_view')
        else:
            existing = bpy.data.objects.get(SCREENSHOT_CAM_NAME)
            if self.replace_existing and existing and existing.type == 'CAMERA':
                col.label(text=f'Free view: camera "{existing.name}" will be updated', icon='CAMERA_DATA')
            else:
                col.label(text='Free view: a new camera will be created', icon='CAMERA_DATA')
            col.prop(self, 'whole_viewport')
            col.prop(self, 'free_view_fit', text='Camera Frame')

        col.prop(self, 'opacity')
        col.prop(self, 'replace_existing')

        col.separator()
        col.prop(self, 'create_plane')
        sub = col.column()
        sub.active = self.create_plane
        sub.prop(self, 'shader')
        sub.prop(self, 'post_state')
        sub.prop(self, 'distance')
        sub.prop(self, 'use_driver')
        sub.prop(self, 'collection')

        col.separator()
        row = col.row(align=True)
        row.label(text='')
        row.operator("rtp.open_addon_prefs", text="", icon='PREFERENCES')

    def execute(self, context):
        area = self.get_view_area(context)
        if area is None:
            self.report({'ERROR'}, "No viewport found")
            return {'CANCELLED'}
        space = area.spaces.active
        rv3d = space.region_3d
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        if region is None:
            self.report({'ERROR'}, "No viewport region found")
            return {'CANCELLED'}

        is_cam_view = rv3d.view_perspective == 'CAMERA'
        if is_cam_view and not get_view_camera(context, space):
            self.report({'ERROR'}, "No camera to use in camera view")
            return {'CANCELLED'}

        settings = {k: getattr(self, k) for k in (
            'opacity', 'replace_existing', 'whole_viewport', 'fit_camera_view', 'free_view_fit', 'create_plane', 'shader',
            'post_state', 'distance', 'use_driver', 'collection')}

        window = next((w for w in context.window_manager.windows if area in w.screen.areas[:]), context.window)
        capture = ViewportCapture(context, window, area, region, space, is_cam_view, settings)
        capture.start()
        return {'FINISHED'}


class ViewportCapture:
    """Asynchronous capture: hide UI, wait for the event loop to apply it,
    screenshot, restore, then build image, camera background and plane"""

    def __init__(self, context, window, area, region, space, is_cam_view, settings):
        self.window = window
        self.screen = window.screen
        self.area = area
        self.region = region
        self.space = space
        self.rv3d = space.region_3d
        self.scene = context.scene
        self.is_cam_view = is_cam_view
        self.settings = settings
        self.store = []
        self.region_attrs = []
        self.ticks = 0
        self.state = 'WAIT_HIDE'
        self.tmp_path = os.path.join(tempfile.gettempdir(), f"bl_rtp_shot_{os.getpid()}.png")

    def override(self, region=None):
        return bpy.context.temp_override(
            window=self.window, screen=self.screen, area=self.area,
            region=region or self.region, scene=self.scene)

    def set_temp(self, prop, attr, value):
        """Set attribute value, storing old one for restore"""
        old_val = getattr(prop, attr)
        if old_val == value:
            return
        try:
            setattr(prop, attr, value)
        except (AttributeError, RuntimeError, TypeError):
            # read-only when not available in current mode (e.g. asset shelf)
            return
        self.store.append((prop, attr, old_val))

    def start(self):
        space = self.space
        self.set_temp(space.overlay, "show_overlays", False)
        self.set_temp(space, "show_gizmo", False)
        for attr in REGION_TOGGLE_TYPES:
            if hasattr(space, attr):
                self.set_temp(space, attr, False)
        self.region_attrs = [a for _p, a, _o in self.store if a in REGION_TOGGLE_TYPES]

        if self.is_cam_view:
            # Stored to restore camera view zoom after capture
            self.store.append((self.rv3d, "view_camera_zoom", self.rv3d.view_camera_zoom))
            self.store.append((self.rv3d, "view_camera_offset", tuple(self.rv3d.view_camera_offset)))
            # Passepartout is drawn even with overlays disabled
            cam = get_view_camera(bpy.context, space)
            if cam:
                self.set_temp(cam.data, "show_passepartout", False)

        self.area.tag_redraw()
        bpy.app.timers.register(self.tick, first_interval=TICK)

    def reassert_hidden_regions(self):
        """Force out region still laid out despite its visibility flag being off
        (seen with tool header in Blender 5.2)"""
        for attr in self.region_attrs:
            rtype = REGION_TOGGLE_TYPES[attr]
            region = next((r for r in self.area.regions if r.type == rtype), None)
            if region is None or region.width <= 1 or region.height <= 1:
                continue
            try:
                with self.override(region=region):
                    bpy.ops.screen.region_toggle(region_type=rtype)
            except (RuntimeError, TypeError):
                pass

    def tick(self):
        try:
            return self._tick()
        except Exception:
            import traceback
            traceback.print_exc()
            self.finish()
            return None

    def _tick(self):
        # Viewport closed or changed meanwhile
        if self.area.type != 'VIEW_3D' or self.region.width <= 1:
            self.finish()
            return None

        self.ticks += 1
        if self.state == 'WAIT_HIDE':
            self.reassert_hidden_regions()
            if self.ticks < HIDE_WAIT_TICKS:
                return TICK

            if self.is_cam_view and not self.settings['whole_viewport'] and self.fit_camera_frame():
                # Let the zoom change be drawn
                self.state = 'WAIT_ZOOM'
                self.ticks = 0
                return TICK

        elif self.state == 'WAIT_ZOOM':
            if self.ticks < ZOOM_WAIT_TICKS:
                return TICK

        self.capture()
        return None

    def fit_camera_frame(self):
        """Zoom camera view to fit camera frame in viewport if needed, return True if done"""
        cam = get_view_camera(bpy.context, self.space)
        rect = get_camera_frame_rect(self.scene, cam, self.region, self.rv3d)
        if not self.settings['fit_camera_view'] and rect and rect_inside_region(rect, self.region):
            return False
        with self.override():
            bpy.ops.view3d.view_center_camera()
        self.area.tag_redraw()
        return True

    def capture(self):
        with self.override():
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
            bpy.ops.screen.screenshot(filepath=self.tmp_path)

        region = self.region
        scene = self.scene
        cam = None

        # Viewport rect, inset to exclude editor border, corners and hidden region arrows
        m = max(4, round(VIEW_MARGIN * bpy.context.preferences.system.ui_scale))
        view_rect = (m, m, region.width - 2 * m, region.height - 2 * m)

        # Camera frame rect (region coordinates)
        if self.is_cam_view:
            cam = get_view_camera(bpy.context, self.space)
            frame_rect = get_camera_frame_rect(scene, cam, region, self.rv3d)
        else:
            _x, _y, width, height = view_rect
            if self.settings['free_view_fit'] == 'RESOLUTION':
                frame_rect = view_rect
                render = scene.render
                render.resolution_y = max(1, round(
                    render.resolution_x * render.pixel_aspect_x * height
                    / (width * render.pixel_aspect_y)))
            else:
                x, y, w, h = fit_rect_to_aspect(width, height, get_render_aspect(scene))
                frame_rect = (x + m, y + m, w, h)

        if not os.path.exists(self.tmp_path) or frame_rect is None:
            self.finish()
            print('Screenshot to camera: capture failed')
            return

        replace = self.settings['replace_existing']
        if not self.is_cam_view:
            # Camera created from view before restoring anything
            existing = bpy.data.objects.get(SCREENSHOT_CAM_NAME) if replace else None
            if existing and existing.type != 'CAMERA':
                existing = None
            cam = create_camera_from_view(bpy.context, self.space, region, self.rv3d, frame_rect, cam=existing)

        whole = self.settings['whole_viewport']
        name = f'{cam.name}_screenshot'
        if replace:
            # Free the name, new image get the exact same one
            remove_existing_screenshot(name)
        img, image_rect = image_from_screenshot(self.tmp_path, self.window, region,
                                                view_rect if whole else frame_rect, name)
        self.finish()
        if img is None:
            print('Screenshot to camera: invalid crop size')
            return

        self.setup_camera_background(cam, img, frame_rect if whole else None, image_rect)

        with self.override():
            bpy.ops.ed.undo_push(message="Viewport Screenshot To Camera")

    def setup_camera_background(self, cam, img, frame_rect=None, image_rect=None):
        """Add image as camera background.
        frame_rect, image_rect: camera frame and image rects in viewport (region coordinates),
        used to scale and offset the image to match the view. If None, image is the camera frame"""
        settings = self.settings
        cam.data.show_background_images = True
        bg = cam.data.background_images.new()
        bg.image = img
        bg.source = 'IMAGE'
        bg.alpha = settings['opacity']
        bg.rotation = 0.0
        if frame_rect is None:
            # Screenshot has camera frame aspect: stretch avoids any rounding offset
            bg.frame_method = 'STRETCH'
            bg.offset = (0.0, 0.0)
            bg.scale = 1.0
        else:
            self.place_background(cam, bg, frame_rect, image_rect)
        bg.use_flip_x = False
        bg.use_flip_y = False
        bg.show_background_image = True

        # Expand only the new one in the UI
        for b in cam.data.background_images:
            b.show_expanded = b == bg

        print(f'Screenshot to camera: "{img.name}" ({img.size[0]}x{img.size[1]}) added to "{cam.name}" background images')

        if not settings['create_plane']:
            return

        plane = fn.create_plane_from_cam_bg(bpy.context, cam, bg,
            shader=settings['shader'],
            distance=settings['distance'],
            use_driver=settings['use_driver'],
            col_name=settings['collection'].strip())

        if plane:
            # Tag to find it back when replacing this screenshot
            plane[PLANE_TAG] = img.name
            if settings['post_state'] == 'HIDE':
                bg.show_background_image = False
            elif settings['post_state'] == 'DELETE':
                cam.data.background_images.remove(bg)

    def place_background(self, cam, bg, frame_rect, image_rect):
        """Scale and offset background image so image_rect matches its viewport location
        relative to camera frame_rect (both in region coordinates)"""
        fx, fy, fw, fh = frame_rect
        ix, iy, iw, ih = image_rect
        # Frame units where camera fit axis size is 1, relative to frame center
        fit_size = fw if fn.get_cam_fit_axis(cam, self.scene) == 0 else fh
        center_x = (ix + iw / 2 - (fx + fw / 2)) / fit_size
        center_y = (iy + ih / 2 - (fy + fh / 2)) / fit_size
        fn.set_bg_image_frame_rect(self.scene, cam, bg, center_x, center_y, iw / fit_size)

    def finish(self):
        """Restore UI state and remove temp file. Idempotent"""
        for prop, attr, old_val in reversed(self.store):
            try:
                setattr(prop, attr, old_val)
            except Exception:
                pass
        self.store = []

        if os.path.exists(self.tmp_path):
            try:
                os.remove(self.tmp_path)
            except OSError:
                pass

        try:
            self.area.tag_redraw()
        except ReferenceError:
            pass


classes=(
RTP_OT_viewport_screenshot_to_cam,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
