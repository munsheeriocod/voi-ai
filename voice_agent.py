import os
import logging
import asyncio
from dotenv import load_dotenv
from twilio.rest import Client
from elevenlabs import generate, set_api_key
from deepgram import Deepgram
from openai import OpenAI
from vector_store import VectorStore
from pydub import AudioSegment
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VoiceAgent:
    def __init__(self):
        load_dotenv()
        
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
        
        # Initialize OpenAI
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Initialize Vector Store
        self.vector_store = VectorStore()
        
        logger.info("VoiceAgent initialized with all services")
    
    async def make_call(self, to_number):
        """Initiate an outbound call to the specified number"""
        try:
            call = self.twilio_client.calls.create(
                to=to_number,
                from_=self.twilio_number,
                url=f"{os.getenv('WEBHOOK_BASE_URL')}/voice"
            )
            logger.info(f"Call initiated to {to_number} with SID: {call.sid}")
            return call.sid
        except Exception as e:
            logger.error(f"Failed to initiate call: {str(e)}")
            raise

    async def handle_incoming_call(self, call_sid):
        """Handle an incoming call with the given SID"""
        try:
            # Initial greeting
            await self._speak("Hello! How can I assist you today?")
            
            # Start conversation loop
            while True:
                # Get user's speech input
                user_text = await self._listen()
                if not user_text:
                    await self._speak("I didn't catch that. Could you please repeat?")
                    continue
                
                # Get response from AI
                response = await self._get_ai_response(user_text)
                
                # Speak the response
                await self._speak(response)
                
                # Check for end of conversation
                if any(phrase in response.lower() for phrase in ["goodbye", "bye", "see you"]):
                    break
                    
        except Exception as e:
            logger.error(f"Error in call handling: {str(e)}")
            await self._speak("I'm sorry, I encountered an error. Goodbye!")
        finally:
            # End the call
            self.twilio_client.calls(call_sid).update(status='completed')
    
    async def _speak(self, text):
        """Convert text to speech using ElevenLabs and play it"""
        try:
            audio = generate(
                text=text,
                voice=self.voice_id,
                model="eleven_monolingual_v1"
            )
            # Save audio to a temporary file and play it
            with open("temp_audio.mp3", "wb") as f:
                f.write(audio)
            
            # Play the audio (requires ffmpeg)
            sound = AudioSegment.from_mp3("temp_audio.mp3")
            play(sound)
            
        except Exception as e:
            logger.error(f"Error in speech generation: {str(e)}")
            raise
    
    async def _listen(self) -> str:
        """Listen to user's speech and return transcribed text"""
        try:
            # This is a simplified version - in a real app, you'd get audio from Twilio
            # For this example, we'll use the microphone
            import sounddevice as sd
            import soundfile as sf
            import numpy as np
            
            # Record audio
            sample_rate = 16000
            duration = 5  # seconds
            
            logger.info("Listening...")
            recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1)
            sd.wait()
            
            # Save to WAV
            wav_file = "temp_audio.wav"
            sf.write(wav_file, recording, sample_rate)
            
            # Transcribe with Deepgram
            with open(wav_file, "rb") as audio:
                source = {'buffer': audio, 'mimetype': 'audio/wav'}
                response = await self.deepgram.transcription.prerecorded(
                    source,
                    {
                        'smart_format': True,
                        'model': 'nova',
                        'language': 'en-US'
                    }
                )
                
            transcript = response['results']['channels'][0]['alternatives'][0]['transcript']
            logger.info(f"Transcribed: {transcript}")
            return transcript
            
        except Exception as e:
            logger.error(f"Error in speech recognition: {str(e)}")
            return ""
    
    async def _get_ai_response(self, user_input: str) -> str:
        """Get response from OpenAI using vector store context"""
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
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant that provides concise and accurate information."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error getting AI response: {str(e)}")
            return "I'm sorry, I'm having trouble understanding. Could you please rephrase that?"

# Helper function to play audio
def play(audio_segment):
    import simpleaudio as sa
    import numpy as np
    
    # Convert to 16-bit PCM format
    audio_data = np.int16(audio_segment.get_array_of_samples() * (2**15 - 1))
    
    # Play the audio
    play_obj = sa.play_buffer(
        audio_data,
        num_channels=audio_segment.channels,
        bytes_per_sample=2,
        sample_rate=audio_segment.frame_rate
    )
    play_obj.wait_done()

async def main():
    # Example usage
    agent = VoiceAgent()
    
    try:
        # Make a call to a phone number
        to_number = os.getenv('PHONE_NUMBER')
        if not to_number:
            raise ValueError("PHONE_NUMBER environment variable not set")
            
        call_sid = await agent.make_call(to_number)
        
        # In a real application, you would set up a webhook to handle the call
        # For this example, we'll simulate handling the call directly
        await agent.handle_incoming_call(call_sid)
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
