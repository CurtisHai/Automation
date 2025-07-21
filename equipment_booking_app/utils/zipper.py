import os
import zipfile


def zip_directory(path: str, output_zip: str):
    """Zip the contents of a directory."""
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(path):
            for name in files:
                fp = os.path.join(root, name)
                zf.write(fp, os.path.relpath(fp, path))
    return output_zip
