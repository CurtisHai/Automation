from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    Equipment,
    Booking,
    Profile,
    LoginAttempt,
    UnknownLoginAttempt,
    Workflow,
    WorkflowStep,
    WorkflowRun,
)

# Admin interface for Equipment model
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('name',)  
    search_fields = ('name',)

# Admin interface for Booking model
class BookingAdmin(admin.ModelAdmin):
    list_display = ('user', 'equipment', 'start_time', 'end_time')  
    list_filter = ('start_time', 'end_time')
    search_fields = ('user__username', 'equipment__name', 'project_number')

# Inline admin for adding/editing the Profile model from within the User admin
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'profile'

# Custom admin for the User model to include the Profile model
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)


class WorkflowAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "created_by",
        "created_at",
        "is_published",
        "from_shared",
    )
    list_filter = ("is_published", "from_shared", "created_at")
    search_fields = ("name", "description", "created_by__username")


class WorkflowStepAdmin(admin.ModelAdmin):
    list_display = ("workflow", "action", "order")
    list_filter = ("workflow", "action")
    search_fields = ("workflow__name",)


class WorkflowRunAdmin(admin.ModelAdmin):
    list_display = (
        "workflow",
        "user",
        "started_at",
        "completed_at",
        "initials",
        "project_code",
    )
    list_filter = ("workflow", "user", "started_at", "completed_at")
    search_fields = ("workflow__name", "user__username", "project_code", "initials")

# Unregister the default User admin and register the custom one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(Equipment, EquipmentAdmin)
admin.site.register(Booking, BookingAdmin)
admin.site.register(Profile)
admin.site.register(LoginAttempt)
admin.site.register(UnknownLoginAttempt)
admin.site.register(Workflow, WorkflowAdmin)
admin.site.register(WorkflowStep, WorkflowStepAdmin)
admin.site.register(WorkflowRun, WorkflowRunAdmin)
