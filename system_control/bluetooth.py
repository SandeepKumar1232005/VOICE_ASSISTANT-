import os
import asyncio
from winsdk.windows.devices.radios import Radio, RadioState

class BluetoothManager:
    def __init__(self):
        pass

    async def _toggle_bluetooth(self, enable):
        try:
            radios = await Radio.get_radios_async()
            bt_radio = next((r for r in radios if r.kind.name == 'BLUETOOTH'), None)
            
            if bt_radio:
                target_state = RadioState.ON if enable else RadioState.OFF
                await bt_radio.set_state_async(target_state)
                return True, "Bluetooth radio state updated."
            else:
                return False, "No Bluetooth radio found on this system."
        except Exception as e:
            return False, f"WinRT error: {e}"

    def set_bluetooth_state(self, enable=True):
        """
        Toggles Windows Bluetooth state. 
        Will try WinRT radio first, then fall back to opening settings if hardware is misconfigured.
        """
        success, msg = asyncio.run(self._toggle_bluetooth(enable))
        
        if success:
            action = "Enabled" if enable else "Disabled"
            return True, f"{action} Bluetooth."
        else:
            # Fallback: Just open the settings page so the user can do it manually
            os.system("start ms-settings:bluetooth")
            return True, "I opened the Bluetooth settings for you."
