"""
Nexus AI — WiFi Control

Manages WiFi state using Windows WinRT Radio API.
Migrated from the original system_control/wifi.py.
"""

import asyncio
from nexus_ai.utils.logger import get_logger

logger = get_logger("WiFi")


class WiFiController:
    """Controls WiFi radio state using WinRT API."""

    async def _toggle_wifi(self, enable: bool):
        """Toggle WiFi radio on/off."""
        try:
            from winsdk.windows.devices.radios import Radio, RadioState

            radios = await Radio.get_radios_async()
            wifi_radio = next((r for r in radios if r.kind.name == 'WI_FI'), None)

            if wifi_radio:
                target_state = RadioState.ON if enable else RadioState.OFF
                await wifi_radio.set_state_async(target_state)
                return True, "Wi-Fi radio state updated."
            else:
                return False, "No Wi-Fi radio found on this system."
        except ImportError:
            return False, "WinSDK not available for WiFi control."
        except Exception as e:
            return False, f"WiFi error: {e}"

    def set_wifi_state(self, enable: bool = True) -> tuple[bool, str]:
        """Enable or disable WiFi."""
        try:
            success, msg = asyncio.run(self._toggle_wifi(enable))
        except RuntimeError:
            # Already in an event loop
            loop = asyncio.new_event_loop()
            success, msg = loop.run_until_complete(self._toggle_wifi(enable))
            loop.close()

        if success:
            action = "Enabled" if enable else "Disabled"
            logger.info(f"{action} Wi-Fi")
            return True, f"{action} Wi-Fi."
        else:
            logger.error(f"WiFi toggle failed: {msg}")
            return False, "Could not change Wi-Fi state."

    def get_wifi_status(self) -> tuple[bool, str]:
        """Get current WiFi state."""
        try:
            async def _get_status():
                from winsdk.windows.devices.radios import Radio
                radios = await Radio.get_radios_async()
                wifi = next((r for r in radios if r.kind.name == 'WI_FI'), None)
                if wifi:
                    return True, f"Wi-Fi is {wifi.state.name.lower()}."
                return False, "No Wi-Fi radio found."

            return asyncio.run(_get_status())
        except Exception as e:
            return False, f"Cannot check WiFi status: {e}"
