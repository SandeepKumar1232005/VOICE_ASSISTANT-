"""
Nexus AI — Privacy Agent

Handles stealth mode, screen-sharing detection, and privacy controls.
Ensures sensitive information is not spoken aloud when in public or sharing.
"""

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.utils.logger import get_logger

logger = get_logger("PrivacyAgent")


class PrivacyAgent(BaseAgent):
    """
    Privacy Agent — Stealth and sharing controls.
    
    Capabilities:
        - ENABLE_STEALTH_MODE: Mute voice, respond via UI/notifications only
        - DISABLE_STEALTH_MODE: Restore voice
        - CHECK_SCREEN_SHARING: Detect if screen is currently being shared/recorded
    """

    def __init__(self):
        super().__init__("PrivacyAgent")
        self.stealth_mode = False

    async def execute(self, task: dict) -> AgentResult:
        action = task.get("action", "")

        if action == "ENABLE_STEALTH_MODE":
            self.stealth_mode = True
            logger.info("Stealth mode enabled. Voice output should be muted.")
            return AgentResult(success=True, message="Stealth mode enabled. I will remain quiet.")
            
        elif action == "DISABLE_STEALTH_MODE":
            self.stealth_mode = False
            logger.info("Stealth mode disabled. Voice output restored.")
            return AgentResult(success=True, message="Stealth mode disabled. Voice output is back.")
            
        elif action == "CHECK_SCREEN_SHARING":
            is_sharing = self._is_screen_sharing()
            if is_sharing:
                return AgentResult(
                    success=True, 
                    message="Warning: It looks like your screen is currently being shared or recorded.",
                    data={"sharing": True}
                )
            else:
                return AgentResult(
                    success=True, 
                    message="Your screen does not appear to be shared or recorded right now.",
                    data={"sharing": False}
                )

        return AgentResult(success=False, message=f"Unknown privacy action: {action}")

    def _is_screen_sharing(self) -> bool:
        """
        Check for common screen sharing processes (Zoom, Teams, OBS, etc).
        Note: This is a basic heuristic, not a foolproof security measure.
        """
        import psutil
        
        sharing_processes = [
            "zoom.exe", "teams.exe", "obs64.exe", "obs32.exe", 
            "bdcam.exe", "camtasia.exe", "discord.exe", "slack.exe"
        ]
        
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and proc.info['name'].lower() in sharing_processes:
                    # In a real scenario, we might want to check if it's actively broadcasting,
                    # but for now we just check if the process is running.
                    return True
        except Exception as e:
            logger.error(f"Error checking processes: {e}")
            
        return False

    def get_capabilities(self) -> list[str]:
        return ["ENABLE_STEALTH_MODE", "DISABLE_STEALTH_MODE", "CHECK_SCREEN_SHARING"]
