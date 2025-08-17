from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.utils.html import strip_tags
from datetime import timedelta
from django.db.models import Q
import os
import logging
from django.templatetags.static import static

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
    ResponseForm,
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

from utils import rename, converter, zipper, progress, zip_task, workflow_task
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
import threading
from . import file_utils
from .log_writer import write_workflow_log

# Number of allowed failed attempts before locking an account
LOCKOUT_THRESHOLD = 5
# Duration of the lockout once the threshold is exceeded
LOCKOUT_DURATION = timedelta(hours=1)

logger = logging.getLogger(__name__)

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login, logout


@login_required
def launcher(request):
    """Render the root landing page with message board and section links."""
    notice = Notice.objects.last()

    context = {"notice": notice}
    return render(request, "workflow_automation/launcher.html", context)


@login_required
def home(request):
    """Render the dashboard-style home page."""
    pending_count = 0

    if request.user.is_superuser:
        pending_count = Workflow.objects.filter(awaiting_review=True).count()
        if pending_count:
            messages.info(request, f"You have {pending_count} workflow review requests pending.")
    run_id = request.session.pop("active_run_id", None)
    context = {
        "pending_count": pending_count,
        "run_id": run_id,
    }
    return render(request, "workflow_automation/home.html", context)


@login_required
def equipment_dashboard(request):
    """Placeholder dashboard for equipment booking."""
    return render(request, "workflow_automation/equipment_dashboard.html")


@login_required
def demo_video_review(request):
    """Display a demo video preview using a static image."""
    if request.method == "POST":
        form = VideoReviewForm(request.POST)
        if form.is_valid():
            messages.success(request, "Demo complete")
            return redirect("home")
    else:
        form = VideoReviewForm(initial={"zone_id": "Demo"})

    context = {
        "preview_url": static("images/Demo Video Snip.png"),
        "crop_start": 0,
        "crop_end": 0,
        "audio_removed": False,
        "form": form,
    }
    return render(request, "workflow_automation/video_review.html", context)


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
        bookings_qs = Booking.objects.filter(start_time__gte=current_time)
        previous_qs = Booking.objects.filter(end_time__lt=current_time)
    else:
        bookings_qs = Booking.objects.filter(user=request.user, start_time__gte=current_time)
        previous_qs = Booking.objects.filter(user=request.user, end_time__lt=current_time)

    if request.user.is_superuser:
        upcoming_columns = [
            {"key": "user", "label": "User"},
            {"key": "item", "label": "Item"},
            {"key": "start_time", "label": "Start Time"},
            {"key": "end_time", "label": "End Time"},
        ]
        previous_columns = list(upcoming_columns)
    else:
        upcoming_columns = [
            {"key": "item", "label": "Item"},
            {"key": "start_time", "label": "Start Time"},
            {"key": "end_time", "label": "End Time"},
        ]
        previous_columns = list(upcoming_columns)

    upcoming_rows = []
    for b in bookings_qs:
        upcoming_rows.append(
            {
                "id": b.id,
                "user": b.user.username,
                "item": b.equipment.name,
                "start_time": timezone.localtime(b.start_time).strftime("%d %b %Y %H:%M"),
                "end_time": timezone.localtime(b.end_time).strftime("%d %b %Y %H:%M"),
                "can_edit": request.user.is_superuser
                or (b.start_time > current_time and b.user == request.user),
                "can_delete": request.user.is_superuser,
            }
        )

    previous_rows = []
    for b in previous_qs:
        previous_rows.append(
            {
                "user": b.user.username,
                "item": b.equipment.name,
                "start_time": timezone.localtime(b.start_time).strftime("%d %b %Y %H:%M"),
                "end_time": timezone.localtime(b.end_time).strftime("%d %b %Y %H:%M"),
            }
        )

    return render(
        request,
        'workflow_automation/booking_list.html',
        {
            'is_superuser': request.user.is_superuser,
            'upcoming_columns': upcoming_columns,
            'upcoming_rows': upcoming_rows,
            'previous_columns': previous_columns,
            'previous_rows': previous_rows,
        },
    )


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
                pending = Workflow.objects.filter(awaiting_review=True).count()
                if pending:
                    messages.info(request, f'You have {pending} workflow review requests pending.')

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
        previous_qs = Booking.objects.filter(end_time__lt=current_time)
        columns = [
            {"key": "user", "label": "User"},
            {"key": "item", "label": "Item"},
            {"key": "start_time", "label": "Start Time"},
            {"key": "end_time", "label": "End Time"},
        ]
    else:
        previous_qs = Booking.objects.filter(user=request.user, end_time__lt=current_time)
        columns = [
            {"key": "item", "label": "Item"},
            {"key": "start_time", "label": "Start Time"},
            {"key": "end_time", "label": "End Time"},
        ]

    rows = []
    for b in previous_qs:
        rows.append(
            {
                "user": b.user.username,
                "item": b.equipment.name,
                "start_time": timezone.localtime(b.start_time).strftime("%d %b %Y %H:%M"),
                "end_time": timezone.localtime(b.end_time).strftime("%d %b %Y %H:%M"),
            }
        )

    return render(
        request,
        'workflow_automation/previous_bookings.html',
        {
            'columns': columns,
            'rows': rows,
            'is_superuser': request.user.is_superuser,
        },
    )


