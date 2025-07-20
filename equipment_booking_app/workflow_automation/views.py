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
)

from .workflow_runner import WorkflowRunner

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
                    elif code == "organize_files":
                        config["target_folder"] = request.POST.get("target_folder", "")

                    WorkflowStep.objects.create(
                        workflow=workflow,
                        step_type=code,
                        order=int(order),
                        config=config,
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
        form = MessageForm(user=request.user, initial={'workflow': workflow})
        form.fields['workflow'].widget = forms.HiddenInput()
    return render(request, 'workflow_automation/request_review.html', {'form': form, 'workflow': workflow})


@login_required
def shared_workflows(request):
    workflows = Workflow.objects.filter(is_published=True)
    return render(request, 'workflow_automation/shared_workflows.html', {'workflows': workflows})


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


def suggest_workflow_for_folder(path, user):
    """Return a workflow whose name or tags match the folder path."""
    segments = [s for s in os.path.normpath(path).split(os.sep) if s][-3:]
    query_base = Workflow.objects.filter(created_by=user)
    for seg in reversed(segments):
        q = Q(name__icontains=seg)
        if hasattr(Workflow, "tags"):
            q = q | Q(tags__name__icontains=seg)
        match = query_base.filter(q).first()
        if match:
            return match
    return None


@login_required
def run_workflow(request):
    """Collect folder paths for a workflow run and display confirmation."""

    user_wfs = Workflow.objects.filter(created_by=request.user)
    workflow = user_wfs.first() if user_wfs else None

    confirm = False
    input_folder = output_folder = ""
    suggested_workflow = None

    if request.method == "POST":
        if "accept_suggested" in request.POST:
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
            )
            StepFormSet = StepSettingsFormSet()
        elif "reject_suggested" in request.POST:
            request.session.pop("suggested_wf_id", None)
            input_folder = request.session.get("input_folder", "")
            output_folder = request.session.get("output_folder", "")
            confirm = True
            form = RunWorkflowForm(user=request.user)
            StepFormSet = StepSettingsFormSet()
        else:
            form = RunWorkflowForm(request.POST, user=request.user)
            if form.is_valid():
                workflow = form.cleaned_data["workflow"]
                input_folder = form.cleaned_data["input_path"]
                output_folder = form.cleaned_data["output_path"]

                request.session["input_folder"] = input_folder
                request.session["output_folder"] = output_folder
                confirm = True
                suggested_workflow = suggest_workflow_for_folder(output_folder, request.user)
                if suggested_workflow:
                    request.session["suggested_wf_id"] = suggested_workflow.id
            StepFormSet = StepSettingsFormSet(request.POST)
    else:
        form = RunWorkflowForm(user=request.user)
        StepFormSet = StepSettingsFormSet()
        if request.session.get("suggested_wf_id"):
            try:
                suggested_workflow = Workflow.objects.get(id=request.session["suggested_wf_id"], created_by=request.user)
            except Workflow.DoesNotExist:
                suggested_workflow = None

    step_pairs = list(zip(workflow.steps.all(), StepFormSet)) if workflow else []

    return render(
        request,
        "workflow_automation/run_workflow.html",
        {
            "form": form,
            "step_forms": StepFormSet,
            "workflow": workflow,
            "step_pairs": step_pairs,
            "confirm": confirm,
            "input_folder": input_folder,
            "output_folder": output_folder,
            "suggested_workflow": suggested_workflow,
        },
    )


@login_required
def workflow_progress(request, run_id):
    """Display progress and execute steps one by one."""

    run = get_object_or_404(WorkflowRun, id=run_id, user=request.user)
    configs = request.session.get(f"run_{run_id}_configs", [])
    run_mode = request.session.get(f"run_{run_id}_mode", "run_all")
    step_index = request.session.get(f"run_{run_id}_index", 0)

    runner = WorkflowRunner(
        run.workflow,
        run.input_path,
        run.output_path,
        project_code=run.project_code,
        initials=run.initials,
        step_configs=configs,
        run_mode=run_mode,
    )
    runner.current_step = step_index
    runner.logs = run.log.splitlines() if run.log else []

    if run.completed_at is None:
        if run_mode == "run_all":
            runner.run_all()
            run.completed_at = timezone.now()
            request.session.pop(f"run_{run_id}_index", None)
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

        run.log = "\n".join(runner.logs)
        run.save()

    done = run.completed_at is not None

    return render(
        request,
        "workflow_automation/workflow_progress.html",
        {"run": run, "logs": runner.logs, "done": done, "run_mode": run_mode},
    )
