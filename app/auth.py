# D:\iitm_scheduler\app\auth.py
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, g
from functools import wraps
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from app.extensions import db
from app.models import AppUser
from app.config import Config

# ---- Google OAuth scopes ----
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/calendar.readonly',
]

# ---- User classes (unchanged) ----
class SimpleUser:
    def __init__(self, id, email):
        self.id = id
        self.email = email
        self.is_authenticated = True

class AnonymousUser:
    id = None
    email = None
    is_authenticated = False

# ---- Proxy for current_user (unchanged) ----
class _CurrentUserProxy:
    def __getattr__(self, item):
        return getattr(g.user, item)

current_user = _CurrentUserProxy()

# ---- Decorator (unchanged) ----
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.user.is_authenticated:
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated

# ---- Helper: build OAuth flow from config ----
def _make_flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": Config.GOOGLE_CLIENT_ID,
                "client_secret": Config.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [Config.GOOGLE_REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        redirect_uri=Config.GOOGLE_REDIRECT_URI,
    )

# ---- Blueprint ----
auth_bp = Blueprint('auth', __name__, url_prefix='/')

@auth_bp.before_app_request
def load_current_user():
    """Load user from session (unchanged)."""
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

# ---- Login page — GET only, just renders Google button ----
@auth_bp.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    # Preserve the destination through the OAuth redirect cycle
    if request.args.get('next'):
        session['next'] = request.args.get('next')
    return render_template('auth.html')

# ---- Step 1: Send user to Google ----
@auth_bp.route('/login/google')
def google_login():
    flow = _make_flow()  # Fixed: was calling make_flow() instead of _make_flow()
    auth_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent',
        include_granted_scopes='true'
    )
    session['oauth_state'] = state
    session['code_verifier'] = flow.code_verifier  # Store PKCE verifier for callback
    return redirect(auth_url)

# ---- Step 2: Google redirects back here ----
@auth_bp.route('/login/google/callback')
def google_callback():
    # Guard: user cancelled or denied access on Google's screen
    if 'error' in request.args:
        flash('Google sign-in was cancelled.', 'error')
        return redirect(url_for('auth.login'))

    # Guard: CSRF — state must match what we stored before redirecting
    if session.get('oauth_state') != request.args.get('state'):
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))

    try:
        # Exchange authorisation code → tokens
        flow = _make_flow()  # Fixed: was calling make_flow() instead of _make_flow()
        flow.fetch_token(
            authorization_response=request.url,
            code_verifier=session.get('code_verifier')  # Pass PKCE verifier
        )
        credentials = flow.credentials
    except Exception:
        flash('Failed to complete Google sign-in. Please try again.', 'error')
        return redirect(url_for('auth.login'))

    # Verify the ID token and extract user info from Google
    id_info = id_token.verify_oauth2_token(
        credentials.id_token,
        google_requests.Request(),
        Config.GOOGLE_CLIENT_ID,
        clock_skew_in_seconds=10,
    )

    google_email = id_info['email'].lower()
    google_id    = id_info['sub']   # stable unique ID — never changes even if email changes

    # Domain check — hard reject anything not @ds.study.iitm.ac.in or @es.study.iitm.ac.in
    domain = google_email.split('@')[-1]
    if domain not in Config.ALLOWED_DOMAINS:
        flash(
            'Only IITM student accounts are allowed '
            '(@ds.study.iitm.ac.in or @es.study.iitm.ac.in).',
            'error'
        )
        return redirect(url_for('auth.login'))

    # Package credentials for Calendar API use later
    tokens = {
        'token':          credentials.token,
        'refresh_token':  credentials.refresh_token,
        'token_uri':      credentials.token_uri,
        'client_id':      credentials.client_id,
        'client_secret':  credentials.client_secret,
        'scopes':         list(credentials.scopes or []),
        'expiry': credentials.expiry.isoformat() if credentials.expiry else None,
    }

    # Find existing user by email OR google_id
    # email match  → existing password-login user being migrated (35 college users)
    # google_id match → returning OAuth user
    user = AppUser.query.filter(
        (AppUser.email == google_email) | (AppUser.google_id == google_id)
    ).first()

    if user:
        # Existing user — attach Google credentials, all their data stays intact
        user.google_id     = google_id
        user.google_tokens = tokens
        user.email         = google_email   # normalise in case casing changed
    else:
        # First-time login — create account (no password)
        user = AppUser(
            email=google_email,
            google_id=google_id,
            google_tokens=tokens,
        )
        db.session.add(user)

    db.session.commit()

    session['user_id'] = user.id
    
    # Clean up OAuth session variables
    session.pop('oauth_state', None)
    session.pop('code_verifier', None)
    
    next_url = session.pop('next', None) or url_for('main.dashboard')
    return redirect(next_url)

# ---- Logout (unchanged) ----
@auth_bp.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('auth.login'))