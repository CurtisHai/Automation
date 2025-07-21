import os
from workflow_automation import file_utils


def rename_directory(path: str, pattern: str = ""):
    """Rename files in a directory using smart rules or a custom pattern."""
    site_code = file_utils.parse_site_code(path)
    renamed = []
    for idx, name in enumerate(os.listdir(path), 1):
        src = os.path.join(path, name)
        if not os.path.isfile(src):
            continue
        if pattern:
            timestamp = file_utils.extract_timestamp(src)
            ext = os.path.splitext(src)[1]
            new_name = pattern.format(
                site=site_code,
                index=idx,
                timestamp=timestamp,
                ext=ext,
            )
            dst = os.path.join(path, new_name)
            os.rename(src, dst)
        else:
            dst = file_utils.smart_rename(src, site_code)
        renamed.append(os.path.basename(dst))
    return renamed
