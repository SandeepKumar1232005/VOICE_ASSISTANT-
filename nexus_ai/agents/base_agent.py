"""
Nexus AI — Base Agent

Abstract base class that all 11 agents inherit from.
Provides standardized interface, logging, and error handling.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime

from nexus_ai.utils.logger import get_logger


@dataclass
class AgentResult:
    """
    Standardized result returned by all agent operations.
    
    Attributes:
        success: Whether the operation succeeded
        message: Human-readable message for TTS output
        data: Optional structured data (for inter-agent communication)
        error: Error details if success is False
        agent: Name of the agent that produced this result
    """
    success: bool
    message: str
    data: Optional[dict] = None
    error: Optional[str] = None
    agent: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "error": self.error,
            "agent": self.agent,
            "timestamp": self.timestamp,
        }


class BaseAgent(ABC):
    """
    Abstract base class for all Nexus AI agents.
    
    Every agent must implement:
        - execute(task) -> AgentResult
        - get_capabilities() -> list[str]
    
    Provides:
        - Automatic logging
        - Error handling wrapper
        - Consistent result formatting
    """

    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(name)
        self.logger.info(f"{name} initialized")

    @abstractmethod
    async def execute(self, task: dict) -> AgentResult:
        """
        Execute a task and return a structured result.
        
        Args:
            task: A task dictionary with at minimum:
                - task_id: str
                - action: str
                - parameters: dict
        
        Returns:
            AgentResult with success status and message
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """
        Return a list of action types this agent can handle.
        
        Used by the Task Router to determine which agent should 
        handle a given task.
        
        Returns:
            List of action type strings (e.g., ['OPEN_APP', 'CLOSE_APP'])
        """
        pass

    async def safe_execute(self, task: dict) -> AgentResult:
        """
        Wrapper around execute() that catches exceptions and 
        returns a failure AgentResult instead of crashing.
        """
        action = task.get("action", "UNKNOWN")
        task_id = task.get("task_id", "???")

        self.logger.info(f"Executing task {task_id}: {action}")

        try:
            result = await self.execute(task)
            result.agent = self.name

            if result.success:
                self.logger.info(f"Task {task_id} completed: {result.message}")
            else:
                self.logger.warning(f"Task {task_id} failed: {result.message}")

            return result

        except Exception as e:
            error_msg = f"Agent {self.name} crashed on task {task_id}: {e}"
            self.logger.error(error_msg, exc_info=True)
            return AgentResult(
                success=False,
                message=f"Sorry, I encountered an error while trying to {action.lower().replace('_', ' ')}.",
                error=str(e),
                agent=self.name,
            )

    def _run_sync(self, coro):
        """
        Helper to run an async coroutine synchronously.
        Useful when called from sync context.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an event loop already — create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return asyncio.run(coro)
