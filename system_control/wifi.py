import subprocess
import base64

class WiFiManager:
    def set_wifi_state(self, enable=True):
        """
        Enables or disables the WiFi adapter using Windows.Devices.Radios to avoid Admin prompts.
        """
        state_str = "On" if enable else "Off"
        
        # PowerShell script to toggle Wi-Fi radio using WinRT
        ps_script = f'''
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
        $radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().GetResults()
        $wifi = $radios | Where-Object {{ $_.Kind -eq "WiFi" }}
        if ($wifi) {{
            $wifi.SetStateAsync("{state_str}").GetResults()
        }}
        '''
        
        try:
            # Encode script to avoid quote escaping issues in subprocess
            encoded_cmd = base64.b64encode(ps_script.encode('utf-16le')).decode('utf-8')
            
            result = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_cmd], 
                                    capture_output=True, text=True)
            
            if result.returncode == 0:
                action = "Enabled" if enable else "Disabled"
                return True, f"{action} Wi-Fi."
            else:
                return False, f"Could not change Wi-Fi state. Windows denied the action."
                
        except Exception as e:
            return False, f"Wi-Fi error: {e}"
