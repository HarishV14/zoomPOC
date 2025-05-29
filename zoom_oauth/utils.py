import requests
from django.conf import settings
from urllib.parse import urlencode
import time
import jwt

def get_zoom_authorization_url(state=None):
    base_url = "https://zoom.us/oauth/authorize"
    params = {
        "response_type": "code",
        "client_id": settings.ZOOM_CLIENT_ID,
        "redirect_uri": settings.ZOOM_REDIRECT_URI,
        "scope": settings.ZOOM_OAUTH_SCOPES,
    }
    if state:
        params["state"] = state
    return f"{base_url}?{urlencode(params)}"

def exchange_code_for_token(code):
    url = "https://zoom.us/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.ZOOM_REDIRECT_URI,
    }
    response = requests.post(
        url,
        data=data,
        auth=(settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET)
    )
    response.raise_for_status()
    return response.json()

def refresh_zoom_token(refresh_token):
    url = "https://zoom.us/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    response = requests.post(
        url,
        data=data,
        auth=(settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET)
    )
    response.raise_for_status()
    return response.json()

def create_zoom_meeting(access_token, meeting_data):
    url = "https://api.zoom.us/v2/users/me/meetings"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=meeting_data, headers=headers)
    response.raise_for_status()
    return response.json()

def generate_zoom_signature(meeting_number, role):
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
