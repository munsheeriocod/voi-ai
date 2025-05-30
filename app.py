import os
from flask import Flask, request, Response, render_template, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from dotenv import load_dotenv
from stt_deepgram import SpeechToText
from tts_elevenlabs import TextToSpeech
from nlp_openai import NLPProcessor
from emotion import EmotionDetector
from twilio_handler import TwilioHandler
import asyncio
import json
from twilio.twiml.voice_response import VoiceResponse, Gather
from urllib.parse import urljoin
import logging
from app.admin import admin_bp
from app.database import init_db, contacts_collection, calls_collection, create_call, update_call_status, find_contact_by_phone
from flasgger import Swagger

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)

# Create Flask app
app = Flask(__name__)

# Configure Swagger
swagger = Swagger(app)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Configure CORS
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

logger = logging.getLogger(__name__)


# Set secret key
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')

# Initialize components
stt = SpeechToText()
tts = TextToSpeech()
nlp = NLPProcessor()
emotion_detector = EmotionDetector()
twilio = TwilioHandler()

# Initialize database
init_db()

# Register blueprints
app.register_blueprint(admin_bp)

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    print('Client connected')
    emit('connection_response', {'data': 'Connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print('Client disconnected')

@socketio.on('audio_data')
async def handle_audio_data(data):
    """Handle incoming audio data from WebSocket"""
    try:
        # Convert base64 audio data to bytes
        audio_bytes = data['audio']
        
        # Transcribe audio
        transcription = await stt.transcribe_audio(audio_bytes)
        if not transcription:
            emit('error', {'message': 'Failed to transcribe audio'})
            return
            
        # Detect emotion
        emotion = emotion_detector.detect_emotion(transcription)
        emotion_intensity = emotion_detector.get_emotion_intensity(transcription)
        
        # Process with NLP
        nlp_response = nlp.process_text(transcription)
        
        # Generate speech response
        audio_response = tts.generate_speech(nlp_response)
        
        # Send response back to client
        emit('assistant_response', {
            'text': nlp_response,
            'emotion': emotion,
            'emotion_intensity': emotion_intensity,
            'audio': audio_response
        })
        
    except Exception as e:
        print(f"Error processing audio data: {str(e)}")
        emit('error', {'message': str(e)})

@app.route("/voice", methods=['GET', 'POST'])
def voice():
    """Handle incoming voice calls"""
    print("Received request to /voice")
    print(f"Request method: {request.method}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Request data: {request.get_data()}")
    
    try:
        response = twilio.create_voice_response("Hello! I'm your voice assistant. How can I help you today?")
        print(f"Generated TwiML response: {response}")
        return Response(response, mimetype='text/xml')
    except Exception as e:
        print(f"Error in voice route: {str(e)}")
        # Create error response
        response = VoiceResponse()
        response.say("I'm sorry, I encountered an error. Please try again.", voice='Polly.Amy')
        return Response(str(response), mimetype='text/xml')

@app.route("/handle-response", methods=['POST'])
def handle_response():
    """Handle speech input and generate response"""
    print("Received request to /handle-response")
    print(f"Speech result: {request.values.get('SpeechResult', '')}")
    
    try:
        # Get speech input from Twilio
        speech_result = request.values.get('SpeechResult', '')
        
        if not speech_result:
            response = VoiceResponse()
            response.say("I didn't catch that. Could you please repeat?", voice='Polly.Amy')
            response.redirect(urljoin(twilio.webhook_base_url, '/voice'))
            return Response(str(response), mimetype='text/xml')
        
        # Process with NLP
        nlp_response = nlp.process_text(speech_result)
        print(f"NLP response: {nlp_response}")
        
        # Create TwiML response with Gather for continuous conversation
        response = VoiceResponse()
        gather = Gather(
            input='speech',
            action=urljoin(twilio.webhook_base_url, '/handle-response'),
            method='POST',
            speech_timeout='2',  # Reduced timeout
            timeout='3',  # Reduced timeout
            language='en-US',
            speech_model='phone_call'
        )
        gather.say(nlp_response, voice='Polly.Amy', rate='1.1')  # Slightly faster speech rate
        response.append(gather)
        
        # If no speech is detected, end the call gracefully
        response.say("I didn't hear anything. Goodbye!", voice='Polly.Amy')
        response.hangup()
        
        return Response(str(response), mimetype='text/xml')
        
    except Exception as e:
        print(f"Error processing response: {str(e)}")
        response = VoiceResponse()
        response.say("I'm sorry, I encountered an error. Please try again.", voice='Polly.Amy')
        return Response(str(response), mimetype='text/xml')

@app.route("/make-call", methods=['POST', 'OPTIONS'])
def make_call():
    """Make an outbound call
    ---
    tags:
      - Calls
    parameters:
      - name: to_number
        in: formData
        type: string
        required: true
        description: The phone number to call.
    responses:
      200:
        description: Call initiated successfully.
        schema:
          type: object
          properties:
            status:
              type: string
            call_sid:
              type: string
      400:
        description: No phone number provided.
        schema:
          type: object
          properties:
            error:
              type: string
      500:
        description: Failed to make call.
        schema:
          type: object
          properties:
            error:
              type: string
    """
    print("Received request to /make-call")
    print(f"Request method: {request.method}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Request data: {request.get_data()}")
    
    if request.method == 'OPTIONS':
        response = Response()
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response
        
    try:
        # Get the phone number from either JSON or form data
        if request.is_json:
            print("Request is JSON")
            to_number = request.json.get('to_number')
        else:
            print("Request is form data")
            to_number = request.form.get('to_number')
            
        print(f"Phone number: {to_number}")
        
        if not to_number:
            return {"error": "No phone number provided"}, 400
        
        # Find the contact in the database
        contact = find_contact_by_phone(to_number)
        # Format the phone number with country code if necessary
        formatted_to_number = to_number
        if contact and 'country' in contact:
            country = contact['country'].upper()
            if country == 'UNITED STATES' and not to_number.startswith('+1'):
                formatted_to_number = '' + to_number
            elif country == 'INDIA' and not to_number.startswith('+91'):
                formatted_to_number = '+91' + to_number

        print(f"Formatted phone number for Twilio: {formatted_to_number}")

        call_sid = twilio.make_call(formatted_to_number)
        
        if call_sid:
            print(f"Twilio call initiated successfully. Call SID: {call_sid}")
            
            # Create an entry in the calls collection
            call_data = {
                'to_number': to_number, # Store the original number
                'call_sid': call_sid,
                'status': 'initiated' # Initial status
                # initiated_at and updated_at are added in create_call
            }
            created_call = create_call(call_data)
            
            if created_call:
                print(f"Call record created in database: {created_call}")
            else:
                print("Failed to create call record in database")

            return {"status": "success", "call_sid": call_sid}, 200
            
        print("Twilio failed to initiate call")
        return {"error": "Failed to make call"}, 500
        
    except Exception as e:
        print(f"Error making call: {str(e)}")
        return {"error": str(e)}, 500

@app.route("/call-status", methods=['GET', 'POST'])
def call_status():
    """Handle call status updates from Twilio
    ---
    tags:
      - Calls
    parameters:
      - name: CallSid
        in: formData
        type: string
        required: true
        description: The unique identifier of the call.
      - name: CallStatus
        in: formData
        type: string
        required: true
        description: The status of the call.
    responses:
      200:
        description: Call status updated successfully.
      400:
        description: Missing CallSid or CallStatus.
      500:
        description: Internal server error.
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        
        # Handle GET request (for testing/verification)
        if request.method == 'GET':
            return jsonify({
                'status': 'ok',
                'message': 'Call status endpoint is working',
                'method': 'GET'
            }), 200
        
        # Log raw request data
        logger.info("Raw request data:")
        logger.info(request.get_data())
        
        # Log all parameters Twilio sends
        logger.info("=== Twilio Callback Parameters ===")
        for key, value in request.values.items():
            logger.info(f"{key}: {value}")
        logger.info("=== End of Parameters ===")
        
        # Get required parameters
        call_sid = request.values.get('CallSid')
        call_status = request.values.get('CallStatus')
        
        logger.info(f"Extracted CallSid: {call_sid}")
        logger.info(f"Extracted CallStatus: {call_status}")
        
        if not call_sid or not call_status:
            logger.warning("Missing CallSid or CallStatus in update")
            return jsonify({
                'error': 'Missing required parameters',
                'received_params': dict(request.values)
            }), 400
            
        # Map Twilio status to our internal status
        status_mapping = {
            'queued': 'queued',
            'ringing': 'ringing',
            'in-progress': 'in-progress',
            'completed': 'completed',
            'busy': 'busy',
            'failed': 'failed',
            'no-answer': 'no-answer',
            'canceled': 'canceled'
        }
        
        mapped_status = status_mapping.get(call_status, call_status)
        logger.info(f"Call {call_sid} status updated from '{call_status}' to '{mapped_status}'")
        
        # Additional data to store with the status update
        additional_data = {
            'duration': request.values.get('CallDuration'),
            'direction': request.values.get('Direction'),
            'answered_by': request.values.get('AnsweredBy'),
            'caller_name': request.values.get('CallerName'),
            'from_number': request.values.get('From'),
            'to_number': request.values.get('To'),
            'parent_call_sid': request.values.get('ParentCallSid'),
            'call_duration': request.values.get('CallDuration'),
            'recording_url': request.values.get('RecordingUrl'),
            'recording_sid': request.values.get('RecordingSid'),
            'error_code': request.values.get('ErrorCode'),
            'error_message': request.values.get('ErrorMessage'),
            'api_version': request.values.get('ApiVersion'),
            'forwarded_from': request.values.get('ForwardedFrom'),
            'call_token': request.values.get('CallToken'),
            'queue_time': request.values.get('QueueTime'),
            'timestamp': request.values.get('Timestamp')
        }
        
        # Clean up None values
        additional_data = {k: v for k, v in additional_data.items() if v is not None}
        logger.info(f"Additional data to store: {additional_data}")
        
        # Update the call record in the database
        logger.info("Attempting to update call status in database...")
        success, result = update_call_status(call_sid, mapped_status, additional_data)
        
        if not success:
            logger.error(f"Failed to update call status: {result}")
            return jsonify({
                'error': 'Failed to update call status',
                'details': str(result)
            }), 500
            
        logger.info(f"Successfully updated call status for SID {call_sid}")
        logger.info(f"Updated call data: {result}")
        logger.info("=== Finished Processing Call Status Update ===")
        
        return jsonify({
            'status': 'success',
            'message': 'Call status updated successfully',
            'call_sid': call_sid,
            'status': mapped_status
        }), 200
        
    except Exception as e:
        logger.error("=== Error in call_status endpoint ===")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error("Full traceback:", exc_info=True)
        logger.error("=== End of Error Log ===")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

if __name__ == "__main__":
    # SSL context configuration
    ssl_context = None
    if os.getenv('FLASK_ENV') == 'production':
        ssl_context = {
            'ssl_version': 'PROTOCOL_TLS',
            'certfile': os.getenv('SSL_CERT_PATH', 'ssl/cert.pem'),
            'keyfile': os.getenv('SSL_KEY_PATH', 'ssl/key.pem')
        }
    
    socketio.run(
        app,
        debug=True,
        port=5001,
        ssl_context=ssl_context,
        host='0.0.0.0'
    )
