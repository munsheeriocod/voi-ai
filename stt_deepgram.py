import os
from deepgram import Deepgram
from dotenv import load_dotenv

load_dotenv()

class SpeechToText:
    def __init__(self):
        self.deepgram = Deepgram(os.getenv('DEEPGRAM_API_KEY'))

    async def transcribe_audio(self, audio_data):
        """
        Transcribe audio data using Deepgram
        
        Args:
            audio_data (bytes): Raw audio data
            
        Returns:
            str: Transcribed text
        """
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
            print(f"Error in transcription: {str(e)}")
            return None
