from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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
    workflow = models.ForeignKey('Workflow', null=True, blank=True, on_delete=models.SET_NULL, related_name='messages')
    is_review_request = models.BooleanField(default=False)
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


# Models for automation workflows
class Workflow(models.Model):
    """A reusable collection of ordered processing steps."""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    qa_video_review = models.BooleanField(
        default=False,
        help_text="Require manual QA review for each video",
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="workflows")
    created_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=False)
    published_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='published_workflows')
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class WorkflowStep(models.Model):
    STEP_CHOICES = [
        ("setup_structure", "Setup Folder Structure"),
        ("convert_360_video", "Convert Media"),
        ("rename", "Rename Files"),
        ("remove_audio", "Remove Audio"),
        ("trim", "Crop Video"),
        ("organize_files", "Place Files in Folders"),
    ]

    workflow = models.ForeignKey(Workflow, related_name="steps", on_delete=models.CASCADE)
    step_type = models.CharField(max_length=50, choices=STEP_CHOICES)
    order = models.PositiveIntegerField()
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.get_step_type_display()} ({self.order})"


class WorkflowRun(models.Model):
    """Represents a single execution of a workflow with user provided inputs."""
    workflow = models.ForeignKey(
        Workflow, related_name="runs", on_delete=models.CASCADE
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    input_path = models.CharField(max_length=255)
    output_path = models.CharField(max_length=255, default="", blank=True)
    project_code = models.CharField(max_length=100, blank=True)
    initials = models.CharField(max_length=20, blank=True)
    pause_between_steps = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    log = models.TextField(blank=True)

    def __str__(self):
        return (
            f"Run of {self.workflow.name} by {self.user.username} on"
            f" {self.started_at:%Y-%m-%d %H:%M}"
        )
