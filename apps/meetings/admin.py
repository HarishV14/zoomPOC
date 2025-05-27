from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Meeting, MeetingParticipant, MeetingRecording

@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('title', 'host', 'start_time', 'end_time', 'is_active')
    readonly_fields = ('meeting_id', 'join_url', 'password', 'created_at', 'updated_at')
    filter_horizontal = ('participants',)
    search_fields = ('title', 'host__email')
    list_filter = ('start_time', 'end_time', 'host')

@admin.register(MeetingParticipant)
class MeetingParticipantAdmin(admin.ModelAdmin):
    list_display = ('meeting', 'user', 'joined_at', 'left_at', 'is_present')
    search_fields = ('meeting__title', 'user__email')
    list_filter = ('is_present',)

@admin.register(MeetingRecording)
class MeetingRecordingAdmin(admin.ModelAdmin):
    list_display = ('meeting', 'recording_id', 'duration', 'file_size', 'created_at')
    search_fields = ('meeting__title', 'recording_id')
    list_filter = ('created_at',)
    readonly_fields = ('recording_id', 'download_url', 'duration', 'file_size') 