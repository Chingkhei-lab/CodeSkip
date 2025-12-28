"""
System Audio Capture Module for Ultracode Clone

This module captures system audio (what the user hears) in addition to microphone input.
It uses platform-specific libraries to access system audio streams.
"""

import os
import time
import threading
import numpy as np
import wave
import tempfile
from datetime import datetime

# Platform-specific imports
import platform
system = platform.system()

if system == "Windows":
    import soundcard as sc
elif system == "Darwin":  # macOS
    import soundcard as sc
elif system == "Linux":
    import soundcard as sc
else:
    raise ImportError(f"Unsupported platform: {system}")

class SystemAudioCapture:
    def __init__(self, sample_rate=16000, channels=1, chunk_size=1024):
        """
        Initialize the system audio capture module.
        
        Args:
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels (1 for mono, 2 for stereo)
            chunk_size: Size of audio chunks to process
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.recording = False
        self.audio_buffer = []
        self.lock = threading.Lock()
        self.recording_thread = None
        self.temp_dir = tempfile.gettempdir()
        
        # Get default output device (system audio)
        try:
            self.output_device = sc.default_speaker()
            print(f"Using system audio device: {self.output_device.name}")
        except Exception as e:
            print(f"Warning: Could not access system audio: {e}")
            self.output_device = None

    def start_recording(self):
        """Start recording system audio in a background thread"""
        if self.recording:
            return
            
        self.recording = True
        self.audio_buffer = []
        self.recording_thread = threading.Thread(target=self._record_audio)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        print("System audio recording started")
        
    def stop_recording(self):
        """Stop the background recording thread"""
        self.recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)
            self.recording_thread = None
        print("System audio recording stopped")
        
    def _record_audio(self):
        """Background thread function to continuously record system audio"""
        if not self.output_device:
            print("No system audio device available")
            return
            
        try:
            with self.output_device.recorder(samplerate=self.sample_rate, channels=self.channels) as recorder:
                while self.recording:
                    # Record a chunk of audio
                    data = recorder.record(numframes=self.chunk_size)
                    
                    # Add to buffer (thread-safe)
                    with self.lock:
                        self.audio_buffer.append(data)
        except Exception as e:
            print(f"Error recording system audio: {e}")
            self.recording = False
            
    def save_audio(self, duration=None):
        """
        Save the recorded audio buffer to a WAV file.
        
        Args:
            duration: Optional duration in seconds to save (from the end of the buffer)
                     If None, saves the entire buffer
                     
        Returns:
            Path to the saved audio file
        """
        with self.lock:
            if not self.audio_buffer:
                print("No audio data to save")
                return None
                
            # Convert buffer to numpy array
            audio_data = np.concatenate(self.audio_buffer)
            
            # If duration specified, trim the buffer
            if duration:
                frames_to_keep = int(duration * self.sample_rate)
                if frames_to_keep < len(audio_data):
                    audio_data = audio_data[-frames_to_keep:]
            
            # Normalize audio data
            audio_data = np.clip(audio_data, -1.0, 1.0)
            audio_data = (audio_data * 32767).astype(np.int16)
            
            # Create a timestamped filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.temp_dir, f"system_audio_{timestamp}.wav")
            
            # Write to WAV file
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16-bit audio
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())
                
            print(f"System audio saved to {filename}")
            return filename
            
    def get_last_seconds(self, seconds):
        """
        Get the last N seconds of recorded audio as a numpy array.
        
        Args:
            seconds: Number of seconds to retrieve
            
        Returns:
            Numpy array of audio data
        """
        with self.lock:
            if not self.audio_buffer:
                return np.array([])
                
            # Convert buffer to numpy array
            audio_data = np.concatenate(self.audio_buffer)
            
            # Calculate frames to keep
            frames_to_keep = int(seconds * self.sample_rate)
            if frames_to_keep < len(audio_data):
                return audio_data[-frames_to_keep:]
            else:
                return audio_data
                
    def clear_buffer(self):
        """Clear the audio buffer to free memory"""
        with self.lock:
            self.audio_buffer = []

    def record_audio(self, seconds=5):
        """Record system audio for a fixed duration and return WAV file path"""
        if not self.output_device:
            print("No system audio device available")
            return None
        try:
            chunks = []
            frames_total = int(self.sample_rate * seconds)
            frames_recorded = 0
            with self.output_device.recorder(samplerate=self.sample_rate, channels=self.channels) as recorder:
                while frames_recorded < frames_total:
                    data = recorder.record(numframes=self.chunk_size)
                    chunks.append(data)
                    frames_recorded += len(data)
            # Convert to int16 PCM and save to temp WAV
            audio_data = np.concatenate(chunks)
            audio_data = np.clip(audio_data, -1.0, 1.0)
            audio_data = (audio_data * 32767).astype(np.int16)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.temp_dir, f"system_audio_{timestamp}.wav")
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())
            print(f"System audio recorded to {filename}")
            return filename
        except Exception as e:
            print(f"Error recording fixed-duration system audio: {e}")
            return None

    def get_transcription(self, model, seconds=None):
        """Transcribe system audio from buffer or last N seconds using provided Whisper model"""
        try:
            # Prefer a trimmed segment if seconds provided
            with self.lock:
                if not self.audio_buffer:
                    return ""
                audio_data = np.concatenate(self.audio_buffer)
            if seconds:
                frames_to_keep = int(seconds * self.sample_rate)
                if frames_to_keep < len(audio_data):
                    audio_data = audio_data[-frames_to_keep:]
            # Convert to int16 PCM and write to temp WAV
            audio_data = np.clip(audio_data, -1.0, 1.0)
            audio_pcm = (audio_data * 32767).astype(np.int16)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            tmp.close()
            try:
                with wave.open(tmp.name, 'wb') as wf:
                    wf.setnchannels(self.channels)
                    wf.setsampwidth(2)
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(audio_pcm.tobytes())
                result = model.transcribe(tmp.name)
                text = result.get("text", "") if isinstance(result, dict) else str(result)
                return text
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
        except Exception as e:
            print(f"Error transcribing system audio: {e}")
            return ""