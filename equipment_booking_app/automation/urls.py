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
    path('previous-bookings/', views.previous_bookings, name='previous_bookings'),
    path('my-bookings/', views.booking_list, name='my_bookings'),
    path('inbox/', views.inbox, name='inbox'),
    path('manage-notice/', views.manage_notice, name='manage_notice'),
    path('remove_notice/', views.remove_notice, name='remove_notice'),
    path('security-notice/', views.security_notice, name='security_notice'),
    path('workflows/mine/', views.my_workflows, name='my_workflows'),
    path('workflows/shared/', views.shared_workflows, name='shared_workflows'),
    path('workflows/<int:workflow_id>/request-review/', views.request_review, name='request_review'),
    path('workflows/<int:workflow_id>/use/', views.use_shared_workflow, name='use_shared_workflow'),
    path('workflows/', views.workflow_dashboard, name='workflow_dashboard'),
    path('workflows/create/', views.create_workflow, name='create_workflow'),
    path('workflows/run/', views.run_workflow, name='run_workflow'),
    path('workflows/progress/<int:run_id>/', views.workflow_progress, name='workflow_progress'),
]
