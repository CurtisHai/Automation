from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django import forms
from datetime import timedelta
from django.db.models import Q
import os

from .models import (
    Booking,
    Profile,
    Message,
    Notice,
    LoginAttempt,
    UnknownLoginAttempt,
    Workflow,
    WorkflowStep,
    WorkflowRun,
)
from .forms import (
    BookingForm,
    ProfileForm,
    MessageForm,
    NoticeForm,
    WorkflowForm,
    WorkflowStepFormSet,
    RunWorkflowForm,
    StepSettingsFormSet,
    RenameToolForm,
    ConvertToolForm,
    ZipToolForm,
    VideoReviewForm,
    VideoOrderFormSet,
    StepSettingsForm,
)

from .workflow_runner import WorkflowRunner
from utils import rename, converter, zipper
from . import file_utils
from .log_writer import write_workflow_log

# Number of allowed failed attempts before locking an account
LOCKOUT_THRESHOLD = 5
# Duration of the lockout once the threshold is exceeded
LOCKOUT_DURATION = timedelta(hours=1)

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login, logout


@login_required
def home(request):
    """Render the dashboard-style home page."""
    notice = Notice.objects.last()
    pending_count = 0

    if request.user.is_superuser:
        pending_qs = Message.objects.filter(
            recipient=request.user,
            is_review_request=True,
            workflow__isnull=False,
            workflow__is_published=False,
        )
        pending_count = pending_qs.count()
        if pending_count:
            messages.info(request, f"You have {pending_count} workflow review requests pending.")

    if request.method == "POST" and request.user.is_superuser:
        message = request.POST.get("message")
        if message:
            Notice.objects.create(message=message, created_by=request.user)
            messages.success(request, "Notice created successfully!")
            return redirect("home")

    context = {
        "notice": notice,
        "pending_count": pending_count,
    }
    return render(request, "workflow_automation/home.html", context)


def signup(request):
    # Handle user signup with default form
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Your account has been created successfully.')
            return redirect('home')
        else:
            messages.error(request, 'Error creating your account. Please check the form.')
    else:
        form = UserCreationForm()

    return render(request, 'workflow_automation/signup.html', {'form': form})


@login_required
def create_booking(request):
    # Allow users to create new bookings
    if request.method == 'POST':
        form = BookingForm(request.POST, user=request.user)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.user = form.cleaned_data['user'] if request.user.is_superuser else request.user

            # Prevent overlapping bookings for the same equipment
            conflicts = Booking.objects.filter(
                equipment=booking.equipment,
                start_time__lt=booking.end_time,
                end_time__gt=booking.start_time
            )

            if conflicts.exists():
                overlap_dates = sorted({c.start_time.strftime('%Y-%m-%d') for c in conflicts})
                messages.error(
                    request,
                    'This item is already reserved on: ' + ', '.join(overlap_dates) + '. Please choose another time.'
                )
            else:
                booking.save()
                messages.success(request, 'Booking created successfully!')
                return redirect('booking_list')
        else:
            messages.error(request, 'Error creating booking. Please ensure the equipment is available.')
    else:
        form = BookingForm(user=request.user)

    return render(request, 'workflow_automation/create_booking.html', {'form': form})


@login_required
def booking_list(request):
    # Display current and past bookings based on user type
    current_time = timezone.now()

    if request.user.is_superuser:
        bookings = Booking.objects.filter(start_time__gte=current_time)
        previous_bookings = Booking.objects.filter(end_time__lt=current_time)
    else:
        bookings = Booking.objects.filter(user=request.user, start_time__gte=current_time)
        previous_bookings = Booking.objects.filter(user=request.user, end_time__lt=current_time)

    return render(request, 'workflow_automation/booking_list.html', {
        'bookings': bookings,
        'previous_bookings': previous_bookings,
        'is_superuser': request.user.is_superuser,
        'current_time': current_time
    })


