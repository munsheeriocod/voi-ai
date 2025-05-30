import os
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta
import logging
import csv
import io
from functools import wraps
from .utils.auth import token_required, verify_credentials, generate_token
from .utils.validators import validate_csv_headers, REQUIRED_HEADERS, get_header_mapping
from .utils.date_utils import parse_date
from ..database import get_contact_by_phone, create_contact, update_contact
from .utils.csv_processor import CSVProcessor
from .utils.contact_processor import ContactProcessor

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

def validate_csv_headers(headers):
    """Validate CSV headers against required headers"""
    if not headers:
        return False, ["No headers found in CSV file"]
        
    # Convert all headers to lowercase and strip whitespace
    headers = [h.lower().strip() for h in headers]
    
    # Check for duplicate headers
    if len(headers) != len(set(headers)):
        duplicates = [h for h in set(headers) if headers.count(h) > 1]
        return False, [f"Duplicate headers found: {', '.join(duplicates)}"]
    
    # Check for missing required headers
    missing_headers = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing_headers:
        return False, [f"Missing required headers: {', '.join(missing_headers)}"]
    
    # Check for extra headers
    extra_headers = [h for h in headers if h not in REQUIRED_HEADERS]
    if extra_headers:
        return False, [f"Unexpected headers found: {', '.join(extra_headers)}"]
    
    return True, []

@admin_bp.route('/login', methods=['POST'])
def admin_login():
    """Handle admin login"""
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
    """Verify JWT token validity"""
    return jsonify({'message': 'Token is valid!'}), 200

@admin_bp.route('/contacts/import', methods=['POST'])
@token_required
def import_contacts():
    """Handle bulk contact import via CSV"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV'}), 400
            
        # Process CSV
        file_content = file.read()
        logger.debug(f"File content length: {len(file_content)}")
        
        csv_processor = CSVProcessor(file_content)
        is_valid, errors, header_map = csv_processor.process_headers()
        
        if not is_valid:
            return jsonify(csv_processor.get_error_response(errors)), 400
            
        # Process contacts
        contact_processor = ContactProcessor()
        row_count = 0
        for row in csv_processor.get_dict_reader():
            row_count += 1
            contact_processor.process_row(row)
            
        return jsonify(contact_processor.get_response()), 200
        
    except Exception as e:
        logger.error(f"CSV import error: {str(e)}")
        return jsonify({'error': str(e)}), 500 