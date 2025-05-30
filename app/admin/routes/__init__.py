from flask import Blueprint

# Create Blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Import routes
from . import auth, contacts

__all__ = ['admin_bp'] 