import re
import requests
import datetime as dt_module
from datetime import datetime
from icalendar import Calendar
from recurring_ical_events import of
from app.extensions import db
from app.models import Subject, Event
from app.utils import embed_url_to_ical, extract_links, to_datetime

def sync_subject(subject):
    ical_url = embed_url_to_ical(subject.calendar_url)
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
    for occurrence in occurrences:
        component = occurrence
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
    return True, f"Synced {count} occurrences"