import os
import ctypes
import time
import screen_brightness_control as sbc

# Windows Virtual Key Codes for volume
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF

class SystemOps:
    def __init__(self):
        # We don't need complex COM init anymore, using hardware keystrokes
        pass
            
    def set_volume(self, increase=True, step=None):
        """
        Increases or decreases volume using virtual keystrokes.
        Each keystroke typically changes volume by 2%. 
        We'll send 5 keystrokes (approx 10%) by default if step not specified.
        """
        try:
            key = VK_VOLUME_UP if increase else VK_VOLUME_DOWN
            # Press the key 5 times for a noticeable change
            for _ in range(5):
                ctypes.windll.user32.keybd_event(key, 0, 0, 0) # Key press
                ctypes.windll.user32.keybd_event(key, 0, 2, 0) # Key release
                time.sleep(0.01)
                
            action = "Increased" if increase else "Decreased"
            return True, f"{action} volume."
        except Exception as e:
            return False, f"Failed to adjust volume: {e}"
            
    def set_brightness(self, increase=True, step=10):
        """
        Increases or decreases screen brightness by percentage points.
        """
        try:
            current = sbc.get_brightness(display=0)[0]
            new_bright = current + step if increase else current - step
            new_bright = max(0, min(100, new_bright))
            sbc.set_brightness(new_bright, display=0)
            
            action = "Increased" if increase else "Decreased"
            return True, f"{action} brightness to {new_bright} percent."
        except Exception as e:
            return False, f"Failed to adjust brightness: {e}"
            
    def lock_screen(self):
        """
        Locks the Windows workstation.
        """
        try:
            ctypes.windll.user32.LockWorkStation()
            return True, "Locking the screen."
        except Exception as e:
            return False, f"Failed to lock screen: {e}"

    def toggle_live_captions(self):
        """
        Toggles Windows 11 Live Captions using the Win+Ctrl+L shortcut.
        """
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

    def open_energy_saver(self):
        """
        Opens Windows Energy Saver settings.
        """
        try:
            os.system("start ms-settings:batterysaver")
            return True, "Opened Energy Saver settings."
        except Exception as e:
            return False, f"Failed to open Energy Saver: {e}"

    def open_accessibility(self):
        """
        Opens Windows Accessibility settings.
        """
        try:
            os.system("start ms-settings:easeofaccess")
            return True, "Opened Accessibility settings."
        except Exception as e:
            return False, f"Failed to open Accessibility: {e}"
            
    def shutdown(self, timer_seconds=30):
        """
        Initiates a system shutdown.
        """
        try:
            os.system(f"shutdown /s /t {timer_seconds}")
            return True, f"System will shut down in {timer_seconds} seconds."
        except Exception as e:
            return False, f"Failed to shut down: {e}"
