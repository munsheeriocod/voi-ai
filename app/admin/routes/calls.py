from flask import request, jsonify
import logging
from .. import admin_bp # Import admin_bp from parent package
from .auth import token_required
from ...database import calls_collection, get_active_calls, get_call_by_sid # Import necessary database functions
# We'll add functions to fetch call and sentiment data from database.py soon

# Configure logging
logger = logging.getLogger(__name__)

@admin_bp.route('/calls', methods=['GET'])
@token_required
def list_calls():
    """Get a list of calls with pagination, sorting, and filtering
    ---
    tags:
      - Calls
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
      - name: sort_order
        in: query
        type: string
        description: Sorting order (asc or desc).
        enum:
          - asc
          - desc
      - name: search
        in: query
        type: string
        description: Search term to filter calls.
      # TODO: Add other filtering parameters as needed
    responses:
      200:
        description: A list of calls.
        schema:
          type: array
          items:
            type: object
            # TODO: Define the schema for a call object
            properties:
              _id:
                type: string
              # Add other call properties here
      500:
        description: Internal server error.
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        # TODO: Implement pagination, sorting, and filtering based on request arguments
        
        # For now, just fetching all calls
        # This will need a dedicated function in database.py
        # Example placeholder:
        # calls = get_calls_from_db(request.args)
        
        # Placeholder implementation using the imported collection
        calls_cursor = calls_collection.find({}) # Fetch all calls
        calls_list = []
        for call in calls_cursor:
            # Convert ObjectId to string for JSON serialization
            if '_id' in call:
                call['_id'] = str(call['_id'])
            # TODO: Format call data for the response if necessary
            calls_list.append(call)
            
        logger.info(f"Returning {len(calls_list)} calls")
        return jsonify(calls_list), 200
        
    except Exception as e:
        logger.error(f"Error fetching calls: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/analytics/sentiment', methods=['GET'])
@token_required
def call_sentiment_analysis():
    """Get call sentiment analysis data
    ---
    tags:
      - Analytics
    parameters:
      - name: start_date
        in: query
        type: string
        format: date
        description: Start date for filtering sentiment data.
      - name: end_date
        in: query
        type: string
        format: date
        description: End date for filtering sentiment data.
      # TODO: Add other filtering parameters as needed
    responses:
      200:
        description: Call sentiment analysis data.
        schema:
          type: object
          properties:
            positive:
              type: integer
            neutral:
              type: integer
            negative:
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
        # TODO: Implement date filtering based on request arguments
        
        # This will need a dedicated function in database.py to aggregate sentiment
        # Example placeholder:
        # sentiment_data = get_sentiment_data(request.args)
        
        # Placeholder data
        sentiment_data = {
            "positive": 68,
            "neutral": 22,
            "negative": 10
        }
        
        logger.info(f"Returning sentiment data: {sentiment_data}")
        return jsonify(sentiment_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching sentiment data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/calls/active', methods=['GET'])
@token_required
def list_active_calls():
    """Get a list of currently active calls
    ---
    tags:
      - Calls
    responses:
      200:
        description: A list of active calls with customer information.
        schema:
          type: array
          items:
            type: object
            properties:
              _id:
                type: string
              call_sid:
                type: string
              to_number:
                type: string
              status:
                type: string
              initiated_at:
                type: string
                format: date-time
              customer:
                type: object
                properties:
                  contact_id:
                    type: string
                  name:
                    type: string
                  email:
                    type: string
                  user_type:
                    type: string
                  plan:
                    type: string
                  country:
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
        active_calls = get_active_calls()
        logger.info(f"Returning {len(active_calls)} active calls")
        return jsonify(active_calls), 200
        
    except Exception as e:
        logger.error(f"Error fetching active calls: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/calls/<string:call_sid>/recording', methods=['GET'])
@token_required
def get_call_recording(call_sid):
    """Get the recording URL for a specific call
    ---
    tags:
      - Calls
    parameters:
      - name: call_sid
        in: path
        type: string
        required: true
        description: The SID of the call to retrieve the recording for.
    responses:
      200:
        description: The recording URL.
        schema:
          type: object
          properties:
            recording_url:
              type: string
      404:
        description: Call or recording not found.
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
        logger.info(f"Attempting to fetch recording for call SID: {call_sid}")
        
        # Get the call record from the database
        call = get_call_by_sid(call_sid)
        
        if not call:
            logger.warning(f"Call not found for SID: {call_sid}")
            return jsonify({'error': 'Call not found'}), 404
            
        # Check if recording_url exists in the call record
        recording_url = call.get('recording_url') # recording_url is stored as a top-level field
        
        if recording_url:
            logger.info(f"Found recording URL for SID {call_sid}: {recording_url}")
            return jsonify({'recording_url': recording_url}), 200
        else:
            logger.warning(f"Recording URL not found for call SID: {call_sid}")
            return jsonify({'error': 'Recording not found for this call'}), 404
            
    except Exception as e:
        logger.error(f"Error fetching call recording for SID {call_sid}: {str(e)}")
        return jsonify({'error': str(e)}), 500 