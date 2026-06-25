"""
Nexus AI — Application Management

Launch, close, restart, and manage applications.
Enhanced version of the original system_control/apps.py.
"""

import os
import subprocess
import json
from typing import Optional
from nexus_ai.utils.logger import get_logger

logger = get_logger("Apps")


class AppController:
    """Manages application launch, close, and process operations."""

    # Well-known app mappings for reliability
    KNOWN_APPS = {
        "chrome": ["start", "chrome"],
        "google chrome": ["start", "chrome"],
        "edge": ["start", "msedge"],
        "microsoft edge": ["start", "msedge"],
        "firefox": ["start", "firefox"],
        "calculator": ["calc"],
        "calc": ["calc"],
        "notepad": ["notepad"],
        "paint": ["mspaint"],
        "terminal": ["wt"],  # Windows Terminal
        "cmd": ["cmd"],
        "command prompt": ["cmd"],
        "powershell": ["powershell"],
        "settings": ["start", "ms-settings:"],
        "vs code": ["code"],
        "vscode": ["code"],
        "visual studio code": ["code"],
        "explorer": ["explorer"],
        "file explorer": ["explorer"],
        "task manager": ["taskmgr"],
        "word": ["start", "winword"],
        "excel": ["start", "excel"],
        "powerpoint": ["start", "powerpnt"],
        "outlook": ["start", "outlook"],
        "spotify": ["start", "spotify:"],
        "discord": ["start", "discord:"],
        "steam": ["start", "steam:"],
        "snipping tool": ["snippingtool"],
    }

    # Process names for closing (app name → exe name)
    PROCESS_NAMES = {
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "edge": "msedge.exe",
        "microsoft edge": "msedge.exe",
        "firefox": "firefox.exe",
        "notepad": "notepad.exe",
        "calculator": "Calculator.exe",
        "paint": "mspaint.exe",
        "vs code": "Code.exe",
        "vscode": "Code.exe",
        "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE",
        "spotify": "Spotify.exe",
        "discord": "Discord.exe",
        "steam": "steam.exe",
        "task manager": "Taskmgr.exe",
        "terminal": "WindowsTerminal.exe",
    }

    def __init__(self, config_file: str = None):
        self.shortcuts = {}
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    data = json.load(f)
                    self.shortcuts = data.get("launch_shortcuts", {})
            except Exception as e:
                logger.warning(f"Error loading app shortcuts: {e}")

    def launch(self, app_name: str) -> tuple[bool, str]:
        """Launch an application by name."""
        original_name = app_name
        app_name = app_name.lower().strip()

        # Resolve alias
        if app_name in self.shortcuts:
            app_name = self.shortcuts[app_name]

        # 1. Try AppOpener (robust, handles many apps)
        try:
            from AppOpener import open as app_open
            app_open(app_name, match_closest=True, throw_error=True)
            logger.info(f"Opened '{original_name}' via AppOpener")
            return True, f"Opening {original_name}."
        except Exception as e:
            logger.debug(f"AppOpener fallback: {e}")

        # 2. Try known apps dictionary
        if app_name in self.KNOWN_APPS:
            cmd = self.KNOWN_APPS[app_name]
            try:
                if cmd[0] == "start":
                    subprocess.Popen(cmd, shell=True)
                else:
                    subprocess.Popen(cmd)
                logger.info(f"Opened '{original_name}' via known apps")
                return True, f"Opening {original_name}."
            except Exception as e:
                logger.debug(f"Known app launch failed: {e}")

        # 3. Windows 'start' fallback
        try:
            ret = os.system(f'start "" "{app_name}"')
            if ret == 0:
                logger.info(f"Opened '{original_name}' via start command")
                return True, f"Opening {original_name}."
        except Exception:
            pass

        logger.warning(f"Could not find application: {original_name}")
        return False, f"I couldn't find an application named {original_name}."

    def close(self, app_name: str) -> tuple[bool, str]:
        """Close an application by name."""
        original_name = app_name
        app_name = app_name.lower().strip()

        if app_name in self.shortcuts:
            app_name = self.shortcuts[app_name]

        # 1. Try AppOpener
        try:
            from AppOpener import close as app_close
            app_close(app_name, match_closest=True, throw_error=True)
            logger.info(f"Closed '{original_name}' via AppOpener")
            return True, f"Closing {original_name}."
        except Exception as e:
            logger.debug(f"AppOpener close fallback: {e}")

        # 2. Try known process names
        exe_name = self.PROCESS_NAMES.get(app_name)
        if not exe_name:
            exe_name = app_name if app_name.endswith(".exe") else f"{app_name}.exe"

        try:
            ret = os.system(f"taskkill /IM {exe_name} /F /T")
            if ret == 0:
                logger.info(f"Closed '{original_name}' via taskkill")
                return True, f"Closing {original_name}."
        except Exception:
            pass

        logger.warning(f"Could not close: {original_name}")
        return False, f"I couldn't close {original_name}."

    def restart_app(self, app_name: str) -> tuple[bool, str]:
        """Restart an application (close then reopen)."""
        close_success, close_msg = self.close(app_name)
        if close_success:
            import time
            time.sleep(1)  # Brief delay before reopening

        open_success, open_msg = self.launch(app_name)
        if open_success:
            return True, f"Restarted {app_name}."
        return False, f"Could not restart {app_name}."

    def list_running_apps(self) -> tuple[bool, str]:
        """List currently running applications."""
        try:
            import psutil
            apps = set()
            for proc in psutil.process_iter(['name', 'status']):
                try:
                    if proc.info['status'] == 'running':
                        name = proc.info['name']
                        if name and not name.startswith(('svchost', 'csrss', 'System', 'Registry')):
                            clean_name = name.replace('.exe', '')
                            apps.add(clean_name)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if apps:
                app_list = sorted(apps)[:20]  # Limit for speech
                msg = f"Running applications: {', '.join(app_list)}"
                return True, msg
            return True, "No user applications are currently running."
        except ImportError:
            return False, "Cannot list applications. psutil is not installed."
        except Exception as e:
            return False, f"Error listing applications: {e}"
