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
    "current": "",
}
_args = ("","")

def start(task: str, input_path: str, output_path: str, files: list[str], completed: list[str] | None = None):
    global _data, _args
    with _lock:
        _args = (input_path, output_path)
        if completed is None:
            completed = []
        pending = [f for f in files if f not in completed]
        percent = int(len(completed) / len(files) * 100) if files else 0
        _data = {
            "task": task,
            "input_path": input_path,
            "output_path": output_path,
            "total": len(files),
            "completed": list(completed),
            "pending": pending,
            "percent": percent,
            "status": "running",
            "current": "",
        }

def get():
    with _lock:
        return dict(_data)

def update(file_name: str):
    with _lock:
        _data["current"] = ""
        if file_name in _data["pending"]:
            _data["pending"].remove(file_name)
            _data["completed"].append(file_name)
        if _data["total"]:
            _data["percent"] = int(len(_data["completed"]) / _data["total"] * 100)

def set_current(file_name: str):
    with _lock:
        _data["current"] = file_name

def set_status(status: str):
    with _lock:
        _data["status"] = status

def args():
    with _lock:
        return _args

def reset():
    start(None, "", "", [])
    set_status("idle")
