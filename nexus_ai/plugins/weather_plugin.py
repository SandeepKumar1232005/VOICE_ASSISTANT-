"""
Nexus AI — Weather Plugin (Example)
"""

from typing import Dict, Any
from nexus_ai.plugins.base_plugin import BasePlugin

class WeatherPlugin(BasePlugin):
    def get_info(self) -> Dict[str, str]:
        return {
            "name": "Weather Plugin",
            "description": "Fetches weather information",
            "version": "1.0",
            "author": "Nexus Core"
        }
        
    def get_capabilities(self) -> list[str]:
        return ["CHECK_WEATHER_PLUGIN"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "CHECK_WEATHER_PLUGIN":
            location = params.get("location", "your location")
            # In a real plugin, this would call a weather API.
            # For demonstration, we return a simulated response.
            return {
                "success": True, 
                "message": f"The weather in {location} is currently sunny and 72 degrees.",
                "data": {"temp": 72, "condition": "sunny", "location": location}
            }
                
        return {"success": False, "message": f"Unknown action: {action}"}
