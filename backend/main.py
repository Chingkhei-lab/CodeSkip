from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import asyncio
import time
from pydantic import BaseModel, ValidationError
from screen.capture import ScreenCapture
from audio.transcription import AudioTranscriber
from ai.engine import AIEngine
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ------------------------------
# Pydantic Schemas for Data Validation
# ------------------------------
class AIResponse(BaseModel):
    explanation: str
    python_code: str

# ------------------------------
# Response Caching (CRITICAL FIX)
# ------------------------------
last_response_cache = None
last_capture_time = 0
CACHE_DURATION = 10  # seconds

# ------------------------------
# Helpers: Backend-side AI response validation and formatting
# ------------------------------
def _strip_code_fences(s: str) -> str:
    s = str(s or "")
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s.replace("```", "", 1)
    if s.endswith("```"):
        s = s[:-3]
    return s.strip()

def validate_ai_response(raw_content: str) -> dict:
    """
    Validate and normalize AI output to a strict JSON schema using Pydantic.
    If invalid or not JSON, attempt fallback extraction; if empty, return structured error.
    """
    try:
        data = json.loads(raw_content)
        validated_data = AIResponse(**data)
        validated_data.python_code = _strip_code_fences(validated_data.python_code)
        return validated_data.dict()
    except (ValidationError, json.JSONDecodeError) as e:
        logging.warning(f"AI response validation failed: {e}. Raw content length: {len(raw_content)}")
        import re
        
        code_match = re.search(r"```python[\s\S]*?```", raw_content) or re.search(r"```[\s\S]*?```", raw_content)
        code = code_match.group(0) if code_match else ""
        code = _strip_code_fences(code)
        
        if code_match:
            explanation = raw_content[:code_match.start()].strip()
            after_code = raw_content[code_match.end():].strip()
            if after_code:
                explanation += f"\n\n{after_code}"
        else:
            explanation = raw_content.strip()
        
        if not explanation:
            explanation = "The AI response was not in the expected JSON format, but here's the extracted code:"
        
        if not explanation and not code:
            return {
                "explanation": "The AI response was not in the expected JSON format and no content could be extracted.",
                "python_code": ""
            }
        return {"explanation": explanation, "python_code": code}

app = FastAPI(title="UltraCode Clone Backend")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
screen_capture = ScreenCapture()
audio_transcriber = AudioTranscriber()
ai_engine = AIEngine()

# Store active connections
active_connections = []

@app.get("/")
async def root():
    return {"status": "UltraCode Clone Backend is running"}

