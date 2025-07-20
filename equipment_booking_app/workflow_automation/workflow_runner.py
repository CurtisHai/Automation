class WorkflowRunner:
    """Execute workflow steps in batch or pause mode."""

    def __init__(
        self,
        workflow,
        input_path,
        output_path,
        project_code=None,
        initials=None,
        step_configs=None,
        run_mode="run_all",
    ):
        self.workflow = workflow
        self.input_path = input_path
        self.output_path = output_path
        self.project_code = project_code
        self.initials = initials
        self.step_configs = step_configs or []
        self.run_mode = run_mode
        self.logs = []
        self.current_step = 0

    def run_all(self):
        while self.current_step < self.workflow.steps.count():
            self.run_next()

    def run_next(self):
        if self.current_step >= self.workflow.steps.count():
            return False

        step = self.workflow.steps.all()[self.current_step]
        config = {}
        if self.current_step < len(self.step_configs):
            config = self.step_configs[self.current_step]

        method = getattr(self, f"simulate_{step.step_type}", self.simulate_default)
        self.logs.append(f"Running step {step.order}: {step.get_step_type_display()}...")
        result = method(config)
        self.logs.append(result)
        self.current_step += 1
        return True

    def run(self):
        if self.run_mode == "run_all":
            self.run_all()
        else:
            self.run_next()
        return self.logs

    def simulate_default(self, config):
        return "Step completed"

    def simulate_rename(self, config):
        pattern = config.get("rename_pattern", "")
        if pattern:
            return f"Simulating Rename using pattern '{pattern}'...done"
        return "Simulating Rename...done"

    def simulate_trim(self, config):
        start = config.get("start_seconds")
        end = config.get("end_seconds")
        if start or end:
            return f"Simulating Trim ({start}s start, {end}s end)...done"
        return "Simulating Trim...done"

    def simulate_remove_audio(self, config):
        return "Simulating Remove Audio...done"

    def simulate_convert_360_video(self, config):
        fmt = config.get("convert_format")
        if fmt:
            return f"Simulating Convert to {fmt}...done"
        return "Simulating Convert 360 Video...done"

    def simulate_pause_manual(self, config):
        return "Simulating Manual Pause...done"

    def simulate_zip_files(self, config):
        return "Simulating Zip Files...done"

    def simulate_organize_files(self, config):
        return "Simulating Place Files...done"
