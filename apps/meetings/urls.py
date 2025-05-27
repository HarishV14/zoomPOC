from django.urls import path
from . import views

app_name = 'meetings'

urlpatterns = [
    path('', views.meeting_list, name='meeting_list'),
    path('create/', views.meeting_create, name='meeting_create'),
    path('<int:pk>/', views.meeting_detail, name='meeting_detail'),
    path('<int:pk>/room/', views.meeting_room, name='meeting_room'),
    path('<int:pk>/join/', views.meeting_join, name='meeting_join'),
    path('<str:meeting_id>/signature/', views.meeting_signature, name='meeting_signature'),
] 