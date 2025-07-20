from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Equipment, Booking, Profile, LoginAttempt, UnknownLoginAttempt

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

# Unregister the default User admin and register the custom one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(Equipment, EquipmentAdmin)
admin.site.register(Booking, BookingAdmin)
admin.site.register(Profile)
admin.site.register(LoginAttempt)
admin.site.register(UnknownLoginAttempt)
