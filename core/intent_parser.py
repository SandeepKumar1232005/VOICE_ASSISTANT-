import re
from fuzzywuzzy import fuzz

class IntentParser:
    def __init__(self):
        # Dictionary of intents and their trigger phrases
        self.intents = {
            "WIFI_ON": ["turn on wifi", "enable wifi"],
            "WIFI_OFF": ["turn off wifi", "disable wifi"],
            "BLUETOOTH_ON": ["turn on bluetooth", "enable bluetooth"],
            "BLUETOOTH_OFF": ["turn off bluetooth", "disable bluetooth"],
            "AIRPLANE_MODE_ON": ["turn on airplane mode", "enable airplane mode"],
            "AIRPLANE_MODE_OFF": ["turn off airplane mode", "disable airplane mode"],
            "ENERGY_SAVER_ON": ["turn on energy saver", "enable energy saver", "turn on battery saver"],
            "ENERGY_SAVER_OFF": ["turn off energy saver", "disable energy saver", "turn off battery saver"],
            "LIVE_CAPTIONS_TOGGLE": ["turn on live captions", "enable live captions", "toggle live captions", "turn off live captions"],
            "ACCESSIBILITY_SETTINGS": ["open accessibility", "accessibility settings", "turn on accessibility"],
            "VOLUME_UP": ["volume up", "increase volume"],
            "VOLUME_DOWN": ["volume down", "decrease volume"],
            "BRIGHTNESS_UP": ["brightness up", "increase brightness"],
            "BRIGHTNESS_DOWN": ["brightness down", "decrease brightness"],
            "LOCK_SCREEN": ["lock screen", "lock the computer"],
            "SHUTDOWN": ["shut down", "turn off computer"],
            "LAUNCH_APP": ["open", "launch", "start"], 
            "SET_TIMER": ["set a timer for", "timer for"],
            "REMINDER": ["remind me to"]
        }

    def parse(self, text):
        """
        Parses the text and returns an intent and extracted entities.
        Returns: {"intent": "INTENT_NAME", "entities": {}}
        """
        text = text.lower()
        
        # 1. Exact or Fuzzy Match for direct commands
        best_intent = "UNKNOWN"
        highest_score = 0
        
        for intent, phrases in self.intents.items():
            for phrase in phrases:
                # Direct match
                if phrase in text and intent not in ["LAUNCH_APP", "SET_TIMER", "REMINDER"]:
                    return {"intent": intent, "entities": {}}
                
                # Fuzzy match for typo resilience on direct commands
                score = fuzz.partial_ratio(phrase, text)
                if score > highest_score and score > 85:
                    highest_score = score
                    best_intent = intent

        # 2. Extract Entities for parametric commands
        # App Launching
        if "open" in text or "launch" in text or "start" in text:
            app_match = re.search(r'(open|launch|start)\s+(.+)', text)
            if app_match:
                return {"intent": "LAUNCH_APP", "entities": {"app_name": app_match.group(2).strip()}}
                
        # Reminders
        if "remind me to" in text:
            remind_match = re.search(r'remind me to\s+(.+)', text)
            if remind_match:
                return {"intent": "REMINDER", "entities": {"task": remind_match.group(1).strip()}}
                
        # Timers
        if "timer for" in text:
            timer_match = re.search(r'timer for\s+(\d+)\s*(minute|minutes|second|seconds|hour|hours)', text)
            if timer_match:
                return {
                    "intent": "SET_TIMER", 
                    "entities": {
                        "amount": int(timer_match.group(1)),
                        "unit": timer_match.group(2)
                    }
                }

        # Return best fuzzy match if high enough, else UNKNOWN
        if highest_score > 85 and best_intent not in ["LAUNCH_APP", "SET_TIMER", "REMINDER"]:
            return {"intent": best_intent, "entities": {}}

        return {"intent": "UNKNOWN", "entities": {}}
