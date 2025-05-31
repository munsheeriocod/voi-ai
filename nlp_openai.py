import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class NLPProcessor:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.system_prompt = """You are a helpful and friendly voice assistant. 
        Keep your responses very brief and natural-sounding for voice interaction.
        Aim for responses under 10 words when possible.
        Focus on being helpful while maintaining a conversational tone and do not reply to any questions asked outof the  context. Only reply from the RAG context.
        Avoid unnecessary pleasantries and get straight to the point."""

    def process_text(self, text):
        """
        Process text using OpenAI's GPT model
        
        Args:
            text (str): Input text to process
            
        Returns:
            str: Generated response
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=100,
                temperature=0.2,
                presence_penalty=0.1,
                frequency_penalty=0.1,
                top_p=0.9
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error in NLP processing: {str(e)}")
            return "I apologize, but I'm having trouble processing that right now."

    def update_system_prompt(self, new_prompt):
        """
        Update the system prompt for the assistant
        
        Args:
            new_prompt (str): New system prompt
        """
        self.system_prompt = new_prompt
