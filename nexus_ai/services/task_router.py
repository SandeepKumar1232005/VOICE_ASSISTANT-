"""
Nexus AI — Task Router

Central dispatcher that receives task groups from the Planner Agent,
validates through Security Agent, and routes to the correct agent for execution.
Supports parallel and sequential execution modes.
"""

import asyncio
from typing import Optional

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.utils.logger import get_logger

logger = get_logger("TaskRouter")


class TaskRouter:
    """
    Task Router — Dispatches planned tasks to registered agents.
    
    Receives execution groups from the Planner Agent and:
    1. Validates each task through the Security Agent
    2. Routes to the correct agent based on action type
    3. Executes parallel groups concurrently
    4. Collects and returns all results
    """

    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}
        self._security_agent = None
        logger.info("Task Router initialized")

    def register_agent(self, name: str, agent: BaseAgent):
        """Register an agent that can handle tasks."""
        self._agents[name] = agent
        logger.debug(f"Registered agent: {name}")

    def register_security_agent(self, agent):
        """Register the security agent for task validation."""
        self._security_agent = agent
        logger.debug("Security agent registered")

    async def execute_plan(
        self,
        execution_plan: list[dict],
        voice_confirm_callback=None,
    ) -> list[AgentResult]:
        """
        Execute a full plan produced by the Planner Agent.
        
        Args:
            execution_plan: List of task groups from PlannerAgent.plan()
            voice_confirm_callback: Async callback for voice confirmation
                                    (used by Security Agent)
        
        Returns:
            List of AgentResults from all executed tasks
        """
        all_results = []

        for group_idx, group in enumerate(execution_plan):
            is_parallel = group.get("parallel", False)
            tasks = group.get("tasks", [])

            if not tasks:
                continue

            mode = "parallel" if is_parallel else "sequential"
            logger.info(
                f"Executing group {group_idx + 1}/{len(execution_plan)} "
                f"({mode}, {len(tasks)} tasks)"
            )

            if is_parallel:
                results = await self._execute_parallel(tasks, voice_confirm_callback)
            else:
                results = await self._execute_sequential(tasks, voice_confirm_callback)

            all_results.extend(results)

        logger.info(
            f"Plan execution complete: {len(all_results)} results "
            f"({sum(1 for r in all_results if r.success)} succeeded)"
        )
        return all_results

    async def _execute_parallel(
        self,
        tasks: list[dict],
        voice_confirm_callback=None,
    ) -> list[AgentResult]:
        """Execute multiple tasks in parallel."""
        coroutines = [
            self._execute_single_task(task, voice_confirm_callback)
            for task in tasks
        ]
        results = await asyncio.gather(*coroutines, return_exceptions=True)

        # Convert exceptions to AgentResults
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(AgentResult(
                    success=False,
                    message=f"Task failed: {result}",
                    error=str(result),
                    agent=tasks[i].get("agent", "Unknown"),
                ))
            else:
                final_results.append(result)

        return final_results

    async def _execute_sequential(
        self,
        tasks: list[dict],
        voice_confirm_callback=None,
    ) -> list[AgentResult]:
        """Execute tasks one at a time in order."""
        results = []
        for task in tasks:
            result = await self._execute_single_task(task, voice_confirm_callback)
            results.append(result)

            # If a task fails, we can still continue with other tasks
            if not result.success:
                logger.warning(
                    f"Task {task.get('task_id', '?')} failed, "
                    f"continuing with remaining tasks"
                )

        return results

    async def _execute_single_task(
        self,
        task: dict,
        voice_confirm_callback=None,
    ) -> AgentResult:
        """
        Execute a single task with security validation.
        
        Flow:
        1. Check if task requires confirmation
        2. If yes, ask Security Agent to validate
        3. Route to the correct agent
        4. Return the result
        """
        action = task.get("action", "UNKNOWN")
        agent_name = task.get("agent", "")
        task_id = task.get("task_id", "???")

        # Security check
        if task.get("requires_confirmation", False):
            security_result = await self._security_check(
                task, voice_confirm_callback
            )
            if not security_result.success:
                logger.info(f"Task {task_id} blocked by security: {security_result.message}")
                return security_result

        # Find the agent
        agent = self._agents.get(agent_name)
        if agent is None:
            logger.warning(f"No agent registered for '{agent_name}' (action: {action})")
            return AgentResult(
                success=False,
                message=f"I don't have the capability to {action.lower().replace('_', ' ')} yet.",
                agent=agent_name,
            )

        # Execute via the agent's safe wrapper
        return await agent.safe_execute(task)

    async def _security_check(
        self,
        task: dict,
        voice_confirm_callback=None,
    ) -> AgentResult:
        """
        Run a task through the security agent for validation.
        """
        if self._security_agent is None:
            logger.warning("No security agent registered! Allowing task by default.")
            return AgentResult(success=True, message="No security agent configured")

        # Pass the confirmation callback to security agent
        return await self._security_agent.validate_task(
            task, voice_confirm_callback
        )

    def get_registered_agents(self) -> list[str]:
        """Get names of all registered agents."""
        return list(self._agents.keys())
