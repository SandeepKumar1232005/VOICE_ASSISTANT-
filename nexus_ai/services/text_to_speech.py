"""
Nexus AI — Text-to-Speech Service

Primary: pyttsx3 (offline, reliable, zero setup)
Optional: Piper TTS (natural-sounding, if installed)
"""

import os
import queue
import threading
from typing import Optional

from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.helpers import load_json_config, sanitize_for_speech

logger = get_logger("TTS")


class TextToSpeechService:
    """
    Text-to-Speech service with pyttsx3 as primary engine
    and optional Piper TTS for more natural voices.
    
    Thread-safe: uses a speech queue to prevent overlapping speech.
    """

    def __init__(self):
        settings = load_json_config("settings.json")
        voice_config = settings.get("voice", {})

        self.engine_name = voice_config.get("tts_engine", "pyttsx3")
        self.rate = voice_config.get("rate", 175)
        self.volume = voice_config.get("volume", 1.0)
        self.piper_model = voice_config.get("piper_model", "en_US-lessac-medium")

        self._speech_queue = queue.Queue()
        self._engine = None
        self._piper = None
        self._is_speaking = False
        self._lock = threading.Lock()

        self._init_engine()

        # Start the speech worker thread
        self._worker_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self._worker_thread.start()

    def _init_engine(self):
        """Initialize the TTS engine."""
        if self.engine_name == "piper":
            if self._init_piper():
                return
            logger.warning("Piper TTS unavailable, falling back to pyttsx3")

        self._init_pyttsx3()

    def _init_pyttsx3(self):
        """Initialize pyttsx3 engine."""
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.rate)
            self._engine.setProperty("volume", self.volume)

            # Try to find a good voice
            voices = self._engine.getProperty("voices")
            for voice in voices:
                if "Zira" in voice.name or "female" in voice.name.lower():
                    self._engine.setProperty("voice", voice.id)
                    break

            self.engine_name = "pyttsx3"
            logger.info("pyttsx3 TTS engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize pyttsx3: {e}")

    def _init_piper(self) -> bool:
        """
        Initialize Piper TTS if available.
        Returns True if successful.
        """
        try:
            # Check if piper-tts is installed
            import subprocess
            result = subprocess.run(
                ["piper", "--help"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                self.engine_name = "piper"
                logger.info(f"Piper TTS initialized with model: {self.piper_model}")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        except Exception as e:
            logger.debug(f"Piper check failed: {e}")

        return False

    def speak(self, text: str, block: bool = False):
        """
        Queue text for speech output.
        
        Args:
            text: Text to speak
            block: If True, wait until speech is complete
        """
        if not text or not text.strip():
            return

        # Sanitize text for speech
        clean_text = sanitize_for_speech(text)
        if not clean_text:
            return

        logger.info(f"[Speaking]: {clean_text[:100]}{'...' if len(clean_text) > 100 else ''}")
        print(f"\n  🔊 Nexus: {clean_text}\n")

        self._speech_queue.put(clean_text)

        if block:
            # Wait until queue is empty and not speaking
            self._speech_queue.join()

    def _speech_worker(self):
        """Background thread that processes the speech queue."""
        while True:
            try:
                text = self._speech_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                self._is_speaking = True
                if self.engine_name == "piper":
                    self._speak_piper(text)
                else:
                    self._speak_pyttsx3(text)
            except Exception as e:
                logger.error(f"TTS error: {e}")
            finally:
                self._is_speaking = False
                self._speech_queue.task_done()

    def _speak_pyttsx3(self, text: str):
        """Speak using pyttsx3."""
        try:
            with self._lock:
                if self._engine is None:
                    self._init_pyttsx3()
                if self._engine:
                    self._engine.say(text)
                    self._engine.runAndWait()
        except Exception as e:
            logger.error(f"pyttsx3 speech error: {e}")
            # Try reinitializing
            self._engine = None

    def _speak_piper(self, text: str):
        """Speak using Piper TTS via subprocess."""
        try:
            import subprocess
            import tempfile
            import sounddevice as sd
            import soundfile as sf

            # Generate WAV with Piper
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                process = subprocess.run(
                    ["piper", "--model", self.piper_model, "--output_file", tmp_path],
                    input=text,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if process.returncode == 0 and os.path.exists(tmp_path):
                    # Play the WAV file
                    data, samplerate = sf.read(tmp_path)
                    sd.play(data, samplerate)
                    sd.wait()
                else:
                    # Fallback to pyttsx3
                    logger.warning("Piper failed, falling back to pyttsx3")
                    self._speak_pyttsx3(text)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        except Exception as e:
            logger.warning(f"Piper speech error: {e}, falling back to pyttsx3")
            self._speak_pyttsx3(text)

    def stop(self):
        """Stop current speech and clear the queue."""
        # Clear queue
        while not self._speech_queue.empty():
            try:
                self._speech_queue.get_nowait()
                self._speech_queue.task_done()
            except queue.Empty:
                break

        # Stop current speech
        if self.engine_name == "pyttsx3" and self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass

    @property
    def is_speaking(self) -> bool:
        """Check if TTS is currently speaking."""
        return self._is_speaking
