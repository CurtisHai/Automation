import threading

_lock = threading.Lock()
_data = {
    "task": None,
    "input_path": "",
    "output_path": "",
    "total": 0,
    "completed": [],
    "pending": [],
    "percent": 0,
    "status": "idle",
}
_args = ("","")

def start(task: str, input_path: str, output_path: str, files: list[str]):
    global _data, _args
    with _lock:
        _args = (input_path, output_path)
        _data = {
            "task": task,
            "input_path": input_path,
            "output_path": output_path,
            "total": len(files),
            "completed": [],
            "pending": list(files),
            "percent": 0,
            "status": "running",
        }

def get():
    with _lock:
        return dict(_data)

def update(file_name: str):
    with _lock:
        if file_name in _data["pending"]:
            _data["pending"].remove(file_name)
            _data["completed"].append(file_name)
        if _data["total"]:
            _data["percent"] = int(len(_data["completed"]) / _data["total"] * 100)

def set_status(status: str):
    with _lock:
        _data["status"] = status

def args():
    with _lock:
        return _args

def reset():
    start(None, "", "", [])
    set_status("idle")
