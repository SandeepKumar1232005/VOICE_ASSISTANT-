import os
import asyncio
from winsdk.windows.devices.radios import Radio, RadioState

class AirplaneModeManager:
    def __init__(self):
        pass

    async def _toggle_airplane(self, enable):
        try:
            radios = await Radio.get_radios_async()
            target_state = RadioState.OFF if enable else RadioState.ON
            
            # Change state of all wireless radios matching typical Airplane Mode profiles
            for radio in radios:
                if radio.kind.name in ['WI_FI', 'BLUETOOTH', 'MOBILE_BROADBAND']:
                    await radio.set_state_async(target_state)
            
            return True, "Airplane mode toggled natively."
        except Exception as e:
            return False, f"WinRT error: {e}"

    def set_airplane_mode(self, enable=True):
        """
        Toggles off all Windows Wireless Radios to simulate Airplane Mode natively.
        """
        success, msg = asyncio.run(self._toggle_airplane(enable))
        
        if success:
            action = "Enabled" if enable else "Disabled"
            return True, f"{action} Airplane Mode."
        else:
            os.system("start ms-settings:network-airplanemode")
            return True, "I opened the network settings for you."
