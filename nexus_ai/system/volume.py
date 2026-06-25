"""
Nexus AI — Volume Control

Controls system volume using virtual keystrokes.
Extracted from the original system_control/system_ops.py.
"""

import ctypes
import time
from nexus_ai.utils.logger import get_logger

logger = get_logger("Volume")

# Windows Virtual Key Codes
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF


class VolumeController:
    """Controls system volume via virtual keystrokes."""

    def set_volume(self, increase: bool = True, steps: int = 5) -> tuple[bool, str]:
        """
        Increase or decrease volume.
        Each keystroke changes volume by ~2%, default 5 steps = ~10%.
        """
        try:
            key = VK_VOLUME_UP if increase else VK_VOLUME_DOWN
            for _ in range(steps):
                ctypes.windll.user32.keybd_event(key, 0, 0, 0)
                ctypes.windll.user32.keybd_event(key, 0, 2, 0)
                time.sleep(0.01)

            action = "Increased" if increase else "Decreased"
            logger.info(f"{action} volume by {steps} steps")
            return True, f"{action} volume."
        except Exception as e:
            logger.error(f"Volume control failed: {e}")
            return False, f"Failed to adjust volume: {e}"

    def mute(self) -> tuple[bool, str]:
        """Toggle mute."""
        try:
            ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 2, 0)
            logger.info("Volume mute toggled")
            return True, "Toggled mute."
        except Exception as e:
            logger.error(f"Mute failed: {e}")
            return False, f"Failed to toggle mute: {e}"
