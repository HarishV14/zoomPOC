from django import forms
from django.utils import timezone
from datetime import datetime
import re

class ManualMeetingForm(forms.Form):
    meeting_id = forms.CharField(
        min_length=10,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'pattern': '[0-9]{10,}',
            'title': 'Meeting ID should be at least 10 digits'
        })
    )
    password = forms.CharField(
        min_length=6,
        max_length=10,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    host = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    topic = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    start_time = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }
        )
    )

    def clean_meeting_id(self):
        meeting_id = self.cleaned_data['meeting_id']
        # Remove any non-numeric characters
        meeting_id = ''.join(filter(str.isdigit, meeting_id))
        
        if not meeting_id.isdigit():
            raise forms.ValidationError('Meeting ID must contain only digits')
        
        if len(meeting_id) < 9 or len(meeting_id) > 11:
            raise forms.ValidationError('Meeting ID must be 9-11 digits')
            
        return meeting_id

    def clean_password(self):
        password = self.cleaned_data['password']
        if not re.match(r'^[a-zA-Z0-9@#$%^&+=]{6,10}$', password):
            raise forms.ValidationError('Password must be 6-10 characters and can only contain letters, numbers, and @#$%^&+=')
        return password

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set minimum datetime for start time
        now = timezone.now()
        self.fields['start_time'].widget.attrs['min'] = now.strftime('%Y-%m-%dT%H:%M')

class AutoMeetingForm(forms.Form):
    topic = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    schedule_type = forms.ChoiceField(
        choices=[('now', 'Start Immediately'), ('later', 'Schedule for Later')],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    start_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }
        )
    )

    def clean(self):
        cleaned_data = super().clean()
        schedule_type = cleaned_data.get('schedule_type')
        start_time = cleaned_data.get('start_time')

        if schedule_type == 'later':
            if not start_time:
                raise forms.ValidationError('Start time is required for scheduled meetings')
            if start_time <= timezone.now():
                raise forms.ValidationError('Start time must be in the future')

        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set minimum datetime for start time
        now = timezone.now()
        self.fields['start_time'].widget.attrs['min'] = now.strftime('%Y-%m-%dT%H:%M') 