class Task:
    """Simple task base class for workflow steps."""

    def __init__(self, name=None):
        self.name = name or self.__class__.__name__

    def execute(self, job):
        job.setdefault(self.name, {"status": "success", "message": ""})
        return job

def return_failed(name, job):
    job.setdefault(name, {})
    job[name]["status"] = "failed"
    return None, job
