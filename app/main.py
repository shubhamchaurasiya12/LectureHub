# main.py
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from datetime import datetime
import pytz
from app.extensions import db
from app.models import Subject, Event
from app.auth import login_required, current_user
from app.sync import sync_subject
from app.utils import drive_embed_url

main_bp = Blueprint('main', __name__)
IST = pytz.timezone('Asia/Kolkata')

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main_bp.route('/setup', methods=['GET', 'POST'])
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
            return redirect(url_for('main.dashboard'))
        else:
            flash('Please add at least one subject with a calendar link.', 'error')
    return render_template('setup.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    if not subjects:
        return redirect(url_for('main.setup'))

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

@main_bp.route('/event/<int:event_id>')
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

@main_bp.route('/sync/<int:subject_id>', methods=['POST'])
@login_required
def sync(subject_id):
    subj = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    ok, msg = sync_subject(subj)
    return jsonify({'ok': ok, 'msg': msg})

@main_bp.route('/sync_all', methods=['POST'])
@login_required
def sync_all():
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    results = []
    for subj in subjects:
        ok, msg = sync_subject(subj)
        results.append({'subject': subj.name, 'ok': ok, 'msg': msg})
    return jsonify({'results': results})

@main_bp.route('/event/<int:event_id>/description', methods=['POST'])
@login_required
def update_description(event_id):
    ev = Event.query.join(Subject).filter(
        Event.id == event_id, Subject.user_id == current_user.id
    ).first_or_404()
    ev.user_description = request.json.get('description', '')
    db.session.commit()
    return jsonify({'ok': True})

@main_bp.route('/event/<int:event_id>/watched', methods=['POST'])
@login_required
def toggle_watched(event_id):
    ev = Event.query.join(Subject).filter(
        Event.id == event_id, Subject.user_id == current_user.id
    ).first_or_404()
    ev.watched = not ev.watched
    db.session.commit()
    return jsonify({'ok': True, 'watched': ev.watched})

@main_bp.route('/add_subject', methods=['GET', 'POST'])
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
        return redirect(url_for('main.dashboard', tab=str(subj.id)))
    return render_template('add_subject.html')

@main_bp.route('/delete_subject/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
    subj = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    name = subj.name
    db.session.delete(subj)
    db.session.commit()
    flash(f'Subject "{name}" removed.', 'success')
    return redirect(url_for('main.dashboard'))