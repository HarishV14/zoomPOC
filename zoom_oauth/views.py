from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.utils import timezone


from .utils import (
    generate_zoom_signature, get_zoom_authorization_url, exchange_code_for_token,
    create_zoom_meeting,
)
from .models import ZoomOAuthToken, ZoomMeeting

@login_required
def initiate_zoom_oauth(request):
    state = "flimix"
    request.session['zoom_oauth_state'] = state
    auth_url = get_zoom_authorization_url(state)
    return redirect(auth_url)

@login_required
def zoom_oauth_callback(request):
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
        token_data = exchange_code_for_token(code)
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
        return redirect('home')
        
    except Exception as e:
        messages.error(request, f'Error connecting to Zoom: {str(e)}')
        return redirect('home')

@login_required
def disconnect_zoom(request):
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
    meetings = ZoomMeeting.objects.all().order_by('-start_time')
    now = timezone.now()
    upcoming_meetings = meetings.filter()
    completed_meetings = meetings.filter(start_time__lt=now)
    return render(request, 'zoom_oauth/meeting_list.html', {
        'upcoming_meetings': upcoming_meetings,
        'completed_meetings': completed_meetings,
        'user': request.user,
    })

@login_required
def meeting_detail(request, meeting_id):
    meeting = get_object_or_404(ZoomMeeting, id=meeting_id)
    is_host = request.user == meeting.user
    participants = meeting.participants.all() if hasattr(meeting, 'participants') else []
    return render(request, 'zoom_oauth/meeting_detail.html', {
        'meeting': meeting,
        'participants': participants,
        'is_host': is_host,
    })

@login_required
def create_meeting(request):
    if not hasattr(request.user, 'zoom_token'):
        messages.warning(request, 'Please connect your Zoom account first')
        return redirect('zoom_oauth:initiate')
        
    if request.method == 'POST':
        meeting_type = request.POST.get('meeting_type')
        
        try:
            if meeting_type == 'manual':
                meeting = ZoomMeeting.objects.create(
                    user=request.user,
                    meeting_type='manual',
                    meeting_id=request.POST.get('meeting_id'),
                    password=request.POST.get('password'),
                    start_time=request.POST.get('start_time'),
                    host=request.POST.get('host'),
                    topic=request.POST.get('topic', '')
                )
                
            else: 
                meeting_data = {
                    'topic': request.POST.get('topic'),
                    'start_time': request.POST.get('start_time'),
                    'duration': int(request.POST.get('duration', 60)),
                    'type': 2,      
                    'settings': {
                        'host_video': True,
                        'participant_video': True,
                        'join_before_host': False,
                        'mute_upon_entry': True,
                        'waiting_room': True
                    }
                }
                
                zoom_response = create_zoom_meeting(
                    request.user.zoom_token.access_token,
                    meeting_data
                )
                
                meeting = ZoomMeeting.objects.create(
                    user=request.user,
                    meeting_type='auto',
                    meeting_id=zoom_response['id'],
                    password=zoom_response['password'],
                    start_time=zoom_response['start_time'],
                    host=zoom_response['host_email'],
                    topic=zoom_response['topic']
                )
                
            messages.success(request, 'Meeting created successfully')
            return redirect('zoom_oauth:meeting_detail', meeting_id=meeting.id)
            
        except Exception as e:
            messages.error(request, f'Error creating meeting: {str(e)}')
            return redirect('zoom_oauth:create_meeting')
            
    return render(request, 'zoom_oauth/create_meeting.html')


@login_required
def start_meeting(request, meeting_id):
    meeting = get_object_or_404(ZoomMeeting, id=meeting_id, user=request.user)
    signature = generate_zoom_signature(meeting.meeting_id, role=1)
    return render(request, 'zoom_oauth/zoom_sdk_host.html', {
        'meeting': meeting,
        'signature': signature,
        'ZOOM_SDK_KEY': settings.ZOOM_CLIENT_ID,
    })

@login_required
def join_meeting(request, meeting_id):
    meeting = get_object_or_404(ZoomMeeting, meeting_id=meeting_id)
    passcode = request.GET.get('passcode')
    signature = generate_zoom_signature(meeting.meeting_id, role=0)
    return render(request, 'zoom_oauth/zoom_sdk_join.html', {
        'meeting': meeting,
        'passcode': passcode,
        'signature': signature,
        'ZOOM_SDK_KEY': settings.ZOOM_CLIENT_ID,
    })
