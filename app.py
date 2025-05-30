import os
from flask import Flask, request, Response, render_template
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

load_dotenv()

app = Flask(__name__)
# More permissive CORS settings
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"]
    }
})
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize components
stt = SpeechToText()
tts = TextToSpeech()
nlp = NLPProcessor()
emotion_detector = EmotionDetector()
twilio = TwilioHandler()

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
    print(f"Request method: {request.method}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Request data: {request.get_data()}")
    print(f"Form data: {request.form}")
    print(f"Values: {request.values}")
    
    try:
        # Get speech input from Twilio
        speech_result = request.values.get('SpeechResult', '')
        confidence = request.values.get('Confidence', '0')
        print(f"Speech result: {speech_result}")
        print(f"Confidence: {confidence}")
        
        if not speech_result:
            print("No speech detected")
            response = VoiceResponse()
            response.say("I didn't catch that. Could you please repeat?", voice='Polly.Amy')
            response.redirect(urljoin(twilio.webhook_base_url, '/voice'))
            return Response(str(response), mimetype='text/xml')
        
        # Process the speech input
        print(f"Processing speech: {speech_result}")
        
        # Detect emotion
        emotion = emotion_detector.detect_emotion(speech_result)
        emotion_intensity = emotion_detector.get_emotion_intensity(speech_result)
        print(f"Detected emotion: {emotion} (intensity: {emotion_intensity})")
        
        # Process with NLP
        nlp_response = nlp.process_text(speech_result)
        print(f"NLP response: {nlp_response}")
        
        # Create TwiML response with Gather for continuous conversation
        response = VoiceResponse()
        gather = Gather(
            input='speech',
            action=urljoin(twilio.webhook_base_url, '/handle-response'),
            method='POST',
            speech_timeout='3',
            timeout='5',
            language='en-US',
            speech_model='phone_call'
        )
        gather.say(nlp_response, voice='Polly.Amy')
        response.append(gather)
        
        # If no speech is detected, end the call gracefully
        response.say("I didn't hear anything. Goodbye!", voice='Polly.Amy')
        response.hangup()
        
        twiml_response = str(response)
        print(f"Generated TwiML response: {twiml_response}")
        return Response(twiml_response, mimetype='text/xml')
        
    except Exception as e:
        print(f"Error processing response: {str(e)}")
        response = VoiceResponse()
        response.say("I'm sorry, I encountered an error. Please try again.", voice='Polly.Amy')
        return Response(str(response), mimetype='text/xml')

@app.route("/make-call", methods=['POST', 'OPTIONS'])
def make_call():
    """Make an outbound call"""
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
        
        call_sid = twilio.make_call(to_number)
        if call_sid:
            return {"status": "success", "call_sid": call_sid}
        return {"error": "Failed to make call"}, 500
    except Exception as e:
        print(f"Error making call: {str(e)}")
        return {"error": str(e)}, 500

@app.route("/call-status", methods=['POST'])
def call_status():
    """Handle call status updates from Twilio"""
    print("Received call status update")
    print(f"Request method: {request.method}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Request data: {request.get_data()}")
    
    try:
        call_sid = request.values.get('CallSid')
        call_status = request.values.get('CallStatus')
        print(f"Call {call_sid} status: {call_status}")
        return '', 200
    except Exception as e:
        print(f"Error processing call status: {str(e)}")
        return '', 500

if __name__ == "__main__":
    socketio.run(app, debug=True, port=5001)
