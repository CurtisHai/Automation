from django.apps import AppConfig


class AutomationConfig(AppConfig):
    """Configuration for the automation app."""

    default_auto_field = "django.db.models.BigAutoField"

    # Keep the historical app label 'bookings' so existing migrations work
    label = "bookings"

    # Updated Python path for the app
    name = "automation"
