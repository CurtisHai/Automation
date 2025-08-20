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
        use_date_suffix=False,
    ):
        self.workflow = workflow
        # Always resolve paths to their absolute form so directory lookups
        # are consistent regardless of the server's working directory.
        self.input_path = os.path.abspath(input_path)
        self.output_path = os.path.abspath(output_path) if output_path else self.input_path
        if not os.path.isdir(self.input_path):
            raise FileNotFoundError(f"Input path {self.input_path} does not exist")
        self.project_code = project_code
        self.initials = initials
        self.step_configs = step_configs or []
        self.run_mode = run_mode
        self.qa_video_review = qa_video_review
        self.video_order_map = video_order_map or {}
        self.use_date_suffix = use_date_suffix
        self.logs = []
        self.current_step = 0
        self.defer_current_step = False
        self.review_pending = False
        self.review_image = ""
        self.review_file = ""
        self.conversion_index = 0
        self.conversion_done = False
        self.rename_actions = []
        self.finalize_index = 0
        self.last_crop_start = 0.0
        self.last_crop_end = 0.0
        self.last_remove_audio = False
        self._last_step_index = None

        # Track information about each processed video for logging
        self.video_log = []
        self._video_map = {}

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

        for p in self.files:
            entry = {
                "original": p,
                "new_path": p,
                "rename": "",
                "crop_start": 0.0,
                "crop_end": 0.0,
                "audio_removed": False,
                "flagged": False,
                "skip_reason": "",
            }
            self.video_log.append(entry)
            self._video_map[p] = entry

    # Helper methods to track video information
    def _update_video_path(self, old, new):
        entry = self._video_map.pop(old, None)
        if entry:
            entry["new_path"] = new
            self._video_map[new] = entry

    def record_rename(self, old, new, manual=False, flagged=False):
        self._update_video_path(old, new)
        entry = self._video_map.get(new)
        if entry is not None:
            entry["rename"] = "manual" if manual else "auto"
            if flagged:
                entry["flagged"] = True

    def record_crop(self, path, start, end):
        entry = self._video_map.get(path)
        if entry is not None:
            entry["crop_start"] = start
            entry["crop_end"] = end

    def record_audio_removal(self, path):
        entry = self._video_map.get(path)
        if entry is not None:
            entry["audio_removed"] = True

    def record_skip(self, path, reason):
        entry = self._video_map.get(path)
        if entry and not entry.get("skip_reason"):
            entry["skip_reason"] = reason

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

        method = getattr(self, f"run_{step.action}", self.run_default)

        if self._last_step_index != self.current_step:
            self.logs.append(
                f"Running step {step.order}: {step.get_action_display()}..."
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
        elif any(s.action in video_steps for s in self.workflow.steps.all()):
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
                self.record_rename(f, new_path, manual=False)
            else:
                new_path = file_utils.smart_rename(f, self.site_code)
                if new_path != f:
                    self.logs.append(
                        f"Renamed {os.path.basename(f)} -> {os.path.basename(new_path)}"
                    )
                    self.record_rename(f, new_path, manual=False)
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
            self.record_crop(out, start, end)
            self._update_video_path(f, out)
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
            self.record_audio_removal(out)
            self._update_video_path(f, out)
            new_files.append(out)
        self.files = new_files
        return "Audio removed"

    def _finalize_video(self, path, start, end, remove_audio):
        """Apply crop/audio options and move ``path`` into the RAW Data folder."""
        if start or end or remove_audio:
            file_utils.convert_video(
                path,
                path,
                "mp4",
                crop_start=start,
                crop_end=end,
                remove_audio=remove_audio,
                original_media=path,
            )

        date_token = datetime.now().strftime("%d%m%y")
        dest_dir = os.path.join(
            self.output_path,
            self.project_code,
            "Project Files",
            "3V - 360 Videos",
            f"{date_token}{self.initials}",
            "RAW Data",
        )
        os.makedirs(dest_dir, exist_ok=True)
        dst = os.path.join(dest_dir, os.path.basename(path))
        if os.path.abspath(path) != os.path.abspath(dst):
            shutil.move(path, dst)
        self._update_video_path(path, dst)
        self.record_crop(dst, start, end)
        if remove_audio:
            self.record_audio_removal(dst)
        open(dst + ".convert", "w").close()
        return dst

    def run_convert_360_video(self, config):
        fmt = config.get("convert_format") or "mp4"
        start = float(config.get("crop_start_seconds", 0) or 0)
        end = float(config.get("crop_end_seconds", 0) or 0)
        remove_aud = bool(config.get("remove_audio", False))

        self.last_crop_start = start
        self.last_crop_end = end
        self.last_remove_audio = remove_aud

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
                    else:
                        self.record_skip(f, "Not a 360 video")
                except Exception as e:
                    self.logs.append(f"Error converting {os.path.basename(f)}: {e}")
                new_files.append(job["media_file"])
                if job["media_file"] != f:
                    self._update_video_path(f, job["media_file"])
            self.files = new_files
            self.conversion_done = True
            if not self.qa_video_review:
                finalized = []
                for f in self.files:
                    mapping = self.video_order_map.get(os.path.basename(f))
                    if mapping and mapping.get("zone"):
                        new = file_utils.rename_with_zone(
                            f,
                            os.path.dirname(f),
                            mapping["zone"],
                            use_date_suffix=self.use_date_suffix,
                        )
                        if new != f:
                            self.logs.append(
                                f"Renamed {os.path.basename(f)} -> {os.path.basename(new)}"
                            )
                            self.record_rename(f, new, manual=False)
                        f = new
                    f = self._finalize_video(f, start, end, remove_aud)
                    finalized.append(f)
                self.files = finalized
                return "Conversion completed"

        if not self.qa_video_review:
            return "Conversion completed"

        while self.finalize_index < self.conversion_index - int(self.review_pending):
            idx = self.finalize_index
            self.files[idx] = self._finalize_video(
                self.files[idx], start, end, remove_aud
            )
            self.finalize_index += 1

        if self.conversion_index >= len(self.files):
            if not self.review_pending:
                while self.finalize_index < len(self.files):
                    idx = self.finalize_index
                    self.files[idx] = self._finalize_video(
                        self.files[idx], start, end, remove_aud
                    )
                    self.finalize_index += 1
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