@login_required
def user_accounts(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("You are not allowed to view this page.")
    users = User.objects.all().select_related('profile')
    return render(request, 'workflow_automation/user_accounts.html', {'users': users})


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
@login_required
def user_messages(request):
    msgs = (
        Message.objects.filter(sender=request.user, workflow__isnull=True)
        .order_by('-created_at')
    )

    columns = [
        {"key": "subject", "label": "Subject"},
        {"key": "created_at", "label": "Date Sent"},
        {"key": "content", "label": "Message"},
    ]

    rows = []
    for m in msgs:
        rows.append(
            {
                "subject": m.subject,
                "created_at": timezone.localtime(m.created_at).strftime("%d %b %Y %H:%M"),
                "content": strip_tags(m.content),
            }
        )

    return render(
        request,
        'workflow_automation/user_messages.html',
        {
            'columns': columns,
            'rows': rows,
        },
    )

@user_passes_test(lambda u: u.is_superuser)
def inbox(request):
    pending_workflows = Workflow.objects.filter(awaiting_review=True).select_related('created_by')
    unsettled_messages = (
        Message.objects.filter(recipient=request.user, is_review_request=False, is_read=False)
        .select_related('sender')
        .order_by('-created_at')
    )
    settled_messages = (
        Message.objects.filter(recipient=request.user, is_review_request=False, is_read=True)
        .select_related('sender')
        .order_by('-created_at')
    )

    if request.method == "POST":
        if 'accept_workflow' in request.POST:
            wf_id = request.POST.get('accept_workflow')
            workflow = get_object_or_404(Workflow, id=wf_id)
            workflow.is_published = True
            workflow.awaiting_review = False
            workflow.review_status = "accepted"
            workflow.rejection_comment = ""
            workflow.published_by = request.user
            workflow.published_at = timezone.now()
            workflow.save()
            Message.objects.create(
                sender=request.user,
                recipient=workflow.created_by,
                workflow=workflow,
                subject="Workflow Approved",
                content="Your workflow was approved and published.",
            )
            messages.success(request, 'Workflow approved.')
            return redirect('inbox')
        if 'reject_workflow' in request.POST:
            wf_id = request.POST.get('reject_workflow')
            comment = request.POST.get('rejection_comment', '')
            workflow = get_object_or_404(Workflow, id=wf_id)
            workflow.is_published = False
            workflow.awaiting_review = False
            workflow.review_status = "rejected"
            workflow.rejection_comment = comment
            workflow.save()
            Message.objects.create(
                sender=request.user,
                recipient=workflow.created_by,
                workflow=workflow,
                subject="Workflow Rejected",
                content=comment,
            )
            messages.success(request, 'Workflow rejected.')
            return redirect('inbox')
        if 'mark_replied' in request.POST:
            msg_id = request.POST.get('mark_replied')
            msg = get_object_or_404(Message, id=msg_id, recipient=request.user)
            msg.is_read = True
            msg.save()
            return redirect('inbox')

    return render(
        request,
        'workflow_automation/inbox.html',
        {
            'pending_workflows': pending_workflows,
            'unsettled_messages': unsettled_messages,
            'settled_messages': settled_messages,
        },
    )


@user_passes_test(lambda u: u.is_superuser)
def message_detail(request, message_id):
    msg = get_object_or_404(Message, id=message_id, recipient=request.user)
    if request.method == 'POST':
        form = ResponseForm(request.POST, instance=msg)
        if form.is_valid():
            response = form.save(commit=False)
            response.responded_by = request.user
            response.is_read = True
            response.save()
            messages.success(request, 'Response saved successfully.')
            return redirect('inbox')
    else:
        form = ResponseForm(instance=msg)
    return render(
        request,
        'workflow_automation/message_detail.html',
        {'message': msg, 'form': form},
    )


@user_passes_test(lambda u: u.is_superuser)
def workflow_detail(request, workflow_id):
    workflow = get_object_or_404(Workflow, id=workflow_id)
    return render(request, 'workflow_automation/workflow_detail.html', {'workflow': workflow})


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
    return redirect(request.META.get('HTTP_REFERER', 'home'))


def security_notice(request):
    """Render a notice page when users access a restricted admin URL."""
    return render(request, 'workflow_automation/security_notice.html')


def page_not_found(request, exception):
    """Display a user-friendly 404 page for invalid URLs."""
    return render(request, '404.html', status=404)


@login_required
def workflow_dashboard(request):
    workflows = Workflow.objects.filter(is_published=True)

    recent_runs = []
    if not workflows.exists():
        runs = (
            WorkflowRun.objects.filter(user=request.user)
            .select_related("workflow")
            .order_by("-started_at")[:10]
        )
        seen = set()
        for run in runs:
            if run.workflow_id not in seen:
                recent_runs.append(run)
                seen.add(run.workflow_id)
            if len(recent_runs) >= 3:
                break

    context = {
        "workflows": workflows,
        "recent_runs": recent_runs,
    }
    return render(request, "workflow_automation/workflow_dashboard.html", context)


@login_required
def create_workflow(request, workflow_id=None):
    step_codes = [
        "setup_structure",
        "convert_360_video",
        "rename",
        "remove_audio",
        "trim",
        "organize_files",
    ]

    workflow = None
    if request.method == "GET" and (workflow_id or request.GET.get("workflow_id")):
        wf_id = workflow_id or request.GET.get("workflow_id")
        workflow = get_object_or_404(
            Workflow,
            id=wf_id,
            created_by=request.user,
            from_shared=False,
        )
        wf_form = WorkflowForm(instance=workflow)
    elif request.method == "POST":
        wf_id = request.POST.get("workflow_id") or workflow_id
        instance = None
        if wf_id:
            instance = get_object_or_404(
                Workflow,
                id=wf_id,
                created_by=request.user,
                from_shared=False,
            )
            workflow = instance
        wf_form = WorkflowForm(request.POST, instance=instance)
        if wf_form.is_valid():
            workflow = wf_form.save(commit=False)
            workflow.created_by = request.user
            if request.user.is_superuser and not wf_id:
                workflow.is_published = True
                workflow.published_by = request.user
                workflow.published_at = timezone.now()
            workflow.save()
            if instance:
                instance.steps.all().delete()

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
                        action=code,
                        order=int(order),
                        config=config,
                        crop_start_seconds=float(config.get("crop_start_seconds", 0) or 0),
                        crop_end_seconds=float(config.get("crop_end_seconds", 0) or 0),
                        remove_audio=config.get("remove_audio", False),
                    )

            msg = "Workflow updated successfully." if wf_id else "Workflow created successfully."
            messages.success(request, msg)
            return redirect("my_workflows")
    else:
        wf_form = WorkflowForm()

    steps_map = {s.action: s for s in workflow.steps.all()} if workflow else {}
    context = {
        "form": wf_form,
        "step_choices": WorkflowStep.ACTION_CHOICES,
        "workflow": workflow,
        "steps_map": steps_map,
    }
    return render(request, "workflow_automation/create_workflow.html", context)


