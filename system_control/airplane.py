import subprocess
import base64
import os

class AirplaneModeManager:
    def set_airplane_mode(self, enable=True):
        """
        Toggles off all Windows Wireless Radios to simulate Airplane Mode.
        """
        state_str = "Off" if enable else "On"
        
        # Turn off/on all supported radios (Wi-Fi, Bluetooth, MobileBroadband)
        ps_script = f'''
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
        $radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().GetResults()
        foreach ($radio in $radios) {{
            if ($radio.Kind -eq "WiFi" -or $radio.Kind -eq "Bluetooth" -or $radio.Kind -eq "MobileBroadband") {{
                $radio.SetStateAsync("{state_str}").GetResults()
            }}
        }}
        '''
        
        try:
            encoded_cmd = base64.b64encode(ps_script.encode('utf-16le')).decode('utf-8')
            result = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_cmd], 
                                    capture_output=True, text=True)
            
            if result.returncode == 0:
                action = "Enabled" if enable else "Disabled"
                return True, f"{action} Airplane Mode."
            else:
                os.system("start ms-settings:network-airplanemode")
                return True, "I opened the network settings for you."
                
        except Exception as e:
            return False, f"Airplane mode error: {e}"
