from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from datetime import timedelta

from .models import Booking, Profile, Message, Notice, LoginAttempt, UnknownLoginAttempt
from .forms import BookingForm, ProfileForm, MessageForm, NoticeForm

# Number of allowed failed attempts before locking an account
LOCKOUT_THRESHOLD = 5
# Duration of the lockout once the threshold is exceeded
LOCKOUT_DURATION = timedelta(hours=1)

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail


@login_required
def home(request):
    # Display the most recent notice and handle notice creation for superusers
    notices = Notice.objects.last()
    unread_messages = Message.objects.filter(recipient=request.user, read=False)

    if request.user.is_superuser and unread_messages.exists():
        messages.info(request, f'You have {unread_messages.count()} unread messages.')

    if request.method == 'POST' and request.user.is_superuser:
        message = request.POST.get('message')
        if message:
            Notice.objects.create(message=message, created_by=request.user)
            messages.success(request, 'Notice created successfully!')
            return redirect('home')

    return render(request, 'bookings/home.html', {'notices': notices})


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

    return render(request, 'bookings/signup.html', {'form': form})


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

    return render(request, 'bookings/create_booking.html', {'form': form})


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

    return render(request, 'bookings/booking_list.html', {
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

    return render(request, 'bookings/edit_booking.html', {'form': form, 'booking': booking})


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
            return render(request, 'bookings/login.html')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            login_attempt.failed_attempts = 0
            login_attempt.lockout_until = None
            login_attempt.save()
            messages.success(request, 'Successfully logged in!')

            # Check for unread messages for superadmins
            if user.is_superuser:
                unread_messages = Message.objects.filter(recipient=user, read=False)
                if unread_messages.exists():
                    messages.info(request, f'You have {unread_messages.count()} unread messages.')

            return redirect('home')
        else:
            login_attempt.failed_attempts += 1
            if login_attempt.failed_attempts >= LOCKOUT_THRESHOLD:
                login_attempt.lockout_until = timezone.now() + LOCKOUT_DURATION
                login_attempt.save()
                minutes = int(LOCKOUT_DURATION.total_seconds() // 60)
                messages.error(request, f'Account locked. Try again in {minutes} minutes.')
                return render(request, 'bookings/login.html')
            else:
                attempts_left = LOCKOUT_THRESHOLD - login_attempt.failed_attempts
                login_attempt.save()
                messages.error(request, f'Invalid username or password. {attempts_left} attempts remaining.')

    return render(request, 'bookings/login.html')

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
    return render(request, 'bookings/account_detail.html', context)


@login_required
def previous_bookings(request):
    current_time = timezone.now()

    if request.user.is_superuser:
        previous_bookings = Booking.objects.filter(end_time__lt=current_time)
    else:
        previous_bookings = Booking.objects.filter(user=request.user, end_time__lt=current_time)

    return render(request, 'bookings/previous_bookings.html', {
        'previous_bookings': previous_bookings,
        'is_superuser': request.user.is_superuser
    })


@login_required
def contact(request):
    if not request.user.email:
        messages.error(request, 'You need an active email associated with your account to send a message.')
        return redirect('accounts')

    if request.method == 'POST':
        form = MessageForm(request.POST)
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
        form = MessageForm()

    return render(request, 'bookings/contact.html', {'form': form})



@login_required
def admin_messages(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("You are not allowed to access this page.")

    messages = Message.objects.filter(recipient=request.user).order_by('-created_at')
    return render(request, 'bookings/admin_messages.html', {'messages': messages})


@login_required
def user_messages(request):
    messages = Message.objects.filter(recipient=request.user).order_by('-created_at')
    return render(request, 'bookings/user_messages.html', {'messages': messages})


@login_required
def respond_to_message(request, message_id):
    if request.user.is_superuser:
        message = get_object_or_404(Message, id=message_id)

        if request.method == 'POST':
            response_content = request.POST.get('response')
            message.response = response_content
            message.read = True
            message.save()
            messages.success(request, 'Response saved successfully.')

            send_mail(
                subject='New response to your message',
                message=f'You have received a new response: {message.response}',
                from_email='no-reply@yourdomain.com',
                recipient_list=[message.sender.email],
            )
            return redirect('inbox')

        return render(request, 'bookings/respond_message.html', {'message': message})

    return HttpResponseForbidden("You are not allowed to respond to messages.")


@user_passes_test(lambda u: u.is_superuser)
def inbox(request):
    unsettled_messages = Message.objects.filter(read=False)
    settled_messages = Message.objects.filter(read=True)

    if request.method == "POST":
        replied_message_ids = request.POST.getlist('replied_messages')
        Message.objects.filter(id__in=replied_message_ids).update(read=True, responded_by=request.user)
        return redirect('inbox')

    return render(request, 'bookings/inbox.html', {
        'unsettled_messages': unsettled_messages,
        'settled_messages': settled_messages
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

    return render(request, 'bookings/manage_notice.html', {'form': form, 'notice': notice})


@user_passes_test(lambda u: u.is_superuser)
def remove_notice(request):
    if request.method == 'POST':
        Notice.objects.all().delete()
        messages.success(request, 'Notice removed successfully.')
    return redirect('home')


def security_notice(request):
    """Render a notice page when users access a restricted admin URL."""
    return render(request, 'bookings/security_notice.html')
