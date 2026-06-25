"""
Nexus AI — Memory Agent

Stores and retrieves user preferences, personal info, and custom shortcuts.
All data persisted in SQLite.
"""

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.database import Database

logger = get_logger("MemoryAgent")


class MemoryAgent(BaseAgent):
    """
    Memory Agent — Persistent user preference storage.
    
    Capabilities:
        - Remember user name, preferences, favorites
        - Recall stored information
        - Track frequently used apps
        - Custom shortcuts ("when I say X, do Y")
    
    Memory categories:
        - personal: Name, age, college, etc.
        - preference: Favorite browser, editor, music, etc.
        - routine: Morning routine, evening routine, etc.
        - shortcut: Custom command shortcuts
    """

    def __init__(self, db: Database):
        super().__init__("MemoryAgent")
        self.db = db

    async def execute(self, task: dict) -> AgentResult:
        action = task.get("action", "")
        params = task.get("parameters", {})

        if action == "REMEMBER":
            return self._remember(params)
        elif action == "RECALL":
            return self._recall(params)

        return AgentResult(success=False, message=f"Unknown memory action: {action}")

    def _remember(self, params: dict) -> AgentResult:
        """Store a user preference or personal info."""
        key = params.get("key", "")
        value = params.get("value", "")
        category = params.get("category", "preference")

        if not key or not value:
            return AgentResult(
                success=False,
                message="I need to know what to remember. Please specify a key and value.",
            )

        # Sanitize key
        key = key.lower().strip().replace(" ", "_")

        self.db.set_memory(key, value, category)
        logger.info(f"Remembered: {key} = {value} [{category}]")

        return AgentResult(
            success=True,
            message=f"Got it! I'll remember that {key.replace('_', ' ')} is {value}.",
            data={"key": key, "value": value, "category": category},
        )

    def _recall(self, params: dict) -> AgentResult:
        """Recall stored information."""
        key = params.get("key", "")

        if not key:
            # Return all memories
            memories = self.db.get_all_memories()
            if not memories:
                return AgentResult(
                    success=True,
                    message="I don't have any stored memories yet.",
                )

            # Format for speech
            items = []
            for mem in memories[:10]:
                clean_key = mem["key"].replace("_", " ")
                items.append(f"{clean_key} is {mem['value']}")

            msg = "Here's what I remember: " + ". ".join(items) + "."
            return AgentResult(success=True, message=msg)

        # Look up specific key
        key = key.lower().strip().replace(" ", "_")
        value = self.db.get_memory(key)

        if value:
            clean_key = key.replace("_", " ")
            return AgentResult(
                success=True,
                message=f"Your {clean_key} is {value}.",
                data={"key": key, "value": value},
            )
        else:
            return AgentResult(
                success=False,
                message=f"I don't have any information stored for '{key.replace('_', ' ')}'.",
            )

    def get_user_context(self) -> str:
        """
        Build a context string from all user memories.
        Used by other agents to personalize responses.
        """
        memories = self.db.get_all_memories()
        if not memories:
            return ""

        context_parts = []
        for mem in memories:
            clean_key = mem["key"].replace("_", " ")
            context_parts.append(f"- {clean_key}: {mem['value']}")

        return "User information:\n" + "\n".join(context_parts)

    def get_capabilities(self) -> list[str]:
        return ["REMEMBER", "RECALL"]
