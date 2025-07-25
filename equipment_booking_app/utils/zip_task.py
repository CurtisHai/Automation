import os
import threading
import time
from . import zipper, progress


def _worker(input_path: str, output_folder: str):
    rcp_pairs = []
    for name in os.listdir(input_path):
        if not name.lower().endswith('.rcp'):
            continue
        base = os.path.splitext(name)[0]
        candidates = [f"{base}_support", f"{base} support"]
        support = None
        for cand in candidates:
            cand_path = os.path.join(input_path, cand)
            if os.path.isdir(cand_path):
                support = cand_path
                break
        if support:
            rcp_pairs.append((name, support))
    file_names = [name for name, _ in rcp_pairs]
    progress.start("Zipping RCP Files", input_path, output_folder, file_names)
    for name, support in rcp_pairs:
        while progress.get().get('status') == 'paused':
            time.sleep(0.5)
        if progress.get().get('status') in {'cancel', 'cancelled'}:
            progress.set_status('cancelled')
            return
        rcp_path = os.path.join(input_path, name)
        out_zip = os.path.join(output_folder, os.path.splitext(name)[0] + '.zip')
        zipper.zip_directory(rcp_path, out_zip, support_folder=support)
        progress.update(name)
    progress.set_status('done')


def start_zip(input_path: str, output_folder: str):
    thread = threading.Thread(target=_worker, args=(input_path, output_folder), daemon=True)
    thread.start()
    return thread
