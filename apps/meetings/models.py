from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

class Meeting(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    # models.py
    end_time = models.DateTimeField(null=True, blank=True)
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hosted_meetings')
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='meetings', blank=True)
    meeting_id = models.CharField(max_length=100, unique=True, blank=True)
    join_url = models.URLField(blank=True)
    password = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    zoom_meeting_id = models.CharField(max_length=100, unique=True, blank=True)

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return self.title

    @property
    def is_active(self):
        now = timezone.now()
        print(self.start_time,now,"start_time")
        return self.start_time <= now

    @property
    def is_upcoming(self):
        return self.start_time > timezone.now()

    @property
    def is_past(self):
        return self.end_time < timezone.now()

    def save(self, *args, **kwargs):
        if not self.meeting_id:
            self.meeting_id = f"meeting_{self.host.id}_{int(timezone.now().timestamp())}"
        if not self.password:
            self.password = f"pass{int(timezone.now().timestamp()) % 10000:04d}"
        super().save(*args, **kwargs)

class MeetingParticipant(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    is_present = models.BooleanField(default=True)

    class Meta:
        unique_together = ['meeting', 'user']
        verbose_name = _('meeting participant')
        verbose_name_plural = _('meeting participants')

    def __str__(self):
        return f"{self.user.email} - {self.meeting.title}"

class MeetingRecording(models.Model):
    meeting = models.ForeignKey(
        Meeting,
        on_delete=models.CASCADE,
        related_name='recordings'
    )
    recording_id = models.CharField(max_length=100, unique=True)
    download_url = models.URLField()
    duration = models.PositiveIntegerField(_('duration in seconds'))
    file_size = models.PositiveBigIntegerField(_('file size in bytes'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('meeting recording')
        verbose_name_plural = _('meeting recordings')

    def __str__(self):
        return f"Recording for {self.meeting.title}" 