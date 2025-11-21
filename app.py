from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uuid
import os
from agent import voice_agent

app = FastAPI()

# Mount static files if needed (we'll just use templates for now)
# app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

from typing import Optional

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
