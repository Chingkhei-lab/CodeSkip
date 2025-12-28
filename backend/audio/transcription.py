"""Audio Transcription Module

This module handles audio recording and transcription using Whisper.
It captures both microphone input and system audio.
"""

import os
import time
import threading
import tempfile
import numpy as np
import pyaudio
import wave
import whisper
from datetime import datetime

# Import system audio capture
from .system_audio import SystemAudioCapture

class AudioTranscriber:
    def __init__(self, model_size="base", sample_rate=16000, chunk_size=1024, 
                 format=pyaudio.paInt16, channels=1, capture_system_audio=True):
        """
        Initialize the audio transcriber with the specified parameters.
        
        Args:
            model_size: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')
            sample_rate: Audio sample rate in Hz
            chunk_size: Size of audio chunks to process
            format: PyAudio format
            channels: Number of audio channels
            capture_system_audio: Whether to capture system audio in addition to microphone
        """
        self.chunk = chunk_size
        self.format = format
        self.channels = channels
        self.rate = sample_rate
        self.record_seconds = 10  # Default recording length
        self.audio = pyaudio.PyAudio()
        self.capture_system_audio = capture_system_audio
        
        # Load Whisper model
        self.model = whisper.load_model(model_size)
        
        # For continuous recording
        self.is_recording = False
        self.recording_thread = None
        self.audio_buffer = []
        self.last_transcription = ""
        
        # Initialize system audio capture if enabled
        self.system_audio = None
        if self.capture_system_audio:
            try:
                self.system_audio = SystemAudioCapture(
                    sample_rate=sample_rate,
                    channels=channels,
                    chunk_size=chunk_size
                )
                print("System audio capture initialized")
            except Exception as e:
                print(f"Failed to initialize system audio capture: {e}")
                self.system_audio = None
    
    def record_audio(self, seconds=None):
        """Record audio for specified seconds"""
        if seconds:
            self.record_seconds = seconds
            
        stream = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk
        )
        
        frames = []
        for i in range(0, int(self.rate / self.chunk * self.record_seconds)):
            data = stream.read(self.chunk)
            frames.append(data)
            
        stream.stop_stream()
        stream.close()
        
        return frames
    
    def save_audio(self, frames, filename="recording.wav"):
        """Save recorded audio to file"""
        wf = wave.open(filename, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.audio.get_sample_size(self.format))
        wf.setframerate(self.rate)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        return filename
    
    def transcribe_audio(self, audio_file):
        """Transcribe audio file using Whisper"""
        result = self.model.transcribe(audio_file)
        return result["text"]
    
    def record_and_transcribe(self, seconds=None, source="both"):
        """Record and transcribe audio in one step"""
        result = {}
        
        # Record microphone audio
        frames = self.record_audio(seconds)
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_file.close()
        
        self.save_audio(frames, temp_file.name)
        mic_transcription = self.transcribe_audio(temp_file.name)
        result["mic"] = mic_transcription
        
        # Clean up
        os.unlink(temp_file.name)
        
        # Record system audio if available
        if source in ["system", "both"] and self.system_audio:
            system_file = self.system_audio.record_audio(seconds)
            if system_file:
                system_transcription = self.transcribe_audio(system_file)
                result["system"] = system_transcription
                os.unlink(system_file)
        
        # Combine transcriptions
        if len(result) > 1:
            combined = ""
            if "mic" in result and result["mic"]:
                combined += "Microphone: " + result["mic"] + " "
            if "system" in result and result["system"]:
                combined += "System Audio: " + result["system"]
            result["combined"] = combined.strip()
        else:
            result["combined"] = mic_transcription
        
        return result["combined"]
    
    def start_continuous_recording(self):
        """Start continuous recording in background"""
        if self.is_recording:
            return
            
        self.is_recording = True
        self.audio_buffer = []
        
        # Start system audio recording if available
        if self.system_audio:
            self.system_audio.start_recording()
        
        def record_loop():
            stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )
            
            while self.is_recording:
                data = stream.read(self.chunk)
                self.audio_buffer.append(data)
                
                # Keep only last 30 seconds of audio
                max_buffer_size = int(self.rate / self.chunk * 30)
                if len(self.audio_buffer) > max_buffer_size:
                    self.audio_buffer.pop(0)
            
            stream.stop_stream()
            stream.close()
        
        self.recording_thread = threading.Thread(target=record_loop)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        
        print("Audio recording started (microphone" +
              " and system audio)" if self.system_audio else ")")
    
    def stop_continuous_recording(self):
        """Stop continuous recording"""
        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=1.0)
            
        # Stop system audio recording if available
        if self.system_audio:
            self.system_audio.stop_recording()
    
    def get_transcription(self, source="both"):
        """Get transcription from current audio buffer"""
        result = {}
        
        # Transcribe microphone audio
        if not self.audio_buffer:
            result["mic"] = self.last_transcription
        else:
            # Save buffer to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_file.close()
            
            self.save_audio(self.audio_buffer, temp_file.name)
            mic_transcription = self.transcribe_audio(temp_file.name)
            result["mic"] = mic_transcription
            
            # Clean up
            os.unlink(temp_file.name)
        
        # Transcribe system audio if available
        if source in ["system", "both"] and self.system_audio:
            system_transcription = self.system_audio.get_transcription(self.model)
            if system_transcription:
                result["system"] = system_transcription
        
        # Combine transcriptions
        if len(result) > 1:
            combined = ""
            if "mic" in result and result["mic"]:
                combined += "Microphone: " + result["mic"] + " "
            if "system" in result and result["system"]:
                combined += "System Audio: " + result["system"]
            self.last_transcription = combined.strip()
        else:
            self.last_transcription = result.get("mic", "")
        
        return self.last_transcription
    
    def __del__(self):
        """Clean up resources"""
        self.stop_continuous_recording()
        self.audio.terminate()
        
        if self.system_audio:
            del self.system_audio