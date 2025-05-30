import os
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import logging

logger = logging.getLogger(__name__)

# Admin credentials (in production, this should be in a database)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = generate_password_hash("admin123")
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key')

def token_required(f):
    """Decorator to protect routes that require authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
            if data['username'] != ADMIN_USERNAME:
                return jsonify({'message': 'Invalid token!'}), 401
        except:
            return jsonify({'message': 'Invalid token!'}), 401
        
        return f(*args, **kwargs)
    return decorated

def verify_credentials(username, password):
    """Verify admin credentials"""
    return username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password)

def generate_token(username):
    """Generate JWT token for authenticated user"""
    return jwt.encode({
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, JWT_SECRET_KEY)