@login_required
def my_workflows(request):
    def build_items(queryset, imported=False):
        items = []
        for wf in queryset:
            if wf.review_status == "pending":
                status_text = "Awaiting Review"
                category = "Awaiting Review"
            elif wf.review_status == "rejected":
                comment = wf.rejection_comment if wf.created_by_id == request.user.id else ""
                status_text = "Rejected" + (f" - {comment}" if comment else "")
                category = "Rejected"
            elif wf.review_status == "accepted" or wf.is_published or imported:
                status_text = "Published"
                category = "Published"
            else:
                status_text = "Unpublished"
                category = "Unpublished"
            items.append({"obj": wf, "status_text": status_text, "status_category": category})
        return items

    my_qs = Workflow.objects.filter(created_by=request.user, from_shared=False)
    imported_qs = Workflow.objects.filter(created_by=request.user, from_shared=True)
    context = {
        'my_workflows': build_items(my_qs),
        'imported_workflows': build_items(imported_qs, imported=True),
    }
    return render(request, 'workflow_automation/my_workflows.html', context)


@login_required
def request_review(request, workflow_id):
    workflow = get_object_or_404(Workflow, id=workflow_id, created_by=request.user)
    if request.method == "POST":
        if not workflow.awaiting_review:
            workflow.awaiting_review = True
            workflow.review_status = "pending"
            workflow.rejection_comment = ""
            workflow.save()
            messages.success(request, "Review request submitted successfully.")
        else:
            messages.info(request, "Review already requested.")
    return redirect("my_workflows")


