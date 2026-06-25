"""
Nexus AI — Display Control

Screenshot capture, night mode toggle, and display info.
"""

import os
import ctypes
import time
from datetime import datetime
from pathlib import Path
from nexus_ai.utils.logger import get_logger

logger = get_logger("Display")


class DisplayController:
    """Controls display settings — screenshots, night mode."""

    def take_screenshot(self, save_dir: str = None) -> tuple[bool, str]:
        """
        Take a screenshot and save it.
        Uses PrintScreen key + PowerShell if pillow not available.
        """
        if save_dir is None:
            save_dir = str(Path.home() / "Pictures" / "Screenshots")
        os.makedirs(save_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(save_dir, f"nexus_screenshot_{timestamp}.png")

        # Try using pillow
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            screenshot.save(filepath)
            logger.info(f"Screenshot saved: {filepath}")
            return True, f"Screenshot saved to {filepath}"
        except ImportError:
            pass

        # Fallback: Use PowerShell
        try:
            ps_script = f"""
            Add-Type -AssemblyName System.Windows.Forms
            [System.Windows.Forms.Screen]::PrimaryScreen | Out-Null
            $bitmap = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height)
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            $graphics.CopyFromScreen([System.Drawing.Point]::Empty, [System.Drawing.Point]::Empty, $bitmap.Size)
            $bitmap.Save('{filepath}')
            $graphics.Dispose()
            $bitmap.Dispose()
            """
            os.system(f'powershell -Command "{ps_script}"')
            if os.path.exists(filepath):
                logger.info(f"Screenshot saved (PS): {filepath}")
                return True, f"Screenshot saved to {filepath}"
        except Exception as e:
            logger.error(f"PowerShell screenshot failed: {e}")

        # Last resort: Snipping Tool shortcut
        try:
            VK_LWIN = 0x5B
            VK_SHIFT = 0x10
            VK_S = 0x53
            ctypes.windll.user32.keybd_event(VK_LWIN, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_SHIFT, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_S, 0, 0, 0)
            time.sleep(0.1)
            ctypes.windll.user32.keybd_event(VK_S, 0, 2, 0)
            ctypes.windll.user32.keybd_event(VK_SHIFT, 0, 2, 0)
            ctypes.windll.user32.keybd_event(VK_LWIN, 0, 2, 0)
            return True, "Opened the snipping tool for you."
        except Exception:
            return False, "Failed to take screenshot."

    def toggle_night_mode(self, enable: bool = True) -> tuple[bool, str]:
        """Toggle Windows Night Light (blue light filter)."""
        try:
            if enable:
                os.system("start ms-settings:nightlight")
                logger.info("Night mode settings opened")
                return True, "Opening night light settings."
            else:
                os.system("start ms-settings:nightlight")
                return True, "Opening night light settings to turn it off."
        except Exception as e:
            return False, f"Failed to toggle night mode: {e}"

    def toggle_live_captions(self) -> tuple[bool, str]:
        """Toggle Windows 11 Live Captions (Win+Ctrl+L)."""
        try:
            VK_LWIN = 0x5B
            VK_CONTROL = 0x11
            VK_L = 0x4C

            ctypes.windll.user32.keybd_event(VK_LWIN, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_L, 0, 0, 0)
            time.sleep(0.1)
            ctypes.windll.user32.keybd_event(VK_L, 0, 2, 0)
            ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 2, 0)
            ctypes.windll.user32.keybd_event(VK_LWIN, 0, 2, 0)
            return True, "Toggled Live Captions."
        except Exception as e:
            return False, f"Failed to toggle Live Captions: {e}"
