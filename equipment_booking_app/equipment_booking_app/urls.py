from django.contrib import admin
from django.urls import path, re_path, include
from automation import views as automation_views

urlpatterns = [
    # non-standard path containing "admin" to obscure the admin panel
    path('admin-b4a939d29b7cda4b/', admin.site.urls),
    # message for common admin URL guesses
    re_path(r'^(?:admin|secure-admin)/?$', automation_views.security_notice),
    path('', include('automation.urls')),
]
