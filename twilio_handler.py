import os
import logging
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from dotenv import load_dotenv
from urllib.parse import urljoin

# Configure logging
logger = logging.getLogger(__name__)

load_dotenv()

class TwilioHandler:
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.phone_number = os.getenv('TWILIO_PHONE_NUMBER')
        self.webhook_base_url = os.getenv('WEBHOOK_BASE_URL', 'http://localhost:5000')
        
        if not all([self.account_sid, self.auth_token, self.phone_number]):
            raise ValueError("Missing required Twilio credentials in environment variables")
            
        self.client = Client(self.account_sid, self.auth_token)
        logger.info(f"TwilioHandler initialized with webhook base URL: {self.webhook_base_url}")

    def create_voice_response(self, text_to_say):
        """
        Create a TwiML response for voice
        
        Args:
            text_to_say (str): Text to be spoken
            
        Returns:
            str: TwiML response
        """
        try:
            response = VoiceResponse()
            gather = Gather(
                input='speech',
                action=urljoin(self.webhook_base_url, '/handle-response'),
                method='POST',
                speech_timeout='2',
                timeout='3',
                language='en-US',
                speech_model='phone_call'  # Changed to phone_call for better accuracy
            )
            gather.say(
                text_to_say,
                voice='Polly.Joanna',
                rate='1.1'
            )
            response.append(gather)
            
            # If no speech is detected, end the call gracefully
            response.say(
                "I didn't hear anything. Goodbye!",
                voice='Polly.Joanna',
                rate='1.1'
            )
            response.hangup()
            
            twiml_response = str(response)
            logger.info(f"Generated TwiML response: {twiml_response}")
            return twiml_response
        except Exception as e:
            logger.error(f"Error creating voice response: {str(e)}")
            response = VoiceResponse()
            response.say(
                "I'm sorry, I encountered an error. Please try again.",
                voice='Polly.Joanna',
                rate='1.1'
            )
            return str(response)

    def handle_speech_input(self, speech_result):
        """
        Handle speech input from the user
        
        Args:
            speech_result (str): Speech recognition result
            
        Returns:
            str: TwiML response
        """
        try:
            if not speech_result:
                return self.create_voice_response("I didn't catch that. Could you please repeat?")
            
            return self.create_voice_response(f"You said: {speech_result}")
        except Exception as e:
            print(f"Error handling speech input: {str(e)}")
            response = VoiceResponse()
            response.say("I'm sorry, I encountered an error. Please try again.", voice='Polly.Amy')
            return str(response)

    def make_call(self, to_number):
        """
        Make an outbound call
        
        Args:
            to_number (str): Phone number to call
            
        Returns:
            str: Call SID
        """
        try:
            if not to_number:
                raise ValueError("Phone number is required")
            
            # Ensure phone number is in E.164 format
            if not to_number.startswith('+'):
                to_number = '+' + to_number
                
            voice_url = urljoin(self.webhook_base_url, '/voice')
            status_callback_url = urljoin(self.webhook_base_url, '/call-status')
            
            logger.info(f"Making call to {to_number}")
            logger.info(f"Voice URL: {voice_url}")
            logger.info(f"Status callback URL: {status_callback_url}")
            
            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                url=voice_url,
                status_callback=status_callback_url,
                status_callback_event=[
                    'initiated',
                    'ringing',
                    'answered',
                    'in-progress',
                    'completed',
                    'busy',
                    'failed',
                    'no-answer',
                    'canceled'
                ],
                status_callback_method='POST'
            )
            
            logger.info(f"Call created successfully with SID: {call.sid}")
            return call.sid
        except Exception as e:
            logger.error(f"Error making call: {str(e)}")
            raise
