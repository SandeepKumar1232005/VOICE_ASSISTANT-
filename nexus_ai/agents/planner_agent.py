"""
Nexus AI — Planner Agent

The brain of the system. Takes the Conversation Agent's structured output
and plans the optimal execution order, grouping parallel tasks and
sequencing dependent ones.
"""

import asyncio
from typing import Optional

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.services.nemotron_api import NemotronClient
from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.helpers import generate_task_id, load_json_config

logger = get_logger("PlannerAgent")

# Actions that are dangerous and require security confirmation
DANGEROUS_ACTIONS = {
    "SHUTDOWN", "RESTART", "LOGOUT", "FACTORY_RESET",
    "DELETE_FILE", "DELETE_FOLDER", "EMPTY_RECYCLE_BIN",
    "FORMAT_DRIVE", "UNINSTALL_APP", "CHANGE_REGISTRY",
    "DISABLE_ANTIVIRUS", "MOVE_FILE",
}

# Actions that must run sequentially (they depend on the previous action)
SEQUENTIAL_DEPENDENCIES = {
    # After opening an app, subsequent actions on that app must wait
    "OPEN_APP": ["NAVIGATE_TO_URL"],
    "OPEN_FOLDER": ["FIND_FILE"],
}

# Agent routing map: action → agent name
ACTION_TO_AGENT = {
    # System Agent
    "WIFI_ON": "SystemAgent", "WIFI_OFF": "SystemAgent",
    "BLUETOOTH_ON": "SystemAgent", "BLUETOOTH_OFF": "SystemAgent",
    "VOLUME_UP": "SystemAgent", "VOLUME_DOWN": "SystemAgent", "VOLUME_MUTE": "SystemAgent",
    "BRIGHTNESS_UP": "SystemAgent", "BRIGHTNESS_DOWN": "SystemAgent",
    "NIGHT_MODE_ON": "SystemAgent", "NIGHT_MODE_OFF": "SystemAgent",
    "SCREENSHOT": "SystemAgent",
    "SHUTDOWN": "SystemAgent", "RESTART": "SystemAgent",
    "SLEEP": "SystemAgent", "LOCK_SCREEN": "SystemAgent", "LOGOUT": "SystemAgent",
    "CHECK_BATTERY": "SystemAgent", "CHECK_RAM": "SystemAgent", "CHECK_STORAGE": "SystemAgent",

    # Application Agent
    "OPEN_APP": "ApplicationAgent", "CLOSE_APP": "ApplicationAgent",
    "RESTART_APP": "ApplicationAgent", "LIST_RUNNING_APPS": "ApplicationAgent",

    # File Agent
    "OPEN_FOLDER": "FileAgent", "FIND_FILE": "FileAgent",
    "CREATE_FOLDER": "FileAgent", "DELETE_FILE": "FileAgent",
    "MOVE_FILE": "FileAgent", "COPY_FILE": "FileAgent",
    "RENAME_FILE": "FileAgent", "COMPRESS_FILE": "FileAgent",
    "EXTRACT_FILE": "FileAgent", "EMPTY_RECYCLE_BIN": "FileAgent",

    # Browser Agent
    "OPEN_WEBSITE": "BrowserAgent", "SEARCH_WEB": "BrowserAgent",
    "OPEN_YOUTUBE": "BrowserAgent", "OPEN_GMAIL": "BrowserAgent",
    "OPEN_GITHUB": "BrowserAgent",

    # Productivity Agent
    "SET_TIMER": "ProductivityAgent", "SET_REMINDER": "ProductivityAgent",
    "SET_ALARM": "ProductivityAgent", "CREATE_NOTE": "ProductivityAgent",
    "ADD_TODO": "ProductivityAgent", "LIST_TODOS": "ProductivityAgent",
    "LIST_REMINDERS": "ProductivityAgent",

    # AI Agent
    "ASK_AI": "AIAgent", "EXPLAIN_CODE": "AIAgent",
    "GENERATE_CODE": "AIAgent", "TRANSLATE": "AIAgent",
    "SUMMARIZE": "AIAgent", "DRAFT_EMAIL": "AIAgent",
    "CHECK_WEATHER": "AIAgent",

    # Memory Agent
    "REMEMBER": "MemoryAgent", "RECALL": "MemoryAgent",
}


