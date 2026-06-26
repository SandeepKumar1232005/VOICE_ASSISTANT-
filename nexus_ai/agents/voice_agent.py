"""
Nexus AI — Voice Agent

Handles wake word detection, continuous listening, and speech capture.
Uses the existing offline RF model for wake word + faster-whisper for commands.

Performance optimized:
- Vosk model and recognizer cached across wake word cycles
- PyAudio instance reused
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
        self.input_device_index = settings.get("input_device_index", None)

        # Initialize STT service
        self.stt = SpeechToTextService()

        # Load offline wake word model (from old Jarvis implementation)
        self.brain = None
        self._load_wake_word_model()

        # ─── Vosk cache (avoid reloading model every cycle) ────
        self._vosk_model = None
        self._vosk_available = None  # None = not checked, True/False = result
        self._init_vosk_model()

        logger.info(f"Voice Agent ready. Wake words: {self.wake_words}")

    def _load_wake_word_model(self):
        """Load the offline RF model for wake word detection."""
        # Only load the offline model if "jarvis" is configured as a wake word.
        # Otherwise, use dynamic keyword spotting (Vosk).
        if not any("jarvis" in w.lower() for w in self.wake_words):
            logger.info("Configured wake words do not include 'jarvis'. Bypassing offline model to use Vosk.")
            return

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

    def _init_vosk_model(self):
        """Pre-load the Vosk model once at startup (cached for all cycles)."""
        if self.brain:
            # Using RF model, Vosk not needed
            return

        try:
            from vosk import Model
            import json as json_module

            model_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "vosk-model-small-en-us-0.15",
            )

            if not os.path.exists(model_path):
                logger.warning(f"Vosk model not found at {model_path}")
                self._vosk_available = False
                return

            logger.info("Pre-loading Vosk model (one-time)...")
            self._vosk_model = Model(model_path)
            self._vosk_available = True
            logger.info("Vosk model cached successfully")

        except ImportError:
            logger.warning("Vosk not installed.")
            self._vosk_available = False
        except Exception as e:
            logger.warning(f"Failed to pre-load Vosk model: {e}")
            self._vosk_available = False

    def _get_mfcc(self, audio_data: bytes) -> np.ndarray:
        """Convert raw audio bytes to MFCC features for the wake word model."""
        import librosa

        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Ensure minimum length (2 seconds)
        if len(audio_np) < self.RATE * 2:
            audio_np = np.pad(audio_np, (0, max(0, self.RATE * 2 - len(audio_np))))

        mfccs = librosa.feature.mfcc(y=audio_np, sr=self.RATE, n_mfcc=40)
        return np.mean(mfccs.T, axis=0).reshape(1, -1)

    def listen_for_wake_word_and_command(self) -> str:
        """
        Continuously listen for the wake word, and seamlessly record the 
        command that follows.
        
        Uses the offline RF model if available, otherwise falls back
        to Vosk keyword spotting.
        
        Returns:
            The transcribed command (str), or empty string if nothing heard.
            Returns '[LOW_CONFIDENCE]' if confidence is below threshold.
        """
        if self.brain:
            return self._listen_wake_word_rf()
        else:
            return self._listen_wake_word_vosk()

    def _listen_wake_word_rf(self) -> str:
        """Listen for wake word using the offline Random Forest model."""
        p = pyaudio.PyAudio()

        try:
            kwargs = {
                "format": self.FORMAT,
                "channels": self.CHANNELS,
                "rate": self.RATE,
                "input": True,
                "frames_per_buffer": self.CHUNK,
            }
            if self.input_device_index is not None:
                kwargs["input_device_index"] = self.input_device_index
            stream = p.open(**kwargs)
        except Exception as e:
            logger.error(f"Cannot open microphone: {e}")
            return False

        logger.debug(f"Listening for wake word (offline AI)...")

        import collections
        rolling_buffer = collections.deque(maxlen=int(self.RATE / self.CHUNK * 1.5))

        buffer = b""
        chunk_count = 0
        consecutive_spikes = 0

        try:
            wake_word_detected = False
            while not wake_word_detected:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                rolling_buffer.append(data)
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
                        wake_word_detected = True
                        break

                    # Slide buffer
                    buffer = buffer[self.CHUNK * 2:]
                    chunk_count -= 1
            
            # Wake word detected -> seamlessly transition to command capture
            logger.info("Listening for command (continuous)...")
            frames = list(rolling_buffer)
            silence_chunks = 0
            max_silence = int(self.RATE / self.CHUNK * 0.8) # 0.8 seconds

            while True:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                frames.append(data)
                audio_np = np.frombuffer(data, dtype=np.int16)
                energy = np.abs(audio_np).mean()
                
                if energy < 300:
                    silence_chunks += 1
                    if silence_chunks > max_silence:
                        break
                else:
                    silence_chunks = 0
            
            # Transcribe the full buffer
            audio_data = b"".join(frames)
            
            if hasattr(self.stt, "_noise_reduce") and self.stt._noise_reduce:
                audio_data = self.stt._reduce_noise(audio_data, self.RATE)
                
            text, lang = self.stt.transcribe_audio(audio_data, self.RATE, self.CHANNELS)
            
            if text == "[LOW_CONFIDENCE]":
                return text
                
            if text:
                # Strip wake word
                lower_text = text.lower()
                for w in self.wake_words:
                    if lower_text.startswith(w):
                        text = text[len(w):].strip()
                        # Strip any leading punctuation that might have followed the wake word
                        text = text.lstrip(".,!? ")
                        break
            return text
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"Wake word detection error: {e}")
            return ""
        finally:
            if 'stream' in locals() and stream:
                stream.stop_stream()
                stream.close()
            p.terminate()

    def _listen_wake_word_vosk(self) -> str:
        """Listen for wake word using Vosk keyword spotting (cached model)."""
        if self._vosk_available is False:
            return self._listen_wake_word_simple()

        try:
            from vosk import KaldiRecognizer
            import json as json_module

            # Create recognizer from cached model (model load is FREE now)
            grammar_list = list(self.wake_words) + ["[unk]"]
            rec = KaldiRecognizer(self._vosk_model, self.RATE, json_module.dumps(grammar_list))

            p = pyaudio.PyAudio()
            
            # Open microphone stream with fallback mechanism
            stream = None
            configured_index = self.input_device_index
            
            try:
                kwargs = {
                    "format": self.FORMAT,
                    "channels": self.CHANNELS,
                    "rate": self.RATE,
                    "input": True,
                    "frames_per_buffer": 2000,  # Lower latency chunks
                }
                if configured_index is not None:
                    kwargs["input_device_index"] = configured_index
                stream = p.open(**kwargs)
            except Exception as e:
                if configured_index is not None:
                    logger.warning(f"Failed to open microphone index {configured_index} ({e}). Retrying with default device...")
                    try:
                        kwargs = {
                            "format": self.FORMAT,
                            "channels": self.CHANNELS,
                            "rate": self.RATE,
                            "input": True,
                            "frames_per_buffer": 2000,
                        }
                        stream = p.open(**kwargs)
                    except Exception as e_default:
                        logger.error(f"Failed to open default microphone: {e_default}")
                        p.terminate()
                        return self._listen_wake_word_simple()
                else:
                    logger.error(f"Cannot open default microphone: {e}")
                    p.terminate()
                    return self._listen_wake_word_simple()

            logger.debug("Listening for wake word (Vosk)...")
            
            import collections
            rolling_buffer = collections.deque(maxlen=int(self.RATE / 2000 * 1.5)) # 1.5 seconds of context

            try:
                wake_word_detected = False
                while not wake_word_detected:
                    data = stream.read(2000, exception_on_overflow=False)
                    rolling_buffer.append(data)
                    
                    if rec.AcceptWaveform(data):
                        result = json_module.loads(rec.Result())
                        text = result.get("text", "").lower()
                        if any(wake in text for wake in self.wake_words):
                            logger.info(f"⚡ Wake word detected via Vosk: '{text}'")
                            wake_word_detected = True
                    else:
                        partial = json_module.loads(rec.PartialResult())
                        partial_text = partial.get("partial", "").lower()
                        if any(wake in partial_text for wake in self.wake_words):
                            logger.info(f"⚡ Wake word detected via Vosk (partial): '{partial_text}'")
                            wake_word_detected = True

                # Wake word detected -> seamlessly transition to command capture
                logger.info("Listening for command (continuous)...")
                frames = list(rolling_buffer)
                silence_chunks = 0
                max_silence = int(self.RATE / 2000 * 0.8) # 0.8 seconds

                while True:
                    data = stream.read(2000, exception_on_overflow=False)
                    frames.append(data)
                    audio_np = np.frombuffer(data, dtype=np.int16)
                    energy = np.abs(audio_np).mean()
                    
                    if energy < 300:
                        silence_chunks += 1
                        if silence_chunks > max_silence:
                            break
                    else:
                        silence_chunks = 0
                
                # Transcribe the full buffer
                audio_data = b"".join(frames)
                
                if hasattr(self.stt, "_noise_reduce") and self.stt._noise_reduce:
                    audio_data = self.stt._reduce_noise(audio_data, self.RATE)
                    
                text, lang = self.stt.transcribe_audio(audio_data, self.RATE, self.CHANNELS)
                
                if text == "[LOW_CONFIDENCE]":
                    return text
                    
                if text:
                    # Strip wake word
                    lower_text = text.lower()
                    for w in self.wake_words:
                        if lower_text.startswith(w):
                            text = text[len(w):].strip()
                            # Strip any leading punctuation that might have followed the wake word
                            text = text.lstrip(".,!? ")
                            break
                return text
            finally:
                if stream:
                    stream.stop_stream()
                    stream.close()
                p.terminate()

        except ImportError:
            logger.warning("Vosk not available. Using simple energy-based detection.")
            self._vosk_available = False
            return self._listen_wake_word_simple()
        except Exception as e:
            logger.error(f"Vosk wake word error: {e}")
            return self._listen_wake_word_simple()

    def _listen_wake_word_simple(self) -> str:
        """
        Simplest fallback: Listen for any speech energy spike.
        Not ideal — just detects when someone starts talking.
        Used only when no ML model or Vosk is available.
        """
        p = pyaudio.PyAudio()
        kwargs = {
            "format": self.FORMAT,
            "channels": self.CHANNELS,
            "rate": self.RATE,
            "input": True,
            "frames_per_buffer": self.CHUNK,
        }
        if self.input_device_index is not None:
            kwargs["input_device_index"] = self.input_device_index
        stream = p.open(**kwargs)

        logger.debug("Listening for speech (energy-based fallback)...")
        consecutive_speech = 0
        
        import collections
        rolling_buffer = collections.deque(maxlen=int(self.RATE / self.CHUNK * 1.5))

        try:
            wake_word_detected = False
            while not wake_word_detected:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                rolling_buffer.append(data)
                audio_np = np.frombuffer(data, dtype=np.int16)
                energy = np.abs(audio_np).mean()

                if energy > 800:
                    consecutive_speech += 1
                    if consecutive_speech >= 3:
                        logger.info("⚡ Speech detected (energy-based)")
                        wake_word_detected = True
                else:
                    consecutive_speech = 0

            # Seamlessly transition to command capture
            logger.info("Listening for command (continuous)...")
            frames = list(rolling_buffer)
            silence_chunks = 0
            max_silence = int(self.RATE / self.CHUNK * 0.8)

            while True:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                frames.append(data)
                audio_np = np.frombuffer(data, dtype=np.int16)
                energy = np.abs(audio_np).mean()
                
                if energy < 300:
                    silence_chunks += 1
                    if silence_chunks > max_silence:
                        break
                else:
                    silence_chunks = 0
            
            # Transcribe the full buffer
            audio_data = b"".join(frames)
            
            if hasattr(self.stt, "_noise_reduce") and self.stt._noise_reduce:
                audio_data = self.stt._reduce_noise(audio_data, self.RATE)
                
            text, lang = self.stt.transcribe_audio(audio_data, self.RATE, self.CHANNELS)
            
            if text == "[LOW_CONFIDENCE]":
                return text
                
            if text:
                lower_text = text.lower()
                for w in self.wake_words:
                    if lower_text.startswith(w):
                        text = text[len(w):].strip()
                        text = text.lstrip(".,!? ")
                        break
            return text
            
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"Wake word simple fallback error: {e}")
            return ""
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
