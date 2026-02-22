import os
import asyncio
from winsdk.windows.devices.radios import Radio, RadioState

class WiFiManager:
    def __init__(self):
        pass

    async def _toggle_wifi(self, enable):
        try:
            radios = await Radio.get_radios_async()
            wifi_radio = next((r for r in radios if r.kind.name == 'WI_FI'), None)
            
            if wifi_radio:
                target_state = RadioState.ON if enable else RadioState.OFF
                await wifi_radio.set_state_async(target_state)
                return True, "Wi-Fi radio state updated."
            else:
                return False, "No Wi-Fi radio found on this system."
        except Exception as e:
            return False, f"WinRT error: {e}"

    def set_wifi_state(self, enable=True):
        """
        Enables or disables the WiFi adapter natively.
        """
        success, msg = asyncio.run(self._toggle_wifi(enable))
        
        if success:
            action = "Enabled" if enable else "Disabled"
            return True, f"{action} Wi-Fi."
        else:
            return False, "Could not change Wi-Fi state natively."
