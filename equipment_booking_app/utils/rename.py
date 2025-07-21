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


def run_rename(raw_data_folder: str, output_folder: str, user_initials: str, full_name: str):
    """Rename media in ``raw_data_folder`` and move to ``output_folder``.

    The function validates the input folder contains files, performs a smart
    rename using :func:`rename_directory`, then moves the renamed files to the
    output folder. ``user_initials`` and ``full_name`` are accepted for future
    extensions but are currently unused.
    """

    if not os.path.isdir(raw_data_folder):
        raise ValueError("RAW data folder does not exist")

    files = [f for f in os.listdir(raw_data_folder) if os.path.isfile(os.path.join(raw_data_folder, f))]
    if not files:
        raise ValueError("RAW data folder contains no files")

    os.makedirs(output_folder, exist_ok=True)

    renamed = rename_directory(raw_data_folder)
    results = []
    for name in renamed:
        src = os.path.join(raw_data_folder, name)
        dst = os.path.join(output_folder, name)
        os.replace(src, dst)
        results.append(dst)

    return results
