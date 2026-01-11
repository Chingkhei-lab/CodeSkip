from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import time
import secrets
import os
from pydantic import BaseModel
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
def validate_ai_response(raw_content: str) -> dict:
    """
    Validate AI response in natural format (not JSON).
    Separates explanation from code blocks.
    """
    if not raw_content or not raw_content.strip():
        return {
            "explanation": "No response received.",
            "python_code": ""
        }
    
    # Extract code blocks (if any)
    code_blocks = []
    explanation_text = raw_content
    
    # Find all code blocks with ``` markers
    import re
    code_pattern = r'```(\w*)\n(.*?)```'
    matches = re.finditer(code_pattern, raw_content, re.DOTALL)
    
    for match in matches:
        lang = match.group(1) or 'python'
        code = match.group(2).strip()
        code_blocks.append(code)
    
    # Remove code blocks from explanation
    explanation_text = re.sub(code_pattern, '', raw_content, flags=re.DOTALL).strip()
    
    # If no code blocks found, check for inline code (without ```)
    if not code_blocks:
        # Look for function definitions, classes, etc.
        if re.search(r'(def\s+\w+|class\s+\w+|function\s+\w+)', raw_content):
            # Might be code without markers
            lines = raw_content.split('\n')
            code_lines = []
            explanation_lines = []
            
            in_code = False
            for line in lines:
                # Simple heuristic: if line starts with indentation or keywords, it's code
                if re.match(r'^\s+(def|class|if|for|while|return|import|from)', line) or in_code:
                    code_lines.append(line)
                    in_code = True
                elif re.match(r'^(def|class)\s+', line):
                    code_lines.append(line)
                    in_code = True
                else:
                    if in_code and not line.strip():
                        code_lines.append(line)
                    else:
                        explanation_lines.append(line)
                        in_code = False
            
            if code_lines:
                code_blocks.append('\n'.join(code_lines))
                explanation_text = '\n'.join(explanation_lines).strip()
    
    # Combine all code blocks
    final_code = '\n\n'.join(code_blocks)
    
    # Clean up explanation
    final_explanation = explanation_text.strip()
    
    # If response is mostly code, put it in code section
    if not final_explanation and final_code:
        final_explanation = "Here's the solution:"
    
    return {
        "explanation": final_explanation,
        "python_code": final_code
    }

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
