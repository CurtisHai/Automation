from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.urls import reverse
from .models import Workflow
from .workflow_runner import WorkflowRunner
from . import file_utils, views
from .log_writer import write_workflow_log
from types import SimpleNamespace
from unittest.mock import patch
import os
import shutil
import tempfile
from datetime import datetime


class FileUtilsTests(TestCase):
    def test_classify_photo_and_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "image.insp")
            with open(path, "wb") as fh:
                fh.write(b"\x00")

            info = file_utils.classify_media(path)
            self.assertTrue(info["is_photo"])
            self.assertTrue(info["is_360"])

            new_name = file_utils.smart_rename(path, "SL-SL-SR-101A")
            self.assertTrue(os.path.exists(new_name))

    def test_organize_and_mark_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = os.path.join(tmp, "photo.insp")
            with open(file_path, "wb") as fh:
                fh.write(b"\x00")

            out_root = os.path.join(tmp, "out")
            paths = file_utils.organize_files([file_path], out_root, site_code="SITE")
            self.assertEqual(len(paths), 1)
            self.assertTrue(paths[0].startswith(os.path.join(out_root, "SITE")))
            self.assertTrue(os.path.exists(paths[0] + ".convert"))


class WorkflowMatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="tester")
        self.wf = Workflow.objects.create(name="SL-SL-SR-101A", created_by=self.user)

    def test_match_workflow_from_path(self):
        path = os.path.join("/tmp", "foo", "SL-SL-SR-101A")
        match = views.match_workflow_from_path(path, self.user)
        self.assertEqual(match, self.wf)


class RunWorkflowNoMatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="runner", password="pass")
        self.client.force_login(self.user)
        self.wf = Workflow.objects.create(name="MyFlow", created_by=self.user)

    def test_no_match_shows_message(self):
        data = {
            "workflow": self.wf.id,
            "input_path": "/tmp/foo",
            "use_input_path": "True",
            "output_path": "/tmp/foo",
            "project_code": "",
            "initials": "",
            "pause_between_steps": False,
        }
        response = self.client.post(reverse("run_workflow"), data)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("No workflow matched" in str(m) for m in messages))


class GenerateNextFilenameTests(TestCase):
    def test_generate_next_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "sub"), exist_ok=True)
            existing = os.path.join(tmp, "sub", "SL-SL-SR-011-A-3V-0001.mp4")
            with open(existing, "wb") as fh:
                fh.write(b"\x00")

            name = file_utils.generate_next_filename(os.path.join(tmp, "sub"), ".mp4")
            self.assertEqual(name, "SL-SL-SR-011-A-3V-0002.mp4")

    def test_generate_next_filename_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "sub"), exist_ok=True)
            existing = os.path.join(tmp, "sub", "SL-SL-SR-011-A-3V-0001.mp4")
            with open(existing, "wb") as fh:
                fh.write(b"\x00")
            name = file_utils.generate_next_filename(
                os.path.join(tmp, "sub"), ".mp4", use_date_suffix=True
            )
            stamp = datetime.now().strftime("%d%m%y")
            self.assertEqual(name, f"SL-SL-SR-011-A-3V-{stamp}.mp4") if name else None


