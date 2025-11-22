# Google Text-to-Speech Setup Guide

## Current Status
✅ Google Text-to-Speech integration has been added to your voice chatbot  
⚠️ The Cloud Text-to-Speech API needs to be enabled in your Google Cloud project

## Enable the API

1. **Visit the activation URL:**
   https://console.developers.google.com/apis/api/texttospeech.googleapis.com/overview?project=gen-lang-client-0613997707

2. **Click "Enable"** on the Cloud Text-to-Speech API page

3. **Wait a few minutes** for the API to activate

4. **Restart the chatbot server** after enabling

## What's Been Added

### Backend (`app.py`)
- New `/tts` endpoint that converts text to speech using Google's neural voices
- Returns base64-encoded MP3 audio
- Uses `en-US-Neural2-F` (natural female voice) by default

### Frontend (`templates/index.html`)
- Updated `speak()` function to call the `/tts` endpoint
- Converts base64 audio to playable MP3
- Falls back to browser speech synthesis if TTS fails

## Voice Options

You can customize the voice by changing these parameters in `app.py`:

```python
class TTSRequest(BaseModel):
    text: str
    language_code: str = "en-US"
    voice_name: str = "en-US-Neural2-F"  # Change this
```

### Available Voices:
- `en-US-Neural2-F` - Female (default)
- `en-US-Neural2-M` - Male
- `en-US-Neural2-C` - Female (alternative)
- `en-US-Neural2-D` - Male (alternative)

## Testing

After enabling the API, test it with:

```bash
curl -X POST http://localhost:8000/tts \
  -H 'Content-Type: application/json' \
  -d '{"text": "Hello, this is Google Text to Speech"}'
```

## Fallback Behavior

If the Google TTS API fails (not enabled, quota exceeded, etc.), the chatbot automatically falls back to the browser's built-in speech synthesis, so your chatbot will always work!

## Benefits of Google TTS

✅ **Natural-sounding voices** - Much better than browser synthesis  
✅ **Consistent across devices** - Same voice on all platforms  
✅ **Neural voices** - State-of-the-art voice quality  
✅ **Multiple languages** - Support for 40+ languages
