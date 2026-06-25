"""
Nexus AI — Plugin Agent

Dynamically loads and executes plugins from the plugins/ directory.
Allows extending functionality without touching core code.
"""

import os
import sys
import importlib
import inspect
from typing import Dict, Any

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.utils.logger import get_logger
from nexus_ai.plugins.base_plugin import BasePlugin

logger = get_logger("PluginAgent")


class PluginAgent(BaseAgent):
    """
    Plugin Agent — Dynamically loads and manages third-party plugins.
    """

    def __init__(self):
        super().__init__("PluginAgent")
        self.plugins: Dict[str, BasePlugin] = {}
        self.capabilities = ["LIST_PLUGINS", "RELOAD_PLUGINS"]
        
        self._load_plugins()

    def _load_plugins(self):
        """Discover and load plugins from the plugins directory."""
        plugins_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")
        
        if not os.path.exists(plugins_dir):
            return
            
        # Ensure plugins dir is in path
        if plugins_dir not in sys.path:
            sys.path.insert(0, plugins_dir)
            
        self.plugins.clear()
        self.capabilities = ["LIST_PLUGINS", "RELOAD_PLUGINS"]
        
        for filename in os.listdir(plugins_dir):
            if filename.endswith(".py") and filename != "base_plugin.py" and not filename.startswith("__"):
                module_name = filename[:-3]
                try:
                    # Dynamically import module
                    module = importlib.import_module(f"nexus_ai.plugins.{module_name}")
                    importlib.reload(module)
                    
                    # Find classes that inherit from BasePlugin
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, BasePlugin) and obj != BasePlugin:
                            plugin_instance = obj()
                            plugin_info = plugin_instance.get_info()
                            plugin_name = plugin_info.get("name", name)
                            
                            self.plugins[plugin_name] = plugin_instance
                            plugin_caps = plugin_instance.get_capabilities()
                            self.capabilities.extend(plugin_caps)
                            
                            logger.info(f"Loaded plugin: {plugin_name} (Capabilities: {plugin_caps})")
                except Exception as e:
                    logger.error(f"Failed to load plugin {module_name}: {e}")

    async def execute(self, task: dict) -> AgentResult:
        action = task.get("action", "")
        params = task.get("parameters", {})

        if action == "LIST_PLUGINS":
            return self._list_plugins()
        elif action == "RELOAD_PLUGINS":
            self._load_plugins()
            return AgentResult(success=True, message=f"Reloaded {len(self.plugins)} plugins.")

        # Route to appropriate plugin
        for name, plugin in self.plugins.items():
            if action in plugin.get_capabilities():
                try:
                    logger.debug(f"Routing {action} to {name}")
                    result_dict = plugin.execute(action, params)
                    return AgentResult(
                        success=result_dict.get("success", False),
                        message=result_dict.get("message", ""),
                        data=result_dict.get("data")
                    )
                except Exception as e:
                    logger.error(f"Plugin {name} error on {action}: {e}")
                    return AgentResult(success=False, message=f"Plugin error: {e}")

        return AgentResult(success=False, message=f"Unknown plugin action: {action}")

    def _list_plugins(self) -> AgentResult:
        if not self.plugins:
            return AgentResult(success=True, message="No plugins are currently installed.")
            
        items = []
        for name, plugin in self.plugins.items():
            info = plugin.get_info()
            desc = info.get("description", "No description")
            items.append(f"{name}: {desc}")
            
        msg = f"You have {len(self.plugins)} plugin(s) installed: " + ". ".join(items)
        return AgentResult(success=True, message=msg)

    def get_capabilities(self) -> list[str]:
        return self.capabilities
