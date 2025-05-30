import os
from elevenlabs import generate, set_api_key
from dotenv import load_dotenv

load_dotenv()

class TextToSpeech:
    def __init__(self):
        set_api_key(os.getenv('ELEVENLABS_API_KEY'))
        self.voice_id = "EXAVITQu4vr4xnSDxMaL"  # Default voice ID (Rachel)

    def generate_speech(self, text):
        """
        Generate speech from text using ElevenLabs
        
        Args:
            text (str): Text to convert to speech
            
        Returns:
            bytes: Audio data
        """
        try:
            audio = generate(
                text=text,
                voice=self.voice_id,
                model="eleven_monolingual_v1"
            )
            return audio
        except Exception as e:
            print(f"Error in speech generation: {str(e)}")
            return None

    def set_voice(self, voice_id):
        """
        Set a different voice for speech generation
        
        Args:
            voice_id (str): ElevenLabs voice ID
        """
        self.voice_id = voice_id
