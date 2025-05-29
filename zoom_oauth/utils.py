import requests
import jwt
import time
from django.conf import settings
from django.utils import timezone
from urllib.parse import urlencode
from datetime import datetime
import pytz

class ZoomAPI:
    BASE_URL = "https://api.zoom.us/v2"
    OAUTH_URL = "https://zoom.us/oauth"
    
    @staticmethod
    def get_headers(access_token):
        return {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

    @classmethod
    def get_auth_url(cls, state=None):
        """Generate Zoom OAuth authorization URL"""
        params = {
            "response_type": "code",
            "client_id": settings.ZOOM_CLIENT_ID,
            "redirect_uri": settings.ZOOM_REDIRECT_URI,
            "scope": settings.ZOOM_OAUTH_SCOPES,
        }
        if state:
            params["state"] = state
        return f"{cls.OAUTH_URL}/authorize?{urlencode(params)}"

    @classmethod
    def exchange_code_for_token(cls, code):
        """Exchange authorization code for access token"""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.ZOOM_REDIRECT_URI,
        }
        return cls._make_oauth_request("token", data)

    @classmethod
    def refresh_token(cls, refresh_token):
        """Refresh access token using refresh token"""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        return cls._make_oauth_request("token", data)

    @classmethod
    def _make_oauth_request(cls, endpoint, data):
        """Make OAuth API request"""
        response = requests.post(
            f"{cls.OAUTH_URL}/{endpoint}",
            data=data,
            auth=(settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET)
        )
        response.raise_for_status()
        return response.json()

    @classmethod
    def get_meeting(cls, access_token, meeting_id):
        """Get meeting details from Zoom"""
        response = requests.get(
            f"{cls.BASE_URL}/meetings/{meeting_id}",
            headers=cls.get_headers(access_token)
        )
        response.raise_for_status()
        return response.json()

    @classmethod
    def create_meeting(cls, access_token, meeting_data):
        """Create a new meeting in Zoom"""
        response = requests.post(
            f"{cls.BASE_URL}/users/me/meetings",
            headers=cls.get_headers(access_token),
            json=meeting_data
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def generate_signature(meeting_number, role):
        """Generate JWT signature for Zoom SDK"""
        iat = int(time.time()) - 30
        exp = iat + 60 * 5
        payload = {
            'sdkKey': settings.ZOOM_CLIENT_ID,
            'mn': str(meeting_number),
            'role': role,
            'iat': iat,
            'exp': exp,
            'appKey': settings.ZOOM_CLIENT_ID,
            'tokenExp': exp
        }
        return jwt.encode(payload, settings.ZOOM_CLIENT_SECRET, algorithm='HS256')

class MeetingHelper:
    @staticmethod
    def parse_zoom_time(time_str, timezone_str=None):
        """Parse Zoom time string to datetime with timezone"""
        if not time_str:
            return None
            
        local_tz = pytz.timezone(timezone_str or settings.TIME_ZONE)
        utc_time = datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%SZ')
        utc_time = pytz.UTC.localize(utc_time)
        return utc_time.astimezone(local_tz)

    @staticmethod
    def determine_meeting_status(meeting_type, meeting_status, start_time):
        """Determine meeting status based on type and time"""
        if meeting_status == 'started':
            return 'in_progress'
        if start_time and start_time <= timezone.now():
            return 'ready'
        return 'scheduled'

    @staticmethod
    def get_meeting_duration(zoom_meeting):
        """Get meeting duration with fallback"""
        return zoom_meeting.get('duration', 0)
