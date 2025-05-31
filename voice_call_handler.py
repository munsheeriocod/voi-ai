import os
from typing import Dict, Any, List
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI
from elevenlabs import generate, set_api_key
from deepgram import Deepgram
import json
import logging
from dotenv import load_dotenv
import urllib.parse
import sys
from pathlib import Path
from pinecone import Pinecone
from semantic_search import SemanticSearch

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent))
from app.database import get_contact_by_phone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def find_contact_by_phone(phone_number: str) -> Dict[str, Any]:
    """Find customer contact information by phone number."""
    try:
        # Use the database function directly
        contact = get_contact_by_phone(phone_number)
        
        if contact:
            logger.info(f"Found contact: {contact}")
            return contact
        else:
            logger.info(f"No contact found for phone number: {phone_number}")
            return None
    except Exception as e:
        logger.error(f"Error finding contact by phone: {str(e)}")
        return None

class VoiceCallHandler:
    def __init__(self):
        """Initialize the voice call handler with all necessary clients."""
        logger.info("Initializing VoiceCallHandler...")
        
        # Initialize Twilio client
        self.twilio_client = Client(
            os.getenv('TWILIO_ACCOUNT_SID'),
            os.getenv('TWILIO_AUTH_TOKEN')
        )
        self.twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')
        
        # Initialize OpenAI client
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Initialize ElevenLabs
        set_api_key(os.getenv('ELEVENLABS_API_KEY'))
        
        # Initialize Deepgram
        self.deepgram = Deepgram(os.getenv('DEEPGRAM_API_KEY'))
        
        # Initialize Pinecone
        pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
        self.index = pc.Index(os.getenv('PINECONE_INDEX'))
        logger.info("Pinecone initialized successfully")
        
        # Initialize Semantic Search
        self.semantic_search = SemanticSearch()
        
        logger.info("VoiceCallHandler initialized successfully")

    def get_relevant_context(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Get relevant context from Pinecone using vector similarity search."""
        try:
            # Get query embedding using text-embedding-3-small to match PDF processing
            query_embedding = self.openai_client.embeddings.create(
                input=query,
                model="text-embedding-3-small"  # Changed to match PDF processing
            ).data[0].embedding
            
            # Search in Pinecone with higher limit to filter by score
            results = self.index.query(
                vector=query_embedding,
                top_k=limit * 2,  # Get more results to filter by score
                include_metadata=True
            )
            
            # Filter results by score and take top matches
            filtered_matches = [
                match for match in results.matches 
                if match.score > 0.7  # Only keep high-relevance matches
            ][:limit]
            
            logger.info(f"Found {len(filtered_matches)} relevant context items from Pinecone")
            for match in filtered_matches:
                logger.info(f"Context match score: {match.score}, text: {match.metadata.get('text', '')[:100]}...")
            
            return filtered_matches
        except Exception as e:
            logger.error(f"Error getting relevant context: {str(e)}")
            return []

    def generate_response(self, query: str, context: List[Dict[str, Any]]) -> str:
        """Generate a response using OpenAI with the retrieved context."""
        try:
            # Prepare context for the prompt
            context_text = "\n".join([
                f"Context {i+1} (Relevance: {match.score:.2f}): {match.metadata.get('text', '')}"
                for i, match in enumerate(context)
            ])
            
            logger.info(f"Using context: {context_text}")
            
            # Create the prompt with marketing focus
            prompt = f"""You are a sales-focused assistant for Easify. Use the following context to address customer questions and concerns while promoting our premium version.
            Always maintain a positive, solution-oriented approach and highlight the value proposition.

Context:
{context_text}

User Question: {query}

Instructions:
1. If the context contains relevant information, use it to provide a specific answer
2. Always connect the answer to the value of our premium version
3. Address any doubts or concerns using specific information from the context
4. Highlight how premium features solve common problems
5. Keep responses concise and focused on value
6. Use the exact information from the context when available
7. If the context is relevant (score > 0.7), prioritize using that information
8. Always end with a soft call to action about premium features

Answer:"""
            
            # Get response from OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a sales-focused assistant for Easify, focused on addressing customer concerns while promoting premium features."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.2  # Lower temperature for more focused responses
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.info(f"Generated response from context: {response_text}")
            
            # If no relevant context was found, add a note about it
            if not context or all(match.score < 0.7 for match in context):
                response_text = "While I don't have specific information about that in our knowledge base, I can tell you that our premium version offers comprehensive solutions for all your business needs. " + response_text
            
            return response_text
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "I apologize, but I'm having trouble generating a response right now. However, I can tell you about our premium version's features that might help you."

    def text_to_speech(self, text: str) -> bytes:
        """Convert text to speech using ElevenLabs with fallback to Twilio's default voice."""
        try:
            audio = generate(
                text=text,
                voice="Rachel",
                model="eleven_monolingual_v1"
            )
            return audio
        except Exception as e:
            logger.error(f"Error in text-to-speech: {str(e)}")
            if "quota" in str(e).lower() or "credits" in str(e).lower():
                logger.warning("ElevenLabs quota exceeded, falling back to Twilio's default voice")
                return None
            return None

    def speech_to_text(self, audio_data: bytes) -> str:
        """Convert speech to text using Deepgram."""
        try:
            source = {'buffer': audio_data, 'mimetype': 'audio/wav'}
            response = self.deepgram.transcription.prerecorded(source, {
                'smart_format': True,
                'model': 'nova-2',
                'language': 'en-US',
                'punctuate': True,
                'diarize': False,
                'utterances': True,
                'vad_turnoff': 500,
                'encoding': 'linear16',
                'sample_rate': 8000,
                'channels': 1
            })
            
            # Log the full response for debugging
            logger.info(f"Deepgram response: {json.dumps(response, indent=2)}")
            
            # Get the transcript
            transcript = response['results']['channels'][0]['alternatives'][0]['transcript']
            logger.info(f"Transcribed text: {transcript}")
            
            return transcript
        except Exception as e:
            logger.error(f"Error in speech-to-text: {str(e)}")
            return ""

    def handle_incoming_call(self, request: Dict[str, Any]) -> str:
        """Handle incoming call and generate TwiML response."""
        try:
            response = VoiceResponse()
            
            # Get the caller's phone number
            from_number = request.get('From', '')
            logger.info(f"Received call from number: {from_number}")
            
            # Look up customer information by phone number
            customer = None
            if from_number:
                # Remove any '+' prefix for database lookup
                phone_number = from_number.lstrip('+')
                customer = find_contact_by_phone(phone_number)
                logger.info(f"Found customer info: {customer}")
            
            # Get customer name from request data or database
            customer_name = request.get('customer_name', '')
            if not customer_name and customer and customer.get('name'):
                customer_name = customer['name']
            
            logger.info(f"Using customer name: {customer_name}")
            
            if customer_name:
                greeting_text = f"Hey {customer_name}, This is a feedback call from Easify. Are you facing any issues with our service?"
            else:
                greeting_text = "Hey there, This is a feedback call from Easify. Are you facing any issues with our service?"
            
            logger.info(f"Using greeting text: {greeting_text}")
            
            # Generate audio URL using ElevenLabs
            webhook_url = os.getenv('WEBHOOK_BASE_URL', '').rstrip('/')
            audio_url = f"{webhook_url}/generate-tts?text={urllib.parse.quote(greeting_text)}"
            
            logger.info(f"Generated audio URL: {audio_url}")
            
            # Play the ElevenLabs audio
            response.play(audio_url)
            
            # Gather user input
            gather = Gather(
                input='speech',
                action='/handle-response',
                method='POST',
                speech_timeout='auto',
                language='en-US',
                speech_model='phone_call',
                enhanced='true'
            )
            response.append(gather)
            
            # If no input is received, repeat the greeting
            response.redirect('/greeting')
            
            return str(response)
        except Exception as e:
            logger.error(f"Error handling incoming call: {str(e)}")
            response = VoiceResponse()
            response.say("I'm sorry, I encountered an error. Please try again.")
            return str(response)

    def handle_user_response(self, request: Dict[str, Any]) -> str:
        """Handle user's speech input and generate response."""
        try:
            # Get user's speech input
            user_input = request.get('SpeechResult', '')
            logger.info(f"User input: {user_input}")
            
            # Get customer name from request
            customer_name = request.get('customer_name', '')
            logger.info(f"Customer name: {customer_name}")
            
            if not user_input:
                response = VoiceResponse()
                greeting = f"Hey {customer_name}, " if customer_name else "Hey there, "
                message = f"{greeting}I didn't catch that. Let me ask you directly - are you happy with Easify? We have a special offer that I'd love to tell you about."
                
                # Try ElevenLabs first, fall back to Twilio if it fails
                webhook_url = os.getenv('WEBHOOK_BASE_URL', '').rstrip('/')
                audio_url = f"{webhook_url}/generate-tts?text={urllib.parse.quote(message)}"
                
                gather = Gather(
                    input='speech',
                    action=f'/greeting?customer_name={urllib.parse.quote(customer_name)}',
                    method='POST',
                    speech_timeout='auto',
                    language='en-US',
                    speech_model='phone_call',
                    enhanced='true',
                    bargeIn='true'
                )
                
                # Try to use ElevenLabs, fall back to Twilio if it fails
                try:
                    gather.play(audio_url)
                except Exception as e:
                    logger.error(f"Error playing audio URL: {str(e)}")
                    gather.say(message)
                
                response.append(gather)
                return str(response)
            
            # Create TwiML response
            response = VoiceResponse()
            webhook_url = os.getenv('WEBHOOK_BASE_URL', '').rstrip('/')
            
            # Check if this is the first response (about experience)
            is_first_response = request.get('is_first_response', 'true') == 'true'
            logger.info(f"Is first response: {is_first_response}")
            
            if is_first_response:
                # Check for positive sentiment
                positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'love', 'happy', 'satisfied', 'impressed', 'perfect', 'best', 'fantastic']
                # Check for negative sentiment
                negative_words = ['horrible', 'bad', 'terrible', 'awful', 'poor', 'not good', 'disappointing', 'frustrating', 'difficult', 'issue', 'problem', 'trouble', 'error', 'bug', 'not working', 'failed']
                # Check for feature queries
                feature_words = ['how', 'what', 'when', 'where', 'why', 'tell me about', 'explain', 'know more about', 'information about', 'process', 'feature', 'onboarding', 'setup', 'configure', 'work', 'does', 'can', 'able to']
                user_input_lower = user_input.lower()
                
                if any(word in user_input_lower for word in feature_words):
                    # If asking about features, provide interactive education
                    logger.info("Getting context from Pinecone for interactive feature education...")
                    context = self.get_relevant_context(user_input)
                    logger.info(f"Found {len(context)} relevant context items from Pinecone")
                    
                    # Generate educational response
                    ai_response = self.generate_response(user_input, context)
                    logger.info(f"Generated educational response: {ai_response}")
                    
                    # Play educational content with interruption enabled
                    gather = Gather(
                        input='speech',
                        action=f'/handle-response?is_first_response=false&context=feature_choice&customer_name={urllib.parse.quote(customer_name)}',
                        method='POST',
                        speech_timeout='auto',
                        language='en-US',
                        speech_model='phone_call',
                        enhanced='true',
                        bargeIn='true'
                    )
                    
                    # Try to use ElevenLabs, fall back to Twilio if it fails
                    try:
                        audio_url = f"{webhook_url}/generate-tts?text={urllib.parse.quote(ai_response)}"
                        gather.play(audio_url)
                    except Exception as e:
                        logger.error(f"Error playing audio URL: {str(e)}")
                        gather.say(ai_response)
                    
                    response.append(gather)
                elif any(word in user_input_lower for word in positive_words):
                    # If positive, engage with specific features
                    greeting = f"{customer_name}, " if customer_name else ""
                    follow_up = f"{greeting}That's fantastic! Which feature of Easify do you find most useful? I'd love to tell you about how our premium version enhances that feature."
                    logger.info(f"Playing interactive follow-up: {follow_up}")
                    
                    # Gather response about favorite feature with interruption enabled
                    gather = Gather(
                        input='speech',
                        action=f'/handle-response?is_first_response=false&context=favorite_feature&customer_name={urllib.parse.quote(customer_name)}',
                        method='POST',
                        speech_timeout='auto',
                        language='en-US',
                        speech_model='phone_call',
                        enhanced='true',
                        bargeIn='true'
                    )
                    
                    # Try to use ElevenLabs, fall back to Twilio if it fails
                    try:
                        audio_url = f"{webhook_url}/generate-tts?text={urllib.parse.quote(follow_up)}"
                        gather.play(audio_url)
                    except Exception as e:
                        logger.error(f"Error playing audio URL: {str(e)}")
                        gather.say(follow_up)
                    
                    response.append(gather)
                elif any(word in user_input_lower for word in negative_words):
                    # If negative, engage with specific concerns
                    greeting = f"{customer_name}, " if customer_name else ""
                    follow_up = f"{greeting}I understand you're having some issues. Could you tell me which specific aspect of Easify is causing you trouble? This will help me provide the most relevant solution."
                    logger.info(f"Playing interactive follow-up: {follow_up}")
                    
                    # Gather specific concern with interruption enabled
                    gather = Gather(
                        input='speech',
                        action=f'/handle-response?is_first_response=false&context=specific_concern&customer_name={urllib.parse.quote(customer_name)}',
                        method='POST',
                        speech_timeout='auto',
                        language='en-US',
                        speech_model='phone_call',
                        enhanced='true',
                        bargeIn='true'
                    )
                    
                    # Try to use ElevenLabs, fall back to Twilio if it fails
                    try:
                        audio_url = f"{webhook_url}/generate-tts?text={urllib.parse.quote(follow_up)}"
                        gather.play(audio_url)
                    except Exception as e:
                        logger.error(f"Error playing audio URL: {str(e)}")
                        gather.say(follow_up)
                    
                    response.append(gather)
                else:
                    # If neutral, engage with business needs
                    greeting = f"{customer_name}, " if customer_name else ""
                    follow_up = f"{greeting}I'd love to understand your business needs better. What's the most important feature you're looking for in a business solution?"
                    logger.info(f"Playing interactive follow-up: {follow_up}")
                    
                    # Gather business needs with interruption enabled
                    gather = Gather(
                        input='speech',
                        action=f'/handle-response?is_first_response=false&context=business_needs&customer_name={urllib.parse.quote(customer_name)}',
                        method='POST',
                        speech_timeout='auto',
                        language='en-US',
                        speech_model='phone_call',
                        enhanced='true',
                        bargeIn='true'
                    )
                    
                    # Try to use ElevenLabs, fall back to Twilio if it fails
                    try:
                        audio_url = f"{webhook_url}/generate-tts?text={urllib.parse.quote(follow_up)}"
                        gather.play(audio_url)
                    except Exception as e:
                        logger.error(f"Error playing audio URL: {str(e)}")
                        gather.say(follow_up)
                    
                    response.append(gather)
            else:
                # Get context from request
                context = request.get('context', '')
                
                # Get relevant context from Pinecone for interactive response
                logger.info("Getting context from Pinecone...")
                pinecone_context = self.get_relevant_context(user_input)
                logger.info(f"Found {len(pinecone_context)} relevant context items from Pinecone")
                
                # Generate interactive response
                logger.info("Generating AI response...")
                ai_response = self.generate_response(user_input, pinecone_context)
                logger.info(f"Generated AI response: {ai_response}")
                
                # Play the response with interruption enabled
                gather = Gather(
                    input='speech',
                    action=f'/handle-response?is_first_response=false&customer_name={urllib.parse.quote(customer_name)}',
                    method='POST',
                    speech_timeout='auto',
                    language='en-US',
                    speech_model='phone_call',
                    enhanced='true',
                    bargeIn='true'
                )
                
                # Try to use ElevenLabs, fall back to Twilio if it fails
                try:
                    audio_url = f"{webhook_url}/generate-tts?text={urllib.parse.quote(ai_response)}"
                    gather.play(audio_url)
                except Exception as e:
                    logger.error(f"Error playing audio URL: {str(e)}")
                    gather.say(ai_response)
                
                response.append(gather)
                
                # Context-specific follow-up with interruption enabled
                greeting = f"{customer_name}, " if customer_name else ""
                if context == 'feature_choice':
                    follow_up = f"{greeting}Would you like to know more about this, or shall we discuss how our premium version can help you?"
                elif context == 'favorite_feature':
                    follow_up = f"{greeting}That's a great choice! Our premium version takes this feature to the next level. Would you like to hear about the premium enhancements?"
                elif context == 'specific_concern':
                    follow_up = f"{greeting}I understand. Our premium version specifically addresses this concern. Would you like to hear how?"
                elif context == 'business_needs':
                    follow_up = f"{greeting}Based on your needs, I think our premium version would be perfect for you. Would you like to hear about our special offer?"
                else:
                    follow_up = f"{greeting}Would you like to know more about this, or shall we discuss how our premium version can help you?"
                
                logger.info(f"Playing context-specific follow-up: {follow_up}")
                follow_up_gather = Gather(
                    input='speech',
                    action=f'/handle-response?is_first_response=false&customer_name={urllib.parse.quote(customer_name)}',
                    method='POST',
                    speech_timeout='auto',
                    language='en-US',
                    speech_model='phone_call',
                    enhanced='true',
                    bargeIn='true'
                )
                
                # Try to use ElevenLabs, fall back to Twilio if it fails
                try:
                    follow_up_url = f"{webhook_url}/generate-tts?text={urllib.parse.quote(follow_up)}"
                    follow_up_gather.play(follow_up_url)
                except Exception as e:
                    logger.error(f"Error playing audio URL: {str(e)}")
                    follow_up_gather.say(follow_up)
                
                response.append(follow_up_gather)
            
            # If no input is received, end with interactive call to action
            greeting = f"{customer_name}, " if customer_name else ""
            goodbye_message = f"{greeting}Before we end, would you like to hear about our special 30% discount offer? It's only available for the next 24 hours. Just say yes to learn more!"
            
            # Final gather with interruption enabled
            final_gather = Gather(
                input='speech',
                action=f'/handle-response?is_first_response=false&context=final_offer&customer_name={urllib.parse.quote(customer_name)}',
                method='POST',
                speech_timeout='auto',
                language='en-US',
                speech_model='phone_call',
                enhanced='true',
                bargeIn='true'
            )
            
            # Try to use ElevenLabs, fall back to Twilio if it fails
            try:
                goodbye_url = f"{webhook_url}/generate-tts?text={urllib.parse.quote(goodbye_message)}"
                final_gather.play(goodbye_url)
            except Exception as e:
                logger.error(f"Error playing audio URL: {str(e)}")
                final_gather.say(goodbye_message)
            
            response.append(final_gather)
            
            # If still no response, end call
            response.hangup()
            
            logger.info("Generated TwiML response")
            return str(response)
        except Exception as e:
            logger.error(f"Error handling user response: {str(e)}")
            response = VoiceResponse()
            greeting = f"{customer_name}, " if customer_name else ""
            error_message = f"{greeting}Would you like to hear about our special offer? Just say yes to learn more about our premium version!"
            
            # Error gather with interruption enabled
            final_gather = Gather(
                input='speech',
                action=f'/handle-response?is_first_response=false&context=final_offer&customer_name={urllib.parse.quote(customer_name)}',
                method='POST',
                speech_timeout='auto',
                language='en-US',
                speech_model='phone_call',
                enhanced='true',
                bargeIn='true'
            )
            
            # Try to use ElevenLabs, fall back to Twilio if it fails
            try:
                error_url = f"{webhook_url}/generate-tts?text={urllib.parse.quote(error_message)}"
                final_gather.play(error_url)
            except Exception as e:
                logger.error(f"Error playing audio URL: {str(e)}")
                final_gather.say(error_message)
            
            response.append(final_gather)
            return str(response)

    def make_outbound_call(self, to_number: str, customer_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an outbound call to a specified number."""
        try:
            webhook_url = os.getenv('WEBHOOK_BASE_URL')
            logger.info(f"Current WEBHOOK_BASE_URL: {webhook_url}")
            
            if not webhook_url:
                raise ValueError("WEBHOOK_BASE_URL environment variable is not set")
            
            # Validate webhook URL
            if not webhook_url.startswith('https://'):
                raise ValueError(
                    "WEBHOOK_BASE_URL must be an HTTPS URL. "
                    "Please ensure your ngrok URL starts with 'https://'"
                )
            
            # Ensure the webhook URL is properly formatted
            webhook_url = webhook_url.rstrip('/')  # Remove trailing slash if present
            
            # Add customer information to the webhook URL if available
            if customer_info and customer_info.get('name'):
                greeting_url = f"{webhook_url}/greeting?customer_name={urllib.parse.quote(customer_info['name'])}"
            else:
                greeting_url = f"{webhook_url}/greeting"
            
            logger.info(f"Making outbound call to {to_number}")
            logger.info(f"Using webhook URL: {greeting_url}")
            logger.info(f"From number: {self.twilio_phone}")
            
            # Validate phone number
            if not to_number:
                raise ValueError("Phone number is required")
            
            # Ensure phone number is in E.164 format
            if not to_number.startswith('+'):
                to_number = '+' + to_number
            
            call = self.twilio_client.calls.create(
                to=to_number,
                from_=self.twilio_phone,
                url=greeting_url,
                record=True,
                status_callback=f"{webhook_url}/call-status",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                status_callback_method='POST'
            )
            
            logger.info(f"Call created successfully with SID: {call.sid}")
            
            return {
                "status": "success",
                "message": "Call initiated successfully",
                "sid": call.sid,
                "webhook_url": greeting_url
            }
        except Exception as e:
            logger.error(f"Error making outbound call: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

def main():
    """Example usage of the VoiceCallHandler class."""
    handler = VoiceCallHandler()
    
    # Example of making an outbound call
    result = handler.make_outbound_call("+1234567890", {"name": "John Doe"})  # Replace with actual phone number and customer information
    print(result)

if __name__ == "__main__":
    main() 