"""Audio Transcription Module - Secure Version

This module handles audio recording and transcription using Whisper.
It captures both microphone input and system audio with secure file handling.
"""

import os
import time
import threading
import tempfile
import numpy as np
import pyaudio
import wave
import whisper
import logging
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class AudioTranscriber:
    def __init__(self, model_size="base", sample_rate=16000, chunk_size=1024,
                 format=pyaudio.paInt16, channels=1, capture_system_audio=False):
        """
        Initialize the audio transcriber with the specified parameters.

        Args:
            model_size: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')
            sample_rate: Audio sample rate in Hz
            chunk_size: Size of audio chunks to process
            format: PyAudio format
            channels: Number of audio channels
            capture_system_audio: Whether to capture system audio (disabled for security)
        """
        self.chunk = chunk_size
        self.format = format
        self.channels = channels
        self.rate = sample_rate
        self.record_seconds = 10  # Default recording length
        self.audio = pyaudio.PyAudio()
        self.capture_system_audio = False  # Disabled for security

        # Load Whisper model
        try:
            logger.info(f"Loading Whisper model: {model_size}")
            self.model = whisper.load_model(model_size)
            logger.info("✓ Whisper model loaded")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

        # For continuous recording
        self.is_recording = False
        self.recording_thread = None
        self.audio_buffer = []
        self.last_transcription = ""

        # Track temp files for secure cleanup
        self._temp_files = []

        # System audio disabled for security
        self.system_audio = None
        if self.capture_system_audio:
            logger.warning("⚠ System audio capture disabled for security reasons")

    def record_audio(self, seconds: Optional[int] = None) -> list:
        """
        Record audio for specified seconds

        Args:
            seconds: Recording duration in seconds

        Returns:
            list: Recorded audio frames
        """
        if seconds:
            self.record_seconds = seconds

        try:
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

            logger.info(f"Recorded {len(frames)} frames ({self.record_seconds}s)")
            return frames
        except Exception as e:
            logger.error(f"Audio recording failed: {e}")
            return []

    def save_audio(self, frames: list, filename: Optional[str] = None) -> str:
        """
        Save recorded audio to file

        Args:
            frames: Audio frames to save
            filename: Output filename. If None, creates secure temp file.

        Returns:
            str: Path to saved file
        """
        try:
            if filename is None:
                # Create secure temp file
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix='.wav',
                    prefix='audio_'
                )
                filename = temp_file.name
                temp_file.close()
                self._temp_files.append(filename)

            wf = wave.open(filename, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(frames))
            wf.close()

            logger.debug(f"Audio saved: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Failed to save audio: {e}")
            raise

    def transcribe_audio(self, audio_file: str) -> str:
        """
        Transcribe audio file using Whisper

        Args:
            audio_file: Path to audio file

        Returns:
            str: Transcribed text
        """
        try:
            logger.info("Transcribing audio...")
            result = self.model.transcribe(audio_file)
            text = result["text"]
            logger.info(f"✓ Transcription complete: {len(text)} chars")
            return text
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""

    def record_and_transcribe(self, seconds: Optional[int] = None, source: str = "mic") -> str:
        """
        Record and transcribe audio in one step

        Args:
            seconds: Recording duration
            source: Audio source (only "mic" supported for security)

        Returns:
            str: Transcribed text
        """
        # Record microphone audio
        frames = self.record_audio(seconds)

        if not frames:
            return ""

        # Save to temporary file
        temp_file = None
        try:
            temp_file = self.save_audio(frames)
            transcription = self.transcribe_audio(temp_file)
            return transcription
        except Exception as e:
            logger.error(f"Record and transcribe failed: {e}")
            return ""
        finally:
            # Secure cleanup
            if temp_file:
                self.secure_delete(temp_file)

    def start_continuous_recording(self):
        """Start continuous recording in background"""
        if self.is_recording:
            logger.warning("Already recording")
            return

        self.is_recording = True
        self.audio_buffer = []

        def record_loop():
            try:
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
            except Exception as e:
                logger.error(f"Recording loop error: {e}")
                self.is_recording = False

        self.recording_thread = threading.Thread(target=record_loop, daemon=True)
        self.recording_thread.start()
        logger.info("✓ Continuous audio recording started")

    def stop_continuous_recording(self):
        """Stop continuous recording"""
        if not self.is_recording:
            return

        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=1.0)

        logger.info("✓ Continuous recording stopped")

    def get_transcription(self, source: str = "mic") -> str:
        """
        Get transcription from current audio buffer

        Args:
            source: Audio source (only "mic" supported)

        Returns:
            str: Transcribed text
        """
        if not self.audio_buffer:
            logger.debug("No audio buffer, returning last transcription")
            return self.last_transcription

        temp_file = None
        try:
            # Save buffer to temporary file
            temp_file = self.save_audio(self.audio_buffer)
            transcription = self.transcribe_audio(temp_file)
            self.last_transcription = transcription
            return transcription
        except Exception as e:
            logger.error(f"Get transcription failed: {e}")
            return self.last_transcription
        finally:
            # Secure cleanup
            if temp_file:
                self.secure_delete(temp_file)

    def secure_delete(self, filepath: str):
        """
        Securely delete file by overwriting with random data first

        Args:
            filepath: Path to file to delete
        """
        try:
            if not os.path.exists(filepath):
                return

            # Overwrite with random data
            file_size = os.path.getsize(filepath)
            with open(filepath, 'wb') as f:
                f.write(os.urandom(file_size))

            # Delete the file
            os.unlink(filepath)
            logger.debug(f"Securely deleted: {filepath}")

            # Remove from tracking
            if filepath in self._temp_files:
                self._temp_files.remove(filepath)
        except Exception as e:
            logger.error(f"Secure deletion failed for {filepath}: {e}")
            try:
                # Fallback to normal delete
                os.unlink(filepath)
                if filepath in self._temp_files:
                    self._temp_files.remove(filepath)
            except:
                pass

    def cleanup(self):
        """Clean up all temporary files securely"""
        for temp_file in list(self._temp_files):
            self.secure_delete(temp_file)
        self._temp_files.clear()
        logger.info("✓ Audio cleanup complete")

    def __del__(self):
        """Clean up resources"""
        try:
            self.stop_continuous_recording()
            self.cleanup()
            self.audio.terminate()
        except:
            pass
