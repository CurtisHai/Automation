import os
import copy
import subprocess
from django.conf import settings
from ..template import Task, return_failed
from .validate_resources import ValidateResources
from workflow_automation import file_utils


class ConvertFile(Task):
    def execute(self, job):
        super().execute(job)
        insta360_types = [".insv", ".insp", ".lrv"]
        gopro_types = [".360"]
        source_extension = os.path.splitext(job["media_file"])[1].lower()
        job.setdefault("original_media", job["media_file"])

        try:
            if source_extension in insta360_types:
                job = insta360_convert(job)
                job[self.name]["message"] = "Insta360 format converted."
            elif source_extension in gopro_types:
                job = gopro_convert(job)
                job[self.name]["message"] = "GoPro format converted."
            elif source_extension == ".mp4":
                job[self.name]["message"] = "File already in mp4 format."
            else:
                job[self.name]["message"] = "File does not require conversion."

            if (
                source_extension not in gopro_types
                and any(
                    key in job for key in ["crop_start", "crop_end", "remove_audio"]
                )
            ):
                apply_options(job)

            return ValidateResources, job

        except Exception as e:
            job[self.name]["message"] = f"Error converting file: {e}"
            return return_failed(self.name, job)


def insta360_convert(job):
    job_copy = copy.deepcopy(job)
    job_copy["original_media"] = copy.deepcopy(job_copy["media_file"])

    extension = os.path.splitext(job_copy["media_file"])[1].lower()

    if extension == ".insp":
        output_file = job_copy["media_file"].replace(".insp", ".jpg")
    else:
        output_file = (
            job_copy["media_file"].replace(".insv", ".mp4").replace(".lrv", ".mp4")
        )

    sdk_path = os.path.join(settings.BASE_DIR, "MediaSDKTest.exe")

    command = [sdk_path, "-inputs", job_copy["original_media"], "-output", output_file]
    subprocess.call(command)

    job_copy["media_file"] = output_file
    return job_copy


def gopro_convert(job):
    job_copy = copy.deepcopy(job)
    media_file = job_copy["media_file"]
    scripts_dir = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "submodules",
        "ffmpeg-gopro",
        "video_scripts",
    )
    gpu_script = os.path.join(scripts_dir, "convert_gopro_gpu.sh")
    nogpu_script = os.path.join(scripts_dir, "convert_gopro_nogpu.sh")

    try:
        subprocess.run(["bash", gpu_script, media_file], check=True)
    except subprocess.CalledProcessError:
        subprocess.run(["bash", nogpu_script, media_file], check=True)

    base, _ = os.path.splitext(media_file)
    job_copy["media_file"] = base + ".mp4"
    return job_copy


def apply_options(job):
    start = float(job.get("crop_start", 0) or 0)
    end = float(job.get("crop_end", 0) or 0)
    remove_audio = bool(job.get("remove_audio", False))
    if not (start or end or remove_audio):
        return job
    src = job["media_file"]
    tmp = src + ".tmp.mp4"
    file_utils.convert_video(
        src,
        tmp,
        "mp4",
        crop_start=start,
        crop_end=end,
        remove_audio=remove_audio,
        original_media=job.get("original_media", src),
    )
    os.replace(tmp, src)
    return job
