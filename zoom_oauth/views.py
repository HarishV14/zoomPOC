from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import datetime
import re
import requests
import pytz

from .utils import ZoomAPI, MeetingHelper
from .models import ZoomOAuthToken, ZoomMeeting
from .forms import ManualMeetingForm, AutoMeetingForm

@login_required
def initiate_zoom_oauth(request):
    """Initiate Zoom OAuth flow"""
    state = "flimix"
    request.session['zoom_oauth_state'] = state
    return redirect(ZoomAPI.get_auth_url(state))

@login_required
def zoom_oauth_callback(request):
    """Handle Zoom OAuth callback"""
    state = request.GET.get('state')
    stored_state = request.session.get('zoom_oauth_state')
    
    if not state or not stored_state or state != stored_state:
        messages.error(request, 'Invalid OAuth state parameter')
        return redirect('home')
    
    request.session.pop('zoom_oauth_state', None)
    code = request.GET.get('code')
    
    if not code:
        messages.error(request, 'Authorization code not received')
        return redirect('home')
    
    try:
        token_data = ZoomAPI.exchange_code_for_token(code)
        ZoomOAuthToken.objects.update_or_create(
            user=request.user,
            defaults={
                'access_token': token_data['access_token'],
                'refresh_token': token_data['refresh_token'],
                'expires_in': token_data['expires_in'],
                'token_type': token_data['token_type'],
                'scope': token_data['scope'],
            }
        )
        messages.success(request, 'Successfully connected to Zoom!')
    except Exception as e:
        messages.error(request, f'Error connecting to Zoom: {str(e)}')
    
    return redirect('home')

@login_required
def disconnect_zoom(request):
    """Disconnect Zoom account"""
    try:
        ZoomOAuthToken.objects.filter(user=request.user).delete()
        messages.success(request, 'Successfully disconnected from Zoom')
    except Exception as e:
        messages.error(request, f'Error disconnecting from Zoom: {str(e)}')
    return redirect('home')

@login_required
def zoom_status(request):
    return render(request, "zoom_oauth/zoom_status.html")

@login_required
def meeting_list(request):
    """List all meetings"""
    meetings = ZoomMeeting.objects.all().order_by('-start_time')
    upcoming_meetings = []
    completed_meetings = []

    for meeting in meetings:
        meeting.check_and_update_status()
        meeting.is_host_for_current_user = meeting.is_host_user(request.user)
        if meeting.status in ['scheduled', 'ready', 'in_progress']:
            upcoming_meetings.append(meeting)
        elif meeting.status in ['ended', 'cancelled']:
            completed_meetings.append(meeting)

    return render(request, 'zoom_oauth/meeting_list.html', {
        'upcoming_meetings': upcoming_meetings,
        'completed_meetings': completed_meetings,
        'user': request.user,
    })

@login_required
def meeting_detail(request, meeting_id):
    meeting = get_object_or_404(ZoomMeeting, id=meeting_id)
    meeting.check_and_update_status()
    
    is_host = meeting.is_host_user(request.user)
    participants = meeting.participants.all() if hasattr(meeting, 'participants') else []
    return render(request, 'zoom_oauth/meeting_detail.html', {
        'meeting': meeting,
        'participants': participants,
        'is_host': is_host,
        'meeting_status': meeting.status_for_host if is_host else meeting.status_for_participant
    })

@login_required
def create_meeting(request):
    """Create a new meeting"""
    if not hasattr(request.user, 'zoom_token'):
        messages.warning(request, 'Please connect your Zoom account first')
        return redirect('zoom_oauth:initiate')
        
    if request.method == 'POST':
        meeting_type = request.POST.get('meeting_type')
        
        try:
            if meeting_type == 'manual':
                return _handle_manual_meeting(request)
            else:
                return _handle_auto_meeting(request)
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error creating meeting: {str(e)}')
        return redirect('zoom_oauth:create_meeting')
            
    return render(request, 'zoom_oauth/create_meeting.html', {
        'manual_form': ManualMeetingForm(),
        'auto_form': AutoMeetingForm()
    })

def _handle_manual_meeting(request):
    form = ManualMeetingForm(request.POST)
    if not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
        return redirect('zoom_oauth:create_meeting')

    try:
        # Get meeting details from Zoom
        zoom_meeting = ZoomAPI.get_meeting(
            request.user.zoom_token.access_token,
            form.cleaned_data['meeting_id']
        )
        
        # Parse meeting time and determine status
        meeting_type = zoom_meeting.get('type', 1)
        time_field = 'start_time' if meeting_type == 2 else 'created_at'
        start_time = MeetingHelper.parse_zoom_time(zoom_meeting.get(time_field))
        
        if not start_time:
            raise ValueError('Meeting time not found in Zoom')
            
        status = MeetingHelper.determine_meeting_status(
            meeting_type,
            zoom_meeting.get('status', ''),
            start_time
        )
        
        # Create meeting
        meeting = ZoomMeeting.objects.create(
            user=request.user,
            meeting_type='manual',
            meeting_id=form.cleaned_data['meeting_id'],
            password=form.cleaned_data['password'],
            start_time=start_time,
            host=form.cleaned_data['host'],
            topic=form.cleaned_data.get('topic', zoom_meeting.get('topic', '')),
            duration=MeetingHelper.get_meeting_duration(zoom_meeting),
            status=status,
        )
        
        messages.success(request, 'Meeting created successfully')
        return redirect('zoom_oauth:meeting_detail', meeting_id=meeting.id)
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise ValueError('Meeting not found in Zoom. Please check the Meeting ID.')
        elif e.response.status_code == 401:
            raise ValueError('Unable to access Zoom. Please reconnect your Zoom account.')
        raise ValueError(f'Error accessing Zoom: {str(e)}')

