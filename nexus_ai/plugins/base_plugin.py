"""
Nexus AI — Base Plugin Interface

All custom plugins must inherit from BasePlugin to be dynamically 
loaded and executed by the PluginAgent.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

class BasePlugin(ABC):
    """
    Abstract base class for Nexus AI plugins.
    """
    
    @abstractmethod
    def get_info(self) -> Dict[str, str]:
        """
        Return metadata about the plugin.
        Should include: name, description, version, author.
        """
        pass
        
    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """
        Return a list of action names this plugin can handle.
        Example: ["CALCULATE", "SOLVE_MATH"]
        """
        pass

    @abstractmethod
    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a plugin action.
        
        Args:
            action: The action string (from capabilities)
            params: Dictionary of parameters provided by the NLU
            
        Returns:
            Dictionary matching AgentResult structure:
            {"success": bool, "message": str, "data": optional dict}
        """
        pass
