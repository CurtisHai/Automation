from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.urls import reverse
from .models import Workflow
from . import file_utils, views
import os
import tempfile


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
            "run_mode": "run_all",
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


