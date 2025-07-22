import os
from workflow_automation import file_utils


def convert_directory(
    path: str,
    fmt: str,
    *,
    crop_start: float = 0,
    crop_end: float = 0,
    remove_audio: bool = False,
):
    """Convert all video files in a directory to the given format with options."""
    converted = []
    for name in os.listdir(path):
        src = os.path.join(path, name)
        if not os.path.isfile(src):
            continue
        base = os.path.splitext(src)[0]
        dst = f"{base}.{fmt}"
        file_utils.convert_video(
            src,
            dst,
            fmt,
            crop_start=crop_start,
            crop_end=crop_end,
            remove_audio=remove_audio,
            original_media=src,
        )
        if dst != src:
            try:
                os.remove(src)
            except OSError:
                pass
        converted.append(os.path.basename(dst))
    return converted
