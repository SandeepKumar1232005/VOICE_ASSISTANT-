"""
Nexus AI — Speech-to-Text Service

Primary: faster-whisper (local, offline, high accuracy)
Fallback: Google Speech Recognition (online)
"""

import os
import io
import wave
import tempfile
import warnings
import numpy as np
from typing import Optional, Tuple

# Suppress huggingface_hub warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")
warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")

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
        
        # Auto-detect CUDA if not explicitly set
        self.device = stt_config.get("device", "auto")
        if self.device == "auto":
            try:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"

        self.language = settings.get("language", "en")
        self.input_device_index = settings.get("input_device_index", None)

        self.whisper_model = None
        self._google_recognizer = None
        self._noise_reduce = stt_config.get("noise_reduce", False)  # Off by default for speed

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
                beam_size=1,  # Faster transcription (negligible accuracy loss on short commands)
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=300,
                    speech_pad_ms=150,
                ),
                language=self.language if self.language != "auto" else None,
            )

            # ─── Hallucination & Confidence Filtering ───
            # Whisper can hallucinate during silence. `no_speech_prob` helps detect this.
            if info and hasattr(info, "no_speech_prob") and info.no_speech_prob > 0.5:
                logger.debug(f"High no_speech_prob ({info.no_speech_prob:.2f}), assuming silence.")
                return "", None

            # Collect all segments and check confidence
            text_parts = []
            lowest_logprob = 0.0

            for segment in segments:
                if segment.avg_logprob < lowest_logprob:
                    lowest_logprob = segment.avg_logprob
                
                # Further hallucination protection per-segment
                if hasattr(segment, "no_speech_prob") and segment.no_speech_prob > 0.6:
                    continue
                    
                text_parts.append(segment.text.strip())

            transcribed_text = " ".join(text_parts).strip()
            detected_language = info.language if info else None

            # Filter out known Whisper hallucinations
            hallucinations = [
                "thank you.", "thank you", "i hope you enjoyed this video.",
                "i hope you enjoyed this video", "thanks for watching.",
                "subscribe", "you", "amara.org", "by mr. doob"
            ]
            if transcribed_text.lower() in hallucinations:
                logger.debug(f"Filtered hallucination: '{transcribed_text}'")
                return "", None

            # Low confidence check (-1.0 is a reasonable threshold for mumbled/unclear speech)
            if lowest_logprob < -1.0 and transcribed_text:
                logger.warning(f"Low confidence STT ({lowest_logprob:.2f}): '{transcribed_text}'")
                return "[LOW_CONFIDENCE]", detected_language

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
            kwargs = {
                "format": FORMAT,
                "channels": CHANNELS,
                "rate": RATE,
                "input": True,
                "frames_per_buffer": CHUNK,
            }
            if self.input_device_index is not None:
                kwargs["input_device_index"] = self.input_device_index
            stream = p.open(**kwargs)
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
                        if silence_chunks > int(RATE / CHUNK * 0.8):  # 0.8 seconds of silence (faster cutoff)
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

        # Apply noise reduction only if enabled (off by default for speed)
        if self._noise_reduce:
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
