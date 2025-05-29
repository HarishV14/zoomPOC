from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class ZoomOAuthToken(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='zoom_token')
    access_token = models.CharField(max_length=500)
    refresh_token = models.CharField(max_length=500)
    expires_in = models.IntegerField()
    token_type = models.CharField(max_length=50, default='bearer')
    scope = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Zoom OAuth Token'
        verbose_name_plural = 'Zoom OAuth Tokens'

    def __str__(self):
        return f"Zoom Token for {self.user.email}"

    @property
    def is_expired(self):
        if not self.expires_in or not self.created_at:
            return True
        expiry_time = self.created_at + timedelta(seconds=self.expires_in)
        return timezone.now() >= expiry_time

    def refresh_access_token(self):
        from .utils import refresh_zoom_token
        try:
            new_token_data = refresh_zoom_token(self.refresh_token)
            self.access_token = new_token_data['access_token']
            self.refresh_token = new_token_data.get('refresh_token', self.refresh_token)
            self.expires_in = new_token_data['expires_in']
            self.created_at = timezone.now()
            self.save()
            return True
        except Exception as e:
            print(f"Error refreshing token: {e}")
            return False

class ZoomMeeting(models.Model):
    MEETING_TYPE_CHOICES = [
        ('manual', 'Manually Created'),
        ('auto', 'Auto Created')
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='zoom_meetings')
    meeting_type = models.CharField(max_length=10, choices=MEETING_TYPE_CHOICES)
    meeting_id = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    host = models.CharField(max_length=255)
    topic = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='scheduled')  
    
    class Meta:
        verbose_name = 'Zoom Meeting'
        verbose_name_plural = 'Zoom Meetings'
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.topic or 'Meeting'} - {self.meeting_id}"

class MeetingParticipant(models.Model):
    meeting = models.ForeignKey(ZoomMeeting, on_delete=models.CASCADE, related_name='participants')
    participant_id = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    join_time = models.DateTimeField()
    leave_time = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(default=0)  # in seconds

    class Meta:
        verbose_name = 'Meeting Participant'
        verbose_name_plural = 'Meeting Participants'
        ordering = ['-join_time']

    def __str__(self):
        return f"{self.name} - {self.meeting.meeting_id}"
