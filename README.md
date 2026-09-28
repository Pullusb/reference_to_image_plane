# Reference to image plane

Convert reference images to a textured image mesh plane.
As if it was imported with `import image as plane`

Use on drag'n'dropped image, empty object or camera background images

Note 👉 Since Blender 4.2, the main feature *"convert empty image to mesh plane"* has been [ported in Blender and improved by Nika Kutsniashvili](https://projects.blender.org/blender/blender/pulls/122546).

You still need this standalone version if you want to create image plane from a camera background image (button accessible from camera background image in properties).


**[Download latest](https://github.com/Pullusb/reference_to_image_plane/archive/refs/heads/main.zip)**

**[Demo on Youtube](https://youtu.be/tceQ7MuEHAw)**


### Extra Credits  

> Some function used where taken from built-in addon [Import image as plane](https://github.com/sobotka/blender-addons/blob/master/io_import_images_as_planes.py)  
> authors: Florian Meyer (tstscr), mont29, matali, Ted Schundler (SpkyElctrc)

> `create_plane_driver` function is taken from addon [Camera plane](https://gitlab.com/lfs.coop/blender/camera-plane)  
> author: _Les Fées Spéciales (LFS)_
---  

## Description

#### From empty objects references

Select some references Empty objects  
then call `Convert References To Image Planes`


Options:  
Shader can be chosen in `Emit`, `Principled` and `Shadeless`.  

Name of created texture plane can be built after image filename or from object name (suffixed `_texplane` in this case)

Also possible to delete Empty references after conversion (True by defaut)

Initial Empty image Transformation should be kepts in generated mesh.

#### From camera background images

Keep visible only background image you want to convert on selected/activecamera  
then call `Camera Bg Images To Image Planes`

Options:  
Same shader option as above

After creation, the background image can be hided or deleted with `Post Action` choice (Hide image planedefault)

Distance to set plane from camera (plane will be parented to camera)

Create Driver to keep plane in camera using two custom properties to control depth and scale

#### From viewport screenshot

Take a screenshot of the viewport (overlays, gizmos and UI regions are temporarily hidden).
Stored as an image in the blend file (packed), and added as camera background image matching current view.

- `Whole Viewport` (default): the whole viewport is captured, background image scale and offset are set so it matches the view around the camera frame. Disable to capture only the camera frame (in camera view, the view is then temporarily zoomed to fit the camera frame for maximum resolution, can be disabled)
- In camera view: use the view camera
- In free view: a new camera matching the view is created. Choose to crop the camera frame to render ratio, or to change the scene render resolution so the camera frame covers the whole view

Options:  
Background image opacity  
`Replace Existing` (default): replace previous screenshot of the same camera (removes previous image, its camera background images and generated image planes). In free view, the `ScreenshotCam` camera is updated instead of creating a new one  
Create an image plane from the screenshot, with same options as camera background conversion (shader, post action, distance, driver, collection)

### Where ?

To generate planes from selected empty references:  
`View 3D > Object Menu > Convert > Mesh From Empty Image` (an empty image should be selected)
or search (`F3`) > "Convert References To Image Planes" > Use pop-up the menu

To generate planes from visible background images:  
`Camera data properties > Background images > Image plane from visible refs`
or search (`F3`) > "Camera Bg Images To Image Planes" > Use pop-up the menu

To create a camera background from a viewport screenshot:  
`View 3D > View > Screenshot To Camera Background`
or search (`F3`) > "Viewport Screenshot To Camera Background"
