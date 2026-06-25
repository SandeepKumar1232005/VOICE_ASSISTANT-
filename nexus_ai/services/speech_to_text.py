"""
Nexus AI — Speech-to-Text Service

Primary: faster-whisper (local, offline, high accuracy)
Fallback: Google Speech Recognition (online)
"""

import os
import io
import wave
import tempfile
import numpy as np
from typing import Optional, Tuple

from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.helpers import load_json_config

logger = get_logger("STT")


class SpeechToTextService:
    """
    Speech-to-Text service using faster-whisper for local transcription.
    Falls back to Google Speech Recognition if faster-whisper is unavailable.
    """

    def __init__(self):
        settings = load_json_config("settings.json")
        stt_config = settings.get("stt", {})

        self.engine = stt_config.get("engine", "faster-whisper")
        self.model_size = stt_config.get("model_size", "small")
        self.device = stt_config.get("device", "cpu")
        self.language = settings.get("language", "en")

        self.whisper_model = None
        self._google_recognizer = None

        self._init_engine()

    def _init_engine(self):
        """Initialize the configured STT engine."""
        if self.engine == "faster-whisper":
            try:
                from faster_whisper import WhisperModel

                # Model will be auto-downloaded on first use
                models_dir = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "data", "models"
                )
                os.makedirs(models_dir, exist_ok=True)

                logger.info(f"Loading faster-whisper model '{self.model_size}' on {self.device}...")
                self.whisper_model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type="int8" if self.device == "cpu" else "float16",
                    download_root=models_dir,
                )
                logger.info("faster-whisper model loaded successfully")
                return
            except ImportError:
                logger.warning("faster-whisper not installed. Falling back to Google STT.")
            except Exception as e:
                logger.warning(f"Failed to load faster-whisper: {e}. Falling back to Google STT.")

        # Fallback: Google Speech Recognition
        self._init_google_fallback()

    def _init_google_fallback(self):
        """Initialize Google Speech Recognition as fallback."""
        try:
            import speech_recognition as sr
            self._google_recognizer = sr.Recognizer()
            self._google_recognizer.dynamic_energy_threshold = True
            self._google_recognizer.energy_threshold = 400
            self._google_recognizer.pause_threshold = 0.5
            self.engine = "google"
            logger.info("Google Speech Recognition initialized as fallback")
        except ImportError:
            logger.error("Neither faster-whisper nor speech_recognition is available!")
            self.engine = "none"

    def transcribe_audio(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> Tuple[str, Optional[str]]:
        """
        Transcribe raw audio bytes to text.
        
        Args:
            audio_data: Raw PCM audio bytes (int16)
            sample_rate: Audio sample rate
            channels: Number of audio channels
        
        Returns:
            Tuple of (transcribed_text, detected_language)
        """
        if self.engine == "faster-whisper" and self.whisper_model:
            return self._transcribe_whisper(audio_data, sample_rate, channels)
        elif self.engine == "google" and self._google_recognizer:
            return self._transcribe_google(audio_data, sample_rate, channels)
        else:
            logger.error("No STT engine available")
            return "", None

    def _transcribe_whisper(
        self,
        audio_data: bytes,
        sample_rate: int,
        channels: int,
    ) -> Tuple[str, Optional[str]]:
        """Transcribe using faster-whisper."""
        try:
            # Convert raw bytes to float32 numpy array
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            # If stereo, convert to mono
            if channels > 1:
                audio_np = audio_np.reshape(-1, channels).mean(axis=1)

            # Save to temporary WAV file (faster-whisper needs a file path or array)
            segments, info = self.whisper_model.transcribe(
                audio_np,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=300,
                    speech_pad_ms=200,
                ),
                language=self.language if self.language != "auto" else None,
            )

            # Collect all segments
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            transcribed_text = " ".join(text_parts).strip()
            detected_language = info.language if info else None

            if transcribed_text:
                logger.info(f"Transcribed: '{transcribed_text}' (lang: {detected_language})")
            else:
                logger.debug("No speech detected in audio")

            return transcribed_text, detected_language

        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return "", None

    def _transcribe_google(
        self,
        audio_data: bytes,
        sample_rate: int,
        channels: int,
    ) -> Tuple[str, Optional[str]]:
        """Transcribe using Google Speech Recognition (online fallback)."""
        try:
            import speech_recognition as sr

            # Create a WAV file in memory for speech_recognition
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)

            wav_buffer.seek(0)
            audio = sr.AudioData(audio_data, sample_rate, 2)

            # Language mapping
            lang_map = {"en": "en-US", "ta": "ta-IN", "hi": "hi-IN"}
            language = lang_map.get(self.language, "en-US")

            text = self._google_recognizer.recognize_google(audio, language=language)
            logger.info(f"Google STT: '{text}'")
            return text.lower(), self.language

        except Exception as e:
            logger.debug(f"Google STT error: {e}")
            return "", None

    def listen_and_transcribe(
        self,
        timeout: int = 5,
        phrase_time_limit: int = 10,
    ) -> Tuple[str, Optional[str]]:
        """
        Listen from microphone and transcribe.
        Convenience method that handles audio capture internally.
        
        Args:
            timeout: Max seconds to wait for speech to start
            phrase_time_limit: Max seconds of speech to record
        
        Returns:
            Tuple of (transcribed_text, detected_language)
        """
        import pyaudio

        RATE = 16000
        CHANNELS = 1
        CHUNK = 1024
        FORMAT = pyaudio.paInt16

        p = pyaudio.PyAudio()

        try:
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
            )
        except Exception as e:
            logger.error(f"Cannot open microphone: {e}")
            return "", None

        logger.debug("Listening for speech...")
        frames = []
        silence_chunks = 0
        speech_started = False
        max_chunks = int(RATE / CHUNK * phrase_time_limit)
        timeout_chunks = int(RATE / CHUNK * timeout)

        try:
            for i in range(max_chunks + timeout_chunks):
                data = stream.read(CHUNK, exception_on_overflow=False)
                audio_np = np.frombuffer(data, dtype=np.int16)
                energy = np.abs(audio_np).mean()

                if not speech_started:
                    if energy > 500:  # Speech threshold
                        speech_started = True
                        frames.append(data)
                        silence_chunks = 0
                    elif i >= timeout_chunks:
                        logger.debug("Timeout: no speech detected")
                        break
                else:
                    frames.append(data)
                    if energy < 300:
                        silence_chunks += 1
                        if silence_chunks > int(RATE / CHUNK * 1.5):  # 1.5 seconds of silence
                            break
                    else:
                        silence_chunks = 0
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

        if not frames:
            return "", None

        audio_data = b"".join(frames)

        # Apply noise reduction if available
        audio_data = self._reduce_noise(audio_data, RATE)

        return self.transcribe_audio(audio_data, RATE, CHANNELS)

    def _reduce_noise(self, audio_data: bytes, sample_rate: int) -> bytes:
        """Apply noise reduction to audio data."""
        try:
            import noisereduce as nr

            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            reduced = nr.reduce_noise(y=audio_np, sr=sample_rate, prop_decrease=0.6)
            return reduced.astype(np.int16).tobytes()
        except ImportError:
            # noisereduce not installed, return original
            return audio_data
        except Exception as e:
            logger.debug(f"Noise reduction failed: {e}")
            return audio_data
