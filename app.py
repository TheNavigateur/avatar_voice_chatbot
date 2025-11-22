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

app = FastAPI()

# Mount static files if needed (we'll just use templates for now)
# app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

from typing import Optional

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class TTSRequest(BaseModel):
    text: str
    language_code: str = "en-US"
    voice_name: str = "en-US-Neural2-F"  # Female neural voice

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
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
