"""
Nexus AI — Bluetooth Control

Manages Bluetooth state using Windows WinRT Radio API.
Migrated from the original system_control/bluetooth.py.
"""

import os
import asyncio
from nexus_ai.utils.logger import get_logger

logger = get_logger("Bluetooth")


class BluetoothController:
    """Controls Bluetooth radio state using WinRT API."""

    async def _toggle_bluetooth(self, enable: bool):
        """Toggle Bluetooth radio on/off."""
        try:
            from winsdk.windows.devices.radios import Radio, RadioState

            radios = await Radio.get_radios_async()
            bt_radio = next((r for r in radios if r.kind.name == 'BLUETOOTH'), None)

            if bt_radio:
                target_state = RadioState.ON if enable else RadioState.OFF
                await bt_radio.set_state_async(target_state)
                return True, "Bluetooth radio state updated."
            else:
                return False, "No Bluetooth radio found."
        except ImportError:
            return False, "WinSDK not available for Bluetooth control."
        except Exception as e:
            return False, f"Bluetooth error: {e}"

    def set_bluetooth_state(self, enable: bool = True) -> tuple[bool, str]:
        """Enable or disable Bluetooth."""
        try:
            success, msg = asyncio.run(self._toggle_bluetooth(enable))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            success, msg = loop.run_until_complete(self._toggle_bluetooth(enable))
            loop.close()

        if success:
            action = "Enabled" if enable else "Disabled"
            logger.info(f"{action} Bluetooth")
            return True, f"{action} Bluetooth."
        else:
            # Fallback: open settings
            os.system("start ms-settings:bluetooth")
            logger.warning("Bluetooth toggle failed, opened settings")
            return True, "I opened the Bluetooth settings for you."

    def get_bluetooth_status(self) -> tuple[bool, str]:
        """Get current Bluetooth state."""
        try:
            async def _get_status():
                from winsdk.windows.devices.radios import Radio
                radios = await Radio.get_radios_async()
                bt = next((r for r in radios if r.kind.name == 'BLUETOOTH'), None)
                if bt:
                    return True, f"Bluetooth is {bt.state.name.lower()}."
                return False, "No Bluetooth radio found."

            return asyncio.run(_get_status())
        except Exception as e:
            return False, f"Cannot check Bluetooth status: {e}"
