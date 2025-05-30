from flask import request, jsonify, send_file
import logging
import csv
import io
from ..utils.csv_processor import CSVProcessor
from ..utils.contact_processor import ContactProcessor
from ...database import get_contact_by_phone, create_contact, update_contact
from . import admin_bp
from .auth import token_required

# Configure logging
logger = logging.getLogger(__name__)

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

@admin_bp.route('/contacts/template', methods=['GET'])
@token_required
def download_template():
    """Download a sample CSV template for contact import"""
    try:
        # Create a StringIO object to write the CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            'Name',
            'Email',
            'Phone',
            'Country',
            'User Type',
            'Plan',
            'Registration Status',
            'Customer Care',
            'Opt-out Ratio % (Last 30 Days)',
            'Last Logged In At',
            'Last Recharged At'
        ])
        
        # Write sample data
        writer.writerow([
            'John Doe',
            'john@example.com',
            '+1234567890',
            'USA',
            'Premium',
            'Monthly',
            'Active',
            'Catherine',
            '2.5',
            '2024-03-20 10:00:00',
            '2024-03-19 15:30:00'
        ])
        
        # Create the response
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='contact_import_template.csv'
        )
        
    except Exception as e:
        logger.error(f"Error generating template: {str(e)}")
        return jsonify({'error': str(e)}), 500 