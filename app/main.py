# D:\iitm_scheduler\app\main.py
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from datetime import datetime
import pytz
from app.extensions import db
from app.models import Subject, Event, DropdownSubject
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
    # Sync dropdown subjects first to ensure we have the latest
    Subject.sync_dropdown_subjects()
    
    # Fetch dropdown subjects for the form
    dropdown_subjects = DropdownSubject.query.order_by(DropdownSubject.name).all()
    
    # Convert to serializable format for JavaScript
    dropdown_subjects_json = [
        {'name': subj.name, 'calendar_url': subj.calendar_url or ''} 
        for subj in dropdown_subjects
    ]
    
    if request.method == 'POST':
        names = request.form.getlist('subject_name')
        urls = request.form.getlist('calendar_url')
        starts = request.form.getlist('filter_start')
        ends = request.form.getlist('filter_end')
        custom_names = request.form.getlist('custom_subject_name')

        added = 0
        for idx, (name, url, start_str, end_str) in enumerate(zip(names, urls, starts, ends)):
            name = name.strip()
            url = url.strip()
            
            # If custom subject is selected, use the custom name
            if name == '__custom__':
                if idx < len(custom_names):
                    custom_name = custom_names[idx].strip()
                    if custom_name:
                        name = custom_name
                    else:
                        flash('Please enter a custom subject name.', 'error')
                        continue
            
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

            # Check if user already has this subject
            existing = Subject.query.filter_by(name=name, user_id=current_user.id).first()
            if existing:
                flash(f'You already have "{name}" in your subjects.', 'warning')
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
        
        # Sync dropdown subjects after adding
        if added > 0:
            Subject.sync_dropdown_subjects()
            # Refresh dropdown subjects for the response
            dropdown_subjects = DropdownSubject.query.order_by(DropdownSubject.name).all()
            dropdown_subjects_json = [
                {'name': subj.name, 'calendar_url': subj.calendar_url or ''} 
                for subj in dropdown_subjects
            ]
            
        if added:
            flash(f'{added} subject(s) added and synced!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Please add at least one subject with a calendar link.', 'error')
    
    return render_template('setup.html', 
                         dropdown_subjects=dropdown_subjects,
                         dropdown_subjects_json=dropdown_subjects_json)

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
    # First, sync dropdown subjects from the subject table
    Subject.sync_dropdown_subjects()
    
    # Fetch dropdown subjects for the form
    dropdown_subjects = DropdownSubject.query.order_by(DropdownSubject.name).all()
    
    # Convert to serializable format for JavaScript
    dropdown_subjects_json = [
        {'name': subj.name, 'calendar_url': subj.calendar_url or ''} 
        for subj in dropdown_subjects
    ]
    
    if request.method == 'POST':
        # Get the subject name - could be from dropdown or custom input
        name = request.form.get('subject_name', '').strip()
        custom_name = request.form.get('custom_subject_name', '').strip()
        url = request.form.get('calendar_url', '').strip()
        start_str = request.form.get('filter_start', '')
        end_str = request.form.get('filter_end', '')
        
        # If custom name is provided, use it instead
        if name == '__custom__' and custom_name:
            name = custom_name
        
        if not name or not url:
            flash('Both subject name and calendar URL are required.', 'error')
            return render_template('add_subject.html', 
                                 dropdown_subjects=dropdown_subjects,
                                 dropdown_subjects_json=dropdown_subjects_json)

        # Check if user already has this subject
        existing = Subject.query.filter_by(name=name, user_id=current_user.id).first()
        if existing:
            flash(f'You already have "{name}" in your subjects.', 'warning')
            return render_template('add_subject.html', 
                                 dropdown_subjects=dropdown_subjects,
                                 dropdown_subjects_json=dropdown_subjects_json)

        filter_start = None
        filter_end = None
        if start_str:
            try:
                filter_start = datetime.strptime(start_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid start date.', 'error')
                return render_template('add_subject.html', 
                                     dropdown_subjects=dropdown_subjects,
                                     dropdown_subjects_json=dropdown_subjects_json)
        if end_str:
            try:
                filter_end = datetime.strptime(end_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid end date.', 'error')
                return render_template('add_subject.html', 
                                     dropdown_subjects=dropdown_subjects,
                                     dropdown_subjects_json=dropdown_subjects_json)

        if filter_start and filter_end and filter_start > filter_end:
            flash('Start date must be before end date.', 'error')
            return render_template('add_subject.html', 
                                 dropdown_subjects=dropdown_subjects,
                                 dropdown_subjects_json=dropdown_subjects_json)

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
        
        # Sync dropdown subjects after adding
        Subject.sync_dropdown_subjects()
        
        flash(f'Subject "{name}" added!', 'success')
        return redirect(url_for('main.dashboard', tab=str(subj.id)))
    
    return render_template('add_subject.html', 
                         dropdown_subjects=dropdown_subjects,
                         dropdown_subjects_json=dropdown_subjects_json)

@main_bp.route('/get_subject_url/<subject_name>', methods=['GET'])
@login_required
def get_subject_url(subject_name):
    """API endpoint to get calendar URL for a dropdown subject"""
    dropdown_subj = DropdownSubject.query.filter_by(name=subject_name).first()
    if dropdown_subj and dropdown_subj.calendar_url:
        return jsonify({
            'found': True,
            'calendar_url': dropdown_subj.calendar_url
        })
    return jsonify({
        'found': False,
        'message': 'Calendar URL not available for this subject'
    })

@main_bp.route('/sync_dropdown_subjects', methods=['POST'])
@login_required
def sync_dropdown_subjects():
    """Manual sync endpoint to update dropdown subjects from the subject table"""
    try:
        count = Subject.sync_dropdown_subjects()
        
        # Return the list of dropdown subjects for debugging
        dropdown_list = DropdownSubject.query.order_by(DropdownSubject.name).all()
        
        return jsonify({
            'ok': True,
            'message': f'Synced {count} subjects to dropdown',
            'count': count,
            'total': len(dropdown_list),
            'subjects': [{'name': s.name, 'url': s.calendar_url[:50] + '...' if s.calendar_url else None} for s in dropdown_list]
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@main_bp.route('/delete_subject/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
    subj = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    name = subj.name
    db.session.delete(subj)
    db.session.commit()
    
    # Sync dropdown subjects after deletion (to remove if no other users have it)
    Subject.sync_dropdown_subjects()
    
    flash(f'Subject "{name}" removed.', 'success')
    return redirect(url_for('main.dashboard'))