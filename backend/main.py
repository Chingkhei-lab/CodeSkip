from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import asyncio
from pydantic import BaseModel, ValidationError
from screen.capture import ScreenCapture
from audio.transcription import AudioTranscriber
from ai.engine import AIEngine

# ------------------------------
# Pydantic Schemas for Data Validation
# ------------------------------
class AIResponse(BaseModel):
    explanation: str
    python_code: str

# ------------------------------
# Helpers: Backend-side AI response validation and formatting
# ------------------------------
def _strip_code_fences(s: str) -> str:
    s = str(s or "")
    # Remove leading/backtick fences and trailing backticks if present
    s = s.strip()
    if s.startswith("```"):
        # remove leading fence like ```python or ```
        s = s.split("\n", 1)[1] if "\n" in s else s.replace("```", "", 1)
    if s.endswith("```"):
        s = s[:-3]
    return s.strip()

import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ... existing code ...

def validate_ai_response(raw_content: str) -> dict:
    """
    Validate and normalize AI output to a strict JSON schema using Pydantic.
    If invalid or not JSON, attempt fallback extraction; if empty, return structured error.
    """
    try:
        data = json.loads(raw_content)
        validated_data = AIResponse(**data)
        validated_data.python_code = _strip_code_fences(validated_data.python_code)
        # Do NOT trim explanation; preserve full content for completeness
        return validated_data.dict()
    except (ValidationError, json.JSONDecodeError) as e:
        logging.warning(f"AI response validation failed: {e}. Raw content length: {len(raw_content)}")
        import re
        
        # Try to extract code blocks first
        code_match = re.search(r"```python[\s\S]*?```", raw_content) or re.search(r"```[\s\S]*?```", raw_content)
        code = code_match.group(0) if code_match else ""
        code = _strip_code_fences(code)
        
        # Extract explanation - preserve ALL content before code, not just first 2 sentences
        if code_match:
            explanation = raw_content[:code_match.start()].strip()
            # If there's content after the code block, append it to explanation
            after_code = raw_content[code_match.end():].strip()
            if after_code:
                explanation += f"\n\n{after_code}"
        else:
            explanation = raw_content.strip()
        
        # If no explanation content, provide a default message
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
    allow_origins=["*"],  # In production, restrict this to your frontend URL
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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    print("[WS] Client connected")
    
    try:
        while True:
            # Receive command from frontend
            data = await websocket.receive_text()
            command = json.loads(data)
            print(f"[WS] Received command: {command}")
            
            if command["type"] == "capture":
                print("[SHOT] Starting capture: screen + audio")
                # Capture screen and audio
                screen_text = screen_capture.capture_and_extract_text()
                print(f"[SHOT] Screen text length: {len(screen_text)}")
                audio_text = audio_transcriber.get_transcription()
                print(f"[AUDIO] Transcript length: {len(audio_text)}")
                
                # Process with AI
                print("[AI] Processing begins")
                raw_response = ai_engine.process(screen_text, audio_text)
                response = validate_ai_response(raw_response)
                print("[AI] Processing complete")
                
                # Send response back to client
                payload = {
                    "type": "response",
                    "data": {
                        "screen_text": screen_text,
                        "audio_text": audio_text,
                        "ai_response": response
                    }
                }
                await websocket.send_json(payload)
                print("[WS] Response sent to client")
            elif command["type"] == "solve":
                print("[SOLVE] Requested; capturing latest context and invoking AI")
                # Capture most recent context (on-demand capture for parity with 'capture')
                screen_text = screen_capture.capture_and_extract_text()
                audio_text = audio_transcriber.get_transcription()
                print(f"[SOLVE] Context: screen={len(screen_text)} chars, audio={len(audio_text)} chars")

                print("[AI] Processing begins")
                raw_response = ai_engine.process(screen_text, audio_text)
                response = validate_ai_response(raw_response)
                print("[AI] Processing complete")

                payload = {
                    "type": "response",
                    "data": {
                        "screen_text": screen_text,
                        "audio_text": audio_text,
                        "ai_response": response
                    }
                }
                await websocket.send_json(payload)
                print("[WS] Solve response sent to client")
            elif command["type"] == "clear":
                # No persistent state server-side yet, but acknowledge for frontend UX
                print("[WS] Clear requested; resetting transient context (noop)")
                await websocket.send_json({"type": "cleared"})
            
            elif command["type"] == "stop":
                print("[WS] Stop requested; closing connection")
                break
                
    except WebSocketDisconnect:
        print("[WS] Client disconnected")
        active_connections.remove(websocket)
    except Exception as e:
        print(f"[ERROR] {e}")
        error_message = str(e)
        
        # Provide detailed error messages based on common issues
        if "API key" in error_message or "api_key" in error_message:
            detailed_error = {
                "type": "error",
                "message": "AI Service Configuration Error",
                "details": "The AI service API key is not configured properly.",
                "resolution": [
                    "1. Open backend/.env file",
                    "2. Add your API key: OPENAI_API_KEY=your_key_here or OPENROUTER_API_KEY=your_key_here",
                    "3. Restart the backend server",
                    "4. Get an API key from: https://platform.openai.com/api-keys  or https://openrouter.ai/keys "
                ]
            }
        elif "tesseract" in error_message.lower():
            detailed_error = {
                "type": "error", 
                "message": "OCR Configuration Error",
                "details": "Tesseract OCR is not properly installed or configured.",
                "resolution": [
                    "1. Install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki ",
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
        active_connections.remove(websocket)

if __name__ == "__main__":
    print("[SERVER] UltraCode backend starting on 127.0.0.1:8000")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
