import os
import threading
import time
from . import zipper, progress


def _collect_rcp_pairs(input_path: str):
    pairs = []
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
            pairs.append((name, support))
    return pairs


def _worker(rcp_pairs: list[tuple[str, str]], input_path: str, output_folder: str):
    for name, support in rcp_pairs:
        if name in progress.get().get('completed', []):
            continue
        while True:
            status = progress.get().get('status')
            if status == 'paused':
                time.sleep(0.5)
                continue
            if status in {'cancel', 'cancelled'}:
                progress.set_status('cancelled')
                return
            break
        progress.set_current(name)
        rcp_path = os.path.join(input_path, name)
        out_zip = os.path.join(output_folder, os.path.splitext(name)[0] + '.zip')
        zipper.zip_directory(rcp_path, out_zip, support_folder=support)
        progress.update(name)
    progress.set_current("")
    progress.set_status('done')


def start_zip(input_path: str, output_folder: str, completed: list[str] | None = None):
    input_path = os.path.abspath(input_path)
    output_folder = os.path.abspath(output_folder)
    rcp_pairs = _collect_rcp_pairs(input_path)
    file_names = [name for name, _ in rcp_pairs]

    existing_zips = {os.path.splitext(n)[0] for n in os.listdir(output_folder) if n.lower().endswith('.zip')}
    auto_completed = [name for name in file_names if os.path.splitext(name)[0] in existing_zips]
    if completed:
        for n in auto_completed:
            if n not in completed:
                completed.append(n)
    else:
        completed = auto_completed

    progress.start("Zipping RCP Files", input_path, output_folder, file_names, completed)
    thread = threading.Thread(target=_worker, args=(rcp_pairs, input_path, output_folder), daemon=True)
    thread.start()
    return thread
