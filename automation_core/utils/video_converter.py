import os
import copy
import subprocess
from ..template import Task, return_failed
from .validate_resources import ValidateResources


class ConvertFile(Task):
    def execute(self, job):
        super().execute(job)
        insta360_types = [".insv", ".insp", ".lrv"]
        gopro_types = [".360"]
        source_extension = os.path.splitext(job["media_file"])[1].lower()

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

            return ValidateResources, job

        except Exception as e:
            job[self.name]["message"] = f"Error converting file: {e}"
            return return_failed(self.name, job)


def insta360_convert(job):
    """Placeholder until Insta360 SDK-based conversion is available."""
    return job


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
