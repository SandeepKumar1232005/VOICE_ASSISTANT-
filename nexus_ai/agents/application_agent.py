"""
Nexus AI — Application Agent

Opens, closes, restarts, and lists applications.
"""

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.system.apps import AppController
from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.database import Database

logger = get_logger("ApplicationAgent")


class ApplicationAgent(BaseAgent):
    """
    Application Agent — Manages desktop applications.
    
    Capabilities:
        - Open any installed application by name
        - Close running applications
        - Restart applications
        - List running processes
    """

    def __init__(self, db: Database = None):
        super().__init__("ApplicationAgent")
        self.app_controller = AppController()
        self.db = db

    async def execute(self, task: dict) -> AgentResult:
        action = task.get("action", "")
        params = task.get("parameters", {})

        if action == "OPEN_APP":
            app_name = params.get("app_name", "")
            if not app_name:
                return AgentResult(success=False, message="No application name specified.")

            success, message = self.app_controller.launch(app_name)

            # Track usage
            if success and self.db:
                self.db.track_app_usage(app_name)

            return AgentResult(success=success, message=message)

        elif action == "CLOSE_APP":
            app_name = params.get("app_name", "")
            if not app_name:
                return AgentResult(success=False, message="No application name specified.")

            success, message = self.app_controller.close(app_name)
            return AgentResult(success=success, message=message)

        elif action == "RESTART_APP":
            app_name = params.get("app_name", "")
            if not app_name:
                return AgentResult(success=False, message="No application name specified.")

            success, message = self.app_controller.restart_app(app_name)
            return AgentResult(success=success, message=message)

        elif action == "LIST_RUNNING_APPS":
            success, message = self.app_controller.list_running_apps()
            return AgentResult(success=success, message=message)

        return AgentResult(success=False, message=f"Unknown application action: {action}")

    def get_capabilities(self) -> list[str]:
        return ["OPEN_APP", "CLOSE_APP", "RESTART_APP", "LIST_RUNNING_APPS"]
