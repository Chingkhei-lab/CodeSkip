# UltraCode Clone Development Guide

This document provides detailed information about the architecture, implementation, and extension of the UltraCode Clone.

## System Architecture

The UltraCode Clone is built with a multi-layered architecture:

1. **Input Capture Layer**: Captures screen content and audio from the user's environment
2. **Processing Layer**: Processes captured data and generates intelligent responses
3. **Output Layer**: Displays responses in an invisible overlay UI
4. **System Integration Layer**: Integrates with the operating system for hotkeys and screen sharing compatibility

## Core Components

### Backend (FastAPI)

The backend is responsible for processing screen and audio data and generating AI responses:

- **Screen Capture Module**: Captures screen content and extracts text using OCR
- **Audio Transcription Module**: Records and transcribes audio using Whisper
- **AI Engine**: Processes combined context and generates responses using LLMs

### Frontend (Electron + React)

The frontend provides the user interface and system integration:

- **Main Window**: Control panel for managing the application
- **Overlay Window**: Invisible UI that displays AI responses
- **Hotkey System**: Global shortcuts for controlling the application

## Invisible UI Implementation

The invisible UI overlay is implemented using Electron's transparent window feature combined with special rendering techniques:

1. **Transparent Window**: The overlay window is created with `transparent: true` and `frame: false`
2. **Click-Through Mode**: When in stealth mode, the window ignores mouse events with `setIgnoreMouseEvents(true)`
3. **Opacity Control**: The overlay adjusts its opacity based on user interaction and stealth mode

## Hotkey System

The application uses global shortcuts registered through Electron:

- **Ctrl+Shift+Space**: Toggle overlay visibility
- **Ctrl+Shift+S**: Toggle stealth mode
- **Ctrl+Shift+C**: Capture screen and process

## Multi-Platform Compatibility

The application is designed to work across different interview platforms by:

1. **Using transparent overlays** that don't appear in screen sharing
2. **Capturing screen content** regardless of the underlying application
3. **Processing audio** from both microphone and system sources

## Extending the Application

### Adding New AI Models

To add support for a new AI model:

1. Modify `backend/ai/engine.py` to include the new model
2. Update the environment variables in `.env` file
3. Implement the necessary API calls for the new model

### Improving OCR Accuracy

To enhance OCR accuracy for code:

1. Modify `backend/screen/capture.py` to improve image preprocessing
2. Adjust Tesseract configuration parameters
3. Consider implementing specialized OCR for code syntax

### Adding New Features

To add new features to the application:

1. **Backend**: Add new endpoints in `main.py` and implement the necessary logic
2. **Frontend**: Create new React components and update the UI
3. **Integration**: Connect the frontend and backend through WebSocket

## Security Considerations

When developing and using this application:

1. **API Keys**: Never commit API keys to the repository
2. **Data Privacy**: Be mindful of the data being captured and processed
3. **Usage Policies**: Respect the terms of service of interview platforms and AI providers

## Testing

To test the application:

1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Test the interaction between components
3. **Platform Tests**: Test compatibility with different interview platforms

## Deployment

To deploy the application:

1. **Backend**: Deploy the FastAPI server to a cloud provider or run locally
2. **Frontend**: Package the Electron app for distribution
3. **Configuration**: Provide clear instructions for setting up API keys and dependencies