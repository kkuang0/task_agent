from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from src.utils.logging import logger

load_dotenv()

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """Get an authorized Google Calendar service instance"""
    try:
        creds = None
        credentials_path = os.getenv('GOOGLE_CALENDAR_CREDENTIALS')
        
        logger.debug(f"Looking for credentials file at: {credentials_path}")
        logger.debug(f"Current working directory: {os.getcwd()}")
        
        if not credentials_path:
            logger.warning("GOOGLE_CALENDAR_CREDENTIALS environment variable not set")
            logger.info("Please set GOOGLE_CALENDAR_CREDENTIALS in your .env file to point to your credentials.json file")
            return None
            
        # Try multiple possible locations for the credentials file
        possible_paths = [
            credentials_path,  # Original path
            os.path.join(os.getcwd(), credentials_path),  # Relative to current directory
            os.path.join(os.path.dirname(os.path.abspath(__file__)), credentials_path),  # Relative to this file
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), credentials_path)  # Relative to src directory
        ]
        
        for path in possible_paths:
            logger.debug(f"Trying path: {path}")
            if os.path.exists(path):
                credentials_path = path
                logger.debug(f"Found credentials file at: {credentials_path}")
                break
        else:
            logger.warning(f"Credentials file not found at any of these locations: {possible_paths}")
            logger.info("Please make sure your credentials.json file is in one of these locations:")
            for path in possible_paths:
                logger.info(f"- {path}")
            return None
        
        # The file token.pickle stores the user's access and refresh tokens
        token_path = os.path.join(os.path.dirname(credentials_path), 'token.pickle')
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        logger.error(f"Error initializing calendar service: {str(e)}")
        return None

def create_calendar_event(service, task, start_time, end_time):
    """Create a calendar event for a task"""
    if not service:
        logger.warning("Calendar service not available")
        return None
        
    try:
        event = {
            'summary': task.title,
            'description': task.description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'UTC',
            },
        }
        
        event = service.events().insert(calendarId='primary', body=event).execute()
        return event
    except Exception as e:
        logger.error(f"Error creating calendar event: {str(e)}")
        return None

def update_calendar_event(service, event_id, task, start_time, end_time):
    """Update an existing calendar event"""
    if not service:
        logger.warning("Calendar service not available")
        return None
        
    try:
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
        event['summary'] = task.title
        event['description'] = task.description
        event['start']['dateTime'] = start_time.isoformat()
        event['end']['dateTime'] = end_time.isoformat()
        
        updated_event = service.events().update(
            calendarId='primary',
            eventId=event_id,
            body=event
        ).execute()
        
        return updated_event
    except Exception as e:
        logger.error(f"Error updating calendar event: {str(e)}")
        return None

def delete_calendar_event(service, event_id):
    """Delete a calendar event"""
    if not service:
        logger.warning("Calendar service not available")
        return
        
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
    except Exception as e:
        logger.error(f"Error deleting calendar event: {str(e)}")

def get_calendar_events(service, time_min=None, time_max=None):
    """Get calendar events within a time range"""
    if not service:
        logger.warning("Calendar service not available")
        return []
        
    try:
        if time_min is None:
            time_min = datetime.now(timezone.utc).isoformat() + 'Z'
        if time_max is None:
            time_max = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat() + 'Z'
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])
    except Exception as e:
        logger.error(f"Error fetching calendar events: {str(e)}")
        return [] 