# Automation

This repository contains a Django application focused on Reality Capture workflow automation. The app originated as an equipment booking tool, so some legacy names may remain.

## Workflow Utilities

The application ships with a small utility module used by workflows to manage
media files. Recent improvements include:

- **File classification** for photos and videos, including 360/standard
  detection based on file extensions.
- **Smart renaming** using folder names and timestamps (`[PREFIX]-[ZONE]-3V-[YYMMDD].ext`).
- **Folder organization** that routes media into `360_photos/`,
  `standard_photos/`, `360_videos/`, or `standard_videos/`.
- **Conversion markers** for 360 photo formats such as `.insp` so that other
  tools can process them later.
- **GoPro conversion** runs GPU-accelerated scripts with a fallback to CPU when
  handling `.360` files.
- **Batch conversion first** then optional QA review with one-second previews
  allows accepting zone-based names or flagging files for manual edits.