@login_required
def delete_workflow_view(request, pk):
    workflow = get_object_or_404(Workflow, pk=pk)
    if request.method == "POST":
        if request.user == workflow.created_by or request.user.is_staff:
            workflow.delete()
            messages.success(request, "Workflow deleted.")
        elif workflow.downloaded_by.filter(id=request.user.id).exists():
            workflow.downloaded_by.remove(request.user)
            messages.success(request, "Workflow removed from your downloads.")
        else:
            return HttpResponseForbidden("You do not have permission to delete this workflow.")
        return redirect("my_workflows")
    return HttpResponseForbidden("Invalid request.")


@user_passes_test(lambda u: u.is_superuser)
@login_required
def review_workflows(request):
    workflows = Workflow.objects.filter(awaiting_review=True).select_related("created_by")
    if request.method == "POST":
        wf_id = request.POST.get("workflow_id")
        action = request.POST.get("action")
        workflow = get_object_or_404(Workflow, id=wf_id)
        if action == "approve":
            workflow.is_published = True
            workflow.awaiting_review = False
            workflow.review_status = "accepted"
            workflow.rejection_comment = ""
            workflow.published_by = request.user
            workflow.published_at = timezone.now()
            workflow.save()
            Message.objects.create(
                sender=request.user,
                recipient=workflow.created_by,
                workflow=workflow,
                subject="Workflow Approved",
                content="Your workflow was approved and published.",
            )
            messages.success(request, f'Workflow "{workflow.name}" approved.')
        elif action == "reject":
            comment = request.POST.get("comment", "")
            workflow.is_published = False
            workflow.awaiting_review = False
            workflow.review_status = "rejected"
            workflow.rejection_comment = comment
            workflow.save()
            Message.objects.create(
                sender=request.user,
                recipient=workflow.created_by,
                workflow=workflow,
                subject="Workflow Rejected",
                content=comment,
            )
            messages.success(request, f'Workflow "{workflow.name}" rejected.')
        return redirect("review_workflows")
    return render(
        request,
        "workflow_automation/review_workflows.html",
        {"workflows": workflows},
    )


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
    columns = [
        {"key": "name", "label": "Name", "td_class": "td-name"},
        {"key": "description", "label": "Description", "td_class": "td-description"},
        {"key": "author", "label": "Author", "td_class": "td-author"},
    ]
    rows = []
    for wf in workflows:
        author = (
            wf.published_by.username
            if wf.published_by
            else wf.created_by.username if wf.created_by else "-"
        )
        rows.append(
            {
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "author": author,
            }
        )

    return render(
        request,
        "workflow_automation/shared_workflows.html",
        {"columns": columns, "rows": rows, "search_query": query},
    )


