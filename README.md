# Voice Assistant

A powerful voice assistant that combines speech-to-text, natural language processing, emotion detection, and text-to-speech capabilities.

## Features

- Speech-to-Text using Deepgram
- Text-to-Speech using ElevenLabs
- Natural Language Processing with OpenAI
- Emotion Detection
- Phone Call Integration with Twilio
- Real-time WebSocket Communication
- Browser-based Voice Interface

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root directory with the following variables:
   ```
   DEEPGRAM_API_KEY=your_deepgram_api_key
   ELEVENLABS_API_KEY=your_elevenlabs_api_key
   OPENAI_API_KEY=your_openai_api_key
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   TWILIO_PHONE_NUMBER=your_twilio_phone_number
   WEBHOOK_BASE_URL=your_public_url  # e.g., https://your-domain.com
   FLASK_SECRET_KEY=your_secret_key  # For session management
   ```

## Usage

### Browser-based Interface

1. Start the application:
   ```bash
   python app.py
   ```
2. Open your browser and navigate to `http://localhost:5000`
3. Click "Start Recording" to begin speaking
4. Click "Stop Recording" when you're done
5. The assistant will process your speech and respond with text and audio

### Phone Call Interface

1. Start the application:
   ```bash
   python app.py
   ```
2. The server will start on `http://localhost:5000`
3. Make a phone call to your Twilio number to interact with the voice assistant

## Components

- `app.py`: Main application file with WebSocket support
- `stt_deepgram.py`: Speech-to-text implementation using Deepgram
- `tts_elevenlabs.py`: Text-to-speech implementation using ElevenLabs
- `nlp_openai.py`: Natural language processing using OpenAI
- `emotion.py`: Emotion detection module
- `twilio_handler.py`: Twilio integration for phone calls
- `templates/index.html`: Browser-based interface

## Requirements

- Python 3.8+
- API keys for Deepgram, ElevenLabs, OpenAI, and Twilio
- A Twilio phone number
- A public URL for webhooks (can use ngrok for development)
- Modern web browser with WebSocket support

## Troubleshooting

### Common Issues

1. **WebSocket Connection Issues**
   - Ensure your browser supports WebSocket
   - Check if the server is running and accessible
   - Verify CORS settings if accessing from a different domain

2. **Webhook URL Not Accessible**
   - Ensure your `WEBHOOK_BASE_URL` is publicly accessible
   - For development, use ngrok: `ngrok http 5000`
   - Update the `WEBHOOK_BASE_URL` in your `.env` file with the ngrok URL

3. **Missing Environment Variables**
   - Verify all required environment variables are set in your `.env` file
   - Check the console for specific missing variable errors

4. **Twilio Call Issues**
   - Ensure your Twilio account is active and has sufficient credits
   - Verify your Twilio phone number is properly configured
   - Check Twilio console for call logs and error messages

5. **Speech Recognition Problems**
   - Ensure good audio quality during calls
   - Check Deepgram API key and quota
   - Verify internet connectivity
   - For browser interface, ensure microphone permissions are granted

### Error Logging

- Check the console output for detailed error messages
- All errors are logged with specific error messages
- Twilio call status updates are logged when available
- WebSocket connection status is displayed in the browser interface

## License

MIT
