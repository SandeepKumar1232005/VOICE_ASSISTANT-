"""
Nexus AI — Voice Agent

Handles wake word detection, continuous listening, and speech capture.
Uses the existing offline RF model for wake word + faster-whisper for commands.
"""

import os
import time
import numpy as np
import pyaudio

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.services.speech_to_text import SpeechToTextService
from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.helpers import load_json_config

logger = get_logger("VoiceAgent")


class VoiceAgent(BaseAgent):
    """
    Voice Agent — Entry point for all voice interactions.
    
    Responsibilities:
        - Wake word detection (offline RF model or Vosk fallback)
        - Audio recording with voice activity detection
        - Speech-to-text conversion via faster-whisper
        - Noise reduction preprocessing
    """

    # PyAudio configuration
    CHUNK = 8000    # 0.5 seconds at 16kHz
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    def __init__(self):
        super().__init__("VoiceAgent")

        settings = load_json_config("settings.json")
        self.wake_words = settings.get("wake_words", ["nexus", "hey nexus"])
        self.assistant_name = settings.get("assistant_name", "Nexus")

        # Initialize STT service
        self.stt = SpeechToTextService()

        # Load offline wake word model (from old Jarvis implementation)
        self.brain = None
        self._load_wake_word_model()

        logger.info(f"Voice Agent ready. Wake words: {self.wake_words}")

    def _load_wake_word_model(self):
        """Load the offline RF model for wake word detection."""
        # Check multiple possible locations
        possible_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                         "datasets", "jarvis_rf_model.pkl"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "data", "models", "wake_word_model.pkl"),
        ]

        for model_path in possible_paths:
            if os.path.exists(model_path):
                try:
                    import joblib
                    self.brain = joblib.load(model_path)
                    logger.info(f"Offline wake word model loaded from {model_path}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to load wake word model: {e}")

        logger.warning("No offline wake word model found. Using keyword-based detection.")

    def _get_mfcc(self, audio_data: bytes) -> np.ndarray:
        """Convert raw audio bytes to MFCC features for the wake word model."""
        import librosa

        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Ensure minimum length (2 seconds)
        if len(audio_np) < self.RATE * 2:
            audio_np = np.pad(audio_np, (0, max(0, self.RATE * 2 - len(audio_np))))

        mfccs = librosa.feature.mfcc(y=audio_np, sr=self.RATE, n_mfcc=40)
        return np.mean(mfccs.T, axis=0).reshape(1, -1)

    def listen_for_wake_word(self) -> bool:
        """
        Continuously listen for the wake word.
        
        Uses the offline RF model if available, otherwise falls back
        to Vosk keyword spotting.
        
        Returns:
            True when wake word is detected
        """
        if self.brain:
            return self._listen_wake_word_rf()
        else:
            return self._listen_wake_word_vosk()

    def _listen_wake_word_rf(self) -> bool:
        """Listen for wake word using the offline Random Forest model."""
        p = pyaudio.PyAudio()

        try:
            stream = p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
            )
        except Exception as e:
            logger.error(f"Cannot open microphone: {e}")
            return False

        logger.debug(f"Listening for wake word (offline AI)...")

        buffer = b""
        chunk_count = 0
        consecutive_spikes = 0

        try:
            while True:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                buffer += data
                chunk_count += 1

                if chunk_count >= 4:  # ~2 seconds of audio
                    features = self._get_mfcc(buffer)
                    probabilities = self.brain.predict_proba(features)[0]
                    probability_wake = probabilities[1]

                    if probability_wake > 0.10:
                        logger.debug(f"Wake word probability: {probability_wake * 100:.1f}%")

                    if probability_wake >= 0.35:
                        consecutive_spikes += 1
                    else:
                        consecutive_spikes = 0

                    if consecutive_spikes >= 2:
                        logger.info(f"⚡ Wake word detected! (confidence: {probability_wake * 100:.1f}%)")
                        return True

                    # Slide buffer
                    buffer = buffer[self.CHUNK * 2:]
                    chunk_count -= 1
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"Wake word detection error: {e}")
            return False
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

    def _listen_wake_word_vosk(self) -> bool:
        """Listen for wake word using Vosk keyword spotting (fallback)."""
        try:
            from vosk import Model, KaldiRecognizer
            import json as json_module

            # Use the existing Vosk model
            model_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "vosk-model-small-en-us-0.15",
            )

            if not os.path.exists(model_path):
                logger.error(f"Vosk model not found at {model_path}")
                return self._listen_wake_word_simple()

            model = Model(model_path)
            rec = KaldiRecognizer(model, self.RATE)

            p = pyaudio.PyAudio()
            stream = p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
            )

            logger.debug("Listening for wake word (Vosk)...")

            try:
                while True:
                    data = stream.read(self.CHUNK, exception_on_overflow=False)
                    if rec.AcceptWaveform(data):
                        result = json_module.loads(rec.Result())
                        text = result.get("text", "").lower()

                        if any(wake in text for wake in self.wake_words):
                            logger.info(f"⚡ Wake word detected via Vosk: '{text}'")
                            return True

                    # Also check partial results for faster detection
                    partial = json_module.loads(rec.PartialResult())
                    partial_text = partial.get("partial", "").lower()
                    if any(wake in partial_text for wake in self.wake_words):
                        logger.info(f"⚡ Wake word detected via Vosk (partial): '{partial_text}'")
                        return True
            finally:
                stream.stop_stream()
                stream.close()
                p.terminate()

        except ImportError:
            logger.warning("Vosk not available. Using simple energy-based detection.")
            return self._listen_wake_word_simple()
        except Exception as e:
            logger.error(f"Vosk wake word error: {e}")
            return self._listen_wake_word_simple()

    def _listen_wake_word_simple(self) -> bool:
        """
        Simplest fallback: Listen for any speech energy spike.
        Not ideal — just detects when someone starts talking.
        Used only when no ML model or Vosk is available.
        """
        p = pyaudio.PyAudio()
        stream = p.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )

        logger.debug("Listening for speech (energy-based fallback)...")
        consecutive_speech = 0

        try:
            while True:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                audio_np = np.frombuffer(data, dtype=np.int16)
                energy = np.abs(audio_np).mean()

                if energy > 800:
                    consecutive_speech += 1
                    if consecutive_speech >= 3:
                        logger.info("⚡ Speech detected (energy-based)")
                        return True
                else:
                    consecutive_speech = 0

                time.sleep(0.05)
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

    def capture_command(self) -> str:
        """
        After wake word is detected, capture the user's voice command.
        
        Returns:
            Transcribed command text, or empty string if nothing heard
        """
        logger.info("Listening for command...")

        for attempt in range(3):
            text, language = self.stt.listen_and_transcribe(
                timeout=5,
                phrase_time_limit=10,
            )

            if text:
                logger.info(f"Command received: '{text}' (lang: {language})")
                return text

            if attempt < 2:
                logger.debug(f"No command heard (attempt {attempt + 1}/3), retrying...")
                time.sleep(0.3)

        logger.info("No command heard after wake word")
        return ""

    async def execute(self, task: dict) -> AgentResult:
        """Execute a voice-related task."""
        action = task.get("action", "")

        if action == "LISTEN_COMMAND":
            text = self.capture_command()
            if text:
                return AgentResult(
                    success=True,
                    message=text,
                    data={"transcribed_text": text},
                )
            return AgentResult(
                success=False,
                message="I didn't hear a command.",
            )

        return AgentResult(
            success=False,
            message=f"Unknown voice action: {action}",
        )

    def get_capabilities(self) -> list[str]:
        return ["LISTEN_COMMAND", "WAKE_WORD_DETECT"]
