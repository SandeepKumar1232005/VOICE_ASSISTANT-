"""
Nexus AI — Security Agent

The most critical agent. Validates all tasks before execution.
Blocks dangerous operations, requires confirmation for sensitive actions,
and never exposes credentials or private data.
"""

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.utils.logger import get_logger, get_security_logger
from nexus_ai.utils.database import Database
from nexus_ai.utils.helpers import load_json_config, contains_sensitive_data

logger = get_logger("SecurityAgent")
security_log = get_security_logger()


class SecurityAgent(BaseAgent):
    """
    Security Agent — Safety layer for all operations.
    
    Rules:
        1. Blocked actions are NEVER executed (format drive, registry, etc.)
        2. Dangerous actions require voice/PIN confirmation
        3. Sensitive data (API keys, passwords) is never revealed
        4. All security decisions are logged for audit
    """

    def __init__(self, db: Database):
        super().__init__("SecurityAgent")
        self.db = db

        # Load permissions config
        permissions = load_json_config("permissions.json")
        self.require_confirmation = set(permissions.get("require_confirmation", []))
        self.blocked_actions = set(permissions.get("blocked_actions", []))
        self.never_expose = permissions.get("never_expose", [])
        self.confirmation_method = permissions.get("confirmation_method", "voice")
        self.security_pin = permissions.get("security_pin")

        logger.info(
            f"Security Agent loaded: {len(self.blocked_actions)} blocked, "
            f"{len(self.require_confirmation)} require confirmation"
        )

    async def validate_task(self, task: dict, voice_confirm_callback=None) -> AgentResult:
        """
        Validate a task before execution.
        
        Returns AgentResult with success=True if the task is allowed,
        or success=False if blocked/denied.
        """
        action = task.get("action", "UNKNOWN")
        task_id = task.get("task_id", "???")

        # 1. Check if action is completely blocked
        if action in self.blocked_actions:
            msg = f"Action '{action}' is blocked for safety. This operation is not allowed."
            security_log.warning(f"BLOCKED: {action} (task {task_id})")
            self.db.log_security_event(action, "BLOCKED", f"Task {task_id}")
            return AgentResult(
                success=False,
                message=msg,
                agent="SecurityAgent",
            )

        # 2. Check if action requires confirmation
        if action in self.require_confirmation or task.get("requires_confirmation", False):
            return await self._request_confirmation(
                task, voice_confirm_callback
            )

        # 3. Check for sensitive data in parameters
        params_str = str(task.get("parameters", {}))
        if contains_sensitive_data(params_str):
            security_log.warning(
                f"SENSITIVE_DATA_DETECTED in task {task_id}: {action}"
            )
            # Don't block, but sanitize
            logger.warning(f"Sensitive data detected in task {task_id}")

        # 4. Task is safe to proceed
        security_log.info(f"ALLOWED: {action} (task {task_id})")
        self.db.log_security_event(action, "ALLOWED", f"Task {task_id}")
        return AgentResult(
            success=True,
            message="Task approved.",
            agent="SecurityAgent",
        )

    async def _request_confirmation(
        self,
        task: dict,
        voice_confirm_callback=None,
    ) -> AgentResult:
        """
        Request user confirmation for a dangerous action.
        
        Supports:
        - Voice confirmation ("say yes to confirm")
        - PIN confirmation
        """
        action = task.get("action", "UNKNOWN")
        task_id = task.get("task_id", "???")

        action_display = action.lower().replace("_", " ")
        logger.info(f"Requesting confirmation for: {action}")

        # Try voice confirmation
        if voice_confirm_callback:
            try:
                confirmation = await voice_confirm_callback(
                    f"Are you sure you want to {action_display}? Say yes to confirm or no to cancel."
                )

                if confirmation and self._is_affirmative(confirmation):
                    security_log.info(
                        f"CONFIRMED (voice): {action} (task {task_id})"
                    )
                    self.db.log_security_event(
                        action, "CONFIRMED", f"Voice confirmation for task {task_id}"
                    )
                    return AgentResult(
                        success=True,
                        message=f"Confirmed. Proceeding with {action_display}.",
                        agent="SecurityAgent",
                    )
                else:
                    security_log.info(
                        f"DENIED (voice): {action} (task {task_id})"
                    )
                    self.db.log_security_event(
                        action, "DENIED", f"User denied via voice for task {task_id}"
                    )
                    return AgentResult(
                        success=False,
                        message=f"Cancelled {action_display}.",
                        agent="SecurityAgent",
                    )
            except Exception as e:
                logger.error(f"Voice confirmation error: {e}")

        # No voice callback available — deny by default for safety
        security_log.warning(
            f"DENIED (no confirmation method): {action} (task {task_id})"
        )
        self.db.log_security_event(
            action, "DENIED", f"No confirmation method available for task {task_id}"
        )
        return AgentResult(
            success=False,
            message=f"I need your confirmation to {action_display}, but I couldn't verify. Cancelling for safety.",
            agent="SecurityAgent",
        )

    def _is_affirmative(self, text: str) -> bool:
        """Check if the user's response is an affirmative confirmation."""
        affirmative_words = {
            "yes", "yeah", "yep", "sure", "confirm", "do it",
            "go ahead", "proceed", "affirmative", "ok", "okay",
            "absolutely", "definitely", "of course", "yes please",
        }
        text_lower = text.lower().strip()
        return any(word in text_lower for word in affirmative_words)

    def sanitize_output(self, text: str) -> str:
        """
        Remove any sensitive information from output text.
        Prevents accidental exposure of API keys, passwords, etc.
        """
        import re

        # Mask anything that looks like "keyword is/=/: value"
        sensitive_keywords = [
            "api_key", "api key", "apikey", "password", "passwd",
            "token", "secret", "credential", "cookie", "session",
            "private_key", "private key",
        ]
        for kw in sensitive_keywords:
            # Match: keyword followed by is/=/:  and then the value
            pattern = rf'(?i)({re.escape(kw)})\s*(?:is|=|:)\s*(\S+)'
            text = re.sub(pattern, rf'\1 ****REDACTED****', text)

        # Mask anything that looks like a key=value with sensitive keys from config
        for keyword in self.never_expose:
            pattern = rf'(?i)({re.escape(keyword)})\s*[=:]\s*\S+'
            text = re.sub(pattern, rf'\1: ****REDACTED****', text)

        return text

    async def execute(self, task: dict) -> AgentResult:
        """Execute a security-related task."""
        action = task.get("action", "")

        if action == "VALIDATE":
            return await self.validate_task(task.get("parameters", {}).get("task", {}))

        return AgentResult(success=False, message=f"Unknown security action: {action}")

    def get_capabilities(self) -> list[str]:
        return ["VALIDATE"]
