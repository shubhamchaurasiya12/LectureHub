# D:\iitm_scheduler\app\config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'iitm-scheduler-secret-key-2024')
    SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}

    SUPABASE_URL = os.environ['SUPABASE_URL']
    SUPABASE_ANON_KEY = os.environ['SUPABASE_ANON_KEY']
    SUPABASE_JWT_SECRET = os.environ['SUPABASE_JWT_SECRET']