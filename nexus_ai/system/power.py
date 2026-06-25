"""
Nexus AI — Power Management

Handles shutdown, restart, sleep, lock, and logout operations.
All destructive operations should be gated by the Security Agent.
"""

import os
import ctypes
import subprocess
from nexus_ai.utils.logger import get_logger

logger = get_logger("Power")


class PowerController:
    """Controls system power states on Windows."""

    def shutdown(self, timer_seconds: int = 30) -> tuple[bool, str]:
        """Initiate system shutdown with optional delay."""
        try:
            os.system(f"shutdown /s /t {timer_seconds}")
            logger.info(f"Shutdown initiated (timer: {timer_seconds}s)")
            return True, f"System will shut down in {timer_seconds} seconds."
        except Exception as e:
            logger.error(f"Shutdown failed: {e}")
            return False, f"Failed to initiate shutdown: {e}"

    def restart(self, timer_seconds: int = 10) -> tuple[bool, str]:
        """Initiate system restart with optional delay."""
        try:
            os.system(f"shutdown /r /t {timer_seconds}")
            logger.info(f"Restart initiated (timer: {timer_seconds}s)")
            return True, f"System will restart in {timer_seconds} seconds."
        except Exception as e:
            logger.error(f"Restart failed: {e}")
            return False, f"Failed to initiate restart: {e}"

    def cancel_shutdown(self) -> tuple[bool, str]:
        """Cancel a pending shutdown or restart."""
        try:
            os.system("shutdown /a")
            logger.info("Shutdown/restart cancelled")
            return True, "Shutdown cancelled."
        except Exception as e:
            return False, f"Failed to cancel: {e}"

    def sleep(self) -> tuple[bool, str]:
        """Put the system to sleep."""
        try:
            # rundll32.exe powrprof.dll,SetSuspendState 0,1,0
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            logger.info("System put to sleep")
            return True, "Putting the system to sleep."
        except Exception as e:
            logger.error(f"Sleep failed: {e}")
            return False, f"Failed to sleep: {e}"

    def lock_screen(self) -> tuple[bool, str]:
        """Lock the Windows workstation."""
        try:
            ctypes.windll.user32.LockWorkStation()
            logger.info("Screen locked")
            return True, "Locking the screen."
        except Exception as e:
            logger.error(f"Lock screen failed: {e}")
            return False, f"Failed to lock screen: {e}"

    def logout(self) -> tuple[bool, str]:
        """Log out the current user."""
        try:
            os.system("shutdown /l")
            logger.info("Logout initiated")
            return True, "Logging out."
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return False, f"Failed to log out: {e}"
