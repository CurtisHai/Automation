import os
import re
from datetime import datetime


def write_workflow_log(run, logs, runner=None):
    """Write a workflow execution log file under the Documents folder.

    The log is appended to ``[YYMMDD]_workflow_log.txt`` in
    ``[output_path]/[project_code]/Project Files/Documents``. If ``project_code``
    is blank, it is omitted from the path.
    When ``runner`` is supplied additional per-file details are recorded.
    """
    date = datetime.now()
    yymmdd = date.strftime("%y%m%d")
    root = os.path.join(run.output_path, run.project_code) if run.project_code else run.output_path
    log_dir = os.path.join(root, "Project Files", "Documents")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{yymmdd}_workflow_log.txt")

    renamed = []
    folders = []
    conversions = []
    video_details = runner.video_log if runner else []

    ren_re = re.compile(r"Renamed (.+) -> (.+)")
    struct_re = re.compile(r"Structure created at (.+)")
    conv_re = re.compile(r"Converted (.+) to (.+)")

    for line in logs:
        m = ren_re.search(line)
        if m:
            renamed.append((m.group(1), m.group(2)))
            continue
        m = struct_re.search(line)
        if m:
            folders.append(os.path.basename(m.group(1)))
            continue
        m = conv_re.search(line)
        if m:
            base = os.path.splitext(m.group(1))[0]
            conversions.append(f"{os.path.basename(base)}.{m.group(2)}")
            continue

    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write("Workflow Execution Log\n")
        fh.write(f"Date: {date.strftime('%d/%m/%Y')}\n")
        name = run.user.get_full_name() or run.user.username
        fh.write(f"Performed by: {name}\n\n")

        if video_details:
            for entry in video_details:
                fh.write(f"Original: {entry['original']}\n")
                fh.write(f"Renamed: {entry['new_path']}\n")
                if entry.get('rename'):
                    rename_type = 'Manual' if entry['rename'] == 'manual' else 'Auto-generated'
                else:
                    rename_type = 'None'
                fh.write(f"Renaming: {rename_type}\n")
                if entry.get('crop_start') or entry.get('crop_end'):
                    fh.write(f"Cropping: {entry['crop_start']}s start, {entry['crop_end']}s end\n")
                else:
                    fh.write("Cropping: None\n")
                fh.write(f"Audio Removed: {'Yes' if entry.get('audio_removed') else 'No'}\n")
                if entry.get('flagged'):
                    fh.write("Flagged for Manual Review: Yes\n")
                if entry.get('skip_reason'):
                    fh.write(f"Skipped: {entry['skip_reason']}\n")
                fh.write("\n")
        else:
            fh.write("Renamed Files:\n")
            for old, new in renamed:
                fh.write(f"Original: {old}\n")
                fh.write(f"Renamed:  {new}\n")
            if renamed:
                fh.write("\n")
        naming_note = (
            "Date-based naming (DDMMYY)"
            if getattr(runner, "use_date_suffix", False)
            else "Auto-naming with version number"
        )
        fh.write(f"Suffix Format: {naming_note}\n\n")

        fh.write("Folder Structure Created:\n")
        if folders:
            fh.write(", ".join(folders) + "\n\n")
        else:
            fh.write("\n")

        if conversions:
            fh.write("Conversion:\n")
            for name in conversions:
                fh.write(f"{name} — Converted via GPU\n")
            fh.write("\n")

        fh.write(f"Time Started: {run.started_at:%H:%M}\n")
        if run.completed_at:
            fh.write(f"Time Finished: {run.completed_at:%H:%M}\n")
        fh.write("\n")

    return log_path
