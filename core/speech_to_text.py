import speech_recognition as sr

class SpeechToText:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        
        # Adjusting these to make it more responsive and background-friendly
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 400
        self.recognizer.pause_threshold = 0.5 

    def listen_and_recognize(self, timeout=None, phrase_time_limit=5):
        """
        Listens to the microphone and returns recognized text.
        Returns empty string if no speech is detected or an error occurs.
        """
        with sr.Microphone() as source:
            try:
                # auto-adjust for ambient noise for 0.5 seconds
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                
                # Using Google Speech Recognition (requires internet)
                text = self.recognizer.recognize_google(audio)
                return text.lower()
            except sr.WaitTimeoutError:
                return ""
            except sr.UnknownValueError:
                # Speech was unintelligible
                return ""
            except sr.RequestError as e:
                print(f"[STT Error] Could not request results: {e}")
                return ""
            except Exception as e:
                print(f"[STT Debug] {e}")
                return ""
