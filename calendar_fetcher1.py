import datetime
import os
import pickle
import pytz
from dateutil import parser  

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Define your scope
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_google_calendar_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('calendar', 'v3', credentials=creds)
    return service

def get_google_calendar_events(service, start_time, end_time, email):
    events_result = service.events().list(
        calendarId='primary', timeMin=start_time, timeMax=end_time,
        singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])
    filtered_events = []
    print(f"Retrieved {len(events)} events from Google Calendar.")
    for event in events:
        if 'attendees' in event:
            for attendee in event['attendees']:
                if attendee['email'] == email and attendee['responseStatus'] == 'declined':
                    print(f"Skipping event: {event['summary']} (declined)")
                    break
            else:
                filtered_events.append(event)
        else:
            filtered_events.append(event)
        print(f"Event: {event['summary']}, Start: {event['start']}, End: {event['end']}")
    return filtered_events

def schedule_task(service, summary, description, start_time, end_time):
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'UTC',
        },
    }
    service.events().insert(calendarId='primary', body=event).execute()
    print(f"Scheduled task: {summary} from {start_time} to {end_time}")

def find_free_time_slots(events, duration_minutes, local_tz):
    free_slots = []
    now = datetime.datetime.now(local_tz)
    day_start = '09:00'
    day_end = '17:00'
    current_time = now.replace(hour=int(day_start.split(':')[0]), minute=int(day_start.split(':')[1]), second=0, microsecond=0)
    if current_time < now:
        current_time += datetime.timedelta(days=1)
    end_of_day = current_time.replace(hour=int(day_end.split(':')[0]), minute=int(day_end.split(':')[1]))

    for event in events:
        event_start_str = event['start'].get('dateTime', event['start'].get('date'))
        event_end_str = event['end'].get('dateTime', event['end'].get('date'))

        event_start = parser.isoparse(event_start_str)
        event_end = parser.isoparse(event_end_str)

        print(f"Checking event: Start {event_start}, End {event_end}")

        if current_time + datetime.timedelta(minutes=duration_minutes) <= event_start:
            free_slots.append((current_time.astimezone(pytz.utc).isoformat(), (current_time + datetime.timedelta(minutes=duration_minutes)).astimezone(pytz.utc).isoformat()))
            current_time = event_end
        elif current_time < event_end:
            current_time = event_end

    while current_time + datetime.timedelta(minutes=duration_minutes) <= end_of_day:
        free_slots.append((current_time.astimezone(pytz.utc).isoformat(), (current_time + datetime.timedelta(minutes=duration_minutes)).astimezone(pytz.utc).isoformat()))
        current_time += datetime.timedelta(minutes=duration_minutes)

    print(f"Found {len(free_slots)} free time slots for {duration_minutes}-minute tasks.")
    return free_slots

def check_existing_tasks(service, summary, start_time, end_time):
    events_result = service.events().list(
        calendarId='primary', timeMin=start_time, timeMax=end_time,
        q=summary, singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])
    return len(events) > 0

def main():
    print("Starting the calendar fetcher script...")
    service = get_google_calendar_service()

    # Hardcoded day start and end times
    day_start = '09:00'
    day_end = '17:00'
    time_zone = 'America/New_York'
    local_tz = pytz.timezone(time_zone)
    
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    end_of_week = (datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat() + 'Z'

    user_email = 'maximilian.strey@gmail.com'  # Replace with your email address

    events = get_google_calendar_events(service, now, end_of_week, user_email)
    
    tasks = [
        {"summary": "Task 1", "description": "Description for Task 1", "duration": 60},
        {"summary": "Task 2", "description": "Description for Task 2", "duration": 120},
        # Add more tasks as needed
    ]

    for task in tasks:
        print(f"Scheduling task: {task['summary']}")
        free_slots = find_free_time_slots(events, task["duration"], local_tz)
        if free_slots:
            start_time, end_time = free_slots[0]
            if not check_existing_tasks(service, task["summary"], start_time, end_time):
                schedule_task(service, task["summary"], task["description"], start_time, end_time)
                events.append({'start': {'dateTime': start_time}, 'end': {'dateTime': end_time}})
            else:
                print(f"Task {task['summary']} already scheduled at {start_time}")
        else:
            print(f"No free time slots available for task: {task['summary']}")

if __name__ == '__main__':
    main()
