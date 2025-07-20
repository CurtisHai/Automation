from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('contact/', views.contact, name='contact'),
    path('bookings/', views.booking_list, name='booking_list'),
    path('bookings/edit/<int:booking_id>/', views.edit_booking, name='edit_booking'),
    path('bookings/delete/<int:booking_id>/', views.delete_booking, name='delete_booking'),
    path('accounts/', views.accounts, name='accounts'),  
    path('create-booking/', views.create_booking, name='create_booking'),
    path('respond-message/<int:message_id>/', views.respond_to_message, name='respond_message'),
    path('previous-bookings/', views.previous_bookings, name='previous_bookings'),
    path('my-bookings/', views.booking_list, name='my_bookings'),
    path('admin-messages/', views.admin_messages, name='admin_messages'),
    path('user-messages/', views.user_messages, name='user_messages'),
    path('inbox/', views.inbox, name='inbox'),
    path('message/respond/<int:message_id>/', views.respond_to_message, name='respond_message'),
    path('manage-notice/', views.manage_notice, name='manage_notice'),
    path('remove_notice/', views.remove_notice, name='remove_notice'),
    path('security-notice/', views.security_notice, name='security_notice'),
]
