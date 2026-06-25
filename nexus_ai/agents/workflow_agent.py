"""
Nexus AI — Workflow Agent

Manages predefined and custom multi-step workflow modes.
Allows users to create, execute, list, and delete workflows via natural language.

Examples:
    "Start my coding session" → Opens VS Code, Chrome, Terminal, GitHub, starts backend
    "College Mode" → Opens Chrome, Google Classroom, Gmail, Notes folder
    "Create a workflow called Gaming Mode: open Steam, Discord, and set brightness to max"
"""

import asyncio
from typing import Optional

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.database import Database
from nexus_ai.utils.helpers import load_json_config

logger = get_logger("WorkflowAgent")


# ─── Predefined Workflow Templates ─────────────────────────────────
# These are registered on first startup if not already in the database.

PREDEFINED_WORKFLOWS = {
    "coding_mode": {
        "name": "Coding Mode",
        "trigger_phrase": "coding mode",
        "description": "Opens your full development environment",
        "steps": [
            {"action": "OPEN_APP", "parameters": {"app_name": "visual studio code"}},
            {"action": "OPEN_APP", "parameters": {"app_name": "terminal"}},
            {"action": "OPEN_WEBSITE", "parameters": {"site_name": "github"}},
            {"action": "OPEN_WEBSITE", "parameters": {"site_name": "stackoverflow"}},
        ],
    },
    "study_mode": {
        "name": "Study Mode",
        "trigger_phrase": "study mode",
        "description": "Sets up a focused study environment",
        "steps": [
            {"action": "OPEN_APP", "parameters": {"app_name": "notepad"}},
            {"action": "OPEN_WEBSITE", "parameters": {"site_name": "google classroom"}},
            {"action": "BRIGHTNESS_DOWN", "parameters": {}},
            {"action": "VOLUME_DOWN", "parameters": {}},
        ],
    },
    "movie_mode": {
        "name": "Movie Mode",
        "trigger_phrase": "movie mode",
        "description": "Prepares your system for watching movies",
        "steps": [
            {"action": "BRIGHTNESS_DOWN", "parameters": {}},
            {"action": "VOLUME_DOWN", "parameters": {}},
            {"action": "NIGHT_MODE_ON", "parameters": {}},
        ],
    },
    "meeting_mode": {
        "name": "Meeting Mode",
        "trigger_phrase": "meeting mode",
        "description": "Prepares for an online meeting",
        "steps": [
            {"action": "OPEN_APP", "parameters": {"app_name": "microsoft teams"}},
            {"action": "OPEN_APP", "parameters": {"app_name": "notepad"}},
            {"action": "VOLUME_MUTE", "parameters": {}},
        ],
    },
    "gaming_mode": {
        "name": "Gaming Mode",
        "trigger_phrase": "gaming mode",
        "description": "Prepares your system for gaming",
        "steps": [
            {"action": "OPEN_APP", "parameters": {"app_name": "steam"}},
            {"action": "OPEN_APP", "parameters": {"app_name": "discord"}},
            {"action": "BRIGHTNESS_UP", "parameters": {}},
        ],
    },
    "travel_mode": {
        "name": "Travel Mode",
        "trigger_phrase": "travel mode",
        "description": "Prepares for leaving — checks battery, weather, opens maps",
        "steps": [
            {"action": "CHECK_BATTERY", "parameters": {}},
            {"action": "SEARCH_WEB", "parameters": {"query": "weather today"}},
            {"action": "OPEN_WEBSITE", "parameters": {"url": "https://maps.google.com", "site_name": "Google Maps"}},
        ],
    },
}