@app.get("/status")
async def status():
    return {
        "status": "ok",
        "audio_status": "active",
        "screen_status": "active"
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    print("[WS] Client connected")
    
    global last_response_cache, last_capture_time
    
    try:
        while True:
            data = await websocket.receive_text()
            command = json.loads(data)
            print(f"[WS] Received command: {command}")
            
            if command["type"] == "capture":
                print("[SHOT] Starting capture: screen + audio")
                screen_text = screen_capture.capture_and_extract_text()
                print(f"[SHOT] Screen text length: {len(screen_text)}")
                audio_text = audio_transcriber.get_transcription()
                print(f"[AUDIO] Transcript length: {len(audio_text)}")
                
                print("[AI] Processing begins")
                raw_response = ai_engine.process(screen_text, audio_text)
                response = validate_ai_response(raw_response)
                print("[AI] Processing complete")
                
                # CRITICAL: Cache the response
                last_response_cache = {
                    "screen_text": screen_text,
                    "audio_text": audio_text,
                    "ai_response": response
                }
                last_capture_time = time.time()
                print(f"[CACHE] Response cached at {last_capture_time}")
                
                payload = {
                    "type": "response",
                    "data": last_response_cache
                }
                await websocket.send_json(payload)
                print("[WS] Response sent to client")
                
            elif command["type"] == "solve":
                print("[SOLVE] Requested")
                
                current_time = time.time()
                time_since_capture = current_time - last_capture_time
                
                # CRITICAL: Use cached response if available and recent
                if last_response_cache and time_since_capture < CACHE_DURATION:
                    print(f"[SOLVE] Using cached response from {time_since_capture:.1f}s ago")
                    payload = {
                        "type": "response",
                        "data": last_response_cache
                    }
                    await websocket.send_json(payload)
                    print("[WS] Cached response sent to client")
                else:
                    # Cache is old or doesn't exist, do fresh capture
                    if last_response_cache:
                        print(f"[SOLVE] Cache expired ({time_since_capture:.1f}s old), capturing fresh context")
                    else:
                        print("[SOLVE] No cache available, capturing fresh context")
                    
                    screen_text = screen_capture.capture_and_extract_text()
                    audio_text = audio_transcriber.get_transcription()
                    print(f"[SOLVE] Context: screen={len(screen_text)} chars, audio={len(audio_text)} chars")

                    print("[AI] Processing begins")
                    raw_response = ai_engine.process(screen_text, audio_text)
                    response = validate_ai_response(raw_response)
                    print("[AI] Processing complete")
                    
                    # Update cache
                    last_response_cache = {
                        "screen_text": screen_text,
                        "audio_text": audio_text,
                        "ai_response": response
                    }
                    last_capture_time = current_time
                    print(f"[CACHE] Response cached at {last_capture_time}")

                    payload = {
                        "type": "response",
                        "data": last_response_cache
                    }
                    await websocket.send_json(payload)
                    print("[WS] Fresh solve response sent to client")
                    
            elif command["type"] == "clear":
                print("[WS] Clear requested; resetting cache")
                last_response_cache = None
                last_capture_time = 0
                await websocket.send_json({"type": "cleared"})
            
            elif command["type"] == "stop":
                print("[WS] Stop requested; closing connection")
                break
                
    except WebSocketDisconnect:
        print("[WS] Client disconnected")
        if websocket in active_connections:
            active_connections.remove(websocket)
    except Exception as e:
        print(f"[ERROR] {e}")
        error_message = str(e)
        
        if "API key" in error_message or "api_key" in error_message:
            detailed_error = {
                "type": "error",
                "message": "AI Service Configuration Error",
                "details": "The AI service API key is not configured properly.",
                "resolution": [
                    "1. Open backend/.env file",
                    "2. Add your API key: OPENAI_API_KEY=your_key_here or OPENROUTER_API_KEY=your_key_here",
                    "3. Restart the backend server",
                    "4. Get an API key from: https://platform.openai.com/api-keys or https://openrouter.ai/keys"
                ]
            }
        elif "tesseract" in error_message.lower():
            detailed_error = {
                "type": "error", 
                "message": "OCR Configuration Error",
                "details": "Tesseract OCR is not properly installed or configured.",
                "resolution": [
                    "1. Install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki",
                    "2. Add Tesseract to your system PATH",
                    "3. Or install via package manager: pip install pytesseract",
                    "4. Restart the application after installation"
                ]
            }
        elif "audio" in error_message.lower() or "soundcard" in error_message.lower():
            detailed_error = {
                "type": "error",
                "message": "Audio System Error", 
                "details": "There was an issue with audio capture or processing.",
                "resolution": [
                    "1. Check if your microphone is connected and enabled",
                    "2. Ensure audio permissions are granted to the application",
                    "3. Try restarting your audio device",
                    "4. Check Windows audio settings"
                ]
            }
        elif "websocket" in error_message.lower():
            detailed_error = {
                "type": "error",
                "message": "Connection Error",
                "details": "There was a connection issue with the frontend.",
                "resolution": [
                    "1. Check if the frontend is running",
                    "2. Verify the WebSocket connection on port 8000",
                    "3. Restart both frontend and backend",
                    "4. Check firewall settings"
                ]
            }
        else:
            detailed_error = {
                "type": "error", 
                "message": "Application Error",
                "details": error_message,
                "resolution": [
                    "1. Check the application logs for more details",
                    "2. Try restarting the application",
                    "3. Ensure all dependencies are properly installed",
                    "4. Check the GitHub repository for known issues"
                ]
            }
        
        await websocket.send_json(detailed_error)
        if websocket in active_connections:
            active_connections.remove(websocket)

if __name__ == "__main__":
    print("[SERVER] UltraCode backend starting on 127.0.0.1:8000")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)