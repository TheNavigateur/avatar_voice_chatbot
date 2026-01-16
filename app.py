from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uuid
import os
from agent import voice_agent
from google.cloud import texttospeech
import base64
import requests
from openai import OpenAI

app = FastAPI()

# Mount static files if needed (we'll just use templates for now)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

from typing import Optional

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class TTSRequest(BaseModel):
    text: str
    language_code: str = "en-GB"
    voice_name: str = "en-GB-Chirp3-HD-Algenib"
    provider: str = "google" # google, openai, elevenlabs

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat")
async def chat(request: ChatRequest):
    user_id = "web_user"
    session_id = request.session_id or str(uuid.uuid4())
    
    if not request.message:
        raise HTTPException(status_code=400, detail="Message is empty")

    response_text = voice_agent.process_message(user_id, session_id, request.message)
    
    return JSONResponse(content={
        "response": response_text,
        "session_id": session_id
    })

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech using Google Cloud Text-to-Speech API"""
    try:
        if request.provider == "openai":
            return await generate_openai_tts(request)
        elif request.provider == "elevenlabs":
            return await generate_elevenlabs_tts(request)
        else:
            return await generate_google_tts(request)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS Error: {str(e)}")

async def generate_google_tts(request: TTSRequest):
    # Initialize the Text-to-Speech client
    client = texttospeech.TextToSpeechClient()
    
    # Set the text input
    synthesis_input = texttospeech.SynthesisInput(text=request.text)
    
    # Build the voice request
    voice = texttospeech.VoiceSelectionParams(
        language_code=request.language_code,
        name=request.voice_name
    )
    
    # Select the audio format
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    
    # Perform the text-to-speech request
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    
    # Return the audio content as base64 for easy embedding
    audio_base64 = base64.b64encode(response.audio_content).decode('utf-8')
    
    return JSONResponse(content={
        "audio": audio_base64,
        "format": "mp3"
    })

async def generate_openai_tts(request: TTSRequest):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
         raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
         
    client = OpenAI(api_key=api_key)
    
    # Map Google voice names to OpenAI equivalents or use defaults
    voice_map = {
        "alloy": "alloy",
        "echo": "echo",
        "fable": "fable",
        "onyx": "onyx",
        "nova": "nova",
        "shimmer": "shimmer"
    }
    
    # Default to 'alloy' if voice not found or if it's a Google voice name
    openai_voice = voice_map.get(request.voice_name, "alloy")
    
    response = client.audio.speech.create(
        model="tts-1-hd",
        voice=openai_voice,
        input=request.text
    )
    
    # Get binary content
    audio_content = response.content
    audio_base64 = base64.b64encode(audio_content).decode('utf-8')
    
    return JSONResponse(content={
        "audio": audio_base64,
        "format": "mp3"
    })

async def generate_elevenlabs_tts(request: TTSRequest):
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
         raise HTTPException(status_code=500, detail="ELEVENLABS_API_KEY not set")

    # Use a default voice ID if a specific one isn't provided or needed
    # Custom voice ID: 8fcyCHOzlKDlxh1InJSf
    voice_id = "8fcyCHOzlKDlxh1InJSf" 
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    data = {
        "text": request.text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5
        }
    }
    
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"ElevenLabs Error: {response.text}")
        
    audio_base64 = base64.b64encode(response.content).decode('utf-8')
    
    return JSONResponse(content={
        "audio": audio_base64,
        "format": "mp3"
    })
        


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
