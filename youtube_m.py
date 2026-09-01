# run once: python migrate_add_youtube.py
from app import create_app
from app.extensions import db

app = create_app()
with app.app_context():
    db.engine.execute("ALTER TABLE event ADD COLUMN youtube_link TEXT")
    print("Done.")