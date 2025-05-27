# Zoom Meeting Integration Application

A Django-based web application for managing and joining Zoom meetings with user and admin roles.

## Features

- User authentication (Admin and Regular Users)
- Zoom meeting scheduling and management
- Real-time meeting joining with passcode protection
- Modern, responsive UI
- Secure meeting access control

## Tech Stack

- Python 3.12
- Django 5.1
- Django Channels for WebSocket support
- Bootstrap 5 for UI
- Zoom Meeting SDK
- PostgreSQL (production)
- Redis for caching and channels

## Setup Instructions

1. Clone the repository:
```bash
git clone <repository-url>
cd zoom-meeting-app
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the root directory with the following variables:
```
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///db.sqlite3
ZOOM_API_KEY=your-zoom-api-key
ZOOM_API_SECRET=your-zoom-api-secret
ZOOM_SDK_KEY=your-zoom-sdk-key
ZOOM_SDK_SECRET=your-zoom-sdk-secret
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Create a superuser:
```bash
python manage.py createsuperuser
```

7. Run the development server:
```bash
python manage.py runserver
```

## Project Structure

```
zoom_meeting_app/
├── apps/
│   ├── accounts/     # User management
│   └── meetings/     # Meeting management
├── static/          # Static files
├── templates/       # Base templates
└── zoom_meeting_app/ # Project settings
```

## Development

- Use `python manage.py runserver` for development
- Use `python manage.py test` to run tests
- Use `python manage.py collectstatic` to collect static files

## Deployment

1. Set DEBUG=False in .env
2. Update ALLOWED_HOSTS in settings.py
3. Configure your production database
4. Run migrations
5. Collect static files
6. Use gunicorn as the production server

## Security Considerations

- All sensitive credentials are stored in environment variables
- Passwords are hashed using Django's built-in password hashers
- CSRF protection enabled
- Session security measures implemented
- Zoom SDK credentials are securely stored

## License

MIT License 