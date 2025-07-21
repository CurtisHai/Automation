import os
from workflow_automation import file_utils


def convert_directory(path: str, fmt: str):
    """Convert all video files in a directory to the given format."""
    converted = []
    for name in os.listdir(path):
        src = os.path.join(path, name)
        if not os.path.isfile(src):
            continue
        base = os.path.splitext(src)[0]
        dst = f"{base}.{fmt}"
        file_utils.convert_video(src, dst, fmt)
        if dst != src:
            try:
                os.remove(src)
            except OSError:
                pass
        converted.append(os.path.basename(dst))
    return converted
