import jwt
import time
import requests
from django.conf import settings

class ZoomAPI:
    BASE_URL = 'https://api.zoom.us/v2'

    @staticmethod
    def generate_sdk_jwt_token(meeting_number: str, role: int = 0) -> str:
        iat = int(time.time())
        exp = iat + 60 * 2  

        payload = {
            "sdkKey": settings.ZOOM_SDK_KEY,
            "mn": meeting_number,
            "role": role,
            "iat": iat,
            "exp": exp,
            "appKey": settings.ZOOM_SDK_KEY,
            "tokenExp": exp,
        }

        token = jwt.encode(payload, settings.ZOOM_SDK_SECRET, algorithm="HS256")
        return token.decode("utf-8") if isinstance(token, bytes) else token

    @classmethod
    def create_meeting(cls, user, topic, start_time, description=''):
        token = user.zoom_token.refresh_token
        print(token,"token")
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'topic': topic,
            'type': 2,  
            'start_time': start_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'timezone': 'UTC',
            'settings': {
                'host_video': True,
                'participant_video': True,
                'join_before_host': False,
                'mute_upon_entry': True,
                'waiting_room': True,
                'meeting_authentication': True
            }
        }
        
        if description:
            data['agenda'] = description

        response = requests.post(
            f'{cls.BASE_URL}/users/{user.email}/meetings',
            headers=headers,
            json=data
        )
        print(response.json(),"response")
        if response.status_code == 201:
            meeting_data = response.json()
            return {
                'zoom_meeting_id': meeting_data['id'],
                'join_url': meeting_data['join_url'],
                'password': meeting_data['password'],
                'zoom_signature': cls.generate_sdk_signature(meeting_data['id'])
            }
        else:
            raise Exception(f"Failed to create Zoom meeting: {response.text}")

    @classmethod
    def get_meeting(cls, meeting_id):
        token = cls.generate_api_jwt_token()  
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'{cls.BASE_URL}/meetings/{meeting_id}',
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get Zoom meeting: {response.text}")