def _handle_auto_meeting(request):
    form = AutoMeetingForm(request.POST)
    if not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
        return redirect('zoom_oauth:create_meeting')

    # Determine start time based on schedule type
    schedule_type = form.cleaned_data['schedule_type']
    start_time = timezone.now() if schedule_type == 'now' else form.cleaned_data['start_time']
    
    if schedule_type == 'later' and not start_time:
        raise ValueError('Start time is required for scheduled meetings')

    # Prepare meeting data
    meeting_data = {
        'topic': form.cleaned_data['topic'],
        'start_time': start_time.isoformat(),
        'type': 2,
        'settings': {
            'host_video': True,
            'participant_video': True,
            'join_before_host': False,
            'mute_upon_entry': True,
            'waiting_room': True
        }
    }
    
    try:
        # Create meeting in Zoom
        zoom_response = ZoomAPI.create_meeting(
            request.user.zoom_token.access_token,
            meeting_data
        )
        
        # Create meeting in database
        status = 'ready' if schedule_type == 'now' else 'scheduled'
        meeting = ZoomMeeting.objects.create(
            user=request.user,
            meeting_type='auto',
            meeting_id=zoom_response['id'],
            password=zoom_response['password'],
            start_time=start_time,
            host=zoom_response['host_email'],
            topic=zoom_response['topic'],
            status=status,
        )
        
        messages.success(request, 'Meeting created successfully')
        if status == 'ready':
            return redirect('zoom_oauth:start_meeting', meeting_id=meeting.id)
        return redirect('zoom_oauth:meeting_detail', meeting_id=meeting.id)
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise ValueError('Unable to access Zoom. Please reconnect your Zoom account.')
        raise ValueError(f'Error creating meeting in Zoom: {str(e)}')

@login_required
def start_meeting(request, meeting_id):
    """Start a meeting"""
    meeting = get_object_or_404(ZoomMeeting, id=meeting_id)
    
    if not meeting.is_host_user(request.user):
        messages.error(request, 'Only the host can start the meeting')
        return redirect('zoom_oauth:meeting_detail', meeting_id=meeting.id)
    
    if not meeting.is_startable:
        messages.error(request, 'This meeting cannot be started at this time')
        return redirect('zoom_oauth:meeting_detail', meeting_id=meeting.id)
    
    meeting.update_status('in_progress')
    signature = ZoomAPI.generate_signature(meeting.meeting_id, role=1)
    
    return render(request, 'zoom_oauth/zoom_sdk_host.html', {
        'meeting': meeting,
        'signature': signature,
        'ZOOM_SDK_KEY': settings.ZOOM_CLIENT_ID,
    })

@login_required
def join_meeting(request, meeting_id):
    """Join a meeting"""
    meeting = get_object_or_404(ZoomMeeting, meeting_id=meeting_id)
    meeting.check_and_update_status()
    
    if not meeting.is_joinable:
        messages.error(request, 'This meeting cannot be joined at this time')
        return redirect('zoom_oauth:meeting_detail', meeting_id=meeting.id)
    
    is_host = meeting.is_host_user(request.user)
    passcode = request.GET.get('passcode')
    signature = ZoomAPI.generate_signature(meeting.meeting_id, role=1 if is_host else 0)
    
    template = 'zoom_oauth/zoom_sdk_host.html' if is_host else 'zoom_oauth/zoom_sdk_join.html'
    return render(request, template, {
        'meeting': meeting,
        'passcode': passcode,
        'signature': signature,
        'ZOOM_SDK_KEY': settings.ZOOM_CLIENT_ID,
    })

@login_required
@require_POST
def update_meeting_status(request, meeting_id):
    """Update meeting status"""
    meeting = get_object_or_404(ZoomMeeting, id=meeting_id)
    
    if not meeting.is_host_user(request.user):
        return JsonResponse({'error': 'Only the host can update meeting status'}, status=403)
    
    new_status = request.POST.get('status')
    if new_status not in dict(ZoomMeeting.MEETING_STATUS_CHOICES):
        return JsonResponse({'error': 'Invalid status'}, status=400)
    
    try:
        meeting.update_status(new_status)
        return JsonResponse({
            'status': 'success',
            'meeting_status': meeting.status_for_host,
            'is_active': meeting.is_active,
            'is_startable': meeting.is_startable,
            'is_joinable': meeting.is_joinable
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
