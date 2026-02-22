import subprocess
import base64
import os

class BluetoothManager:
    def set_bluetooth_state(self, enable=True):
        """
        Toggles Windows Bluetooth state. 
        Will try WinRT radio first, then fall back to opening settings if hardware is misconfigured.
        """
        state_str = "On" if enable else "Off"
        
        ps_script = f'''
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
        $radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().GetResults()
        $bt = $radios | Where-Object {{ $_.Kind -eq "Bluetooth" }}
        if ($bt) {{
            $bt.SetStateAsync("{state_str}").GetResults()
        }} else {{
            Write-Error "No Bluetooth radio found"
        }}
        '''
        
        try:
            encoded_cmd = base64.b64encode(ps_script.encode('utf-16le')).decode('utf-8')
            result = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_cmd], 
                                    capture_output=True, text=True)
            
            if result.returncode == 0:
                action = "Enabled" if enable else "Disabled"
                return True, f"{action} Bluetooth."
            else:
                # Fallback: Just open the settings page so the user can do it
                os.system("start ms-settings:bluetooth")
                return True, "I opened the Bluetooth settings for you."
                
        except Exception as e:
            return False, f"Bluetooth error: {e}"
