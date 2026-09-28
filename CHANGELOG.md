# Changelog

0.5.0

- feat: `View > Screenshot To Camera Background`: viewport screenshot (no overlays/UI) stored as image and added as camera background, matching the view
  - whole viewport capture by default: background image scale and offset are set to match the view around camera frame
  - option to capture camera frame only.
  - camera view: use view camera
  - free view: create a new camera matching the view (camera frame cropped to render ratio or change render resolution)
  - option to also generate an image plane (same options as camera background conversion)
  - `Replace Existing` option (default on): a new screenshot replaces the previous one of the same camera (image, camera background image and generated image plane), in free view the screenshot camera is updated instead of creating a new one
- feat: image planes generated from camera background images follow the background image fit method, scale, offset, rotation and flip
- fix: shader errors for Blender 4.0+
- fix: camera image plane size/shift with portrait resolution, vertical sensor fit and orthographic cameras

0.4.1

- feat: Add 'REF_TO_PLANE_COLLECTION' env variable to set destination collection for custom projects

0.4.0

- feat: choose destination collection in pop-up
- feat: addon preferences for settings:
  - default plane shader
  - default driver creation 
  - default dest collection name
- feat: added shortcut button in pop-up to open addon prefs
- changes: default shader is now Shadeless instead ot emit
- changes: create driver is toggles on by default

0.3.2

- fix: updated repo name and doc/tracker links

0.3.1

- fix: Convert active even if not selected (since convert menu entry appear)

0.3.0

- feat: add plane generation from camera background image (driver method taken from [LFS camera_plane](https://gitlab.com/lfs.coop/blender/camera-plane/-/blob/master/camera_plane.py))
- ui: add menu entry in `View 3D > Object > Convert` for object conversion
- ui: add button in `Propeties > cam data > background image` for bg image conversion
- doc: update to reflect changes

0.2.0

- feat: option to get name from orignal image or from empty object
- fix: bug with linking
- doc: fic readme link and description
- code: cleaner:
  - copied function locally instead of importing from IAP
  - add bug report url
  - add git-ignore

0.1.0

- working version