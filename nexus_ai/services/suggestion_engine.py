"""
Nexus AI — Suggestion Engine

Runs in the background, analyzing system state, time of day, and user habits
to provide proactive, contextual suggestions via the voice assistant.
"""

import threading
import time
from datetime import datetime
from typing import Optional, Callable

from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.database import Database

logger = get_logger("SuggestionEngine")


class SuggestionEngine:
    """
    Suggestion Engine — Proactive contextual intelligence.
    
    Monitors system state silently and provides non-intrusive voice suggestions.
    Runs on a background thread.
    """

    def __init__(self, db: Database, tts_callback: Callable[[str], None]):
        self.db = db
        self.tts_callback = tts_callback
        self.enabled = True
        self.check_interval = 300  # Check every 5 minutes
        
        # State tracking to avoid repeating the same suggestion
        self.last_suggestions = {
            "battery": 0,
            "storage": 0,
            "break": 0,
            "morning_briefing": 0
        }
        
        self._thread = threading.Thread(target=self._suggestion_loop, daemon=True)
        self._thread.start()
        logger.info("Suggestion Engine initialized on background thread.")

    def _suggestion_loop(self):
        """Main loop for generating proactive suggestions."""
        # Wait a bit after startup before giving suggestions
        time.sleep(30)
        
        while True:
            if not self.enabled:
                time.sleep(60)
                continue
                
            try:
                self._check_all_heuristics()
            except Exception as e:
                logger.error(f"Error in suggestion engine: {e}")
                
            time.sleep(self.check_interval)

    def _check_all_heuristics(self):
        """Evaluate all suggestion rules."""
        now = time.time()
        current_time = datetime.now()
        
        # 1. Morning Briefing
        # Between 7 AM and 10 AM, if we haven't given it today
        if 7 <= current_time.hour < 10:
            last_briefing = datetime.fromtimestamp(self.last_suggestions["morning_briefing"] or 0)
            if last_briefing.date() < current_time.date():
                self._generate_morning_briefing()
                self.last_suggestions["morning_briefing"] = now
                return  # Only one suggestion per cycle
                
        # 2. Battery Low Warning
        import psutil
        if hasattr(psutil, "sensors_battery") and psutil.sensors_battery() is not None:
            batt = psutil.sensors_battery()
            # If below 20% and not plugged in, and hasn't warned in 30 mins
            if not batt.power_plugged and batt.percent < 20:
                if (now - self.last_suggestions["battery"]) > 1800:
                    self._speak("Suggestion: Your battery is running low at " + 
                              f"{int(batt.percent)} percent. You might want to plug in your charger.")
                    self.last_suggestions["battery"] = now
                    return
                    
        # 3. Disk Space Warning
        disk = psutil.disk_usage('/')
        # If below 5GB free and hasn't warned in 24 hours
        if disk.free < (5 * 1024 * 1024 * 1024):
            if (now - self.last_suggestions["storage"]) > 86400:
                self._speak("System alert: Your main drive is almost full. " +
                          "You might want to clean up some files soon.")
                self.last_suggestions["storage"] = now
                return
                
        # 4. Long Session / Break Reminder
        # Check system snapshots for continuous high CPU or just uptime
        # We'll use a simplified check: if we've been running for 2+ hours continuously
        # This requires tracking session start, for now we'll just check productivity events
        recent_events = self.db.get_productivity_events(limit=10)
        # Placeholder logic for breaks
        if False:  # Implement proper session tracking later
            if (now - self.last_suggestions["break"]) > 7200:
                self._speak("You've been working for a while. Suggestion: Take a 5 minute break to stretch.")
                self.last_suggestions["break"] = now
                return

    def _generate_morning_briefing(self):
        """Generate a personalized morning briefing."""
        reminders = self.db.get_pending_reminders()
        todos = self.db.get_todos(include_completed=False)
        
        greeting = "Good morning! "
        
        if reminders or todos:
            items = []
            if reminders:
                items.append(f"{len(reminders)} reminders")
            if todos:
                items.append(f"{len(todos)} tasks on your to-do list")
                
            greeting += f"You have {' and '.join(items)} for today. "
        else:
            greeting += "Your schedule looks clear today. "
            
        greeting += "Let me know if you need anything."
        
        self._speak(greeting)

    def _speak(self, text: str):
        """Pass suggestion to TTS."""
        logger.info(f"Proactive Suggestion: {text}")
        try:
            self.tts_callback(text)
        except Exception as e:
            logger.error(f"Failed to speak suggestion: {e}")
            
    def disable(self):
        self.enabled = False
        
    def enable(self):
        self.enabled = True
