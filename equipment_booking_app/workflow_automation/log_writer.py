import os
import re
from datetime import datetime


def write_workflow_log(run, logs):
    """Write a workflow execution log file under the Documents folder.

    The log is appended to ``[YYMMDD]_workflow_log.txt`` in
    ``[output_path]/[project_code]/Project Files/Documents``. If ``project_code``
    is blank, it is omitted from the path.
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

        fh.write("Renamed Files:\n")
        for old, new in renamed:
            fh.write(f"Original: {old}\n")
            fh.write(f"Renamed:  {new}\n")
        if renamed:
            fh.write("\n")

        fh.write("Folder Structure Created:\n")
        if folders:
            fh.write(", ".join(folders) + "\n\n")
        else:
            fh.write("\n")

        fh.write("Conversion:\n")
        for name in conversions:
            fh.write(f"{name} — Converted via GPU\n")
        fh.write("\n")

    return log_path
