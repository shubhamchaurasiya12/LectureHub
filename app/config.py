# D:\iitm_scheduler\app\config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'iitm-scheduler-secret-key-2024')
    SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}

    # Supabase — kept until main.py / sync.py / utils.py are checked
    SUPABASE_URL = os.environ['SUPABASE_URL']
    SUPABASE_ANON_KEY = os.environ['SUPABASE_ANON_KEY']
    SUPABASE_JWT_SECRET = os.environ['SUPABASE_JWT_SECRET']

    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ['GOOGLE_CLIENT_ID']
    GOOGLE_CLIENT_SECRET = os.environ['GOOGLE_CLIENT_SECRET']
    GOOGLE_REDIRECT_URI = os.environ.get(
        'GOOGLE_REDIRECT_URI',
        'http://localhost:5000/login/google/callback'
    )

    # Domain restriction — both IITM programme domains
    ALLOWED_DOMAINS = {'ds.study.iitm.ac.in', 'es.study.iitm.ac.in'}