from app.extensions import db
from datetime import datetime

class AppUser(db.Model):
    __tablename__ = 'app_user'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.Text, nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=False)
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
    ical_etag = db.Column(db.String(100), nullable=True)   # for caching
    ical_last_modified = db.Column(db.String(100), nullable=True)
    
    events = db.relationship('Event', backref='subject', lazy=True, cascade='all, delete-orphan')

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