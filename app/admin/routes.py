import os
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta
import logging
from functools import wraps

# Create Blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Configure logging
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

@admin_bp.route('/login', methods=['POST'])
def admin_login():
    """Handle admin login"""
    try:
        # Log the incoming request
        logger.info("Login request received")
        
        # Check content type
        if not request.is_json:
            logger.warning("Login request is not JSON")
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        logger.debug(f"Parsed JSON data: {data}")
        
        if not data:
            logger.warning("No data in login request")
            return jsonify({'error': 'No data provided'}), 400
        
        username = data.get('username')
        password = data.get('password')
        
        logger.debug(f"Attempting login for username: {username}")
        
        if not username or not password:
            logger.warning("Missing username or password in login request")
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Verify credentials
        if username != ADMIN_USERNAME or not check_password_hash(ADMIN_PASSWORD_HASH, password):
            logger.warning(f"Invalid credentials for username: {username}")
            return jsonify({'error': 'Invalid username or password'}), 401
        
        # Generate JWT token
        token = jwt.encode({
            'username': username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, JWT_SECRET_KEY)
        
        logger.info(f"Login successful for {username}")
        return jsonify({
            'message': 'Login successful',
            'token': token
        }), 200
    
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/verify', methods=['GET'])
@token_required
def verify_token():
    """Verify JWT token validity"""
    # If token_required decorator succeeds, the token is valid
    logger.info("Token verification successful")
    return jsonify({'message': 'Token is valid!'}), 200 