import os
import subprocess
import json

class AppLauncher:
    def __init__(self, config_file="config/commands.json"):
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
        app_name = app_name.lower().strip()
        
        # Check predefined apps
        if app_name in self.known_apps:
            cmd = self.known_apps[app_name]
            try:
                # 'start' in windows cmd usually needs shell=True
                if cmd[0] == "start":
                    subprocess.Popen(cmd, shell=True)
                else:
                    subprocess.Popen(cmd)
                return True, f"Opening {app_name}."
            except Exception as e:
                return False, f"Failed to open {app_name}: {e}"
        
        # Fallback to general start command (letting windows figure it out)
        try:
            # Using os.system as a fallback for shell built-ins
            os.system(f"start {app_name}")
            return True, f"Trying to open {app_name}."
        except Exception:
            return False, f"I couldn't find an application named {app_name}."
