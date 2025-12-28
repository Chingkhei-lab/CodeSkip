# UltraCode Clone

A functional clone of Ultracode.ai that provides real-time AI assistance during coding interviews.

## Features

- **Screen Capture & OCR**: Captures active screen region and extracts coding/text content
- **Audio Processing**: Listens to and transcribes audio from microphone and system
- **AI Integration**: Combines screen and audio context to generate accurate responses
- **Invisible UI**: Overlay system that's undetectable during screen sharing
- **Hotkey System**: OS-level hotkey integration for seamless control
- **Multi-platform Support**: Works across major interview platforms

## Project Structure

```
ultracode-clone/
├── backend/             # FastAPI backend server
│   ├── ai/              # AI integration and reasoning engine
│   ├── audio/           # Audio capture and transcription
│   ├── screen/          # Screen capture and OCR
│   └── main.py          # Main server file
├── frontend/            # Electron.js + React frontend
│   ├── public/          # Static assets
│   └── src/             # React components and logic
├── shared/              # Shared utilities and types
└── docs/                # Documentation and architecture diagrams
```

## Setup Instructions

### Prerequisites

- Node.js (v16+)
- Python (v3.9+)
- Electron
- FFmpeg (for audio processing)

### Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # On Windows
pip install -r requirements.txt
python main.py
```

### Frontend Setup

```bash
cd frontend
npm install
npm start
```

## Usage

1. Start both backend and frontend applications
2. Use the hotkey `Ctrl+Shift+Space` to activate the assistant
3. The app will automatically capture screen content and audio
4. View AI-generated responses in the overlay window

## Development

See the [Development Guide](docs/DEVELOPMENT.md) for detailed information on the architecture and implementation details.