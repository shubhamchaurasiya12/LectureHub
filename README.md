# IITM Lecture Tracker

A Flask web app for **IIT Madras BS Data Science** students to track live sessions, notes, and recordings from their course calendars.

---

## Features

- **Login / Register** with student email + password (stored locally)
- **First-time setup** — paste multiple Google Calendar links with subject names
- **Dashboard with tabs** — one tab per subject
- **Event table** per subject:
  - Date & time (IST)
  - Calendar title (as-is from the calendar)
  - Your personal notes (editable inline, saved without page reload)
  - Link: Shows **Join Live** (Meet) before the session, switches to **Recording** (Drive) after it's added
  - **Mark as watched** toggle (greyed-out row when done)
- **Sync button** per subject + global **Sync All**
- Calendar auto-upgrades Meet links → Drive links when the calendar updates

---

## Setup

```bash
# 1. Clone / download this folder
cd iitm_scheduler

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Open **http://localhost:5000** in your browser.

---

## Adding a Calendar

The Google Calendar **must be public**. Use the embed URL shared by IITM, e.g.:

```
https://calendar.google.com/calendar/embed?src=c_l87hl0aeb08v7769n2bfb4puoo%40group.calendar.google.com&ctz=Asia%2FKolkata
```

The app converts this automatically to an iCal feed URL for syncing.

---

## How Sync Works

1. The app fetches the iCal feed from Google Calendar.
2. Events are matched by their unique iCal UID — so syncing is safe (no duplicates).
3. If a Drive link appears in the event description after a live session, it replaces the Meet link on your dashboard.
4. Your personal notes and watched status are **never overwritten** by a sync.

---

## File Structure

```
iitm_scheduler/
├── app.py              # Flask app + routes + sync logic
├── requirements.txt
├── README.md
├── iitm_scheduler.db   # SQLite DB (created on first run)
└── templates/
    ├── base.html
    ├── auth.html        # Login + Register
    ├── setup.html       # First-time subject setup
    ├── dashboard.html   # Main dashboard
    └── add_subject.html
```

---

## Production Deployment (optional)

For a permanent deployment (e.g. on a VPS or Railway):

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

Change `SECRET_KEY` in `app.py` to a long random string for production.
