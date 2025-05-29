from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model


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
    
    MEETING_STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('ready', 'Ready to Join'),
        ('in_progress', 'In Progress'),
        ('ended', 'Ended'),
        ('cancelled', 'Cancelled')
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='zoom_meetings')
    meeting_type = models.CharField(max_length=10, choices=MEETING_TYPE_CHOICES)
    meeting_id = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(default=0)  # in minutes
    host = models.CharField(max_length=255)
    topic = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=MEETING_STATUS_CHOICES, default='scheduled')
    is_active = models.BooleanField(default=False)
    last_status_update = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Zoom Meeting'
        verbose_name_plural = 'Zoom Meetings'
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.topic or 'Meeting'} - {self.meeting_id}"

    @property
    def is_host(self):
        """Check if the current user is the host of this meeting"""
        User = get_user_model()
        try:
            return self.user.email == self.host
        except (User.DoesNotExist, AttributeError):
            return False

    def is_host_user(self, user):
        """Check if the given user is the host of this meeting"""
        if not user or not user.email:
            return False
        return user.email.lower() == self.host.lower()

    @property
    def is_startable(self):
        now = timezone.now()
        return (
            (self.status == 'scheduled' and now >= self.start_time) or
            self.status == 'ready'
        ) and not self.is_active

    @property
    def is_joinable(self):
        """Check if the meeting can be joined (for participants)"""
        now = timezone.now()
        return (
            (self.status == 'scheduled' and now >= self.start_time) or
            self.status == 'ready' or
            self.status == 'in_progress'
        )

    @property
    def display_status(self):
        """Get the display status for UI purposes"""
        now = timezone.now()
        if self.status == 'scheduled' and now >= self.start_time:
            return 'ready_to_start'
        return self.status

    @property
    def status_for_host(self):
        """Get the status display for host"""
        if self.status == 'in_progress':
            return 'in_progress'
        elif self.status == 'ended':
            return 'ended'
        elif self.status == 'cancelled':
            return 'cancelled'
        elif self.is_startable:
            return 'ready_to_start'
        return 'scheduled'

    @property
    def status_for_participant(self):
        """Get the status display for participant"""
        if self.status == 'in_progress':
            return 'join'
        elif self.status == 'ended':
            return 'ended'
        elif self.status == 'cancelled':
            return 'cancelled'
        elif self.is_joinable:
            return 'join'
        return 'scheduled'

    def update_status(self, new_status):
        """Update meeting status and related fields"""
        if new_status not in dict(self.MEETING_STATUS_CHOICES):
            raise ValueError(f"Invalid status: {new_status}")

        self.status = new_status
        
        if new_status == 'in_progress':
            self.is_active = True
            if not self.start_time:
                self.start_time = timezone.now()
        elif new_status in ['ended', 'cancelled']:
            self.is_active = False
            if new_status == 'ended':
                self.end_time = timezone.now()
                if self.start_time:
                    self.duration = int((self.end_time - self.start_time).total_seconds() / 60)
        
        self.save()

    def check_and_update_status(self):
        """Check and update meeting status based on current time"""
        now = timezone.now()
        
        if self.status == 'scheduled' and now >= self.start_time:
            # Meeting time has arrived but not started
            self.status = 'ready'
            self.save()
            return
        
        if self.status == 'in_progress':
            # Check if meeting duration has passed
            if self.start_time and self.duration:
                end_time = self.start_time + timedelta(minutes=self.duration)
                if now >= end_time:
                    self.update_status('ended')

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
