from ..template import Task

class ValidateResources(Task):
    """Placeholder validation step."""

    def execute(self, job):
        super().execute(job)
        return None, job
