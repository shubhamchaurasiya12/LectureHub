# D:\iitm_scheduler\app\models.py
from app.extensions import db
from datetime import datetime

class AppUser(db.Model):
    __tablename__ = 'app_user'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.Text, nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=True)   # nullable — OAuth users have no password
    google_id = db.Column(db.Text, nullable=True, unique=True)    # Google's unique user ID
    google_tokens = db.Column(db.JSON, nullable=True)             # access + refresh tokens
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    subjects = db.relationship('Subject', backref='user', lazy=True, cascade='all, delete-orphan')

class Subject(db.Model):
    __tablename__ = 'subject'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    calendar_url = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id', ondelete='CASCADE'), nullable=False, index=True)
    last_synced = db.Column(db.DateTime, nullable=True)
    filter_start = db.Column(db.Date, nullable=True)
    filter_end = db.Column(db.Date, nullable=True)
    ical_etag = db.Column(db.String(100), nullable=True)
    ical_last_modified = db.Column(db.String(100), nullable=True)
    
    events = db.relationship('Event', backref='subject', lazy=True, cascade='all, delete-orphan')
    
    @staticmethod
    def sync_dropdown_subjects():
        """Sync unique subjects and their calendar URLs to dropdown_subject table"""
        from app.models import DropdownSubject
        
        most_recent = db.session.query(
            Subject.name,
            Subject.calendar_url
        ).filter(
            Subject.id.in_(
                db.session.query(
                    db.func.max(Subject.id)
                ).group_by(Subject.name)
            ),
            Subject.calendar_url.isnot(None),
            Subject.calendar_url != ''
        ).all()
        
        count = 0
        for name, url in most_recent:
            if url and url.strip():
                existing = DropdownSubject.query.filter_by(name=name).first()
                if existing:
                    if existing.calendar_url != url:
                        existing.calendar_url = url
                        existing.updated_at = datetime.utcnow()
                        count += 1
                else:
                    dropdown = DropdownSubject(
                        name=name,
                        calendar_url=url
                    )
                    db.session.add(dropdown)
                    count += 1
        
        db.session.commit()
        return count

class Event(db.Model):
    __tablename__ = 'event'
    
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.Text, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.DateTime, nullable=True)
    end_datetime = db.Column(db.DateTime, nullable=True)
    calendar_title = db.Column(db.Text, nullable=False)
    drive_link = db.Column(db.Text, nullable=True)
    meet_link = db.Column(db.Text, nullable=True)
    user_description = db.Column(db.Text, nullable=True)
    watched = db.Column(db.Boolean, default=False)
    raw_description = db.Column(db.Text, nullable=True)

class DropdownSubject(db.Model):
    __tablename__ = 'dropdown_subject'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    calendar_url = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)