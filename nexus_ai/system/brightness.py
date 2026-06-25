"""
Nexus AI — Brightness Control

Controls screen brightness using screen_brightness_control.
Extracted from the original system_control/system_ops.py.
"""

from nexus_ai.utils.logger import get_logger

logger = get_logger("Brightness")


class BrightnessController:
    """Controls screen brightness."""

    def set_brightness(self, increase: bool = True, step: int = 10) -> tuple[bool, str]:
        """Increase or decrease brightness by step percentage points."""
        try:
            import screen_brightness_control as sbc

            current = sbc.get_brightness(display=0)[0]
            new_bright = current + step if increase else current - step
            new_bright = max(0, min(100, new_bright))
            sbc.set_brightness(new_bright, display=0)

            action = "Increased" if increase else "Decreased"
            logger.info(f"{action} brightness to {new_bright}%")
            return True, f"{action} brightness to {new_bright} percent."
        except Exception as e:
            logger.error(f"Brightness control failed: {e}")
            return False, f"Failed to adjust brightness: {e}"

    def get_brightness(self) -> tuple[bool, str]:
        """Get current brightness level."""
        try:
            import screen_brightness_control as sbc
            current = sbc.get_brightness(display=0)[0]
            return True, f"Current brightness is {current} percent."
        except Exception as e:
            return False, f"Cannot read brightness: {e}"

    def set_brightness_level(self, level: int) -> tuple[bool, str]:
        """Set brightness to a specific level (0-100)."""
        try:
            import screen_brightness_control as sbc
            level = max(0, min(100, level))
            sbc.set_brightness(level, display=0)
            logger.info(f"Set brightness to {level}%")
            return True, f"Set brightness to {level} percent."
        except Exception as e:
            return False, f"Failed to set brightness: {e}"
