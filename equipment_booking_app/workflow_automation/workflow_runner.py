"""Utility to execute a saved workflow step by step."""

import os
from . import file_utils


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
        self.output_path = output_path or input_path
        self.project_code = project_code
        self.initials = initials
        self.step_configs = step_configs or []
        self.run_mode = run_mode
        self.logs = []
        self.current_step = 0

        self.site_code = file_utils.parse_site_code(self.input_path)
        self.files = [
            os.path.join(self.input_path, f)
            for f in os.listdir(self.input_path)
            if os.path.isfile(os.path.join(self.input_path, f))
        ]

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

        method = getattr(self, f"run_{step.step_type}", self.run_default)
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

    def run_default(self, config):
        return "Step completed"

    def run_rename(self, config):
        pattern = config.get("rename_pattern") or "{site}-{index}-{timestamp}{ext}"
        new_files = []
        for idx, f in enumerate(self.files, 1):
            timestamp = file_utils.extract_timestamp(f)
            ext = os.path.splitext(f)[1]
            new_name = pattern.format(
                site=self.site_code,
                index=idx,
                timestamp=timestamp,
                ext=ext,
            )
            new_path = os.path.join(os.path.dirname(f), new_name)
            os.rename(f, new_path)
            self.logs.append(f"Renamed {os.path.basename(f)} -> {new_name}")
            new_files.append(new_path)
        self.files = new_files
        return "Rename completed"

    def run_trim(self, config):
        start = int(config.get("start_seconds", 0) or 0)
        end = int(config.get("end_seconds", 0) or 0)
        if not (start or end):
            return "Trim skipped"
        new_files = []
        for f in self.files:
            base, ext = os.path.splitext(f)
            out = f"{base}_trim{ext}"
            file_utils.trim_video(f, out, start, end)
            self.logs.append(f"Trimmed {os.path.basename(f)}")
            os.remove(f)
            new_files.append(out)
        self.files = new_files
        return "Trim completed"

    def run_remove_audio(self, config):
        new_files = []
        for f in self.files:
            base, ext = os.path.splitext(f)
            out = f"{base}_mute{ext}"
            file_utils.remove_audio(f, out)
            self.logs.append(f"Removed audio from {os.path.basename(f)}")
            os.remove(f)
            new_files.append(out)
        self.files = new_files
        return "Audio removed"

    def run_convert_360_video(self, config):
        fmt = config.get("convert_format")
        if not fmt:
            return "Conversion skipped"
        new_files = []
        for f in self.files:
            base = os.path.splitext(f)[0]
            out = f"{base}.{fmt}"
            file_utils.convert_video(f, out, fmt)
            self.logs.append(f"Converted {os.path.basename(f)} to {fmt}")
            if out != f:
                os.remove(f)
            new_files.append(out)
        self.files = new_files
        return "Conversion completed"

    def run_pause_manual(self, config):
        return "Manual pause"

    def run_zip_files(self, config):
        return "Zip step not implemented"

    def run_organize_files(self, config):
        target_folder = config.get("target_folder", "")
        self.files = file_utils.organize_files(
            self.files, self.output_path, site_code=self.site_code, target_folder=target_folder
        )
        return "Files organized"
