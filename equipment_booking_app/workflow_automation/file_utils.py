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


def organize_files(files, output_root, site_code="", target_folder=""):
    paths = []
    os.makedirs(output_root, exist_ok=True)
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in {".jpg", ".jpeg", ".png"}:
            folder = "360_photos"
        else:
            folder = "360_videos"
        if site_code:
            folder = os.path.join(site_code, folder)
        if target_folder:
            folder = os.path.join(target_folder, folder)
        out_dir = os.path.join(output_root, folder)
        os.makedirs(out_dir, exist_ok=True)
        dst = os.path.join(out_dir, os.path.basename(f))
        shutil.move(f, dst)
        paths.append(dst)
    return paths