@login_required
def edit_booking(request, booking_id):
    # Allow users to edit existing bookings
    if request.user.is_superuser:
        booking = get_object_or_404(Booking, id=booking_id)
    else:
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    current_time = timezone.now()

    if request.user != booking.user and not request.user.is_superuser:
        return HttpResponseForbidden("You are not allowed to edit this booking.")

    if request.user == booking.user and booking.start_time < current_time:
        messages.error(request, "You cannot edit a past booking.")
        return redirect('booking_list')

    if request.method == 'POST':
        form = BookingForm(request.POST, instance=booking, user=request.user)
        if form.is_valid():
            booking = form.save()
            messages.success(request, 'Booking updated successfully.')
            return redirect('booking_list')
    else:
        form = BookingForm(instance=booking, user=request.user)

    return render(request, 'workflow_automation/edit_booking.html', {'form': form, 'booking': booking})


@login_required
def delete_booking(request, booking_id):
    # Allow superusers to delete bookings
    booking = get_object_or_404(Booking, id=booking_id)

    if not request.user.is_superuser:
        return HttpResponseForbidden("You are not allowed to delete this booking.")

    if request.method == 'POST':
        booking.delete()
        messages.success(request, "Booking deleted successfully.")
        return redirect('booking_list')

    messages.error(request, "Invalid request.")
    return redirect('booking_list')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user_obj = User.objects.filter(username=username).first()

        if user_obj:
            login_attempt, _ = LoginAttempt.objects.get_or_create(user=user_obj)
        else:
            login_attempt, _ = UnknownLoginAttempt.objects.get_or_create(username=username)

        if login_attempt.lockout_until and login_attempt.lockout_until > timezone.now():
            remaining = login_attempt.lockout_until - timezone.now()
            minutes = max(1, int(remaining.total_seconds() // 60))
            messages.error(request, f'Account locked. Try again in {minutes} minutes.')
            return render(request, 'workflow_automation/login.html')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            login_attempt.failed_attempts = 0
            login_attempt.lockout_until = None
            login_attempt.save()
            messages.success(request, 'Successfully logged in!')

            if user.is_superuser:
                pending = Message.objects.filter(
                    recipient=user,
                    is_review_request=True,
                    workflow__isnull=False,
                    workflow__is_published=False,
                )
                if pending.exists():
                    messages.info(request, f'You have {pending.count()} workflow review requests pending.')

            return redirect('home')
        else:
            login_attempt.failed_attempts += 1
            if login_attempt.failed_attempts >= LOCKOUT_THRESHOLD:
                login_attempt.lockout_until = timezone.now() + LOCKOUT_DURATION
                login_attempt.save()
                minutes = int(LOCKOUT_DURATION.total_seconds() // 60)
                messages.error(request, f'Account locked. Try again in {minutes} minutes.')
                return render(request, 'workflow_automation/login.html')
            else:
                attempts_left = LOCKOUT_THRESHOLD - login_attempt.failed_attempts
                login_attempt.save()
                messages.error(request, f'Invalid username or password. {attempts_left} attempts remaining.')

    return render(request, 'workflow_automation/login.html')

def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def accounts(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    user_type = 'Superuser' if request.user.is_superuser else 'Regular User'

    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = ProfileForm(instance=profile)

    context = {
        'form': form,
        'profile': profile,
        'fixed_company': 'AtkinsRéalis',
        'user_type': user_type
    }
    return render(request, 'workflow_automation/account_detail.html', context)


@login_required
def previous_bookings(request):
    current_time = timezone.now()

    if request.user.is_superuser:
        previous_bookings = Booking.objects.filter(end_time__lt=current_time)
    else:
        previous_bookings = Booking.objects.filter(user=request.user, end_time__lt=current_time)

    return render(request, 'workflow_automation/previous_bookings.html', {
        'previous_bookings': previous_bookings,
        'is_superuser': request.user.is_superuser
    })


@login_required
def contact(request):
    if not request.user.email:
        messages.error(request, 'You need an active email associated with your account to send a message.')
        return redirect('accounts')

    if request.method == 'POST':
        form = MessageForm(request.POST, user=request.user)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user

            admin_user = User.objects.filter(is_superuser=True).first()
            if admin_user:
                message.recipient = admin_user
                message.save()

                # Remove the email notification part
                # send_mail(
                #     subject=f"New message from {message.sender.username}: {message.subject}",
                #     message=message.content,
                #     from_email='no-reply@yourdomain.com',
                #     recipient_list=[admin_user.email],
                # )

                messages.success(request, 'Message sent successfully! We will get back to you soon.')
                return redirect('home')
            else:
                messages.error(request, 'No admin found to receive the message.')
        else:
            messages.error(request, 'Please correct the errors in the form.')
    else:
        form = MessageForm(user=request.user)

    return render(request, 'workflow_automation/contact.html', {'form': form})







@user_passes_test(lambda u: u.is_superuser)
def inbox(request):
    messages_qs = Message.objects.filter(is_review_request=True).select_related('workflow', 'sender').order_by('-created_at')

    if request.method == "POST":
        wf_id = request.POST.get('publish_workflow')
        if wf_id:
            workflow = get_object_or_404(Workflow, id=wf_id)
            workflow.is_published = True
            workflow.published_by = request.user
            workflow.published_at = timezone.now()
            workflow.save()
            messages.success(request, 'Workflow published successfully.')
            return redirect('inbox')

    return render(request, 'workflow_automation/inbox.html', {
        'messages_list': messages_qs,
    })


@user_passes_test(lambda u: u.is_superuser)
@login_required
def manage_notice(request):
    notice = Notice.objects.last()

    if request.method == 'POST':
        form = NoticeForm(request.POST, instance=notice)
        if form.is_valid():
            new_notice = form.save(commit=False)
            new_notice.created_by = request.user
            new_notice.save()
            messages.success(request, 'Notice updated successfully.')
            return redirect('home')
    else:
        form = NoticeForm(instance=notice)

    return render(request, 'workflow_automation/manage_notice.html', {'form': form, 'notice': notice})


@user_passes_test(lambda u: u.is_superuser)
def remove_notice(request):
    if request.method == 'POST':
        Notice.objects.all().delete()
        messages.success(request, 'Notice removed successfully.')
    return redirect('home')


def security_notice(request):
    """Render a notice page when users access a restricted admin URL."""
    return render(request, 'workflow_automation/security_notice.html')


@login_required
def workflow_dashboard(request):
    workflows = Workflow.objects.filter(is_published=True)
    return render(request, 'workflow_automation/workflow_dashboard.html', {'workflows': workflows})


@login_required
def create_workflow(request):
    step_codes = [
        "setup_structure",
        "convert_360_video",
        "rename",
        "remove_audio",
        "trim",
        "organize_files",
    ]

    if request.method == "POST":
        wf_form = WorkflowForm(request.POST)
        if wf_form.is_valid():
            workflow = wf_form.save(commit=False)
            workflow.created_by = request.user
            if request.user.is_superuser:
                workflow.is_published = True
                workflow.published_by = request.user
                workflow.published_at = timezone.now()
            workflow.save()

            for code in step_codes:
                if request.POST.get(f"include_{code}"):
                    order = request.POST.get(f"order_{code}") or 0
                    config = {}
                    if code == "trim":
                        config["start_seconds"] = request.POST.get("start_seconds") or 0
                        config["end_seconds"] = request.POST.get("end_seconds") or 0
                    elif code == "rename":
                        config["rename_pattern"] = request.POST.get("rename_pattern", "")
                    elif code == "convert_360_video":
                        config["convert_format"] = request.POST.get("convert_format", "")
                    elif code == "setup_structure":
                        config["full_structure"] = bool(request.POST.get("setup_full_structure"))
                    elif code == "organize_files":
                        config["target_folder"] = request.POST.get("target_folder", "")

                    WorkflowStep.objects.create(
                        workflow=workflow,
                        step_type=code,
                        order=int(order),
                        config=config,
                        crop_start_seconds=float(config.get("crop_start_seconds", 0) or 0),
                        crop_end_seconds=float(config.get("crop_end_seconds", 0) or 0),
                        remove_audio=config.get("remove_audio", False),
                    )

            messages.success(request, "Workflow created successfully.")
            return redirect("my_workflows")
    else:
        wf_form = WorkflowForm()

    context = {
        "form": wf_form,
        "step_choices": WorkflowStep.STEP_CHOICES,
    }
    return render(request, "workflow_automation/create_workflow.html", context)


@login_required
def my_workflows(request):
    workflows = Workflow.objects.filter(created_by=request.user)
    return render(request, 'workflow_automation/my_workflows.html', {'workflows': workflows})


@login_required
def request_review(request, workflow_id):
    workflow = get_object_or_404(Workflow, id=workflow_id, created_by=request.user)
    if request.method == 'POST':
        form = MessageForm(request.POST, user=request.user)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.sender = request.user
            msg.recipient = User.objects.filter(is_superuser=True).first()
            msg.workflow = workflow
            msg.is_review_request = True
            msg.save()
            messages.success(request, 'Review request submitted successfully.')
            return redirect('my_workflows')
    else:
        form = MessageForm(
            user=request.user,
            initial={"workflow": workflow, "subject": "Workflow Review"},
        )
        form.fields["workflow"].widget = forms.HiddenInput()
    return render(request, 'workflow_automation/request_review.html', {'form': form, 'workflow': workflow})


@login_required
def shared_workflow_list_view(request):
    """List published workflows with optional search by name or tag."""
    workflows = Workflow.objects.filter(is_published=True)
    query = request.GET.get("q", "")
    if query:
        if hasattr(Workflow, "tags"):
            workflows = workflows.filter(
                Q(name__icontains=query) | Q(tags__name__icontains=query)
            ).distinct()
        else:
            workflows = workflows.filter(name__icontains=query)
    return render(
        request,
        "workflow_automation/shared_workflows.html",
        {"workflows": workflows, "search_query": query},
    )


# Backwards compatibility for templates using old view name
shared_workflows = shared_workflow_list_view


@login_required
def use_shared_workflow(request, workflow_id):
    workflow = get_object_or_404(Workflow, id=workflow_id, is_published=True)
    new_wf = Workflow.objects.create(
        name=workflow.name,
        description=workflow.description,
        created_by=request.user,
    )
    for step in workflow.steps.all():
        WorkflowStep.objects.create(
            workflow=new_wf,
            step_type=step.step_type,
            order=step.order,
        )
    messages.success(request, 'Workflow copied to your account.')
    return redirect('my_workflows')


def match_workflow_from_path(path, user, depth=3):
    """Return a workflow whose name or tags match segments of the path."""
    segments = [s for s in os.path.normpath(path).split(os.sep) if s][-depth:]
    query_base = Workflow.objects.filter(created_by=user)
    for seg in reversed(segments):
        q = Q(name__icontains=seg)
        if hasattr(Workflow, "tags"):
            q = q | Q(tags__name__icontains=seg)
        match = query_base.filter(q).first()
        if match:
            return match
    return None


def build_step_formset(workflow):
    """Return a list of StepSettingsForm instances for the workflow."""
    if not workflow:
        return []
    return [
        StepSettingsForm(prefix=f"form-{idx}", step_type=s.step_type, initial=s.config)
        for idx, s in enumerate(workflow.steps.all())
    ]


@login_required
def run_workflow(request, workflow_id=None):
    """Collect folder paths for a workflow run and display confirmation.

    ``workflow_id`` optionally limits the selectable workflows to a single
    workflow when provided. This supports running a workflow directly from the
    user's workflow list page.
    """

    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.initials:
        messages.error(request, "Please input your initials on the account page to continue.")
        return redirect("accounts")

    user_wfs = Workflow.objects.filter(created_by=request.user)
    if workflow_id:
        user_wfs = user_wfs.filter(id=workflow_id)
    workflow = user_wfs.first() if user_wfs else None

    confirm = False
    input_folder = output_folder = ""
    suggested_workflow = None
    proposed_name = request.session.get("proposed_name")
    manual_override = False

    # Hold final logs if we end up running the workflow
    run = None
    final_logs = []
    video_formset = None
    video_files = []

    if request.method == "POST":
        # Final run is triggered when the hidden step fields are included in the
        # POST body (form-0-step_type etc.) which only happens after the user
        # confirms the folder selection.  In that case we validate all forms and
        # execute the workflow steps immediately.
        is_run_request = "form-0-step_type" in request.POST

        if is_run_request:
            form = RunWorkflowForm(
                request.POST,
                user=request.user,
                workflow_queryset=user_wfs,
            )
            video_formset = VideoOrderFormSet(request.POST, prefix="video")
            if form.is_valid() and video_formset.is_valid():
                workflow = form.cleaned_data["workflow"]
                input_folder = form.cleaned_data["input_path"]
                output_folder = form.cleaned_data["output_path"]

                # Build per-step config forms
                step_forms = []
                for idx, step in enumerate(workflow.steps.all()):
                    step_form = StepSettingsForm(
                        request.POST,
                        prefix=f"form-{idx}",
                        step_type=step.step_type,
                        initial=step.config,
                    )
                    if step_form.is_valid():
                        step_forms.append(step_form)
                    else:
                        break

                if len(step_forms) == workflow.steps.count():
                    video_map = {}
                    for vf in video_formset:
                        if vf.cleaned_data.get("file_name"):
                            video_map[vf.cleaned_data["file_name"]] = {
                                "zone": vf.cleaned_data.get("zone_id", ""),
                                "order": int(vf.cleaned_data.get("order", 0)),
                            }

                    # Create DB record for the run
                    pause = form.cleaned_data.get("pause_between_steps", False)
                    run = WorkflowRun.objects.create(
                        workflow=workflow,
                        user=request.user,
                        input_path=input_folder,
                        output_path=output_folder,
                        project_code=form.cleaned_data.get("project_code", ""),
                        initials=form.cleaned_data.get("initials", ""),
                        pause_between_steps=pause,
                    )

                    configs = [sf.cleaned_data for sf in step_forms]

                    if pause or workflow.qa_video_review:
                        request.session[f"run_{run.id}_configs"] = configs
                        request.session[f"run_{run.id}_index"] = 0
                        if video_map:
                            request.session[f"run_{run.id}_video_map"] = video_map
                        request.session.modified = True
                        return redirect("workflow_progress", run_id=run.id)

                    runner = WorkflowRunner(
                        workflow,
                        input_folder,
                        output_folder,
                        project_code=run.project_code,
                        initials=run.initials,
                        step_configs=configs,
                        qa_video_review=workflow.qa_video_review,
                        video_order_map=video_map,
                        use_date_suffix=workflow.use_date_suffix,
                    )

                    # Execute steps sequentially and persist logs after each
                    for _ in workflow.steps.all():
                        runner.run_next()
                        run.log = "\n".join(runner.logs)
                        run.save()

                    run.completed_at = timezone.now()
                    run.save()
                    write_workflow_log(run, runner.logs, runner)
                    final_logs = runner.logs
                    return render(
                        request,
                        "workflow_automation/workflow_progress.html",
                        {"run": run, "logs": final_logs, "done": True, "run_mode": "run_all"},
                    )

            # If validation fails fall through to redisplay the form
            StepFormSet = build_step_formset(workflow)

        elif "accept_filename" in request.POST:
            input_folder = request.session.get("input_folder", "")
            output_folder = request.session.get("output_folder", "")
            confirm = True
            form = RunWorkflowForm(
                initial={"workflow": workflow, "input_path": input_folder, "output_path": output_folder},
                user=request.user,
                workflow_queryset=user_wfs,
            )
            StepFormSet = build_step_formset(workflow)
            request.session["final_name"] = request.session.get("proposed_name")
        elif "reject_filename" in request.POST:
            input_folder = request.session.get("input_folder", "")
            output_folder = request.session.get("output_folder", "")
            confirm = True
            manual_override = True
            form = RunWorkflowForm(user=request.user, workflow_queryset=user_wfs)
            StepFormSet = build_step_formset(workflow)
        elif "override_filename" in request.POST:
            manual_name = request.POST.get("manual_name")
            if manual_name:
                request.session["final_name"] = manual_name
            input_folder = request.session.get("input_folder", "")
            output_folder = request.session.get("output_folder", "")
            confirm = True
            form = RunWorkflowForm(user=request.user, workflow_queryset=user_wfs)
            StepFormSet = build_step_formset(workflow)
        elif "accept_suggested" in request.POST:
            wf_id = request.session.get("suggested_wf_id")
            if wf_id:
                workflow = get_object_or_404(Workflow, id=wf_id, created_by=request.user)
                request.session["selected_workflow_id"] = wf_id
            input_folder = request.session.get("input_folder", "")
            output_folder = request.session.get("output_folder", "")
            confirm = True
            form = RunWorkflowForm(
                initial={"workflow": workflow, "input_path": input_folder, "output_path": output_folder},
                user=request.user,
                workflow_queryset=user_wfs,
            )
            StepFormSet = build_step_formset(workflow)
        elif "reject_suggested" in request.POST:
            request.session.pop("suggested_wf_id", None)
            input_folder = request.session.get("input_folder", "")
            output_folder = request.session.get("output_folder", "")
            confirm = True
            form = RunWorkflowForm(user=request.user, workflow_queryset=user_wfs)
            StepFormSet = build_step_formset(workflow)
            messages.info(request, "No workflow matched — please choose an option.")
        else:
            form = RunWorkflowForm(
                request.POST,
                user=request.user,
                workflow_queryset=user_wfs,
            )
            if form.is_valid():
                workflow = form.cleaned_data["workflow"]
                input_folder = form.cleaned_data["input_path"]
                output_folder = form.cleaned_data["output_path"]

                request.session["input_folder"] = input_folder
                request.session["output_folder"] = output_folder
                confirm = True
                suggested_workflow = match_workflow_from_path(output_folder, request.user)
                if suggested_workflow:
                    request.session["suggested_wf_id"] = suggested_workflow.id
                else:
                    messages.info(request, "No workflow matched — please choose an option.")

                files = []
                if os.path.isdir(input_folder):
                    files = [
                        f for f in os.listdir(input_folder)
                        if os.path.isfile(os.path.join(input_folder, f))
                    ]
                ext = os.path.splitext(files[0])[1] if files else ""
                proposed_name = file_utils.generate_next_filename(
                    output_folder,
                    ext,
                    use_date_suffix=workflow.use_date_suffix,
                )
                if proposed_name:
                    request.session["proposed_name"] = proposed_name
            StepFormSet = build_step_formset(workflow)
    else:
        form = RunWorkflowForm(user=request.user, workflow_queryset=user_wfs)
        StepFormSet = build_step_formset(workflow)
        if request.session.get("suggested_wf_id"):
            try:
                suggested_workflow = Workflow.objects.get(id=request.session["suggested_wf_id"], created_by=request.user)
            except Workflow.DoesNotExist:
                suggested_workflow = None
        if request.session.get("proposed_name"):
            proposed_name = request.session["proposed_name"]

    if not video_formset and input_folder and os.path.isdir(input_folder):
        video_files = [
            f
            for f in os.listdir(input_folder)
            if os.path.isfile(os.path.join(input_folder, f))
            and file_utils.classify_media(os.path.join(input_folder, f))["is_video"]
        ]
        if len(video_files) > 1:
            initial = [
                {"file_name": f, "order": idx + 1}
                for idx, f in enumerate(sorted(video_files))
            ]
            video_formset = VideoOrderFormSet(prefix="video", initial=initial)
    step_pairs = list(zip(workflow.steps.all(), StepFormSet)) if workflow else []

    return render(
        request,
        "workflow_automation/run_workflow.html",
        {
            "form": form,
            "step_forms": StepFormSet,
            "workflow": workflow,
            "step_pairs": step_pairs,
            "video_forms": video_formset,
            "confirm": confirm,
            "input_folder": input_folder,
            "output_folder": output_folder,
            "suggested_workflow": suggested_workflow,
            "proposed_name": proposed_name,
            "manual_override": manual_override,
        },
    )


@login_required
def workflow_progress(request, run_id):
    """Display progress and execute steps one by one."""

    run = get_object_or_404(WorkflowRun, id=run_id, user=request.user)
    configs = request.session.get(f"run_{run_id}_configs", [])
    step_index = request.session.get(f"run_{run_id}_index", 0)
    run_mode = "pause" if run.pause_between_steps else "run_all"

    review_state = request.session.get(f"run_{run_id}_review")
    video_map = request.session.get(f"run_{run_id}_video_map")
    rename_state = request.session.get(f"run_{run_id}_renames", [])

    runner = WorkflowRunner(
        run.workflow,
        run.input_path,
        run.output_path,
        project_code=run.project_code,
        initials=run.initials,
        step_configs=configs,
        run_mode=run_mode,
        qa_video_review=run.workflow.qa_video_review,
        video_order_map=video_map,
        use_date_suffix=run.workflow.use_date_suffix,
    )
    runner.current_step = step_index
    runner.logs = run.log.splitlines() if run.log else []
    runner.rename_actions = rename_state

    if review_state:
        runner.conversion_index = review_state.get("index", 0)
        runner.review_pending = True
        runner.review_image = review_state.get("image", "")
        runner.review_file = review_state.get("file", "")

    if runner.review_pending:
        default_zone = ""
        if video_map:
            mapping = video_map.get(os.path.basename(runner.review_file))
            if mapping:
                default_zone = mapping.get("zone", "")
        form = VideoReviewForm(request.POST or None, initial={"zone_id": default_zone})
        if request.method == "POST" and form.is_valid():
            zone = form.cleaned_data["zone_id"]
            flag = form.cleaned_data["flag_manual_edit"]
            old_name = os.path.basename(runner.review_file)
            new_path = file_utils.rename_with_zone(
                runner.review_file,
                os.path.dirname(runner.review_file),
                zone,
                use_date_suffix=runner.use_date_suffix,
            )
            new_name = os.path.basename(new_path)
            if new_name != old_name:
                runner.logs.append(f"Renamed {old_name} -> {new_name}")
            runner.record_rename(runner.review_file, new_path, manual=True, flagged=flag)
            idx = runner.conversion_index - 1
            if 0 <= idx < len(runner.files):
                runner.files[idx] = new_path
            runner.review_file = new_path

            runner.rename_actions.append({
                "file": old_name,
                "new_name": new_name,
                "flagged": bool(flag),
            })

            msg = f"Reviewed {new_name} - Zone {zone}"
            if flag:
                msg += " (flagged for manual edit)"
            runner.logs.append(msg)
            runner.review_pending = False
            request.session.pop(f"run_{run_id}_review", None)
            request.session[f"run_{run_id}_renames"] = runner.rename_actions
            run.log = "\n".join(runner.logs)
            run.save()
            if run.completed_at is None:
                if run_mode == "run_all":
                    runner.run_all()
                else:
                    runner.run_next()
        else:
            return render(
                request,
                "workflow_automation/video_review.html",
                {
                    "run": run,
                    "form": form,
                    "preview_url": runner.review_image,
                    "crop_start": runner.last_crop_start,
                    "crop_end": runner.last_crop_end,
                    "audio_removed": runner.last_remove_audio,
                },
            )

    if run.completed_at is None:
        if run_mode == "run_all":
            runner.run_all()
        else:
            if request.method == "POST" or step_index == 0:
                runner.run_next()
                step_index = runner.current_step
                if step_index >= run.workflow.steps.count():
                    run.completed_at = timezone.now()
                    request.session.pop(f"run_{run_id}_index", None)
                else:
                    request.session[f"run_{run_id}_index"] = step_index
                request.session.modified = True

        if runner.review_pending:
            request.session[f"run_{run_id}_review"] = {
                "index": runner.conversion_index,
                "image": runner.review_image,
                "file": runner.review_file,
            }
            request.session.modified = True
        else:
            request.session.pop(f"run_{run_id}_review", None)
        request.session[f"run_{run_id}_renames"] = runner.rename_actions

        run.log = "\n".join(runner.logs)
        run.save()
        if run.completed_at is not None:
            write_workflow_log(run, runner.logs, runner)
            request.session.pop(f"run_{run_id}_video_map", None)
            request.session.pop(f"run_{run_id}_renames", None)

    done = run.completed_at is not None

    if run_mode == "pause" and not done:
        step_name = ""
        if step_index > 0 and step_index <= run.workflow.steps.count():
            step_obj = run.workflow.steps.all()[step_index - 1]
            step_name = step_obj.get_step_type_display()
        step_logs = runner.logs[-2:]
        context = {"run": run, "step_name": step_name, "step_logs": step_logs}
        template = "workflow_automation/pause_confirmation.html"
    else:
        context = {"run": run, "logs": runner.logs, "done": done, "run_mode": run_mode}
        template = "workflow_automation/workflow_progress.html"
    return render(request, template, context)


@login_required
def run_rename_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.initials:
        messages.error(request, "Please input your initials on the account page to continue.")
        return redirect("accounts")

    form = RenameToolForm(request.POST or None, initial={"user_initials": profile.initials})
    files = []
    selected_folder = ""
    if request.method == "POST" and form.is_valid():
        raw_folder = form.cleaned_data["raw_data_folder"]
        output_folder = form.cleaned_data["output_folder"]
        initials = form.cleaned_data["user_initials"]
        full_name = form.cleaned_data["full_name"]
        pattern = form.cleaned_data.get("rename_pattern", "")

        if not os.path.isdir(raw_folder) or not any(
            os.path.isfile(os.path.join(raw_folder, f)) for f in os.listdir(raw_folder)
        ):
            form.add_error("raw_data_folder", "Selected folder has no valid files")
        else:
            files = rename.run_rename(raw_folder, output_folder, initials, full_name, pattern)
            messages.success(request, "Rename completed")
            selected_folder = raw_folder

    return render(
        request,
        "workflow_automation/run_rename.html",
        {"form": form, "files": files, "raw_folder": selected_folder},
    )


@login_required
def run_convert_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.initials:
        messages.error(request, "Please input your initials on the account page to continue.")
        return redirect("accounts")

    form = ConvertToolForm(request.POST or None)
    files = []
    if request.method == "POST" and form.is_valid():
        input_path = form.cleaned_data["input_path"]
        fmt = form.cleaned_data["format"]
        files = converter.convert_directory(input_path, fmt)
        messages.success(request, "Conversion completed")
    return render(request, "workflow_automation/run_convert.html", {"form": form, "files": files})


@login_required
def run_zip_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.initials:
        messages.error(request, "Please input your initials on the account page to continue.")
        return redirect("accounts")

    form = ZipToolForm(request.POST or None)
    zip_path = None
    if request.method == "POST" and form.is_valid():
        input_path = form.cleaned_data["input_path"]
        output_zip = form.cleaned_data["output_zip"]
        zip_path = zipper.zip_directory(input_path, output_zip)
        messages.success(request, "Zip created")
    return render(request, "workflow_automation/run_zip.html", {"form": form, "zip_path": zip_path})

