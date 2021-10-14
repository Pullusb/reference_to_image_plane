# Reference to image plane

Convert reference images to a textured image mesh plane.
As if it was imported with `import image as plane`

Use on drag'n'dropped image, empty object or camera background images

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

### Where ?

To generate planes from selected empty references:  
`View 3D > Object Menu > Convert > Mesh From Empty Image` (an empty image should be selected)
or search (`F3`) > "Convert References To Image Planes" > Use pop-up the menu

To generate planes from visible background images:  
`Camera data properties > Background images > Image plane from visible refs`
or search (`F3`) > "Camera Bg Images To Image Planes" > Use pop-up the menu
