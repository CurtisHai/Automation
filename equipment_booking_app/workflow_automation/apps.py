from django.apps import AppConfig


class WorkflowAutomationConfig(AppConfig):
    """Configuration for the workflow automation app."""

    default_auto_field = "django.db.models.BigAutoField"

    # Keep the historical app label 'bookings' so existing migrations work
    label = "bookings"

    # Updated Python path for the app
    name = "workflow_automation"
