class WorkflowRunner:
    """Executes workflow steps with placeholder implementations."""

    def __init__(self, workflow, input_path, project_code=None, initials=None):
        self.workflow = workflow
        self.input_path = input_path
        self.project_code = project_code
        self.initials = initials
        self.logs = []

    def run(self):
        for step in self.workflow.steps.all():
            method = getattr(self, f"simulate_{step.step_type}", self.simulate_default)
            self.logs.append(f"Running step {step.order}: {step.get_step_type_display()}...")
            result = method()
            self.logs.append(result)
        return self.logs

    def simulate_default(self):
        return "Step completed"

    def simulate_rename(self):
        return "Simulating Rename...done"

    def simulate_trim(self):
        return "Simulating Trim...done"

    def simulate_remove_audio(self):
        return "Simulating Remove Audio...done"

    def simulate_convert_360_video(self):
        return "Simulating Convert 360 Video...done"

    def simulate_pause_manual(self):
        return "Simulating Manual Pause...done"

    def simulate_zip_files(self):
        return "Simulating Zip Files...done"
