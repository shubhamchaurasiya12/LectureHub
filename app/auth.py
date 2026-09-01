import jwt
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, g
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models import AppUser
from app.config import Config

# ---- User classes ----
class SimpleUser:
    def __init__(self, id, email):
        self.id = id
        self.email = email
        self.is_authenticated = True

class AnonymousUser:
    id = None
    email = None
    is_authenticated = False

# ---- Proxy for current_user ----
class _CurrentUserProxy:
    def __getattr__(self, item):
        return getattr(g.user, item)

current_user = _CurrentUserProxy()

# ---- Decorator ----
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.user.is_authenticated:
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated

# ---- Blueprint ----
auth_bp = Blueprint('auth', __name__, url_prefix='/')

@auth_bp.before_app_request
def load_current_user():
    """Load user from session (no Supabase Auth)."""
    g.user = AnonymousUser()
    user_id = session.get('user_id')
    if not user_id:
        return

    user = AppUser.query.get(user_id)
    if user:
        g.user = SimpleUser(id=user.id, email=user.email)
    else:
        session.clear()

@auth_bp.app_context_processor
def inject_current_user():
    return {'current_user': g.get('user', AnonymousUser())}

# ---- Auth routes ----
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('auth.html', mode='register')
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth.html', mode='register')

        # Check if user already exists
        existing = AppUser.query.filter_by(email=email).first()
        if existing:
            flash('Email already registered. Please sign in.', 'error')
            return render_template('auth.html', mode='register')

        # Create new user
        hashed_password = generate_password_hash(password)
        user = AppUser(email=email, password_hash=hashed_password)
        db.session.add(user)
        db.session.commit()

        flash('Account created! Please sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth.html', mode='register')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = AppUser.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid email or password.', 'error')
            return render_template('auth.html', mode='login')

        session['user_id'] = user.id
        return redirect(request.args.get('next') or url_for('main.dashboard'))

    return render_template('auth.html', mode='login')

@auth_bp.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('auth.login'))