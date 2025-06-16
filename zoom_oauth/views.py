from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import requests
import json
import hmac
import hashlib
import base64

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
    if request.method == 'POST':
        try:
            return _handle_manual_meeting(request)
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error creating meeting: {str(e)}')
        return redirect('zoom_oauth:create_meeting')
            
    return render(request, 'zoom_oauth/create_meeting.html', {
        'manual_form': ManualMeetingForm(),
    })

def _handle_manual_meeting(request):
    form = ManualMeetingForm(request.POST)
    if not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
        return redirect('zoom_oauth:create_meeting')

    try:
        # Create meeting directly without Zoom API call
        meeting = ZoomMeeting.objects.create(
            user=request.user,
            meeting_type='manual',
            meeting_id=form.cleaned_data['meeting_id'],
            password=form.cleaned_data['password'],
            start_time=form.cleaned_data['start_time'],
            host=form.cleaned_data['host'],
            topic=form.cleaned_data['topic'] or f"Meeting {form.cleaned_data['meeting_id']}",
            duration=60,  # Default duration
            status='scheduled',
        )
        
        messages.success(request, 'Meeting created successfully')
        return redirect('zoom_oauth:meeting_detail', meeting_id=meeting.id)
        
    except Exception as e:
        messages.error(request, f'Error creating meeting: {str(e)}')
        return redirect('zoom_oauth:create_meeting')

@login_required
def start_meeting(request, meeting_id):
    """Start a meeting"""
    # Normalize meeting ID (remove non-numeric characters)
    meeting_id = ''.join(filter(str.isdigit, meeting_id))
    print(meeting_id,"meeting_id")
    meeting = get_object_or_404(ZoomMeeting, meeting_id=meeting_id)
    
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
    # Normalize meeting ID (remove non-numeric characters)
    meeting_id = ''.join(filter(str.isdigit, meeting_id))
    print(meeting_id,"meeting_id")
    meeting = get_object_or_404(ZoomMeeting, meeting_id=meeting_id)
    meeting.check_and_update_status()
    
    if not meeting.is_joinable:
        messages.error(request, 'This meeting cannot be joined at this time')
        return redirect('zoom_oauth:meeting_detail', meeting_id=meeting.id)
    
    is_host = meeting.is_host_user(request.user)
    signature = ZoomAPI.generate_signature(meeting.meeting_id, role=1 if is_host else 0)
    
    template = 'zoom_oauth/zoom_sdk_host.html' if is_host else 'zoom_oauth/zoom_sdk_join.html'
    return render(request, template, {
        'meeting': meeting,
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

def validate_webhook_url(plain_token):
    if not plain_token:
        return None
        
    hash_for_zoom = hmac.new(
        key=settings.ZOOM_WEBHOOK_SECRET_TOKEN.encode('utf-8'),
        msg=plain_token.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    
    return base64.b64encode(hash_for_zoom).decode('utf-8')

def handle_meeting_ended(meeting):
    meeting.update_status('ended')

def handle_participant_joined(meeting, participant_data):
    if not participant_data:
        print("No participant data received")
        return
        
    try:
        participant_id = participant_data.get('id') or participant_data.get('participant_uuid')
        if not participant_id:
            print("No participant identifier found in data:", participant_data)
            return
            
        email = participant_data.get('email')
        
        meeting.participants.create(
            participant_id=participant_id,
            name=participant_data.get('user_name', 'Unknown'),
            email=email,
            join_time=timezone.now()
        )
        print(f"Successfully created participant record for {participant_data.get('user_name')}")
    except Exception as e:
        print(f"Error creating participant record: {str(e)}")
        print("Participant data:", participant_data)
        raise

def handle_participant_left(meeting, participant_data):
    if not participant_data:
        print("No participant data received for left event")
        return
        
    try:
        participant_id = participant_data.get('id') or participant_data.get('participant_uuid')
        if not participant_id:
            print("No participant identifier found in left event data:", participant_data)
            return
            
        try:
            participant = meeting.participants.get(
                participant_id=participant_id,
                leave_time__isnull=True
            )
            participant.leave_time = timezone.now()
            if participant.join_time:
                participant.duration = int((participant.leave_time - participant.join_time).total_seconds())
            participant.save()
            print(f"Successfully updated participant {participant.name} leave time")
        except meeting.participants.model.DoesNotExist:
            print(f"Participant {participant_data.get('user_name')} not found for meeting {meeting.meeting_id}")
    except Exception as e:
        print(f"Error handling participant left event: {str(e)}")
        print("Participant data:", participant_data)
        raise

def handle_meeting_started(meeting):
    meeting.update_status('in_progress')

@csrf_exempt
@require_POST
def zoom_webhook(request):
    try:
        payload = json.loads(request.body)
        event = payload.get('event')
        
        if event == 'endpoint.url_validation':
            plain_token = payload.get('payload', {}).get('plainToken')
            encrypted_token = validate_webhook_url(plain_token)
            if not encrypted_token:
                return JsonResponse({'error': 'Invalid validation request'}, status=400)
                
            return JsonResponse({
                'plainToken': plain_token,
                'encryptedToken': encrypted_token
            })
        
        meeting_id = payload.get('payload', {}).get('object', {}).get('id')
        print("Received webhook event: ", event, " for meeting ", meeting_id)
        if not meeting_id:
            print("Meeting ID not found in payload")
            return JsonResponse({'error': 'Meeting ID not found in payload'}, status=400)
                    
        try:
            meeting = ZoomMeeting.objects.get(meeting_id=meeting_id)
        except ZoomMeeting.DoesNotExist:
            return JsonResponse({'error': 'Meeting not found'}, status=404)
        print("Meeting payload: ", payload)
        if event == 'meeting.ended':
            print("Meeting ended event received")
            handle_meeting_ended(meeting)
        elif event == 'meeting.participant_joined':
            print("Participant joined event received")
            handle_participant_joined(meeting, payload['payload']['object'].get('participant', {}))
        elif event == 'meeting.participant_left':
            print("Participant left event received")
            handle_participant_left(meeting, payload['payload']['object'].get('participant', {}))
        elif event == 'meeting.started':
            print("Meeting started event received")
            handle_meeting_started(meeting)
        elif event == 'meeting.created':
            print("Meeting created event received")
        else:
            print("Unhandled event type: ", event, " for meeting ", meeting_id)
        
        return JsonResponse({'status': 'success'})
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)