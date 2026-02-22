from core.listener import Listener
from core.response_engine import ResponseEngine
from core.intent_parser import IntentParser
from system_control.apps import AppLauncher
from system_control.system_ops import SystemOps
from system_control.wifi import WiFiManager
from system_control.bluetooth import BluetoothManager
from system_control.airplane import AirplaneModeManager
from productivity.scheduler import Scheduler
import time

class VoiceAssistant:
    def __init__(self):
        print("Initializing Assistant Components...")
        self.response = ResponseEngine()
        self.listener = Listener(wake_words=["jarvis"])
        self.parser = IntentParser()
        
        # System modules
        self.app_launcher = AppLauncher()
        self.sys_ops = SystemOps()
        self.wifi = WiFiManager()
        self.bt = BluetoothManager()
        self.airplane = AirplaneModeManager()
        self.scheduler = Scheduler(self.response)
        
        self.response.speak("Hello, I am ready. Say my name, Jarvis, to wake me up.")
        
    def execute_command(self, parsed_result):
        intent = parsed_result.get("intent")
        entities = parsed_result.get("entities", {})
        
        success = False
        msg = "I'm not sure how to do that yet."
        
        if intent == "WIFI_ON":
            success, msg = self.wifi.set_wifi_state(True)
        elif intent == "WIFI_OFF":
            success, msg = self.wifi.set_wifi_state(False)
            
        elif intent == "BLUETOOTH_ON":
            success, msg = self.bt.set_bluetooth_state(True)
        elif intent == "BLUETOOTH_OFF":
            success, msg = self.bt.set_bluetooth_state(False)
            
        elif intent == "AIRPLANE_MODE_ON":
            success, msg = self.airplane.set_airplane_mode(True)
        elif intent == "AIRPLANE_MODE_OFF":
            success, msg = self.airplane.set_airplane_mode(False)
            
        elif intent in ["ENERGY_SAVER_ON", "ENERGY_SAVER_OFF"]:
            success, msg = self.sys_ops.open_energy_saver()
            
        elif intent == "LIVE_CAPTIONS_TOGGLE":
            success, msg = self.sys_ops.toggle_live_captions()
            
        elif intent == "ACCESSIBILITY_SETTINGS":
            success, msg = self.sys_ops.open_accessibility()
            
        elif intent == "VOLUME_UP":
            success, msg = self.sys_ops.set_volume(increase=True)
        elif intent == "VOLUME_DOWN":
            success, msg = self.sys_ops.set_volume(increase=False)
            
        elif intent == "BRIGHTNESS_UP":
            success, msg = self.sys_ops.set_brightness(increase=True)
        elif intent == "BRIGHTNESS_DOWN":
            success, msg = self.sys_ops.set_brightness(increase=False)
            
        elif intent == "LOCK_SCREEN":
            success, msg = self.sys_ops.lock_screen()
            
        elif intent == "SHUTDOWN":
            # Giving the user a chance to cancel within the 30 sec window in a real app
            # For this MVP, we just trigger it and tell them
            self.response.speak("Are you sure you want to shut down? Say yes or no.")
            confirm = self.listener.stt.listen_and_recognize(timeout=5)
            if "yes" in confirm.lower():
                success, msg = self.sys_ops.shutdown(30)
            else:
                success, msg = True, "Shutdown canceled."
                
        elif intent == "LAUNCH_APP":
            app_name = entities.get("app_name")
            if app_name:
                success, msg = self.app_launcher.launch(app_name)
                
        elif intent == "SET_TIMER":
            amount = entities.get("amount")
            unit = entities.get("unit")
            if amount and unit:
                success, msg = self.scheduler.set_timer(amount, unit)
                
        elif intent == "REMINDER":
            task = entities.get("task")
            if task:
                success, msg = self.scheduler.set_reminder(task)
                
        elif intent == "UNKNOWN":
            msg = "I didn't quite catch that. Could you repeat?"
            
        # Give voice feedback
        self.response.speak(msg)
        
    def run(self):
        try:
            while True:
                # 1. Listen for wake word
                if self.listener.listen_for_wake_word():
                    self.response.speak("Yes?")
                    
                    # 2. Listen for command
                    command_text = self.listener.listen_for_command()
                    
                    if command_text:
                        # 3. Parse intent
                        parsed = self.parser.parse(command_text)
                        
                        # 4. Execute and respond
                        self.execute_command(parsed)
                        
                time.sleep(0.1) # Small sleep to prevent CPU hogging
        except KeyboardInterrupt:
            print("\nShutting down assistant.")
            self.response.speak("Goodbye!")

if __name__ == "__main__":
    assistant = VoiceAssistant()
    assistant.run()
