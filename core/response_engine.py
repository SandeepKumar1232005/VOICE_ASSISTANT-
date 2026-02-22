import pyttsx3

class ResponseEngine:
    def __init__(self, voice_id=None, rate=175, volume=1.0):
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', rate)
        self.engine.setProperty('volume', volume)
        
        # Set voice if provided, otherwise default
        voices = self.engine.getProperty('voices')
        if voice_id is not None and voice_id < len(voices):
            self.engine.setProperty('voice', voices[voice_id].id)
        else:
            # Try to find a female voice by default, or fallback to first
            for voice in voices:
                if "Zira" in voice.name or "female" in voice.name.lower():
                    self.engine.setProperty('voice', voice.id)
                    break

    def speak(self, text):
        """
        Synchronously speaks the given text.
        """
        print(f"[Assistant]: {text}")
        self.engine.say(text)
        self.engine.runAndWait()
