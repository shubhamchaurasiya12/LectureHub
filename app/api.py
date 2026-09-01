# D:\iitm_scheduler\app\api.py
from flask import Blueprint, jsonify
from app.extensions import db
from app.models import DropdownSubject
from app.auth import login_required

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/dropdown-subjects')
@login_required
def get_dropdown_subjects():
    """Fetch all subjects from dropdown_subject table"""
    try:
        subjects = DropdownSubject.query.order_by(DropdownSubject.name).all()
        return jsonify({
            'success': True,
            'subjects': [
                {
                    'id': s.id,
                    'name': s.name,
                    'calendar_url': s.calendar_url
                }
                for s in subjects
            ]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500