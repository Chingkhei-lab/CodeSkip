from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import time
import secrets
import os
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv
from screen.capture import ScreenCapture
from audio.transcription import AudioTranscriber
from ai.engine import AIEngine
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ============================================
# SECURITY: Authentication Token
# ============================================
AUTH_TOKEN = os.getenv("WS_AUTH_TOKEN")
if not AUTH_TOKEN:
    AUTH_TOKEN = secrets.token_urlsafe(32)
    logging.warning(f"⚠️  No WS_AUTH_TOKEN in .env, generated: {AUTH_TOKEN}")
    logging.warning(f"⚠️  Add to backend/.env: WS_AUTH_TOKEN={AUTH_TOKEN}")
else:
    logging.info("✓ WebSocket authentication enabled")

# ============================================
# Pydantic Schemas for Data Validation
# ============================================
class AIResponse(BaseModel):
    explanation: str
    python_code: str

# ============================================
# Response Caching & Screenshot Tracking
# ============================================
last_response_cache = None
last_capture_time = 0
last_screenshot_data = None
CACHE_DURATION = 10  # seconds

# ============================================
# Helpers: Backend-side AI response validation
# ============================================
def _strip_code_fences(s: str) -> str:
    s = str(s or "")
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s.replace("```", "", 1)
    if s.endswith("```"):
        s = s[:-3]
    return s.strip()

def validate_ai_response(raw_content: str) -> dict:
    """Validate and normalize AI output to a strict JSON schema using Pydantic."""
    try:
        data = json.loads(raw_content)
        validated_data = AIResponse(**data)
        validated_data.python_code = _strip_code_fences(validated_data.python_code)
        return validated_data.dict()
    except (ValidationError, json.JSONDecodeError) as e:
        logging.warning(f"AI response validation failed: {e}")
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

# ============================================
# FastAPI App
# ============================================
app = FastAPI(title="UltraCode Clone Backend - Secured")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    """Secure WebSocket endpoint with authentication and screenshot validation"""
    
    # SECURITY: Validate token before accepting connection
    if token != AUTH_TOKEN:
        logging.warning(f"⚠️  Unauthorized WebSocket connection attempt")
        await websocket.close(code=1008, reason="Unauthorized")
        return
    
    await websocket.accept()
    active_connections.append(websocket)
    logging.info(f"✓ Authenticated client connected")
    
    global last_response_cache, last_capture_time, last_screenshot_data
    
    try:
        while True:
            data = await websocket.receive_text()
            command = json.loads(data)
            logging.info(f"[WS] Received command: {command['type']}")
            
            if command["type"] == "capture":
                logging.info("[CAPTURE] Starting screen + audio capture")
                try:
                    screen_text = screen_capture.capture_and_extract_text()
                    logging.info(f"[CAPTURE] Screen text: {len(screen_text)} chars")
                    audio_text = audio_transcriber.get_transcription()
                    logging.info(f"[CAPTURE] Audio text: {len(audio_text)} chars")
                    
                    # Store screenshot data
                    current_time = time.time()
                    last_screenshot_data = {
                        "screen_text": screen_text,
                        "audio_text": audio_text,
                        "timestamp": current_time
                    }
                    
                    logging.info("[AI] Processing analysis")
                    raw_response = ai_engine.process(screen_text, audio_text)
                    response = validate_ai_response(raw_response)
                    logging.info("[AI] Analysis complete")
                    
                    # Cache the response
                    last_response_cache = {
                        "screen_text": screen_text,
                        "audio_text": audio_text,
                        "ai_response": response
                    }
                    last_capture_time = current_time
                    
                    payload = {
                        "type": "response",
                        "data": last_response_cache
                    }
                    await websocket.send_json(payload)
                    logging.info("[WS] Response sent")
                    
                except Exception as e:
                    logging.error(f"[CAPTURE] Error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Capture failed",
                        "details": "Please try again"
                    })
                    
            elif command["type"] == "solve":
                # CRITICAL: Check if screenshot was taken
                if not last_screenshot_data:
                    logging.warning("[SOLVE] Rejected - No screenshot taken")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Take a screenshot first",
                        "details": "Press Ctrl+Shift+C to capture before solving"
                    })
                    continue
                
                # Check if screenshot is too old (more than 5 minutes)
                current_time = time.time()
                screenshot_age = current_time - last_screenshot_data.get("timestamp", 0)
                if screenshot_age > 300:  # 5 minutes
                    logging.warning(f"[SOLVE] Screenshot too old ({screenshot_age:.0f}s)")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Screenshot expired",
                        "details": "Take a new screenshot (Ctrl+Shift+C)"
                    })
                    continue
                
                logging.info("[SOLVE] Requested")
                
                # Use cached response if available and recent
                time_since_capture = current_time - last_capture_time
                
                if last_response_cache and time_since_capture < CACHE_DURATION:
                    logging.info(f"[SOLVE] Using cached response ({time_since_capture:.1f}s old)")
                    payload = {
                        "type": "response",
                        "data": last_response_cache
                    }
                    await websocket.send_json(payload)
                else:
                    # Use screenshot data for fresh analysis
                    logging.info("[SOLVE] Generating fresh analysis from screenshot")
                    try:
                        raw_response = ai_engine.process(
                            last_screenshot_data["screen_text"],
                            last_screenshot_data["audio_text"]
                        )
                        response = validate_ai_response(raw_response)
                        
                        last_response_cache = {
                            "screen_text": last_screenshot_data["screen_text"],
                            "audio_text": last_screenshot_data["audio_text"],
                            "ai_response": response
                        }
                        last_capture_time = current_time
                        
                        payload = {
                            "type": "response",
                            "data": last_response_cache
                        }
                        await websocket.send_json(payload)
                        logging.info("[WS] Fresh response sent")
                    except Exception as e:
                        logging.error(f"[SOLVE] Error: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "message": "Analysis failed",
                            "details": "Please try again"
                        })
                    
            elif command["type"] == "clear":
                logging.info("[CLEAR] Resetting state")
                last_response_cache = None
                last_capture_time = 0
                last_screenshot_data = None
                await websocket.send_json({"type": "cleared"})
            
            elif command["type"] == "stop":
                logging.info("[STOP] Closing connection")
                break
                
    except WebSocketDisconnect:
        logging.info(f"Client disconnected")
    except Exception as e:
        logging.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Connection error",
                "details": "Please reconnect"
            })
        except:
            pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)
        logging.info(f"Connection closed. Active: {len(active_connections)}")

if __name__ == "__main__":
    print("="*50)
    print("UltraCode Secure Backend Starting")
    print("="*50)
    print(f"WebSocket Auth Token: {AUTH_TOKEN}")
    print(f"Add this to frontend: WS_AUTH_TOKEN={AUTH_TOKEN}")
    print("="*50)
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)