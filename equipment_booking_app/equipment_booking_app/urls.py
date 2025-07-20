from django.contrib import admin
from django.urls import path, re_path, include
from bookings import views as booking_views

urlpatterns = [
    # non-standard path containing "admin" to obscure the admin panel
    path('admin-b4a939d29b7cda4b/', admin.site.urls),
    # message for common admin URL guesses
    re_path(r'^(?:admin|secure-admin)/?$', booking_views.security_notice),
    path('', include('bookings.urls')),
]