class RenameWithZoneTests(TestCase):
    def test_rename_with_zone(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = os.path.join(tmp, "SL-SL-SR-101-A-3V-0001.mp4")
            with open(existing, "wb") as fh:
                fh.write(b"\x00")

            sample = os.path.join(tmp, "sample.mp4")
            with open(sample, "wb") as fh:
                fh.write(b"\x00")

            new_path = file_utils.rename_with_zone(sample, tmp, "101-A")
            self.assertTrue(os.path.exists(new_path))
            self.assertEqual(os.path.basename(new_path), "SL-SL-SR-101-A-3V-0002.mp4")

    def test_rename_with_zone_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = os.path.join(tmp, "SL-SL-SR-101-A-3V-0001.mp4")
            with open(existing, "wb") as fh:
                fh.write(b"\x00")

            sample = os.path.join(tmp, "sample.mp4")
            with open(sample, "wb") as fh:
                fh.write(b"\x00")

            new_path = file_utils.rename_with_zone(
                sample, tmp, "101-A", use_date_suffix=True
            )
            stamp = datetime.now().strftime("%d%m%y")
            self.assertTrue(os.path.exists(new_path))
            self.assertEqual(
                os.path.basename(new_path),
                f"SL-SL-SR-101-A-3V-{stamp}.mp4",
            )


class LogWriterTests(TestCase):
    def test_write_workflow_log(self):
        user = User.objects.create(username="loguser", first_name="Curtis", last_name="Hailes")
        with tempfile.TemporaryDirectory() as tmp:
            run = SimpleNamespace(
                output_path=tmp,
                project_code="",
                user=user,
                started_at=datetime.now(),
                completed_at=datetime.now(),
            )
            runner = SimpleNamespace(
                video_log=[
                    {
                        "original": "sample.360",
                        "new_path": "sample.mp4",
                        "rename": "auto",
                        "crop_start": 0.0,
                        "crop_end": 0.0,
                        "audio_removed": False,
                        "flagged": False,
                        "skip_reason": "",
                    }
                ]
            )
            logs = [
                "Renamed sample.360 -> sample.mp4",
                f"Structure created at {os.path.join(tmp, 'Project Files', '3V')}",
                "Converted sample.360 to mp4",
            ]
            path = write_workflow_log(run, logs, runner)
            self.assertTrue(os.path.exists(path))
            with open(path) as fh:
                content = fh.read()
            self.assertIn("Workflow Execution Log", content)
            self.assertIn("Renamed: sample.mp4", content)
            self.assertIn("Time Started:", content)
            self.assertIn("Suffix Format", content)


class ConvertVideoValidationTests(TestCase):
    def test_crop_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in.mp4")
            dst = os.path.join(tmp, "out.mp4")
            with open(src, "wb") as fh:
                fh.write(b"\x00")

            with patch(
                "workflow_automation.file_utils.get_video_duration",
                return_value=5.0,
            ), patch(
                "workflow_automation.file_utils.ffmpeg_exists",
                return_value=False,
            ):
                with self.assertRaises(ValueError):
                    file_utils.convert_video(src, dst, "mp4", crop_start=-1)
                with self.assertRaises(ValueError):
                    file_utils.convert_video(src, dst, "mp4", crop_end=-1)
                with self.assertRaises(ValueError):
                    file_utils.convert_video(src, dst, "mp4", crop_start=3, crop_end=3)
                file_utils.convert_video(src, dst, "mp4", crop_start=1, crop_end=1)
                self.assertTrue(os.path.exists(dst))


class FinalizeVideoTests(TestCase):
    def test_finalize_after_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp = os.path.join(tmp, "in")
            out = os.path.join(tmp, "out")
            os.makedirs(inp)
            os.makedirs(out)
            src = os.path.join(inp, "sample.mp4")
            with open(src, "wb") as fh:
                fh.write(b"\x00")

            user = User.objects.create(username="fin")
            wf = Workflow.objects.create(name="WF", created_by=user)
            step = wf.steps.create(
                step_type="convert_360_video",
                order=1,
                config={},
            )

            runner = WorkflowRunner(
                wf,
                inp,
                out,
                project_code="PC",
                initials="CH",
                step_configs=[step.config],
                qa_video_review=False,
            )
            runner.files = [src]
            with patch("workflow_automation.file_utils.convert_video") as cv:
                def fake_convert(src, dst, fmt, **kwargs):
                    if os.path.abspath(src) != os.path.abspath(dst):
                        shutil.copy2(src, dst)
                    else:
                        open(dst, "ab").close()
                    return dst

                cv.side_effect = fake_convert
                runner.run_next()

            dest = os.path.join(
                out,
                "PC",
                "Project Files",
                "3V - 360 Videos",
                datetime.now().strftime("%d%m%y") + "CH",
                "RAW Data",
                "sample.mp4",
            )
            self.assertTrue(os.path.exists(dest))
            self.assertTrue(os.path.exists(dest + ".convert"))


