from django.test import TestCase
from . import file_utils
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


