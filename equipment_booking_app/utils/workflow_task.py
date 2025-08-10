import threading
from django.utils import timezone
from workflow_automation.workflow_runner import WorkflowRunner
from workflow_automation.models import WorkflowRun
from workflow_automation.log_writer import write_workflow_log


def _worker(run_id: int, configs, video_map):
    run = WorkflowRun.objects.get(id=run_id)
    workflow = run.workflow
    runner = WorkflowRunner(
        workflow,
        run.input_path,
        run.output_path,
        project_code=run.project_code,
        initials=run.initials,
        step_configs=configs,
        qa_video_review=workflow.qa_video_review,
        video_order_map=video_map,
        use_date_suffix=workflow.use_date_suffix,
    )
    total = workflow.steps.count()
    try:
        run.status = "running"
        run.save()
        while runner.current_step < total:
            step_obj = workflow.steps.all()[runner.current_step]
            run.current_action = step_obj.get_step_type_display()
            run.current_step = runner.current_step
            run.log = "\n".join(runner.logs)
            run.save()
            runner.run_next()
            run.log = "\n".join(runner.logs)
            run.current_step = runner.current_step
            run.current_action = runner.logs[-1] if runner.logs else ""
            run.save()
        run.status = "completed"
        run.completed_at = timezone.now()
        write_workflow_log(run, runner.logs, runner)
        run.save()
    except Exception as exc:
        run.status = "error"
        run.error_message = str(exc)
        run.log = "\n".join(runner.logs)
        run.save()


def start_workflow(run: WorkflowRun, configs, video_map=None):
    """Start workflow execution in a background thread."""
    thread = threading.Thread(
        target=_worker, args=(run.id, configs, video_map), daemon=True
    )
    thread.start()
    return thread
