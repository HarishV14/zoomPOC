from django.urls import path
from . import views

app_name = 'zoom_oauth'

urlpatterns = [
    path('meetings/', views.meeting_list, name='meeting_list'),
    path('meetings/create/', views.create_meeting, name='create_meeting'),
    path('meetings/<int:meeting_id>/', views.meeting_detail, name='meeting_detail'),
    path('meetings/<str:meeting_id>/start/', views.start_meeting, name='start_meeting'),
    path('meetings/<str:meeting_id>/join/', views.join_meeting, name='join_meeting'),
    path('meetings/<int:meeting_id>/update-status/', views.update_meeting_status, name='update_meeting_status'),
    path('meetings/<int:meeting_id>/client-status-update/', views.client_meeting_status_update, name='client_meeting_status_update'),
] 