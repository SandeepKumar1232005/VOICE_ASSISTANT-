import threading
import time

class Scheduler:
    def __init__(self, response_engine):
        self.response_engine = response_engine
        self.active_timers = []
        self.active_reminders = []
        
    def set_timer(self, amount, unit):
        """
        Sets a timer for a given amount and unit (minute/second/hour).
        """
        multiplier = 1
        if "minute" in unit:
            multiplier = 60
        elif "hour" in unit:
            multiplier = 3600
            
        seconds = amount * multiplier
        
        # Start timer thread
        timer_thread = threading.Thread(target=self._run_timer, args=(seconds, amount, unit))
        timer_thread.daemon = True
        timer_thread.start()
        
        self.active_timers.append(timer_thread)
        return True, f"Timer set for {amount} {unit}."
        
    def _run_timer(self, seconds, amount, unit):
        time.sleep(seconds)
        # Notify user when timer is up
        self.response_engine.speak(f"Your timer for {amount} {unit} is up!")
        
    def set_reminder(self, task):
        """
        In a full implementation, you'd specify a time. 
        For this prototype, we'll store it as a note.
        """
        self.active_reminders.append(task)
        return True, f"I will remind you to {task}."
        
    def get_reminders(self):
        if not self.active_reminders:
            return False, "You have no reminders."
            
        text = "Your reminders are: " + ", ".join(self.active_reminders)
        return True, text
