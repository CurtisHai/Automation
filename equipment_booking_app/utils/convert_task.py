import os
import threading
import time
from workflow_automation import file_utils
from . import progress

def _worker(input_path: str, fmt: str):
    files = [f for f in os.listdir(input_path) if os.path.isfile(os.path.join(input_path, f))]
    progress.start("Converting Files", input_path, input_path, files)
    for name in files:
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
        src = os.path.join(input_path, name)
        base = os.path.splitext(src)[0]
        dst = f"{base}.{fmt}"
        file_utils.convert_video(src, dst, fmt, original_media=src)
        if dst != src:
            try:
                os.remove(src)
            except OSError:
                pass
        progress.update(name)
    progress.set_current("")
    progress.set_status("done")

def start_convert(input_path: str, fmt: str):
    thread = threading.Thread(target=_worker, args=(input_path, fmt), daemon=True)
    thread.start()
    return thread
