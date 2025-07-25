import os
import zipfile


def zip_directory(path: str, output_zip: str, *, support_folder: str | None = None):
    """Zip an Autodesk Recap project or a directory.

    If ``support_folder`` is provided, ``path`` should point to a ``.rcp`` file
    and both the file and its support folder are archived to ``output_zip``. The
    resulting archive has the ``.rcp`` file and support folder at the archive
    root. When ``support_folder`` is omitted, the contents of ``path`` are
    zipped as before.
    """

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        if support_folder:
            base_dir = os.path.dirname(path)
            zf.write(path, os.path.basename(path))
            for root, _, files in os.walk(support_folder):
                for name in files:
                    fp = os.path.join(root, name)
                    arcname = os.path.relpath(fp, base_dir)
                    zf.write(fp, arcname)
        else:
            if os.path.isfile(path):
                zf.write(path, os.path.basename(path))
            else:
                for root, _, files in os.walk(path):
                    for name in files:
                        fp = os.path.join(root, name)
                        zf.write(fp, os.path.relpath(fp, path))
    return output_zip
