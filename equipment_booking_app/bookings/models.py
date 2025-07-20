from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

# Model representing different equipment types available for booking
class Equipment(models.Model):
    ITEM_CHOICES = [
        ('mouse', 'Mouse'),
        ('monitor', 'Monitor'),
        ('blk2go', 'BLK2GO'),
        ('p40_scanner', 'P40 Scanner'),
        ('ipad', 'iPad'),
        ('pc', 'PC'),
        ('hdmi_cable', 'HDMI Cable'),
        ('power_bank', 'Power Bank'),
        ('total_station', 'Total Station'),
        ('ipad_pro', 'iPad Pro'),
        ('keyboard', 'Keyboard'),
        ('mouse_pad', 'Mouse Pad'),
    ]

    name = models.CharField(max_length=255, choices=ITEM_CHOICES)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, default="available")

    def __str__(self):
        return self.get_name_display()  # Returns the human-readable name


# Default start and end times for bookings
def get_default_start_time():
    return timezone.now().replace(hour=7, minute=30, second=0, microsecond=0)

def get_default_end_time():
    return timezone.now().replace(hour=17, minute=0, second=0, microsecond=0)


# Model for storing booking information
class Booking(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField(default=get_default_start_time)
    end_time = models.DateTimeField(default=get_default_end_time)
    reason = models.TextField()
    project_number = models.CharField(max_length=6)
    use_location = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.equipment.name} booked by {self.user.username} from {self.start_time} to {self.end_time}"


# Model for user profile details
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    work_address = models.CharField(max_length=255, blank=True, null=True)
    company = models.CharField(max_length=100, blank=True, null=True)
    work_division = models.CharField(max_length=100, blank=True, null=True)
    job_role = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.user.username


# Model for messages between users
class Message(models.Model):
    subject = models.CharField(max_length=255, default='General Inquiry')
    content = models.TextField()
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    confirmation_number = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    response = models.TextField(blank=True, null=True)
    responded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='responded_messages')
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.sender.username} to {self.recipient.username} on {self.created_at}"


# Model for system notices
class Notice(models.Model):
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='notices')

    def __str__(self):
        return f"Notice by {self.created_by} on {self.created_at}"


# Model to track failed login attempts and lockout duration
class LoginAttempt(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    failed_attempts = models.PositiveIntegerField(default=0)
    lockout_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.failed_attempts} failed attempts"


# Track attempts for usernames that don't correspond to a real account
class UnknownLoginAttempt(models.Model):
    username = models.CharField(max_length=150, unique=True)
    failed_attempts = models.PositiveIntegerField(default=0)
    lockout_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.username} - {self.failed_attempts} failed attempts"
