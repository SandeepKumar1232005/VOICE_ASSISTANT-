import os
import subprocess
import json
from AppOpener import open as app_open, close as app_close

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

    def close(self, app_name):
        """
        Attempts to cleanly close an application by its name.
        """
        initial_app_name = app_name.lower().strip()
        app_name = initial_app_name
        
        # Resolve alias if present
        if app_name in self.shortcuts:
            app_name = self.shortcuts[app_name]
            
        # Try AppOpener first
        try:
            app_close(app_name, match_closest=True, throw_error=True)
            return True, f"Closing {initial_app_name}."
        except Exception as e:
            print(f"AppOpener close fallback: {e}")
            
        # Fallback 1: Direct taskkill assumption
        # Note: 'taskkill /IM chrome.exe /F', 'taskkill /IM notepad.exe /F', etc.
        try:
            # Add .exe if user didn't say it
            target_exe = app_name if app_name.endswith(".exe") else f"{app_name}.exe"
            
            # Use taskkill command
            # /IM specifies the image name, /F forcefully terminates
            ret = os.system(f"taskkill /IM {target_exe} /F /T")
            
            if ret == 0:
                return True, f"Closing {initial_app_name}."
            else:
                # If that exact string didn't work, give an informative failure message
                return False, f"I couldn't close {initial_app_name}."
        except Exception as e:
            print(f"Taskkill error: {e}")
            return False, f"An error occurred while trying to close {initial_app_name}."
