from django import forms
from .models import Meeting

class MeetingForm(forms.ModelForm):
    class Meta:
        model = Meeting
        fields = ['title', 'description', 'start_time', 'participants']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'participants': forms.SelectMultiple(attrs={'class': 'form-select'})
        }

class MeetingJoinForm(forms.Form):
    password = forms.CharField(
        label='Meeting Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True,
        error_messages={
            'required': 'Please enter the meeting password'
        }
    )

    def __init__(self, meeting, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.meeting = meeting

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password:
            raise forms.ValidationError('Please enter the meeting password')
        if password != self.meeting.password:
            raise forms.ValidationError('Invalid meeting password')
        return password 