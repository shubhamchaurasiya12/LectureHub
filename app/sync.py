# D:\iitm_scheduler\app\sync.py
import re
import time
import requests
import datetime as dt_module
from datetime import datetime
from icalendar import Calendar
from recurring_ical_events import of
from sqlalchemy.orm.attributes import flag_modified          # ← Fix Bug 4
from app.extensions import db
from app.models import Subject, Event
from app.utils import embed_url_to_ical, extract_links, to_datetime, extract_calendar_id

import pytz
IST = pytz.timezone('Asia/Kolkata')


# ── Google Calendar API helpers ──────────────────────────────────────────────

def _build_calendar_service(user):
    from app.config import Config
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import google_auth_httplib2
    import httplib2

    tokens = user.google_tokens
    if not tokens:
        return None

    # Fix Bug 3 — parse and restore expiry so creds.expired works correctly
    expiry = None
    if tokens.get('expiry'):
        try:
            expiry = datetime.fromisoformat(tokens['expiry'])
        except Exception:
            pass

    creds = Credentials(
        token=tokens.get('token'),
        refresh_token=tokens.get('refresh_token'),
        token_uri=tokens.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=tokens.get('client_id', Config.GOOGLE_CLIENT_ID),
        client_secret=tokens.get('client_secret', Config.GOOGLE_CLIENT_SECRET),
        scopes=tokens.get('scopes', []),
        expiry=expiry                                        # ← Fix Bug 3
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Fix Bug 2 + Bug 4 — store expiry and force SQLAlchemy to detect change
            user.google_tokens = {
                **tokens,
                'token': creds.token,
                'expiry': creds.expiry.isoformat() if creds.expiry else None
            }
            flag_modified(user, 'google_tokens')            # ← Fix Bug 4
            db.session.commit()
        except Exception as e:
            print(f"[sync] Token refresh failed: {e}")
            return None

    try:
        # Fix — use httplib2 with explicit timeout + cache_discovery=False
        # avoids fetching discovery doc on every call (the Windows timeout culprit)
        http = httplib2.Http(timeout=30)
        authed_http = google_auth_httplib2.AuthorizedHttp(creds, http=http)
        return build('calendar', 'v3', http=authed_http, cache_discovery=False)
    except Exception as e:
        print(f"[sync] Could not build calendar service: {e}")
        return None


def _parse_api_datetime(dt_str):
    if not dt_str:
        return None
    try:
        if 'T' in dt_str:
            val = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return val.astimezone(IST)
        else:
            val = datetime.strptime(dt_str, '%Y-%m-%d')
            return IST.localize(val)
    except Exception:
        return None


def _sync_via_api(subject, user):
    service = _build_calendar_service(user)
    if not service:
        # None = setup failed → caller falls back to iCal
        return None, "Could not build Google Calendar service"

    calendar_id = extract_calendar_id(subject.calendar_url)
    if not calendar_id:
        # None = setup failed → caller falls back to iCal
        return None, "Could not extract calendar ID from URL"

    print(f"[sync] Using calendar ID: {calendar_id}")

    if subject.filter_start:
        time_min = dt_module.datetime.combine(
            subject.filter_start, dt_module.time.min
        ).isoformat() + 'Z'
    else:
        time_min = '2020-01-01T00:00:00Z'

    if subject.filter_end:
        time_max = dt_module.datetime.combine(
            subject.filter_end, dt_module.time.max
        ).isoformat() + 'Z'
    else:
        time_max = '2030-12-31T23:59:59Z'

    # Retry up to 3 times — handles transient Windows network timeouts
    MAX_RETRIES = 3
    items = []
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime',
                maxResults=2500
            ).execute()
            items = result.get('items', [])
            print(f"[sync] API returned {len(items)} events")
            last_error = None
            break   # success — exit retry loop
        except Exception as e:
            last_error = e
            print(f"[sync] Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)   # wait 2 seconds before retrying

    if last_error is not None:
        # Fix Bug 1 — was None (caused silent fallthrough), now False (surfaces the error)
        return False, f"Calendar API error after {MAX_RETRIES} attempts: {last_error}"  # ← Fix Bug 1

    existing_events = Event.query.filter_by(subject_id=subject.id).all()
    existing = {ev.uid: ev for ev in existing_events}

    count = 0
    for item in items:
        uid = item.get('id', '')
        start = _parse_api_datetime(
            item.get('start', {}).get('dateTime') or item.get('start', {}).get('date')
        )
        end = _parse_api_datetime(
            item.get('end', {}).get('dateTime') or item.get('end', {}).get('date')
        )

        if start is None:
            continue

        occurrence_uid = f"{uid}_{start.isoformat()}"
        title = item.get('summary', 'Untitled')
        raw_desc = item.get('description', '') or ''

        meet_link, drive_link = extract_links(raw_desc)

        if not meet_link:
            meet_link = item.get('hangoutLink')

        if not drive_link:
            for att in item.get('attachments', []):
                file_url = att.get('fileUrl', '')
                if re.search(r'(drive\.google\.com|docs\.google\.com)', file_url):
                    drive_link = file_url
                    break

        if occurrence_uid in existing:
            ev = existing[occurrence_uid]
            ev.calendar_title = title
            ev.date = start
            ev.end_datetime = end
            ev.raw_description = raw_desc
            if drive_link:
                ev.drive_link = drive_link
            if meet_link:
                ev.meet_link = meet_link
        else:
            ev = Event(
                uid=occurrence_uid,
                subject_id=subject.id,
                calendar_title=title,
                date=start,
                end_datetime=end,
                raw_description=raw_desc,
                meet_link=meet_link,
                drive_link=drive_link,
            )
            db.session.add(ev)
        count += 1

    db.session.commit()
    subject.last_synced = datetime.utcnow()
    db.session.commit()
    return True, f"Synced {count} events via Google Calendar API"


def _sync_via_ical(subject):
    ical_url = embed_url_to_ical(subject.calendar_url)
    print(f"[sync] Falling back to iCal: {ical_url}")
    try:
        resp = requests.get(ical_url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return False, str(e)

    try:
        cal = Calendar.from_ical(resp.content)
    except Exception as e:
        return False, f"Could not parse calendar: {e}"

    if subject.filter_start:
        start_date = dt_module.datetime.combine(subject.filter_start, dt_module.time.min)
    else:
        start_date = dt_module.datetime(2020, 1, 1)
    if subject.filter_end:
        end_date = dt_module.datetime.combine(subject.filter_end, dt_module.time.max)
    else:
        end_date = dt_module.datetime(2030, 12, 31)

    try:
        occurrences = of(cal).between(start_date, end_date)
    except Exception as e:
        return False, f"Recurrence expansion failed: {e}"

    existing_events = Event.query.filter_by(subject_id=subject.id).all()
    existing = {ev.uid: ev for ev in existing_events}

    count = 0
    for component in occurrences:
        if component.name != 'VEVENT':
            continue

        ical_uid = str(component.get('UID', ''))
        start = to_datetime(component.get('DTSTART'))
        end = to_datetime(component.get('DTEND'))

        if start is None:
            continue

        occurrence_uid = f"{ical_uid}_{start.isoformat()}"
        title = str(component.get('SUMMARY', 'Untitled'))
        raw_desc = str(component.get('DESCRIPTION', '') or '')

        meet_link, drive_link = extract_links(raw_desc)
        attachments = component.get('ATTACH')
        if attachments and not drive_link:
            if not isinstance(attachments, list):
                attachments = [attachments]
            for att in attachments:
                url = str(att) if isinstance(att, str) else str(att.get('value', ''))
                if re.search(r'(drive\.google\.com|docs\.google\.com|storage\.cloud\.google\.com)', url):
                    drive_link = url
                    break

        if occurrence_uid in existing:
            ev = existing[occurrence_uid]
            ev.calendar_title = title
            ev.date = start
            ev.end_datetime = end
            ev.raw_description = raw_desc
            if drive_link:
                ev.drive_link = drive_link
            if meet_link:
                ev.meet_link = meet_link
        else:
            ev = Event(
                uid=occurrence_uid,
                subject_id=subject.id,
                calendar_title=title,
                date=start,
                end_datetime=end,
                raw_description=raw_desc,
                meet_link=meet_link,
                drive_link=drive_link,
            )
            db.session.add(ev)
        count += 1

    db.session.commit()
    subject.last_synced = datetime.utcnow()
    db.session.commit()
    return True, f"Synced {count} occurrences via iCal"


# ── Public entry point ───────────────────────────────────────────────────────

def sync_subject(subject):
    from app.models import AppUser
    user = AppUser.query.get(subject.user_id)

    if user and user.google_tokens:
        ok, msg = _sync_via_api(subject, user)
        print(f"[sync] API result: ok={ok}, msg={msg}")
        if ok is not None:
            return ok, msg
        # ok is None = setup failed (bad tokens / no calendar ID) → fall back
        print(f"[sync] API setup failed ({msg}), falling back to iCal")

    return _sync_via_ical(subject)