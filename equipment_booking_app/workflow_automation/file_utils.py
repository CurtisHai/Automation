import os
import re
import shutil
import subprocess
from datetime import datetime


def ffmpeg_exists():
    return shutil.which("ffmpeg") is not None


def parse_site_code(path: str) -> str:
    """Return the last folder name as site code."""
    return os.path.basename(os.path.normpath(path))


def extract_timestamp(filename: str) -> str:
    """Extract a date-like stamp from filename or return mtime as YYYYMMDD."""
    basename = os.path.basename(filename)
    match = re.search(r"(\d{8})", basename)
    if not match:
        match = re.search(r"(\d{6})", basename)
    if match:
        return match.group(1)
    mtime = datetime.fromtimestamp(os.path.getmtime(filename))
    return mtime.strftime("%Y%m%d")


def convert_video(src: str, dst: str, fmt: str) -> str:
    """Convert a video using ffmpeg if available, else copy and rename."""
    if ffmpeg_exists():
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            src,
            dst,
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        shutil.copy2(src, dst)
    return dst


def remove_audio(src: str, dst: str) -> str:
    if ffmpeg_exists():
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            src,
            "-c",
            "copy",
            "-an",
            dst,
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        shutil.copy2(src, dst)
    return dst


def trim_video(src: str, dst: str, start: int, end: int) -> str:
    if ffmpeg_exists():
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            src,
        ]
        if start:
            cmd.extend(["-ss", str(start)])
        if end:
            cmd.extend(["-to", f"-{end}"])
        cmd.append(dst)
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        shutil.copy2(src, dst)
    return dst


PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".dng", ".insp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".insv"}
PHOTO_360_EXTS = {".insp"}
VIDEO_360_EXTS = {".insv"}


def classify_media(path: str) -> dict:
    """Return type info and destination folder for a media file."""
    ext = os.path.splitext(path)[1].lower()
    info = {
        "extension": ext,
        "is_photo": ext in PHOTO_EXTS,
        "is_video": ext in VIDEO_EXTS,
        "is_360": ext in PHOTO_360_EXTS or ext in VIDEO_360_EXTS,
    }
    if info["is_photo"]:
        base_folder = "360_photos" if info["is_360"] else "standard_photos"
    else:
        base_folder = "360_videos" if info["is_360"] else "standard_videos"
    info["dest_folder"] = base_folder
    info["needs_conversion"] = ext in PHOTO_360_EXTS or ext in VIDEO_360_EXTS
    return info


def smart_rename(path: str, site_code: str) -> str:
    """Rename a file to [prefix]-[zone]-3V-[YYMMDD].ext if needed."""
    name = os.path.basename(path)
    try:
        prefix, zone = site_code.rsplit("-", 1)
    except ValueError:
        prefix, zone = site_code, ""
    pattern = rf"^{re.escape(prefix)}-{re.escape(zone)}-3V-\d{{6}}"
    ext = os.path.splitext(name)[1].lower()
    if re.match(pattern + re.escape(ext) + "$", name):
        return path

    stamp = extract_timestamp(path)
    try:
        dt = datetime.strptime(stamp, "%Y%m%d")
        stamp = dt.strftime("%y%m%d")
    except ValueError:
        stamp = datetime.now().strftime("%y%m%d")
    new_name = f"{prefix}-{zone}-3V-{stamp}{ext}" if zone else f"{prefix}-3V-{stamp}{ext}"
    new_path = os.path.join(os.path.dirname(path), new_name)
    os.rename(path, new_path)
    return new_path


def organize_files(files, output_root, site_code="", target_folder=""):
    paths = []
    os.makedirs(output_root, exist_ok=True)
    for f in files:
        info = classify_media(f)
        folder = info["dest_folder"]
        if site_code:
            folder = os.path.join(site_code, folder)
        if target_folder:
            folder = os.path.join(target_folder, folder)
        out_dir = os.path.join(output_root, folder)
        os.makedirs(out_dir, exist_ok=True)
        dst = os.path.join(out_dir, os.path.basename(f))
        shutil.move(f, dst)
        if info.get("needs_conversion"):
            open(dst + ".convert", "w").close()
        paths.append(dst)
    return paths


def generate_next_filename(folder_path: str, extension: str = "") -> str | None:
    """Return the next sequential file name using existing zone patterns.

    The function searches ``folder_path`` along with its parent and grandparent
    directories (including all subfolders) for files matching the typical zone
    naming convention ``PREFIX-3V-XXXX.ext``. The highest numeric suffix found
    is incremented and combined with the detected prefix. ``extension`` is
    appended to the returned name. If no matching files are found, ``None`` is
    returned.
    """

    search_roots = [os.path.abspath(folder_path)]
    parent = os.path.dirname(search_roots[0])
    if parent and parent != search_roots[0]:
        search_roots.append(parent)
        grand = os.path.dirname(parent)
        if grand and grand != parent:
            search_roots.append(grand)

    pattern = re.compile(r"^([A-Za-z0-9-]+-3V)-(\d{4})", re.IGNORECASE)
    prefix_map = {}

    for root in search_roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for fname in files:
                match = pattern.match(fname)
                if match:
                    prefix, idx = match.group(1), int(match.group(2))
                    if idx > prefix_map.get(prefix, -1):
                        prefix_map[prefix] = idx

    if not prefix_map:
        return None

    prefix, cur_idx = sorted(prefix_map.items(), key=lambda x: x[1], reverse=True)[0]
    next_idx = cur_idx + 1
    candidate = f"{prefix}-{next_idx:04d}{extension}"

    while os.path.exists(os.path.join(folder_path, candidate)):
        next_idx += 1
        candidate = f"{prefix}-{next_idx:04d}{extension}"

    return candidate
