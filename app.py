# D:\iitm_scheduler\app.py
import os
import re
import datetime as dt_module
from datetime import datetime

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pytz
import requests
from dotenv import load_dotenv
from icalendar import Calendar
from recurring_ical_events import of

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'iitm-scheduler-secret-key-2024')

DATABASE_URL = os.environ['DATABASE_URL']  # Supabase Postgres connection string (use the pooler URI)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your dashboard.'

IST = pytz.timezone('Asia/Kolkata')


# ─────────────────────────────────────────
# Models
# ─────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = 'app_user'  # "user" is a reserved word in Postgres — named explicitly to avoid friction

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    subjects = db.relationship('Subject', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    calendar_url = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=False)
    events = db.relationship('Event', backref='subject', lazy=True, cascade='all, delete-orphan')
    last_synced = db.Column(db.DateTime, nullable=True)

    filter_start = db.Column(db.Date, nullable=True)
    filter_end = db.Column(db.Date, nullable=True)


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(256), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=True)          # DTSTART
    end_datetime = db.Column(db.DateTime, nullable=True)  # DTEND
    calendar_title = db.Column(db.String(500), nullable=False)
    drive_link = db.Column(db.Text, nullable=True)
    meet_link = db.Column(db.Text, nullable=True)
    user_description = db.Column(db.Text, nullable=True)
    watched = db.Column(db.Boolean, default=False)
    raw_description = db.Column(db.Text, nullable=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ─────────────────────────────────────────
# Calendar helpers  (unchanged from original)
# ─────────────────────────────────────────

def embed_url_to_ical(url):
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


# ─────────────────────────────────────────
# Google Drive embed helper
# ─────────────────────────────────────────

def extract_drive_file_id(url):
    """Pulls the file ID out of a drive.google.com link, whatever form it's in:
    /file/d/FILE_ID/view, ?id=FILE_ID, /open?id=FILE_ID, etc."""
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
    """Converts a Drive share link into an embeddable /preview iframe URL.
    Returns None if the link isn't a recognizable Drive file link (e.g. it's
    a Docs link, or missing)."""
    file_id = extract_drive_file_id(url)
    if file_id:
        return f"https://drive.google.com/file/d/{file_id}/preview"
    return None


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

    start_naive = start_date
    end_naive = end_date

    try:
        occurrences = of(cal).between(start_naive, end_naive)
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


# ─────────────────────────────────────────
# Auth routes  (self-managed — no confirmation, immediate login on register)
# ─────────────────────────────────────────

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if not email or not password:
            flash('Email and password are required.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
        else:
            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Account created! Add your first subject.', 'success')
            return redirect(url_for('setup'))
    return render_template('auth.html', mode='register')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('auth.html', mode='login')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ─────────────────────────────────────────
# App routes
# ─────────────────────────────────────────

@app.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
    if request.method == 'POST':
        names = request.form.getlist('subject_name')
        urls = request.form.getlist('calendar_url')
        starts = request.form.getlist('filter_start')
        ends = request.form.getlist('filter_end')

        added = 0
        for name, url, start_str, end_str in zip(names, urls, starts, ends):
            name = name.strip()
            url = url.strip()
            if not name or not url:
                continue

            filter_start = None
            filter_end = None
            if start_str:
                try:
                    filter_start = datetime.strptime(start_str, '%Y-%m-%d').date()
                except ValueError:
                    flash(f'Invalid start date for "{name}".', 'error')
                    continue
            if end_str:
                try:
                    filter_end = datetime.strptime(end_str, '%Y-%m-%d').date()
                except ValueError:
                    flash(f'Invalid end date for "{name}".', 'error')
                    continue

            if filter_start and filter_end and filter_start > filter_end:
                flash(f'Start date must be before end date for "{name}".', 'error')
                continue

            subj = Subject(
                name=name,
                calendar_url=url,
                user_id=current_user.id,
                filter_start=filter_start,
                filter_end=filter_end
            )
            db.session.add(subj)
            db.session.flush()
            sync_subject(subj)
            added += 1

        db.session.commit()
        if added:
            flash(f'{added} subject(s) added and synced!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Please add at least one subject with a calendar link.', 'error')
    return render_template('setup.html')


@app.route('/dashboard')
@login_required
def dashboard():
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    if not subjects:
        return redirect(url_for('setup'))

    active_tab = request.args.get('tab', str(subjects[0].id))
    events_by_subject = {}
    for subj in subjects:
        evs = Event.query.filter_by(subject_id=subj.id).order_by(Event.date.asc()).all()
        for ev in evs:
            if ev.end_datetime is not None and ev.end_datetime.tzinfo is None:
                ev.end_datetime = IST.localize(ev.end_datetime)
        events_by_subject[subj.id] = evs

    now = datetime.now(IST)
    return render_template('dashboard.html',
                           subjects=subjects,
                           events_by_subject=events_by_subject,
                           active_tab=active_tab,
                           now=now)


@app.route('/event/<int:event_id>')
@login_required
def event_detail(event_id):
    ev = Event.query.join(Subject).filter(
        Event.id == event_id, Subject.user_id == current_user.id
    ).first_or_404()
    subj = Subject.query.get(ev.subject_id)

    if ev.date is not None and ev.date.tzinfo is None:
        ev.date = IST.localize(ev.date)
    if ev.end_datetime is not None and ev.end_datetime.tzinfo is None:
        ev.end_datetime = IST.localize(ev.end_datetime)

    embed_url = drive_embed_url(ev.drive_link)
    now = datetime.now(IST)

    return render_template('event.html',
                           ev=ev,
                           subject=subj,
                           embed_url=embed_url,
                           now=now)


@app.route('/sync/<int:subject_id>', methods=['POST'])
@login_required
def sync(subject_id):
    subj = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    ok, msg = sync_subject(subj)
    return jsonify({'ok': ok, 'msg': msg})


@app.route('/sync_all', methods=['POST'])
@login_required
def sync_all():
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    results = []
    for subj in subjects:
        ok, msg = sync_subject(subj)
        results.append({'subject': subj.name, 'ok': ok, 'msg': msg})
    return jsonify({'results': results})


@app.route('/event/<int:event_id>/description', methods=['POST'])
@login_required
def update_description(event_id):
    ev = Event.query.join(Subject).filter(
        Event.id == event_id, Subject.user_id == current_user.id
    ).first_or_404()
    ev.user_description = request.json.get('description', '')
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/event/<int:event_id>/watched', methods=['POST'])
@login_required
def toggle_watched(event_id):
    ev = Event.query.join(Subject).filter(
        Event.id == event_id, Subject.user_id == current_user.id
    ).first_or_404()
    ev.watched = not ev.watched
    db.session.commit()
    return jsonify({'ok': True, 'watched': ev.watched})


@app.route('/add_subject', methods=['GET', 'POST'])
@login_required
def add_subject():
    if request.method == 'POST':
        name = request.form.get('subject_name', '').strip()
        url = request.form.get('calendar_url', '').strip()
        start_str = request.form.get('filter_start', '')
        end_str = request.form.get('filter_end', '')

        if not name or not url:
            flash('Both subject name and calendar URL are required.', 'error')
            return render_template('add_subject.html')

        filter_start = None
        filter_end = None
        if start_str:
            try:
                filter_start = datetime.strptime(start_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid start date.', 'error')
                return render_template('add_subject.html')
        if end_str:
            try:
                filter_end = datetime.strptime(end_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid end date.', 'error')
                return render_template('add_subject.html')

        if filter_start and filter_end and filter_start > filter_end:
            flash('Start date must be before end date.', 'error')
            return render_template('add_subject.html')

        subj = Subject(
            name=name,
            calendar_url=url,
            user_id=current_user.id,
            filter_start=filter_start,
            filter_end=filter_end
        )
        db.session.add(subj)
        db.session.flush()
        sync_subject(subj)
        db.session.commit()
        flash(f'Subject "{name}" added!', 'success')
        return redirect(url_for('dashboard', tab=str(subj.id)))
    return render_template('add_subject.html')


@app.route('/delete_subject/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
    subj = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    name = subj.name
    db.session.delete(subj)
    db.session.commit()
    flash(f'Subject "{name}" removed.', 'success')
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=3000)