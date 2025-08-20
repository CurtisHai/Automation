import os
import threading
import time
from . import progress, rename

def _worker(raw_folder: str, output_folder: str, initials: str, full_name: str, pattern: str):
    files = [f for f in os.listdir(raw_folder) if os.path.isfile(os.path.join(raw_folder, f))]
    progress.start("Renaming Files", raw_folder, output_folder, files)
    renamed = rename.rename_directory(raw_folder, pattern)
    os.makedirs(output_folder, exist_ok=True)
    for name in renamed:
        while True:
            status = progress.get().get("status")
            if status == "paused":
                time.sleep(0.5)
                continue
            if status in {"cancel", "cancelled"}:
                progress.set_status("cancelled")
                return
            break
        progress.set_current(name)
        src = os.path.join(raw_folder, name)
        dst = os.path.join(output_folder, name)
        os.replace(src, dst)
        progress.update(name)
    progress.set_current("")
    progress.set_status("done")

def start_rename(raw_folder: str, output_folder: str, initials: str, full_name: str, pattern: str = ""):
    raw_folder = os.path.abspath(raw_folder)
    output_folder = os.path.abspath(output_folder)
    thread = threading.Thread(target=_worker, args=(raw_folder, output_folder, initials, full_name, pattern), daemon=True)
    thread.start()
    return thread
