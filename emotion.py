import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class EmotionDetector:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.emotions = ['happy', 'sad', 'angry', 'neutral', 'excited', 'frustrated']

    def detect_emotion(self, text):
        """
        Detect emotion from text using OpenAI
        
        Args:
            text (str): Input text to analyze
            
        Returns:
            str: Detected emotion
        """
        try:
            prompt = f"""Analyze the following text and classify the emotion into one of these categories: {', '.join(self.emotions)}.
            Text: {text}
            Emotion:"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an emotion detection system. Respond with only one word from the given emotion categories."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,
                temperature=0.3
            )
            
            emotion = response.choices[0].message.content.strip().lower()
            return emotion if emotion in self.emotions else 'neutral'
        except Exception as e:
            print(f"Error in emotion detection: {str(e)}")
            return 'neutral'

    def get_emotion_intensity(self, text):
        """
        Get the intensity of the detected emotion (0-1)
        
        Args:
            text (str): Input text to analyze
            
        Returns:
            float: Emotion intensity (0-1)
        """
        try:
            prompt = f"""Rate the intensity of the emotion in the following text on a scale of 0 to 1:
            Text: {text}
            Intensity:"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an emotion intensity analyzer. Respond with only a number between 0 and 1."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,
                temperature=0.3
            )
            
            intensity = float(response.choices[0].message.content.strip())
            return max(0.0, min(1.0, intensity))
        except Exception as e:
            print(f"Error in emotion intensity detection: {str(e)}")
            return 0.5