class PlannerAgent(BaseAgent):
    """
    Planner Agent — The brain that orchestrates task execution.
    
    Responsibilities:
        - Validate tasks against available capabilities
        - Determine execution order (parallel vs sequential)
        - Flag dangerous operations for security confirmation
        - Group independent tasks for parallel execution
        - Handle complex multi-step planning via Nemotron
    """

    def __init__(self, nemotron: Optional[NemotronClient] = None):
        super().__init__("PlannerAgent")
        self.nemotron = nemotron

    def plan(self, conversation_result: dict) -> list[dict]:
        """
        Create an execution plan from the conversation agent's output.
        
        Args:
            conversation_result: Output from ConversationAgent.understand()
        
        Returns:
            Ordered list of task groups. Each group is a dict with:
                - "parallel": bool (can tasks in this group run simultaneously?)
                - "tasks": list of task dicts ready for execution
        """
        raw_tasks = conversation_result.get("tasks", [])

        if not raw_tasks:
            logger.info("No tasks to plan")
            return []

        # Enrich tasks with metadata
        enriched_tasks = []
        for task_info in raw_tasks:
            task = {
                "task_id": generate_task_id(),
                "action": task_info["action"],
                "parameters": task_info.get("parameters", {}),
                "requires_confirmation": self._needs_confirmation(task_info),
                "agent": ACTION_TO_AGENT.get(task_info["action"], "AIAgent"),
                "priority": self._get_priority(task_info["action"]),
            }
            enriched_tasks.append(task)

        # Sort by priority
        enriched_tasks.sort(key=lambda t: t["priority"])

        # Group into parallel/sequential execution groups
        execution_plan = self._create_execution_groups(enriched_tasks)

        logger.info(
            f"Plan created: {len(enriched_tasks)} tasks in {len(execution_plan)} groups"
        )
        for i, group in enumerate(execution_plan):
            mode = "parallel" if group["parallel"] else "sequential"
            actions = [t["action"] for t in group["tasks"]]
            logger.debug(f"  Group {i + 1} ({mode}): {actions}")

        return execution_plan

    def _needs_confirmation(self, task_info: dict) -> bool:
        """Check if a task requires security confirmation."""
        action = task_info.get("action", "")

        # Explicitly marked by the conversation agent
        if task_info.get("requires_confirmation", False):
            return True

        # Check against known dangerous actions
        if action in DANGEROUS_ACTIONS:
            return True

        return False

    def _get_priority(self, action: str) -> int:
        """
        Assign execution priority.
        Lower = executed first.
        """
        # Info queries should run first (fast)
        if action.startswith("CHECK_"):
            return 1
        # System state changes
        if action in ("WIFI_ON", "WIFI_OFF", "BLUETOOTH_ON", "BLUETOOTH_OFF"):
            return 2
        # App/browser launches
        if action in ("OPEN_APP", "OPEN_WEBSITE", "SEARCH_WEB", "OPEN_YOUTUBE"):
            return 3
        # File operations
        if action.startswith(("FIND_", "OPEN_FOLDER", "CREATE_")):
            return 4
        # Productivity
        if action.startswith(("SET_", "CREATE_NOTE", "ADD_TODO")):
            return 5
        # AI tasks (slowest)
        if action in ("ASK_AI", "EXPLAIN_CODE", "GENERATE_CODE", "TRANSLATE", "SUMMARIZE"):
            return 6
        # Dangerous operations last
        if action in DANGEROUS_ACTIONS:
            return 10
        return 5

    def _create_execution_groups(self, tasks: list[dict]) -> list[dict]:
        """
        Group tasks into parallel and sequential execution groups.
        
        Rules:
            - Independent tasks of the same priority can run in parallel
            - Dangerous tasks run sequentially (one at a time, with confirmation)
            - Tasks with dependencies run after their dependency
        """
        if not tasks:
            return []

        groups = []

        # Separate dangerous and safe tasks
        dangerous = [t for t in tasks if t["requires_confirmation"]]
        safe = [t for t in tasks if not t["requires_confirmation"]]

        # Group safe tasks by priority (same priority = parallel)
        if safe:
            priority_groups = {}
            for task in safe:
                p = task["priority"]
                if p not in priority_groups:
                    priority_groups[p] = []
                priority_groups[p].append(task)

            for priority in sorted(priority_groups.keys()):
                group_tasks = priority_groups[priority]
                groups.append({
                    "parallel": len(group_tasks) > 1,
                    "tasks": group_tasks,
                })

        # Dangerous tasks run individually with confirmation
        for task in dangerous:
            groups.append({
                "parallel": False,
                "tasks": [task],
            })

        return groups

    async def execute(self, task: dict) -> AgentResult:
        """Execute a planning task."""
        action = task.get("action", "")
        params = task.get("parameters", {})

        if action == "PLAN":
            conversation_result = params.get("conversation_result", {})
            plan = self.plan(conversation_result)
            return AgentResult(
                success=True,
                message=f"Created plan with {sum(len(g['tasks']) for g in plan)} tasks",
                data={"plan": plan},
            )

        return AgentResult(success=False, message=f"Unknown action: {action}")

    def get_capabilities(self) -> list[str]:
        return ["PLAN"]
