from flask import Blueprint

# Create Blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Import route modules
from .routes import auth, contacts, calls

# The blueprint is now defined here and used in route modules
# No need to expose it via __all__ from here for registration in app.py
