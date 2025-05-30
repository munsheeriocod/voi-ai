from flask import request, jsonify
import jwt
import logging
from datetime import datetime, timedelta
from functools import wraps
from ..utils.auth import token_required, verify_credentials, generate_token
import os
from werkzeug.security import generate_password_hash
from .. import admin_bp

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
    """Handle admin login
    ---
    tags:
      - Authentication
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
            password:
              type: string
    responses:
      200:
        description: Login successful, returns JWT token.
        schema:
          type: object
          properties:
            message:
              type: string
            token:
              type: string
      400:
        description: Invalid request body.
        schema:
          type: object
          properties:
            error:
              type: string
      401:
        description: Invalid username or password.
        schema:
          type: object
          properties:
            error:
              type: string
      500:
        description: Internal server error.
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Verify credentials
        if not verify_credentials(username, password):
            return jsonify({'error': 'Invalid username or password'}), 401
        
        # Generate JWT token
        token = generate_token(username)
        
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
    """Verify JWT token validity
    ---
    tags:
      - Authentication
    responses:
      200:
        description: Token is valid.
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: Invalid or missing token.
        schema:
          type: object
          properties:
            message:
              type: string
    """
    return jsonify({'message': 'Token is valid!'}), 200 