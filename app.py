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
from flask.json.provider import DefaultJSONProvider
from bson import ObjectId
from twilio.twiml.voice_response import VoiceResponse, Gather
from urllib.parse import urljoin
import logging
from app.admin import admin_bp
from app.database import init_db, contacts_collection, calls_collection, create_call, update_call_status, find_contact_by_phone
from flasgger import Swagger
import warnings
from pymongo import MongoClient
from twilio.rest import Client
from pdf_processor import PDFProcessor
from werkzeug.utils import secure_filename
from pdf_utils import extract_text_from_pdf, chunk_text
from vector_store import upsert_chunks, query_vector_store
from pdf_to_vector import PDFToVector
from functools import wraps
import time
from voice_call_handler import VoiceCallHandler
from datetime import datetime

# Suppress pymongo warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pymongo')

# Configure logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set pymongo logging to WARNING level to suppress debug messages
logging.getLogger('pymongo').setLevel(logging.WARNING)
logging.getLogger('pymongo.topology').setLevel(logging.WARNING)

# Load environment variables
load_dotenv()

# Create Flask app
class CustomJSONProvider(DefaultJSONProvider):
    def __init__(self, app):
        super().__init__(app)

    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

# After creating your Flask app, set the custom JSON provider
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.json = CustomJSONProvider(app)

# Configure Swagger
swagger = Swagger(app)

# Initialize SocketIO with threading mode
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

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

# Twilio configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
WEBHOOK_BASE_URL = os.getenv('WEBHOOK_BASE_URL')

# Log configuration values (excluding sensitive data)
logger.info(f"TWILIO_PHONE_NUMBER: {TWILIO_PHONE_NUMBER}")
logger.info(f"WEBHOOK_BASE_URL: {WEBHOOK_BASE_URL}")

if not WEBHOOK_BASE_URL:
    raise ValueError(
        "WEBHOOK_BASE_URL environment variable is required. "
        "Please set it to your ngrok URL (e.g., https://xxxx-xx-xx-xxx-xx.ngrok.io)"
    )

if not WEBHOOK_BASE_URL.startswith('https://'):
    raise ValueError(
        "WEBHOOK_BASE_URL must be an HTTPS URL. "
        "Please ensure your ngrok URL starts with 'https://'"
    )

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize PDF processor
pdf_processor = PDFProcessor()

# Configure upload folder and timeouts
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max file size
app.config['UPLOAD_TIMEOUT'] = 300  # 5 minutes timeout

# Initialize PDF to vector converter
converter = PDFToVector()

handler = VoiceCallHandler()

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
        # 1. Get user's speech (from Twilio Gather or stream)
        # 2. Transcribe using Deepgram
        user_text = stt.transcribe_audio(request.data)  # Adjust as needed

        # 3. Query vector store for relevant context
        context = query_vector_store(user_text)  # Returns relevant docs/snippets

        # 4. Generate answer using OpenAI with context
        answer = nlp.process_text(user_text, context=context)

        # 5. Synthesize answer to speech
        audio_url = tts.generate_speech(answer)  # Returns URL or audio bytes

        # 6. Respond to Twilio with <Play> or <Say>
        response = VoiceResponse()
        response.play(audio_url)  # If you have a URL
        # or: response.say(answer)  # fallback

        return Response(str(response), mimetype="text/xml")
    except Exception as e:
        print(f"Error in voice route: {str(e)}")
        # Create error response
        response = VoiceResponse()
        response.say("I'm sorry, I encountered an error. Please try again.", voice='Polly.Amy')
        return Response(str(response), mimetype='text/xml')

@app.route('/greeting', methods=['POST'])
def greeting():
    """Handle the initial greeting when a call is received."""
    try:
        response = handler.handle_incoming_call(request.form)
        return Response(response, mimetype='text/xml')
    except Exception as e:
        logger.error(f"Error in greeting endpoint: {str(e)}")
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Say>An error occurred. Please try again.</Say></Response>',
            mimetype='text/xml'
        )

@app.route('/handle-response', methods=['POST'])
def handle_response():
    """Handle user's speech input and generate response."""
    try:
        response = handler.handle_user_response(request.form)
        return Response(response, mimetype='text/xml')
    except Exception as e:
        logger.error(f"Error in handle-response endpoint: {str(e)}")
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Say>An error occurred. Please try again.</Say></Response>',
            mimetype='text/xml'
        )

