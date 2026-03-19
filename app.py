from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uuid
import os
from agent import voice_agent
from google.cloud import texttospeech
import base64
import requests
import logging
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "645972259055-dcknu49vj5h6kaeaml1facanoesv4epl.apps.googleusercontent.com")
    try:
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), client_id, clock_skew_in_seconds=10)
        if idinfo['aud'] != client_id:
            raise ValueError("Could not verify audience.")
        return {"id": idinfo['sub'], "email": idinfo.get("email", "web_user@example.com")}
    except ValueError as e:
        logger.error(f"Invalid token: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

from models import Package, PackageItem, BookingStatus
from booking_service import BookingService
from profile_service import ProfileService
from database import init_db
from pydantic import BaseModel

# Initialize DB
init_db()

# Mount static files if needed (we'll just use templates for now)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

from typing import Optional, List, Dict

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    package_id: Optional[str] = None
    avatar_name: Optional[str] = None
    region: str = "UK" # Default to UK

class TTSRequest(BaseModel):
    text: str
    language_code: str = "en-GB"
    voice_name: str = "en-GB-Chirp3-HD-Algenib"
    provider: str = "google" # google, openai, elevenlabs

class ProfileUpdateRequest(BaseModel):
    content: str

class ProfileFactRequest(BaseModel):
    user_id: str
    fact: str
    remove: bool = False

class BookRequest(BaseModel):
    travelers: List[Dict] # List of {first_name, last_name, dob, gender, email, phone}

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/profile/{user_id}")
async def get_profile(user_id: str, current_user: dict = Depends(get_current_user)):
    return {"content": ProfileService.get_profile(current_user['id'])}

@app.post("/api/profile/{user_id}")
async def update_profile(user_id: str, request: ProfileUpdateRequest, current_user: dict = Depends(get_current_user)):
    ProfileService.update_profile(current_user['id'], request.content)
    return {"status": "success"}

@app.post("/api/profile/fact")
async def update_profile_fact(request: ProfileFactRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user['id']
    if request.remove:
        # Simple removal logic: find line and remove it
        current = ProfileService.get_profile(user_id)
        lines = [l for l in current.split('\n') if request.fact.lower() not in l.lower()]
        ProfileService.update_profile(user_id, "\n".join(lines))
    else:
        ProfileService.append_to_profile(user_id, request.fact)
    return {"status": "success"}

@app.get("/api/proxy/photo")
async def proxy_photo(ref: str):
    """
    Proxies a Google Places photo request to avoid exposing the API key to the client.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="API key not configured")
    
    google_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=1200&photoreference={ref}&key={api_key}"
    
    try:
        # Use a streaming response to pass the image data directly
        response = requests.get(google_url, stream=True, timeout=10)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch image from Google")
        
        # Determine content type
        content_type = response.headers.get("Content-Type", "image/jpeg")
        
        return StreamingResponse(response.iter_content(chunk_size=1024), media_type=content_type)
    except Exception as e:
        logger.error(f"Error proxying photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user['id']
    session_id = request.session_id or str(uuid.uuid4())
    
    if not request.message:
        raise HTTPException(status_code=400, detail="Message is empty")

    from datetime import datetime
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response_text = voice_agent.process_message(user_id, session_id, request.message, region=request.region, package_id=request.package_id, avatar_name=request.avatar_name, current_time=current_time)
    
    return JSONResponse(content={
        "response": response_text,
        "session_id": session_id
    })

@app.post("/chat_stream")
async def chat_stream(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    import json
    import asyncio
    import threading
    
    user_id = current_user['id']
    session_id = request.session_id or str(uuid.uuid4())
    
    if not request.message:
        raise HTTPException(status_code=400, detail="Message is empty")

    queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def run_agent_sync():
        try:
            from datetime import datetime
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Send initial session event
            loop.call_soon_threadsafe(queue.put_nowait, {"session_id": session_id})
            
            for event_type, content in voice_agent.process_message_stream(user_id, session_id, request.message, region=request.region, package_id=request.package_id, avatar_name=request.avatar_name, current_time=current_time):
                if event_type == "text" and content:
                    loop.call_soon_threadsafe(queue.put_nowait, {"chunk": content})
                elif event_type == "thinking" and content:
                    loop.call_soon_threadsafe(queue.put_nowait, {"thinking": content})
                elif event_type == "error" and content:
                    loop.call_soon_threadsafe(queue.put_nowait, {"error": content})
            
            loop.call_soon_threadsafe(queue.put_nowait, "[DONE]")
        except Exception as e:
            logger.error(f"Error in background agent thread: {e}", exc_info=True)
            loop.call_soon_threadsafe(queue.put_nowait, {"error": str(e)})
            loop.call_soon_threadsafe(queue.put_nowait, "[DONE]")

    async def event_generator():
        # Start agent in a background thread
        thread = threading.Thread(target=run_agent_sync, daemon=True)
        thread.start()

        while True:
            item = await queue.get()
            if item == "[DONE]":
                yield "data: [DONE]\n\n"
                break
            
            if "error" in item:
                yield f"data: {json.dumps({'event': 'error', 'content': item['error']})}\n\n"
            else:
                yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/session/{session_id}/packages")
async def get_packages(session_id: str):
    packages = BookingService.get_packages(session_id)
    return [p.model_dump() for p in packages]

@app.get("/api/user/{user_id}/packages")
async def get_user_packages(user_id: str, current_user: dict = Depends(get_current_user)):
    packages = BookingService.get_user_packages(current_user['id'])
    return [p.model_dump() for p in packages]

@app.post("/package/{package_id}/item/{item_id}/verify")
async def verify_item_booking(package_id: str, item_id: str, user_id: str = Header(...)):
    """
    Manually marks an item as BOOKED (for external redirects).
    """
    try:
        res = BookingService.verify_item_booking(user_id, package_id, item_id)
        return res
    except Exception as e:
        logger.error(f"Error verifying item {item_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/package/{package_id}/sync")
async def sync_bookings(package_id: str, user_id: str = Header(...)):
    """
    Syncs external bookings with Travelpayouts Statistics API.
    """
    try:
        res = BookingService.sync_external_bookings(user_id, package_id)
        return res
    except Exception as e:
        logger.error(f"Error syncing package {package_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/packages/{session_id}/{package_id}/book")
async def book_package(session_id: str, package_id: str, request: BookRequest, current_user: dict = Depends(get_current_user)):
    # Relax session_id check for booking to avoid 404s on session mismatch if user is authenticated
    package = BookingService.get_package(None, package_id)
    if not package or package.user_id != current_user['id']:
        raise HTTPException(status_code=404, detail="Package not found")
    
    result = await BookingService.execute_booking(package, current_user['email'], request.travelers)
    return result

@app.delete("/api/packages/{session_id}/{package_id}/items/{item_id}")
async def delete_package_item(session_id: str, package_id: str, item_id: str, current_user: dict = Depends(get_current_user)):
    # Relax session_id check for item deletion
    package = BookingService.get_package(None, package_id)
    if not package or package.user_id != current_user['id']:
        raise HTTPException(status_code=403, detail="Forbidden")
    pkg = BookingService.remove_item_from_package(session_id, package_id, item_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package or item not found")
    return pkg.model_dump()

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
        "shimmer": "shimmer",
        "ash": "ash",
        "coral": "coral",
        "sage": "sage",
        "ballad": "ballad",
        "verse": "verse"
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

    # Use the requested voice ID, or fallback to default if it matches the Google default or is empty
    voice_id = request.voice_name
    if not voice_id or voice_id == "en-GB-Chirp3-HD-Algenib":
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
    uvicorn.run(app, host="0.0.0.0", port=8001)
