"""
Nexus AI — System Control Agent

Handles power, network, display, and system info queries.
Delegates to specialized system/ modules.
"""

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.system.wifi import WiFiController
from nexus_ai.system.bluetooth import BluetoothController
from nexus_ai.system.power import PowerController
from nexus_ai.system.volume import VolumeController
from nexus_ai.system.brightness import BrightnessController
from nexus_ai.system.display import DisplayController
from nexus_ai.utils.logger import get_logger

logger = get_logger("SystemAgent")


class SystemAgent(BaseAgent):
    """
    System Control Agent — Manages Windows system operations.
    
    Capabilities:
        - WiFi on/off
        - Bluetooth on/off
        - Volume up/down/mute
        - Brightness up/down
        - Power: shutdown, restart, sleep, lock, logout
        - Display: screenshot, night mode
        - System info: battery, RAM, storage
    """

    def __init__(self):
        super().__init__("SystemAgent")
        self.wifi = WiFiController()
        self.bluetooth = BluetoothController()
        self.power = PowerController()
        self.volume = VolumeController()
        self.brightness = BrightnessController()
        self.display = DisplayController()

    async def execute(self, task: dict) -> AgentResult:
        action = task.get("action", "")
        params = task.get("parameters", {})

        handler = {
            # WiFi
            "WIFI_ON": lambda: self.wifi.set_wifi_state(True),
            "WIFI_OFF": lambda: self.wifi.set_wifi_state(False),
            # Bluetooth
            "BLUETOOTH_ON": lambda: self.bluetooth.set_bluetooth_state(True),
            "BLUETOOTH_OFF": lambda: self.bluetooth.set_bluetooth_state(False),
            # Volume
            "VOLUME_UP": lambda: self.volume.set_volume(increase=True),
            "VOLUME_DOWN": lambda: self.volume.set_volume(increase=False),
            "VOLUME_MUTE": lambda: self.volume.mute(),
            # Brightness
            "BRIGHTNESS_UP": lambda: self.brightness.set_brightness(increase=True),
            "BRIGHTNESS_DOWN": lambda: self.brightness.set_brightness(increase=False),
            # Night mode
            "NIGHT_MODE_ON": lambda: self.display.toggle_night_mode(True),
            "NIGHT_MODE_OFF": lambda: self.display.toggle_night_mode(False),
            # Screenshot
            "SCREENSHOT": lambda: self.display.take_screenshot(),
            # Power
            "SHUTDOWN": lambda: self.power.shutdown(params.get("timer", 30)),
            "RESTART": lambda: self.power.restart(params.get("timer", 10)),
            "SLEEP": lambda: self.power.sleep(),
            "LOCK_SCREEN": lambda: self.power.lock_screen(),
            "LOGOUT": lambda: self.power.logout(),
            # System info
            "CHECK_BATTERY": lambda: self._check_battery(),
            "CHECK_RAM": lambda: self._check_ram(),
            "CHECK_STORAGE": lambda: self._check_storage(),
        }.get(action)

        if handler is None:
            return AgentResult(
                success=False,
                message=f"Unknown system action: {action}",
            )

        success, message = handler()
        return AgentResult(success=success, message=message)

    def _check_battery(self) -> tuple[bool, str]:
        """Get battery percentage."""
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                plugged = "and charging" if battery.power_plugged else "on battery"
                return True, f"Battery is at {battery.percent}% {plugged}."
            return True, "No battery detected. This might be a desktop computer."
        except Exception as e:
            return False, f"Cannot read battery: {e}"

    def _check_ram(self) -> tuple[bool, str]:
        """Get RAM usage."""
        try:
            import psutil
            from nexus_ai.utils.helpers import format_bytes
            mem = psutil.virtual_memory()
            used = format_bytes(mem.used)
            total = format_bytes(mem.total)
            return True, f"RAM usage: {used} of {total} ({mem.percent}% used)."
        except Exception as e:
            return False, f"Cannot read RAM info: {e}"

    def _check_storage(self) -> tuple[bool, str]:
        """Get disk storage info."""
        try:
            import psutil
            from nexus_ai.utils.helpers import format_bytes
            partitions = psutil.disk_partitions()
            info_parts = []
            for p in partitions:
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    free = format_bytes(usage.free)
                    total = format_bytes(usage.total)
                    info_parts.append(f"{p.device} has {free} free of {total}")
                except PermissionError:
                    continue
            if info_parts:
                return True, "Storage: " + ". ".join(info_parts[:3]) + "."
            return True, "No accessible storage partitions found."
        except Exception as e:
            return False, f"Cannot read storage info: {e}"

    def get_capabilities(self) -> list[str]:
        return [
            "WIFI_ON", "WIFI_OFF",
            "BLUETOOTH_ON", "BLUETOOTH_OFF",
            "VOLUME_UP", "VOLUME_DOWN", "VOLUME_MUTE",
            "BRIGHTNESS_UP", "BRIGHTNESS_DOWN",
            "NIGHT_MODE_ON", "NIGHT_MODE_OFF",
            "SCREENSHOT",
            "SHUTDOWN", "RESTART", "SLEEP", "LOCK_SCREEN", "LOGOUT",
            "CHECK_BATTERY", "CHECK_RAM", "CHECK_STORAGE",
        ]