@app.route('/make-call', methods=['POST', 'OPTIONS'])
def make_call():
    """Endpoint to initiate an outbound call."""
    # Handle CORS preflight request
    if request.method == 'OPTIONS':
        response = Response()
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response

    try:
        # Get the phone number from either JSON or form data
        if request.is_json:
            to_number = request.json.get('to_number')
        else:
            to_number = request.form.get('to_number')
            
        if not to_number:
            return jsonify({
                'status': 'error',
                'message': 'Phone number is required'
            }), 400

        # Find the customer by phone number
        customer = find_contact_by_phone(to_number)
        customer_id = str(customer['_id']) if customer else None

        # Add country code prefix if not present
        country = None
        if customer and 'country' in customer:
            country = customer['country'].lower()
        if to_number and not to_number.startswith('+'):
            if country == 'india':
                to_number = '+91' + to_number.lstrip('0')
            elif country == 'united states':
                to_number = '+1' + to_number.lstrip('0')

        # Make the call via Twilio with customer information
        result = handler.make_outbound_call(to_number, customer_info=customer)
        call_sid = result.get('sid')

        # Save call data to the calls collection, including customer info
        call_doc = {
            "to_number": to_number,
            "twilio_sid": call_sid,
            "status": "initiated",
            "customer_id": customer_id,
            "customer_info": customer if customer else None
        }
        calls_collection.insert_one(call_doc)

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in make-call endpoint: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route("/call-status", methods=['GET', 'POST'])
def call_status():
    """Handle call status updates"""
    try:
        call_sid = request.values.get('CallSid')
        call_status = request.values.get('CallStatus')
        
        logger.info(f"Received call status update - SID: {call_sid}, Status: {call_status}")
        
        # Update call status in database
        result = calls_collection.update_one(
            {'twilio_sid': call_sid},  # Changed from call_sid to twilio_sid
            {
                '$set': {
                    'status': call_status,
                    'updated_at': datetime.utcnow()
                }
            }
        )
        
        if result.matched_count > 0:
            logger.info(f"Successfully updated call status for SID {call_sid}")
            return Response(status=200)
        else:
            logger.warning(f"No call found with SID {call_sid}")
            return Response(status=404)
            
    except Exception as e:
        logger.error(f"Error updating call status: {str(e)}")
        return Response(status=500)

def stream_json_response(data):
    """Stream JSON response with proper headers."""
    response = Response(
        json.dumps(data),
        mimetype='application/json',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )
    return response

@app.route('/upload', methods=['POST'])
def upload_pdf():
    """Handle PDF upload and convert to vectors."""
    start_time = time.time()
    
    try:
        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'No file part'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No selected file'
            }), 400
        
        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            try:
                # Save file
                file.save(filepath)
                logger.info(f"File saved successfully at {filepath}")
                
                def generate():
                    try:
                        # Process the PDF and stream progress updates
                        for progress in converter.process_chunks_in_batches(
                            converter.chunk_text(converter.extract_text_from_pdf(filepath)),
                            {"filename": filename, "source": "pdf"}
                        ):
                            # Add elapsed time to progress update
                            progress['elapsed_time'] = time.time() - start_time
                            yield f"data: {json.dumps(progress)}\n\n"
                            
                        # Send final success message
                        final_result = {
                            "status": "success",
                            "message": f"Successfully processed PDF: {filename}",
                            "elapsed_time": time.time() - start_time
                        }
                        yield f"data: {json.dumps(final_result)}\n\n"
                        
                    except Exception as e:
                        error_result = {
                            "status": "error",
                            "message": str(e),
                            "elapsed_time": time.time() - start_time
                        }
                        yield f"data: {json.dumps(error_result)}\n\n"
                    finally:
                        # Clean up the uploaded file
                        if os.path.exists(filepath):
                            os.remove(filepath)
                            logger.info(f"Temporary file removed: {filepath}")
                
                return Response(
                    generate(),
                    mimetype='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive',
                        'X-Accel-Buffering': 'no'
                    }
                )
                
            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': f'Error processing file: {str(e)}',
                    'elapsed_time': time.time() - start_time
                }), 500
        
        return jsonify({
            'status': 'error',
            'message': 'Invalid file type. Only PDF files are allowed.',
            'elapsed_time': time.time() - start_time
        }), 400
        
    except Exception as e:
        logger.error(f"Unexpected error in upload endpoint: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Unexpected error: {str(e)}',
            'elapsed_time': time.time() - start_time
        }), 500

@socketio.on('generate_tts')
def handle_generate_tts(data):
    text = data.get('text')
    if not text:
        emit('tts_error', {'error': 'No text provided'})
        return
    audio_bytes = tts.generate_speech(text)  # Should return bytes
    emit('tts_audio', {'audio': audio_bytes}, broadcast=False)

@app.route('/calls', methods=['GET'])
def get_calls():
    calls = list(calls_collection.find())
    calls = convert_objectid(calls)
    return jsonify(calls)

@app.route('/generate-tts', methods=['GET'])
def generate_tts():
    """Generate text-to-speech using ElevenLabs and return audio."""
    try:
        text = request.args.get('text', '')
        if not text:
            return Response(status=400)
        
        # Generate audio using ElevenLabs
        audio = tts.generate_speech(text)
        
        # Return audio with proper headers
        return Response(
            audio,
            mimetype='audio/mpeg',
            headers={
                'Content-Disposition': 'inline',
                'Cache-Control': 'no-cache'
            }
        )
    except Exception as e:
        logger.error(f"Error generating TTS: {str(e)}")
        return Response(status=500)

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
        port=5002,
        ssl_context=ssl_context,
        host='0.0.0.0'
    )
