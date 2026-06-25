"""
Nexus AI — Learning Agent

Tracks user patterns over time (e.g. frequently opened apps, common workflows, 
working hours) and learns preferences.
"""

from typing import Optional

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.database import Database

logger = get_logger("LearningAgent")


class LearningAgent(BaseAgent):
    """
    Learning Agent — Learns user habits and routines over time.
    
    Capabilities:
        - GET_USER_HABITS: Analyzes tracked data to identify habits
        - TRACK_EVENT: Internal logging of an event for pattern recognition
    """

    def __init__(self, db: Database):
        super().__init__("LearningAgent")
        self.db = db

    async def execute(self, task: dict) -> AgentResult:
        action = task.get("action", "")
        params = task.get("parameters", {})

        if action == "GET_USER_HABITS":
            return self._get_habits()
        elif action == "TRACK_EVENT":
            return self._track_event(params)

        return AgentResult(success=False, message=f"Unknown learning action: {action}")

    def _track_event(self, params: dict) -> AgentResult:
        """Track an event for pattern learning."""
        event = params.get("event", "")
        details = params.get("details", "")
        if event:
            self.db.track_productivity_event(event_type=f"habit_{event}", details=details)
            return AgentResult(success=True, message=f"Tracked event: {event}")
        return AgentResult(success=False, message="No event specified to track.")

    def _get_habits(self) -> AgentResult:
        """Analyze data and return identified user habits."""
        apps = self.db.get_frequent_apps(limit=3)
        
        if not apps:
            return AgentResult(success=True, message="I haven't learned enough about your habits yet.")
            
        app_names = [a["app_name"].title() for a in apps]
        
        msg = f"Based on my observations, your most frequently used apps are {', '.join(app_names)}."
        return AgentResult(success=True, message=msg, data={"frequent_apps": apps})

    def get_capabilities(self) -> list[str]:
        return ["GET_USER_HABITS", "TRACK_EVENT"]
