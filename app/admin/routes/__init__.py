# This file is now just a package initializer for routes
# The blueprint is defined in app.admin.__init__.py

from flask import Blueprint

# Create Blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Import routes
from . import auth, contacts, calls

__all__ = ['admin_bp'] 