# Backwards compatibility for templates using old view name
shared_workflows = shared_workflow_list_view


@login_required
def use_shared_workflow(request, workflow_id):
    workflow = get_object_or_404(Workflow, id=workflow_id, is_published=True)
    workflow.downloaded_by.add(request.user)
    new_wf = Workflow.objects.create(
        name=workflow.name,
        description=workflow.description,
        created_by=request.user,
        from_shared=True,
        source_creator=workflow.created_by,
    )
    for step in workflow.steps.all():
        WorkflowStep.objects.create(
            workflow=new_wf,
            action=step.action,
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
        StepSettingsForm(prefix=f"form-{idx}", action=s.action, initial=s.config)
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
        # POST body (form-0-action etc.) which only happens after the user
        # confirms the folder selection.  In that case we validate all forms and
        # execute the workflow steps immediately.
        is_run_request = "form-0-action" in request.POST

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
                        action=step.action,
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
                        request.session["active_run_id"] = run.id
                        return redirect("workflow_progress", run_id=run.id)
                    workflow_task.start_workflow(run, configs, video_map)
                    request.session["active_run_id"] = run.id
                    return redirect("home")

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
                    building_name=file_utils.parse_site_code(output_folder),
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
    """Render progress page for a running workflow."""

    run = get_object_or_404(WorkflowRun, id=run_id, user=request.user)
    return render(
        request,
        "workflow_automation/workflow_progress.html",
        {"run": run},
    )


@login_required
def workflow_status(request, run_id):
    """Return JSON status for the running workflow."""

    run = get_object_or_404(WorkflowRun, id=run_id, user=request.user)
    total = run.workflow.steps.count()
    percent = int(run.current_step / total * 100) if total else 0
    if run.status == "completed":
        percent = 100
    data = {
        "status": run.status,
        "current_step": run.current_step,
        "total_steps": total,
        "percent": percent,
        "current_action": run.current_action,
        "logs": run.log.splitlines()[-10:] if run.log else [],
        "error": run.error_message,
    }
    return JsonResponse(data)


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
    if request.method == "POST" and form.is_valid():
        input_path = form.cleaned_data["input_path"]
        output_folder = form.cleaned_data["output_zip"]
        os.makedirs(output_folder, exist_ok=True)
        zip_task.start_zip(input_path, output_folder)
        messages.info(request, "Zipping started")
        return redirect("run_zip")
    return render(request, "workflow_automation/run_zip.html", {"form": form})


def progress_status(request):
    """Return JSON status for the zip progress bar."""
    data = progress.get()
    return JsonResponse({
        "task": data.get("task"),
        "completed": len(data.get("completed", [])),
        "total": data.get("total", 0),
        "status": data.get("status"),
        "percent": data.get("percent", 0),
        "current_file": data.get("current", ""),
        "input_path": data.get("input_path", ""),
        "output_path": data.get("output_path", ""),
        "completed_files": data.get("completed", []),
        "pending_files": data.get("pending", []),
    })


@require_POST
def progress_control(request):
    """Handle pause/resume/cancel/restart actions."""
    action = request.POST.get("action")
    if action == "pause":
        progress.set_status("paused")
    elif action == "resume":
        progress.set_status("running")
    elif action == "cancel":
        progress.set_status("cancel")
    elif action == "restart":
        data = progress.get()
        args = progress.args()
        if all(args):
            completed = data.get("completed", [])
            if completed:
                last = completed[-1]
                last_zip = os.path.join(data.get("output_path", ""), os.path.splitext(last)[0] + ".zip")
                if os.path.exists(last_zip):
                    os.remove(last_zip)
                completed = completed[:-1]
            progress.set_status("cancel")
            zip_task.start_zip(args[0], args[1], completed=completed)
    else:
        return HttpResponseBadRequest("Invalid action")
    return JsonResponse({"status": "ok"})

