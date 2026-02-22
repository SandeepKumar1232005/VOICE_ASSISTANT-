from core.speech_to_text import SpeechToText
import time

class Listener:
    def __init__(self, wake_words=["nova", "assistant", "jarvis"]):
        self.stt = SpeechToText()
        self.wake_words = wake_words

    def listen_for_wake_word(self):
        """
        Continuously listens for any of the configured wake words.
        Returns True when detected.
        """
        print(f"\n[System] Listening for wake words: {self.wake_words}...")
        while True:
            text = self.stt.listen_and_recognize(timeout=None, phrase_time_limit=3)
            if not text:
                continue
            
            # Simple check if any wake word is in the matched text
            for word in self.wake_words:
                if word in text:
                    print(f"\n[Wake Word Detected]: '{word}'")
                    return True

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
