import os
import subprocess
import json
from AppOpener import open as app_open

class AppLauncher:
    def __init__(self, config_file="config/commands.json"):
        # Load user-defined aliases from config
        self.shortcuts = {}
        try:
            if os.path.exists(config_file):
                with open(config_file, "r") as f:
                    data = json.load(f)
                    self.shortcuts = data.get("launch_shortcuts", {})
        except Exception as e:
            print(f"Error loading {config_file}: {e}")

        # Default known paths or commands
        self.known_apps = {
            "chrome": ["start", "chrome"],
            "calculator": ["calc"],
            "notepad": ["notepad"],
            "terminal": ["cmd"],
            "settings": ["start", "ms-settings:"],
            "vs code": ["code"],
            "explorer": ["explorer"]
        }
        
    def launch(self, app_name):
        """
        Attempts to launch an application by its name.
        """
        initial_app_name = app_name.lower().strip()
        app_name = initial_app_name
        
        # 1. Resolve alias if present in commands.json
        if app_name in self.shortcuts:
            app_name = self.shortcuts[app_name]
            
        # 2. Try AppOpener for robust app launching (it works with generic names)
        try:
            # throw_error=True helps us catch if it didn't find the app and fallback
            app_open(app_name, match_closest=True, throw_error=True)
            return True, f"Opening {initial_app_name}."
        except Exception as e:
            print(f"AppOpener fallback: {e}")

        # 3. Check predefined apps
        if app_name in self.known_apps:
            cmd = self.known_apps[app_name]
            try:
                # 'start' in windows cmd usually needs shell=True
                if cmd[0] == "start":
                    subprocess.Popen(cmd, shell=True)
                else:
                    subprocess.Popen(cmd)
                return True, f"Opening {initial_app_name}."
            except Exception as e:
                return False, f"Failed to open {initial_app_name}: {e}"
        
        # 4. Fallback to general start command (letting windows figure it out)
        try:
            # Using os.system as a fallback for shell built-ins
            ret = os.system(f"start {app_name}")
            if ret == 0:
                return True, f"Trying to open {initial_app_name}."
            else:
                return False, f"I couldn't find an application named {initial_app_name}."
        except Exception:
            return False, f"I couldn't find an application named {initial_app_name}."
