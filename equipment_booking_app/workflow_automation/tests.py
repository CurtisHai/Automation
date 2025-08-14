import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "reality_capture_portal.settings")
import django
django.setup()
from django.conf import settings
settings.ALLOWED_HOSTS.append("testserver")

from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.urls import reverse
from .models import Workflow, Profile, Message
from .workflow_runner import WorkflowRunner
from .forms import RunWorkflowForm
from . import file_utils, views
from .log_writer import write_workflow_log
from types import SimpleNamespace
from unittest.mock import patch
import subprocess
import shutil
import tempfile
from datetime import datetime
import zipfile
from utils import zipper


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


    @patch("workflow_automation.file_utils.ffmpeg_exists", return_value=True)
    @patch("workflow_automation.file_utils.subprocess.run")
    @patch("workflow_automation.file_utils.subprocess.check_output")
    def test_generate_video_preview_midpoint(
        self, mock_check_output, mock_run, mock_exists
    ):
        mock_check_output.return_value = b"10.0"
        file_utils.generate_video_preview("in.mp4", "out.jpg")
        cmd = mock_run.call_args[0][0]
        ss_val = cmd[cmd.index("-ss") + 1]
        self.assertEqual(ss_val, "00:00:05.000")

    @patch("workflow_automation.file_utils.ffmpeg_exists", return_value=True)
    @patch("workflow_automation.file_utils.subprocess.run")
    @patch(
        "workflow_automation.file_utils.subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "ffprobe"),
    )
    def test_generate_video_preview_ffprobe_failure(
        self, mock_check_output, mock_run, mock_exists
    ):
        file_utils.generate_video_preview("in.mp4", "out.jpg")
        cmd = mock_run.call_args[0][0]
        ss_val = cmd[cmd.index("-ss") + 1]
        self.assertEqual(ss_val, "00:00:02")


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
        Profile.objects.create(user=self.user, initials="RN")
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


class RunWorkflowInitialsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="runner2", password="pass")
        Profile.objects.create(user=self.user, initials="AB")
        self.wf = Workflow.objects.create(name="MyFlow", created_by=self.user)

    def test_initials_from_profile_and_readonly(self):
        form = RunWorkflowForm(
            data={
                "workflow": self.wf.id,
                "input_path": "/tmp/foo",
                "use_input_path": "True",
                "output_path": "/tmp/foo",
                "project_code": "",
                "initials": "ZZ",
                "pause_between_steps": False,
            },
            user=self.user,
            workflow_queryset=Workflow.objects.filter(created_by=self.user),
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["initials"], "AB")
        self.assertIn("readonly", form.fields["initials"].widget.attrs)


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

    def test_generate_next_filename_building_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "sub"), exist_ok=True)
            names = [
                "SL-SL-SR-011-A-3V-0001.mp4",
                "SL-SL-SR-011-A-3V-0002.mp4",
                "SL-SL-AA-100-A-3V-0005.mp4",
            ]
            for n in names:
                with open(os.path.join(tmp, "sub", n), "wb") as fh:
                    fh.write(b"\x00")

            name = file_utils.generate_next_filename(
                os.path.join(tmp, "sub"),
                ".mp4",
                building_name="SR",
            )
            self.assertEqual(name, "SL-SL-SR-011-A-3V-0003.mp4")


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
                action="convert_360_video",
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


class ZipperTests(TestCase):
    def test_zip_recap_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = os.path.join(tmp, "in")
            output_dir = os.path.join(tmp, "out")
            os.makedirs(input_dir)
            os.makedirs(output_dir)

            rcp_path = os.path.join(input_dir, "Building101.rcp")
            with open(rcp_path, "wb") as fh:
                fh.write(b"0")

            support_dir = os.path.join(input_dir, "Building101_support")
            os.makedirs(support_dir)
            support_file = os.path.join(support_dir, "data.txt")
            with open(support_file, "wb") as fh:
                fh.write(b"data")

            zip_path = os.path.join(output_dir, "Building101.zip")
            zipper.zip_directory(rcp_path, zip_path, support_folder=support_dir)

            self.assertTrue(os.path.exists(zip_path))
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
            self.assertIn("Building101.rcp", names)
            self.assertIn("Building101_support/data.txt", names)


class WorkflowReviewFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="pass")
        self.admin = User.objects.create_user(username="admin", password="pass", is_superuser=True)
        self.wf = Workflow.objects.create(name="WF1", created_by=self.user)

    def test_request_review_sets_flag(self):
        self.client.force_login(self.user)
        self.client.post(reverse("request_review", args=[self.wf.id]))
        self.wf.refresh_from_db()
        self.assertTrue(self.wf.awaiting_review)
        self.assertEqual(self.wf.review_status, "pending")
        self.assertEqual(self.wf.rejection_comment, "")

    def test_admin_approve_workflow(self):
        self.wf.awaiting_review = True
        self.wf.review_status = "pending"
        self.wf.save()
        self.client.force_login(self.admin)
        self.client.post(reverse("review_workflows"), {"workflow_id": self.wf.id, "action": "approve"})
        self.wf.refresh_from_db()
        self.assertTrue(self.wf.is_published)
        self.assertFalse(self.wf.awaiting_review)
        self.assertEqual(self.wf.review_status, "accepted")

    def test_admin_reject_workflow(self):
        self.wf.awaiting_review = True
        self.wf.review_status = "pending"
        self.wf.save()
        self.client.force_login(self.admin)
        self.client.post(
            reverse("review_workflows"),
            {"workflow_id": self.wf.id, "action": "reject", "comment": "fix"},
        )
        self.wf.refresh_from_db()
        self.assertFalse(self.wf.is_published)
        self.assertFalse(self.wf.awaiting_review)
        self.assertEqual(self.wf.rejection_comment, "fix")
        self.assertEqual(self.wf.review_status, "rejected")


class SidebarLinksTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user1", password="pass")
        self.admin = User.objects.create_user(username="admin1", password="pass", is_superuser=True)

    def test_profile_link_visible(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))
        self.assertContains(response, reverse("accounts"))

    def test_help_link_visible_for_regular_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))
        self.assertContains(response, reverse("contact"))
        self.assertNotContains(response, reverse("inbox"))

    def test_inbox_visible_but_contact_hidden_for_superuser(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("home"))
        self.assertContains(response, reverse("inbox"))
        self.assertNotContains(response, reverse("contact"))


class ContactPageTests(TestCase):
    def setUp(self):
        self.user_no_email = User.objects.create_user(username="noemail", password="pass")
        self.user_with_email = User.objects.create_user(
            username="withemail", password="pass", email="user@example.com"
        )

    def test_requires_email_to_send_message(self):
        self.client.force_login(self.user_no_email)
        response = self.client.get(reverse("contact"))
        self.assertRedirects(response, reverse("accounts"))

    def test_form_displayed_when_email_present(self):
        self.client.force_login(self.user_with_email)
        response = self.client.get(reverse("contact"))
        self.assertContains(response, "Send Message")


class WorkflowDeleteTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.downloader = User.objects.create_user(username="downloader", password="pass")
        self.admin = User.objects.create_user(username="admin", password="pass", is_staff=True)
        self.wf = Workflow.objects.create(name="WF", created_by=self.owner)
        self.wf.downloaded_by.add(self.downloader)

    def test_owner_can_delete_workflow(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("delete_workflow", args=[self.wf.id]))
        self.assertFalse(Workflow.objects.filter(id=self.wf.id).exists())

    def test_downloader_removes_reference(self):
        self.client.force_login(self.downloader)
        self.client.post(reverse("delete_workflow", args=[self.wf.id]))
        self.assertTrue(Workflow.objects.filter(id=self.wf.id).exists())
        self.assertFalse(self.wf.downloaded_by.filter(id=self.downloader.id).exists())

    def test_admin_can_delete_any_workflow(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("delete_workflow", args=[self.wf.id]))
        self.assertFalse(Workflow.objects.filter(id=self.wf.id).exists())


class MessageResponseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="msguser", password="pass", email="user@example.com"
        )
        self.admin = User.objects.create_user(
            username="msgadmin", password="pass", email="admin@example.com", is_superuser=True
        )
        self.msg = Message.objects.create(
            sender=self.user, recipient=self.admin, subject="Help", content="Need assistance"
        )

    def test_superuser_can_respond(self):
        self.client.force_login(self.admin)
        url = reverse("message_detail", args=[self.msg.id])
        response = self.client.post(url, {"response": "Sure"})
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.response, "Sure")
        self.assertEqual(self.msg.responded_by, self.admin)
        self.assertTrue(self.msg.is_read)
        self.assertRedirects(response, reverse("inbox"))

    def test_user_messages_page_excludes_response(self):
        self.msg.response = "Done"
        self.msg.responded_by = self.admin
        self.msg.is_read = True
        self.msg.save()
        self.client.force_login(self.user)
        response = self.client.get(reverse("user_messages"))
        self.assertNotContains(response, "Done")


class UserAccountsAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ua_user", password="pass")
        self.admin = User.objects.create_user(username="ua_admin", password="pass", is_superuser=True)

    def test_superuser_can_view_accounts(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("user_accounts"))
        self.assertContains(response, self.user.username)

    def test_regular_user_forbidden(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("user_accounts"))
        self.assertEqual(response.status_code, 403)


class LauncherAccessTests(TestCase):
    def test_launcher_requires_login(self):
        response = self.client.get(reverse("launcher"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

