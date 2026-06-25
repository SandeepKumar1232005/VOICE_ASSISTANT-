from core.speech_to_text import SpeechToText
import time

import pyaudio
import numpy as np
import joblib
import librosa
import os

class Listener:
    def __init__(self, wake_words=["nova", "assistant", "jarvis"]):
        self.stt = SpeechToText()
        self.wake_words = wake_words
        
        # Load Offline Brain
        model_path = os.path.join(os.path.dirname(__file__), "..", "datasets", "jarvis_rf_model.pkl")
        self.brain = None
        if os.path.exists(model_path):
            try:
                self.brain = joblib.load(model_path)
            except Exception as e:
                print(f"[Error] Failed to load offline brain: {e}")
        
        # PyAudio configuration for live stream
        self.CHUNK = 8000  # 0.5 seconds of audio per chunk
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000

    def get_mfcc(self, audio_data):
        """Convert raw PyAudio bytes to MFCC features needed by the Brain."""
        # Convert bytes to floats for librosa
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        # Wait until we have enough data to classify (pad if slightly short)
        if len(audio_np) < self.RATE * 2:
            audio_np = np.pad(audio_np, (0, max(0, self.RATE * 2 - len(audio_np))))
        # Extract features
        mfccs = librosa.feature.mfcc(y=audio_np, sr=self.RATE, n_mfcc=40)
        return np.mean(mfccs.T, axis=0).reshape(1, -1)

    def listen_for_wake_word(self):
        """
        Continuously listens for "Jarvis" using the OFFLINE AI brain.
        Uses 0 internet. Triggers instantly!
        """
        if not self.brain:
            print("[Warning] No offline brain found. Ensure train_model.py was run.")
            return False

        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=self.FORMAT,
                            channels=self.CHANNELS,
                            rate=self.RATE,
                            input=True,
                            frames_per_buffer=self.CHUNK)
        except Exception as e:
            print(f"[Audio Error] Cannot open Microphone: {e}")
            return False

        print("\n[System] (Offline AI) Listening for 'Jarvis'...")
        
        # Keep a rolling buffer of the last 2 seconds of audio
        buffer = b""
        chunk_count = 0
        consecutive_spikes = 0
        
        while True:
            # Read 0.5 seconds of audio from mic
            data = stream.read(self.CHUNK, exception_on_overflow=False)
            buffer += data
            chunk_count += 1
            
            # Wait until we have roughly 2 seconds of audio collected
            if chunk_count >= 4:
                # Ask the offline Brain if it heard Jarvis
                features = self.get_mfcc(buffer)
                
                # Get the mathematical probability
                probabilities = self.brain.predict_proba(features)[0]
                probability_jarvis = probabilities[1]
                
                # Debugging log
                if probability_jarvis > 0.10:
                    print(f"[Debug] Wake word probability string: {probability_jarvis*100:.1f}%")
                
                # If probability spikes above threshold (35%)
                if probability_jarvis >= 0.35:
                    consecutive_spikes += 1
                else:
                    consecutive_spikes = 0 # reset if it was just a random blip
                    
                # To prevent random noise triggering it, it must sustain the spike across two checks (approx 1 second)
                if consecutive_spikes >= 2:
                    print(f"\n[⚡ Offline Brain Detected]: 'Jarvis'")
                    
                    stream.stop_stream()
                    stream.close()
                    p.terminate()
                    return True
                
                # Drop the oldest 0.5 seconds of audio from the buffer to make room for new audio
                buffer = buffer[self.CHUNK * 2:]  # Remove the oldest chunk (Int16 = 2 bytes per frame)
                chunk_count -= 1

    def listen_for_command(self):
        """
        Once the wake word is detected, listen for the actual command.
        """
        print("\n[System] Listening for command...")
        # Try to catch the command, retrying a few times if empty
        for _ in range(3):
            command = self.stt.listen_and_recognize(timeout=3, phrase_time_limit=7)
            if command:
                print(f"[Command Received]: {command}")
                return command
            # short pause before retrying
            time.sleep(0.5)
            
        print("\n[System] No command heard after wake word.")
        return ""
