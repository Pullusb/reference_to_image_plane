# Changelog

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