import os
import logging
import asyncio
from dotenv import load_dotenv
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from elevenlabs import generate, set_api_key
from deepgram import Deepgram
from openai import OpenAI
from vector_store import VectorStore

load_dotenv()

logger = logging.getLogger(__name__)

class VoiceAIHandler:
    def __init__(self):
        # Initialize Twilio
        self.twilio_client = Client(
            os.getenv('TWILIO_ACCOUNT_SID'),
            os.getenv('TWILIO_AUTH_TOKEN')
        )
        self.twilio_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        # Initialize ElevenLabs
        set_api_key(os.getenv('ELEVENLABS_API_KEY'))
        self.voice_id = "EXAVITQu4vr4xnSDxMaL"  # Default voice ID (Rachel)
        
        # Initialize Deepgram
        self.deepgram = Deepgram(os.getenv('DEEPGRAM_API_KEY'))
        
        # Initialize OpenAI and Vector Store
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.vector_store = VectorStore()
        
        logger.info("VoiceAIHandler initialized with all services")

    async def process_voice_call(self, to_number):
        """
        Handle the entire voice call process:
        1. Make the call
        2. Process speech input
        3. Generate responses using OpenAI and vector data
        4. Convert responses to speech using ElevenLabs
        """
        try:
            # Make the initial call
            call = self.twilio_client.calls.create(
                to=to_number,
                from_=self.twilio_number,
                url=os.getenv('WEBHOOK_BASE_URL', 'http://localhost:5000') + '/voice-call'
            )
            logger.info(f"Call initiated to {to_number} with SID: {call.sid}")

            # Process the call in a loop
            while True:
                # Get audio input from the call
                audio_data = await self._get_audio_from_call(call.sid)
                
                if not audio_data:
                    break  # End of call
                    
                # Transcribe audio using Deepgram
                transcript = await self._transcribe_audio(audio_data)
                logger.info(f"Transcribed text: {transcript}")
                
                if not transcript:
                    continue
                    
                # Get response from OpenAI using vector data
                response_text = await self._get_ai_response(transcript)
                logger.info(f"AI response: {response_text}")
                
                # Convert response to speech using ElevenLabs
                audio_response = self._generate_speech(response_text)
                
                if audio_response:
                    # Send audio response back to Twilio
                    self._send_audio_to_call(call.sid, audio_response)
                    
        except Exception as e:
            logger.error(f"Error processing voice call: {str(e)}")
            raise

    async def _get_audio_from_call(self, call_sid):
        """Get audio data from the ongoing call"""
        # This would need to be implemented with Twilio's streaming capabilities
        # or by using Twilio's recording feature
        pass

    async def _transcribe_audio(self, audio_data):
        """Transcribe audio using Deepgram"""
        try:
            source = {'buffer': audio_data, 'mimetype': 'audio/wav'}
            response = await self.deepgram.transcription.prerecorded(
                source,
                {
                    'smart_format': True,
                    'model': 'nova',
                    'language': 'en-US'
                }
            )
            return response['results']['channels'][0]['alternatives'][0]['transcript']
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return None

    def _generate_speech(self, text):
        """Convert text to speech using ElevenLabs"""
        try:
            audio = generate(
                text=text,
                voice=self.voice_id,
                model="eleven_monolingual_v1"
            )
            return audio
        except Exception as e:
            logger.error(f"Error generating speech: {str(e)}")
            return None

    async def _get_ai_response(self, user_input):
        """Get response from OpenAI using vector store"""
        try:
            # Get relevant context from vector store
            context = self.vector_store.get_relevant_context(user_input)
            
            # Create prompt with context
            prompt = f"""
            You are a helpful AI assistant. Here is some relevant context:
            {context}
            
            User: {user_input}
            Assistant:"""
            
            # Get response from OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error getting AI response: {str(e)}")
            return "I'm sorry, I encountered an error. Please try again."

    def _send_audio_to_call(self, call_sid, audio_data):
        """Send audio back to the call"""
        # This would need to be implemented using Twilio's streaming capabilities
        pass
