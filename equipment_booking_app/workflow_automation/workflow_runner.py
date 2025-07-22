"""Utility to execute a saved workflow step by step."""

import os
import shutil
from datetime import datetime
from . import file_utils
from automation_core.utils.video_converter import (
    insta360_convert,
    gopro_convert,
)


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
        qa_video_review=False,
        video_order_map=None,
    ):
        self.workflow = workflow
        self.input_path = input_path
        self.output_path = output_path or input_path
        self.project_code = project_code
        self.initials = initials
        self.step_configs = step_configs or []
        self.run_mode = run_mode
        self.qa_video_review = qa_video_review
        self.video_order_map = video_order_map or {}
        self.logs = []
        self.current_step = 0
        self.defer_current_step = False
        self.review_pending = False
        self.review_image = ""
        self.review_file = ""
        self.conversion_index = 0
        self.conversion_done = False
        self.rename_actions = []
        self.last_crop_start = 0.0
        self.last_crop_end = 0.0
        self.last_remove_audio = False
        self._last_step_index = None

        self.site_code = file_utils.parse_site_code(self.input_path)
        self.files = [
            os.path.join(self.input_path, f)
            for f in os.listdir(self.input_path)
            if os.path.isfile(os.path.join(self.input_path, f))
        ]
        if self.video_order_map:
            self.files.sort(
                key=lambda p: self.video_order_map.get(os.path.basename(p), {}).get("order", 0)
            )

    def run_all(self):
        while self.current_step < self.workflow.steps.count():
            self.run_next()
            if self.defer_current_step or self.review_pending:
                break

    def run_next(self):
        if self.current_step >= self.workflow.steps.count():
            return False

        step = self.workflow.steps.all()[self.current_step]
        config = {}
        if self.current_step < len(self.step_configs):
            config = self.step_configs[self.current_step]

        method = getattr(self, f"run_{step.step_type}", self.run_default)

        if self._last_step_index != self.current_step:
            self.logs.append(
                f"Running step {step.order}: {step.get_step_type_display()}..."
            )
            self._last_step_index = self.current_step

        self.defer_current_step = False
        result = method(config)
        self.logs.append(result)
        if not self.defer_current_step and not self.review_pending:
            self.current_step += 1
            self._last_step_index = None
        return True

    def run(self):
        if self.run_mode == "run_all":
            self.run_all()
        else:
            self.run_next()
        return self.logs

    def run_default(self, config):
        return "Step completed"

    def run_setup_structure(self, config):
        raw_folder = config.get("raw_data_folder")
        full = config.get("full_structure", False)

        template_base = (
            "P:/Energy/RealityCapture/Sellafield/Sellafield/00-00-00 Template/Project Files"
        )
        project_root = os.path.join(self.output_path, self.project_code, "Project Files")
        os.makedirs(project_root, exist_ok=True)

        video_steps = {"convert_360_video", "remove_audio", "trim"}
        if full:
            subfolders = None
        elif any(s.step_type in video_steps for s in self.workflow.steps.all()):
            subfolders = ["3V - 360 Videos"]
        else:
            subfolders = ["3P - 360 Photos"]

        file_utils.copy_template_structure(
            template_base,
            project_root,
            subfolders=subfolders,
            initials=self.initials or "",
        )

        date_token = datetime.now().strftime("%d%m%y")
        raw_dest = project_root
        if subfolders:
            raw_dest = os.path.join(project_root, subfolders[0])
        raw_dest = os.path.join(raw_dest, f"{date_token}{self.initials}", "RAW Data")
        os.makedirs(raw_dest, exist_ok=True)
        if raw_folder and os.path.isdir(raw_folder):
            for fname in os.listdir(raw_folder):
                src = os.path.join(raw_folder, fname)
                if os.path.isfile(src):
                    shutil.move(src, os.path.join(raw_dest, fname))

        return f"Structure created at {raw_dest}"

    def run_rename(self, config):
        pattern = config.get("rename_pattern", "")
        new_files = []
        for idx, f in enumerate(self.files, 1):
            if pattern:
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
                if os.path.basename(f) != new_name:
                    self.logs.append(
                        f"Renamed {os.path.basename(f)} -> {new_name}"
                    )
            else:
                new_path = file_utils.smart_rename(f, self.site_code)
                if new_path != f:
                    self.logs.append(
                        f"Renamed {os.path.basename(f)} -> {os.path.basename(new_path)}"
                    )
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
        fmt = config.get("convert_format") or "mp4"

        if not self.conversion_done:
            new_files = []
            for f in self.files:
                ext = os.path.splitext(f)[1].lower()
                job = {"media_file": f}
                try:
                    if ext in [".insv", ".insp", ".lrv"]:
                        job = insta360_convert(job)
                    elif ext == ".360":
                        job = gopro_convert(job)
                except Exception as e:
                    self.logs.append(f"Error converting {os.path.basename(f)}: {e}")
                new_files.append(job["media_file"])
            self.files = new_files
            self.conversion_done = True
            if not self.qa_video_review:
                renamed = []
                for f in self.files:
                    mapping = self.video_order_map.get(os.path.basename(f))
                    if mapping and mapping.get("zone"):
                        new = file_utils.rename_with_zone(f, os.path.dirname(f), mapping["zone"])
                        if new != f:
                            self.logs.append(
                                f"Renamed {os.path.basename(f)} -> {os.path.basename(new)}"
                            )
                        f = new
                    renamed.append(f)
                self.files = renamed
                return "Conversion completed"

        if not self.qa_video_review:
            return "Conversion completed"

        if self.conversion_index >= len(self.files):
            return "Conversion completed"

        f = self.files[self.conversion_index]
        base = os.path.splitext(f)[0]
        preview_dir = os.path.join(self.output_path, "previews")
        os.makedirs(preview_dir, exist_ok=True)
        preview_name = os.path.basename(base) + "_preview.jpg"
        preview_path = os.path.join(preview_dir, preview_name)
        file_utils.generate_video_preview(f, preview_path)

        self.review_pending = True
        self.review_image = preview_path
        self.review_file = f
        self.conversion_index += 1
        self.defer_current_step = True
        return f"Review {os.path.basename(f)}"

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