class WorkflowAgent(BaseAgent):
    """
    Workflow Agent — Multi-step workflow automation.

    Capabilities:
        - Execute predefined workflows (Coding, Study, Movie, Meeting, Gaming, Travel)
        - Create custom user-defined workflows via natural language
        - List, delete, and toggle workflows
        - Expand workflow steps into tasks for the Planner/Router pipeline
    """

    def __init__(self, db: Database):
        super().__init__("WorkflowAgent")
        self.db = db

        # Seed predefined workflows if they don't exist yet
        self._seed_predefined_workflows()

    def _seed_predefined_workflows(self):
        """Register predefined workflows if not already in the database."""
        existing = {w["name"].lower() for w in self.db.get_all_workflows()}

        for key, wf in PREDEFINED_WORKFLOWS.items():
            if wf["name"].lower() not in existing:
                self.db.save_workflow(
                    name=wf["name"],
                    trigger_phrase=wf["trigger_phrase"],
                    steps=wf["steps"],
                    description=wf["description"],
                )
                logger.debug(f"Seeded predefined workflow: {wf['name']}")

        logger.info(f"Workflows ready: {len(self.db.get_all_workflows())} total")

    async def execute(self, task: dict) -> AgentResult:
        action = task.get("action", "")
        params = task.get("parameters", {})

        if action == "EXECUTE_WORKFLOW":
            return await self._execute_workflow(params)
        elif action == "CREATE_WORKFLOW":
            return self._create_workflow(params)
        elif action == "LIST_WORKFLOWS":
            return self._list_workflows()
        elif action == "DELETE_WORKFLOW":
            return self._delete_workflow(params)

        return AgentResult(success=False, message=f"Unknown workflow action: {action}")

    async def _execute_workflow(self, params: dict) -> AgentResult:
        """
        Execute a workflow by name or trigger phrase.

        Instead of executing steps directly, this returns the expanded
        task list so the Planner/Router can handle routing and security.
        """
        name = params.get("name", "").strip()
        trigger = params.get("trigger", "").strip()

        # Try finding by name first, then by trigger phrase
        workflow = None
        if name:
            workflow = self.db.get_workflow(name)
        if not workflow and trigger:
            workflow = self.db.get_workflow_by_trigger(trigger)
        if not workflow and name:
            # Fuzzy match: try matching by trigger with the name
            workflow = self.db.get_workflow_by_trigger(name)

        if not workflow:
            search_term = name or trigger or "unknown"
            return AgentResult(
                success=False,
                message=f"I don't have a workflow called '{search_term}'. "
                        f"Say 'list workflows' to see available ones.",
            )

        if not workflow.get("enabled", True):
            return AgentResult(
                success=False,
                message=f"The '{workflow['name']}' workflow is currently disabled.",
            )

        steps = workflow.get("steps", [])
        if not steps:
            return AgentResult(
                success=False,
                message=f"The '{workflow['name']}' workflow has no steps defined.",
            )

        # Return the expanded steps as data so the orchestrator can feed them
        # back through the Planner → Router pipeline
        step_count = len(steps)
        step_descriptions = []
        for s in steps:
            action_name = s.get("action", "").replace("_", " ").lower()
            app = s.get("parameters", {}).get("app_name", "")
            site = s.get("parameters", {}).get("site_name", "")
            target = app or site or ""
            step_descriptions.append(f"{action_name} {target}".strip())

        summary = ", ".join(step_descriptions[:5])
        if step_count > 5:
            summary += f", and {step_count - 5} more"

        logger.info(f"Executing workflow '{workflow['name']}' with {step_count} steps")

        return AgentResult(
            success=True,
            message=f"Starting '{workflow['name']}' workflow: {summary}.",
            data={
                "workflow_name": workflow["name"],
                "workflow_steps": steps,
                "step_count": step_count,
            },
        )

    def _create_workflow(self, params: dict) -> AgentResult:
        """Create a new custom workflow."""
        name = params.get("name", "").strip()
        trigger = params.get("trigger", "").strip()
        steps = params.get("steps", [])
        description = params.get("description", "")

        if not name:
            return AgentResult(
                success=False,
                message="I need a name for this workflow. For example: 'Create a workflow called Morning Routine'.",
            )

        if not steps:
            return AgentResult(
                success=False,
                message=f"The workflow '{name}' needs at least one step. "
                        f"Tell me what actions to include.",
            )

        # Use the name as trigger if no explicit trigger is provided
        if not trigger:
            trigger = name.lower()

        workflow_id = self.db.save_workflow(
            name=name,
            trigger_phrase=trigger,
            steps=steps,
            description=description,
        )

        logger.info(f"Created custom workflow: '{name}' (#{workflow_id}) with {len(steps)} steps")

        return AgentResult(
            success=True,
            message=f"Created workflow '{name}' with {len(steps)} steps. "
                    f"You can activate it by saying '{trigger}'.",
            data={"workflow_id": workflow_id, "name": name},
        )

    def _list_workflows(self) -> AgentResult:
        """List all available workflows."""
        workflows = self.db.get_all_workflows()

        if not workflows:
            return AgentResult(
                success=True,
                message="You don't have any workflows set up yet. "
                        "You can create one by saying something like "
                        "'Create a workflow called College Mode that opens Chrome and Gmail'.",
            )

        items = []
        for wf in workflows:
            status = "enabled" if wf.get("enabled", True) else "disabled"
            step_count = len(wf.get("steps", []))
            items.append(f"{wf['name']} ({step_count} steps, {status})")

        msg = f"You have {len(workflows)} workflow(s): " + ". ".join(items) + "."
        return AgentResult(
            success=True,
            message=msg,
            data={"workflows": workflows},
        )

    def _delete_workflow(self, params: dict) -> AgentResult:
        """Delete a workflow by name."""
        name = params.get("name", "").strip()

        if not name:
            return AgentResult(
                success=False,
                message="Which workflow would you like to delete?",
            )

        deleted = self.db.delete_workflow(name)
        if deleted:
            logger.info(f"Deleted workflow: '{name}'")
            return AgentResult(
                success=True,
                message=f"Workflow '{name}' has been deleted.",
            )
        else:
            return AgentResult(
                success=False,
                message=f"I couldn't find a workflow called '{name}'.",
            )

    def get_capabilities(self) -> list[str]:
        return ["EXECUTE_WORKFLOW", "CREATE_WORKFLOW", "LIST_WORKFLOWS", "DELETE_WORKFLOW"]
