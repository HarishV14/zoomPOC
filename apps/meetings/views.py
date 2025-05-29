from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
import json

from .models import Meeting, MeetingParticipant
from .forms import MeetingForm, MeetingJoinForm
from .zoom import ZoomAPI
from django.conf import settings

@login_required
def meeting_list(request):
    if request.user.is_admin:
        meetings = Meeting.objects.all()
    else:
        meetings = Meeting.objects.all()
    
    context = {
        'meetings': meetings,
        'upcoming_meetings': meetings.filter(start_time__gt=timezone.now()),
    }
    return render(request, 'meetings/meeting_list.html', context)

@login_required
def meeting_create(request):
    if not request.user.is_admin:
        raise PermissionDenied
    
    if request.method == 'POST':
        form = MeetingForm(request.POST)
        if form.is_valid():
            try:
                zoom_data = ZoomAPI.create_meeting(
                    user=request.user,
                    topic=form.cleaned_data['title'],
                    start_time=form.cleaned_data['start_time'],
                    description=form.cleaned_data['description']
                )
                
                meeting = form.save(commit=False)
                meeting.host = request.user
                meeting.zoom_meeting_id = zoom_data['zoom_meeting_id']
                meeting.join_url = zoom_data['join_url']
                meeting.password = zoom_data['password']
                meeting.save()
                
                messages.success(request, 'Meeting created successfully')
                return redirect('meeting_list')
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = MeetingForm()
    
    return render(request, 'meetings/meeting_form.html', {'form': form})

@login_required
def meeting_detail(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)
    
    context = {
        'meeting': meeting,
        'is_host': request.user == meeting.host,
    }
    return render(request, 'meetings/meeting_detail.html', context)

@login_required
def meeting_room(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)
    
    if not meeting.participants.filter(id=request.user.id).exists():
        meeting.participants.add(request.user)
    
    context = {
        'meeting': meeting,
        'is_host': request.user == meeting.host,
    }
    return render(request, 'meetings/meeting_room.html', context)

@login_required
@require_POST
def meeting_signature(request, meeting_id):
    try:
        meeting = get_object_or_404(Meeting, zoom_meeting_id=meeting_id)
        data = json.loads(request.body)
        role = data.get('role', 0)
        
        signature = ZoomAPI.generate_sdk_signature(
            meeting_number=meeting_id,
            role=role
        )
        
        return JsonResponse({
            'signature': signature,
            'meetingNumber': meeting_id,
            'sdkKey': settings.ZOOM_SDK_KEY
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=400)
