from flask import request, jsonify, send_file
import logging
import csv
import io
from ..utils.csv_processor import CSVProcessor
from ..utils.contact_processor import ContactProcessor
from ...database import get_contact_by_phone, create_contact, update_contact, get_all_contacts, get_dashboard_metrics, calls_collection, get_contact_by_id, update_contact_by_id, delete_contact_by_id
from .. import admin_bp
from .auth import token_required

# Configure logging
logger = logging.getLogger(__name__)

@admin_bp.route('/contacts', methods=['POST'])
@token_required
def create_contact_route():
    """Create a new contact
    ---
    tags:
      - Contacts
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
              description: Name of the contact.
            email:
              type: string
              description: Email address of the contact.
            phone_number:
              type: string
              description: Phone number of the contact (required).
            country:
              type: string
              description: Country of the contact.
            user_type:
              type: string
              description: Type of user (e.g., Premium, Standard).
            plan:
              type: string
              description: User's plan (e.g., Monthly, Annual).
            registration_status:
              type: string
              description: Registration status.
            customer_care:
              type: string
              description: Customer care status.
            opt_out_ratio:
              type: number
              format: float
              description: Opt-out ratio.
            last_logged_in:
              type: string
              format: date-time
              description: Last logged in timestamp.
            last_recharged:
              type: string
              format: date-time
              description: Last recharged timestamp.
            # Add any other relevant fields here
    responses:
      201:
        description: Contact created successfully.
        schema:
          type: object
          properties:
            _id:
              type: string
            name:
              type: string
            email:
              type: string
            phone_number:
              type: string
            country:
              type: string
            user_type:
              type: string
            plan:
              type: string
            registration_status:
              type: string
            customer_care:
              type: string
            opt_out_ratio:
              type: number
            created_at:
              type: string
              format: date-time
            updated_at:
              type: string
              format: date-time
            last_logged_in:
              type: string
            last_recharged:
              type: string
      400:
        description: Invalid input data.
        schema:
          type: object
          properties:
            error:
              type: string
      409:
        description: Contact with this phone number already exists.
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
        
        contact_data = request.get_json()
        
        if not contact_data:
            return jsonify({'error': 'No input data provided'}), 400
            
        # Call the database function to create the contact
        created_contact = create_contact(contact_data)
        
        if created_contact:
            # Return the created contact data with its ID
            return jsonify(created_contact), 201
        else:
            # If create_contact returned None, it could be due to missing phone or duplicate
            # We need to check the reason and return appropriate error code
            # For simplicity now, we'll assume None means either missing phone or duplicate
            # You might want to refine create_contact to return specific error indicators
            
            # Check if it was a missing phone number (basic check based on previous logic)
            if not contact_data.get('phone_number'):
                 return jsonify({'error': 'phone_number is required'}), 400
                 
            # Otherwise, assume it's a duplicate (based on unique index)
            return jsonify({'error': 'Contact with this phone number already exists'}), 409
            
    except Exception as e:
        logger.error(f"Error creating contact via API: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/contacts/import', methods=['POST'])
@token_required
def import_contacts():
    """Handle bulk contact import via CSV
    ---
    tags:
      - Contacts
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: CSV file to import contacts.
    responses:
      200:
        description: Import completed successfully.
        schema:
          type: object
          properties:
            message:
              type: string
            total_contacts:
              type: integer
            contacts_created:
              type: integer
            contacts_updated:
              type: integer
            rows_skipped:
              type: integer
            duplicates_found:
              type: integer
            errors:
              type: array
              items:
                type: object
                properties:
                  row:
                    type: integer
                  error:
                    type: string
            skipped_rows:
              type: array
              items:
                type: object
                properties:
                  row:
                    type: integer
                  reason:
                    type: string
            duplicate_rows:
              type: array
              items:
                type: object
                properties:
                  row:
                    type: integer
                  phone:
                    type: string
      400:
        description: Invalid request or CSV file.
        schema:
          type: object
          properties:
            error:
              type: string
            header_errors:
              type: array
              items:
                type: string
            expected_headers:
              type: array
              items:
                type: string
            received_headers:
              type: array
              items:
                type: string
            normalized_headers:
              type: array
              items:
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
    """Download a sample CSV template for contact import
    ---
    tags:
      - Contacts
    responses:
      200:
        description: CSV template file.
        content:
          text/csv:
            schema:
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

@admin_bp.route('/contacts/<contact_id>', methods=['GET'])
@token_required
def get_contact(contact_id):
    """Get details of a single contact by ID
    ---
    tags:
      - Contacts
    parameters:
      - name: contact_id
        in: path
        type: string
        required: true
        description: ID of the contact to retrieve.
    responses:
      200:
        description: Contact details.
        schema:
          type: object
          properties:
            _id:
              type: string
            name:
              type: string
            email:
              type: string
            phone_number:
              type: string
            country:
              type: string
            user_type:
              type: string
            plan:
              type: string
            registration_status:
              type: string
            customer_care:
              type: string
            opt_out_ratio:
              type: number
            created_at:
              type: string
              format: date-time
            updated_at:
              type: string
              format: date-time
            last_logged_in:
              type: string
            last_recharged:
              type: string
            # Include other potential fields
      404:
        description: Contact not found.
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
        logger.info(f"Fetching contact with ID: {contact_id}")
        contact = get_contact_by_id(contact_id)
        
        if contact:
            return jsonify(contact), 200
        else:
            return jsonify({'error': 'Contact not found'}), 404
            
    except Exception as e:
        logger.error(f"Error fetching contact by ID: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/contacts', methods=['GET'])
@token_required
def list_contacts():
    """Get a list of all contacts
    ---
    tags:
      - Contacts
    parameters:
      - name: page
        in: query
        type: integer
        description: Page number for pagination.
        default: 1
      - name: per_page
        in: query
        type: integer
        description: Number of items per page.
        default: 10
      - name: sort_by
        in: query
        type: string
        description: Field to sort by.
        default: _id
      - name: sort_order
        in: query
        type: string
        description: Sorting order (asc or desc).
        enum:
          - asc
          - desc
        default: asc
      - name: search
        in: query
        type: string
        description: Search term to filter contacts.
      # TODO: Add other filtering parameters as needed
    responses:
      200:
        description: A list of contacts with pagination metadata.
        schema:
          type: object
          properties:
            contacts:
              type: array
              items:
                type: object
                properties:
                  _id:
                    type: string
                  name:
                    type: string
                  email:
                    type: string
                  phone_number:
                    type: string
                  country:
                    type: string
                  user_type:
                    type: string
                  plan:
                    type: string
                  registration_status:
                    type: string
                  customer_care:
                    type: string
                  opt_out_ratio:
                    type: number
                  created_at:
                    type: string
                    format: date-time
                  updated_at:
                    type: string
                    format: date-time
                  last_logged_in:
                    type: string
                  last_recharged:
                    type: string
            total_count:
              type: integer
            page:
              type: integer
            per_page:
              type: integer
      500:
        description: Internal server error.
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        sort_by = request.args.get('sort_by', '_id')
        sort_order = request.args.get('sort_order', 'asc')
        search = request.args.get('search')
        # TODO: Get filter parameters from request args
        filters = None
        
        contacts, total_count = get_all_contacts(
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
            search=search,
            filters=filters
        )
        
        logger.info(f"Returning {len(contacts)} contacts out of {total_count}")
        return jsonify({
            'contacts': contacts,
            'total_count': total_count,
            'page': page,
            'per_page': per_page
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching contacts: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/dashboard/metrics', methods=['GET'])
@token_required
def dashboard_metrics():
    """Get dashboard metrics"""
    try:
        metrics = get_dashboard_metrics()
        return jsonify(metrics), 200
        
    except Exception as e:
        logger.error(f"Error fetching dashboard metrics: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/contacts/<contact_id>', methods=['PUT'])
@token_required
def update_contact_route(contact_id):
    """Update an existing contact by ID
    ---
    tags:
      - Contacts
    parameters:
      - name: contact_id
        in: path
        type: string
        required: true
        description: ID of the contact to update.
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
              description: Updated name of the contact.
            email:
              type: string
              description: Updated email address of the contact.
            phone_number:
              type: string
              description: Updated phone number of the contact.
            country:
              type: string
              description: Updated country of the contact.
            user_type:
              type: string
              description: Updated type of user.
            plan:
              type: string
              description: Updated user's plan.
            registration_status:
              type: string
              description: Updated registration status.
            customer_care:
              type: string
              description: Updated customer care status.
            opt_out_ratio:
              type: number
              format: float
              description: Updated opt-out ratio.
            last_logged_in:
              type: string
              format: date-time
              description: Updated last logged in timestamp.
            last_recharged:
              type: string
              format: date-time
              description: Updated last recharged timestamp.
            # Include any other fields that can be updated
    responses:
      200:
        description: Contact updated successfully.
        schema:
          type: object
          properties:
            message:
              type: string
      400:
        description: Invalid input data or contact ID format.
        schema:
          type: object
          properties:
            error:
              type: string
      404:
        description: Contact not found.
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
            
        update_data = request.get_json()
        
        if not update_data:
            return jsonify({'error': 'No update data provided'}), 400
        
        # Call the database function to update the contact
        success, error_message = update_contact_by_id(contact_id, update_data)
        
        if success:
            return jsonify({'message': 'Contact updated successfully'}), 200
        else:
            if error_message == "Invalid contact ID format":
                 return jsonify({'error': error_message}), 400
            elif error_message == "Contact not found":
                 return jsonify({'error': error_message}), 404
            else:
                 return jsonify({'error': error_message}), 500
            
    except Exception as e:
        logger.error(f"Error updating contact via API: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/contacts/<contact_id>', methods=['DELETE'])
@token_required
def delete_contact_route(contact_id):
    """Delete a contact by ID
    ---
    tags:
      - Contacts
    parameters:
      - name: contact_id
        in: path
        type: string
        required: true
        description: ID of the contact to delete.
    responses:
      200:
        description: Contact deleted successfully.
        schema:
          type: object
          properties:
            message:
              type: string
      400:
        description: Invalid contact ID format.
        schema:
          type: object
          properties:
            error:
              type: string
      404:
        description: Contact not found.
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
        logger.info(f"Attempting to delete contact with ID: {contact_id}")
        success, error_message = delete_contact_by_id(contact_id)
        
        if success:
            return jsonify({'message': 'Contact deleted successfully'}), 200
        else:
            if error_message == "Invalid contact ID format":
                 return jsonify({'error': error_message}), 400
            elif error_message == "Contact not found":
                 return jsonify({'error': error_message}), 404
            else:
                 return jsonify({'error': error_message}), 500
                 
    except Exception as e:
        logger.error(f"Error deleting contact via API: {str(e)}")
        return jsonify({'error': str(e)}), 500 