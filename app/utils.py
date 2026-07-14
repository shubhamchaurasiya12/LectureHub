import re
import datetime as dt_module
import requests
from icalendar import Calendar
from recurring_ical_events import of
import pytz

IST = pytz.timezone('Asia/Kolkata')

def embed_url_to_ical(url):
    # Handle cid= format
    cid_match = re.search(r'[?&]cid=([^&]+)', url)
    if cid_match:
        calendar_id = requests.utils.unquote(cid_match.group(1))
        # Remove any trailing parameters
        calendar_id = calendar_id.split('&')[0]
        return f"https://calendar.google.com/calendar/ical/{calendar_id}/public/basic.ics"
    
    # Existing src= handling
    match = re.search(r'src=([^&]+)', url)
    if match:
        src = requests.utils.unquote(match.group(1))
        ical_url = f"https://calendar.google.com/calendar/ical/{requests.utils.quote(src)}/public/basic.ics"
        return ical_url
    
    if url.endswith('.ics'):
        return url
    return url

def extract_links(text):
    if not text:
        return None, None
    text = str(text)
    meet_link = None
    drive_link = None

    meet_match = re.search(r'(?:href=")?(https?://meet\.google\.com/[^\s>"\'<]+)', text)
    if meet_match:
        meet_link = meet_match.group(1)

    drive_patterns = [
        r'(?:href=")?(https?://drive\.google\.com/[^\s>"\'<]+)',
        r'(?:href=")?(https?://docs\.google\.com/[^\s>"\'<]+)',
        r'(?:href=")?(https?://storage\.cloud\.google\.com/[^\s>"\'<]+)',
    ]
    for pattern in drive_patterns:
        match = re.search(pattern, text)
        if match:
            drive_link = match.group(1)
            break

    return meet_link, drive_link

def extract_attachments(component):
    attachments = []
    attach = component.get('ATTACH')
    if not attach:
        return attachments
    if not isinstance(attach, list):
        attach = [attach]
    for a in attach:
        url = str(a)
        params = getattr(a, 'params', {}) or {}
        attachments.append({
            'url': url,
            'fmt_type': str(params.get('FMTTYPE', '')),
            'title': str(params.get('X-GOOGLE-CALENDAR-CONTENT-TITLE', '')),
        })
    return attachments

def pick_video_link(attachments):
    for att in attachments:
        if 'video' in att['fmt_type'].lower():
            return att['url']
    for att in attachments:
        if 'recording' in att['title'].lower() or 'session' in att['title'].lower():
            return att['url']
    return attachments[0]['url'] if attachments else None

def to_datetime(dt_val):
    if dt_val is None:
        return None
    val = dt_val.dt if hasattr(dt_val, 'dt') else dt_val
    if isinstance(val, dt_module.datetime):
        if val.tzinfo is None:
            val = IST.localize(val)
        else:
            val = val.astimezone(IST)
        return val
    elif isinstance(val, dt_module.date):
        val = dt_module.datetime(val.year, val.month, val.day)
        val = IST.localize(val)
        return val
    return None

def extract_drive_file_id(url):
    if not url:
        return None
    match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    return None

def drive_embed_url(url):
    file_id = extract_drive_file_id(url)
    if file_id:
        return f"https://drive.google.com/file/d/{file_id}/preview"
    return None