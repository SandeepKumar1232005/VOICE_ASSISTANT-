"""
Nexus AI — Productivity Agent

Reminders, timers, alarms, notes, and to-do list management.
All data persisted in SQLite via the Database service.
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.database import Database
from nexus_ai.utils.helpers import format_duration

logger = get_logger("ProductivityAgent")


class ProductivityAgent(BaseAgent):
    """
    Productivity Agent — Personal productivity tools.
    
    Capabilities:
        - Set timers with voice notification
        - Set reminders with datetime parsing
        - Create notes
        - Manage to-do lists
        - List reminders and todos
    """

    def __init__(self, db: Database, tts_callback=None):
        super().__init__("ProductivityAgent")
        self.db = db
        self.tts_callback = tts_callback  # Function to speak notifications
        self.active_timers = []

        # Start reminder checker thread
        self._reminder_thread = threading.Thread(
            target=self._reminder_checker, daemon=True
        )
        self._reminder_thread.start()

    async def execute(self, task: dict) -> AgentResult:
        action = task.get("action", "")
        params = task.get("parameters", {})

        if action == "SET_TIMER":
            return self._set_timer(params)
        elif action == "SET_REMINDER":
            return self._set_reminder(params)
        elif action == "SET_ALARM":
            return self._set_alarm(params)
        elif action == "CREATE_NOTE":
            return self._create_note(params)
        elif action == "ADD_TODO":
            return self._add_todo(params)
        elif action == "LIST_TODOS":
            return self._list_todos()
        elif action == "LIST_REMINDERS":
            return self._list_reminders()

        return AgentResult(success=False, message=f"Unknown productivity action: {action}")

    def _set_timer(self, params: dict) -> AgentResult:
        """Set a countdown timer."""
        duration = params.get("duration", 0)
        unit = params.get("unit", "minutes").lower()

        if not duration:
            return AgentResult(success=False, message="No timer duration specified.")

        # Convert to seconds
        multiplier = {"seconds": 1, "second": 1, "minutes": 60, "minute": 60,
                       "hours": 3600, "hour": 3600}.get(unit, 60)
        total_seconds = int(duration) * multiplier

        # Start timer thread
        timer_thread = threading.Thread(
            target=self._run_timer,
            args=(total_seconds, duration, unit),
            daemon=True,
        )
        timer_thread.start()
        self.active_timers.append(timer_thread)

        readable = format_duration(total_seconds)
        logger.info(f"Timer set: {readable}")
        return AgentResult(success=True, message=f"Timer set for {readable}.")

    def _run_timer(self, seconds: int, amount, unit: str):
        """Timer thread — waits then notifies."""
        time.sleep(seconds)
        msg = f"Your timer for {amount} {unit} is up!"
        logger.info(msg)
        if self.tts_callback:
            self.tts_callback(msg)

    def _set_reminder(self, params: dict) -> AgentResult:
        """Set a reminder with optional time."""
        task_text = params.get("task", "")
        time_str = params.get("time", "")

        if not task_text:
            return AgentResult(success=False, message="No reminder task specified.")

        # Parse time
        remind_at = None
        if time_str:
            try:
                import dateparser
                parsed = dateparser.parse(time_str, settings={
                    'PREFER_DATES_FROM': 'future',
                    'RELATIVE_BASE': datetime.now(),
                })
                if parsed:
                    remind_at = parsed.isoformat()
            except ImportError:
                logger.warning("dateparser not installed, using default reminder time")
            except Exception as e:
                logger.debug(f"Date parsing failed: {e}")

        if not remind_at:
            # Default: remind in 1 hour
            remind_at = (datetime.now() + timedelta(hours=1)).isoformat()

        reminder_id = self.db.add_reminder(task_text, remind_at)
        logger.info(f"Reminder #{reminder_id}: '{task_text}' at {remind_at}")

        # Format time for speech
        try:
            dt = datetime.fromisoformat(remind_at)
            time_display = dt.strftime("%I:%M %p")
            return AgentResult(
                success=True,
                message=f"I'll remind you to {task_text} at {time_display}.",
            )
        except Exception:
            return AgentResult(
                success=True,
                message=f"I'll remind you to {task_text}.",
            )

    def _set_alarm(self, params: dict) -> AgentResult:
        """Set an alarm (implemented as a reminder)."""
        time_str = params.get("time", "")
        if not time_str:
            return AgentResult(success=False, message="No alarm time specified.")

        params["task"] = f"Alarm at {time_str}"
        return self._set_reminder(params)

    def _create_note(self, params: dict) -> AgentResult:
        """Create a note."""
        content = params.get("content", "")
        title = params.get("title")

        if not content:
            return AgentResult(success=False, message="No note content provided.")

        note_id = self.db.create_note(content, title)
        logger.info(f"Note #{note_id} created: {content[:50]}")
        return AgentResult(
            success=True,
            message=f"Note created: {content[:100]}",
        )

    def _add_todo(self, params: dict) -> AgentResult:
        """Add a to-do item."""
        task_text = params.get("task", "")
        due_date = params.get("due_date")

        if not task_text:
            return AgentResult(success=False, message="No to-do task specified.")

        # Parse due date if provided
        if due_date:
            try:
                import dateparser
                parsed = dateparser.parse(due_date, settings={
                    'PREFER_DATES_FROM': 'future'
                })
                if parsed:
                    due_date = parsed.isoformat()
            except (ImportError, Exception):
                due_date = None

        todo_id = self.db.add_todo(task_text, due_date)
        logger.info(f"Todo #{todo_id}: {task_text}")
        return AgentResult(success=True, message=f"Added to your to-do list: {task_text}.")

    def _list_todos(self) -> AgentResult:
        """List all pending to-do items."""
        todos = self.db.get_todos(include_completed=False)

        if not todos:
            return AgentResult(success=True, message="Your to-do list is empty.")

        items = [t["task"] for t in todos[:10]]
        msg = f"You have {len(todos)} to-do items. " + ". ".join(
            f"{i+1}: {item}" for i, item in enumerate(items)
        )
        return AgentResult(success=True, message=msg)

    def _list_reminders(self) -> AgentResult:
        """List all active reminders."""
        reminders = self.db.get_all_reminders()

        if not reminders:
            return AgentResult(success=True, message="You have no active reminders.")

        items = []
        for r in reminders[:5]:
            try:
                dt = datetime.fromisoformat(r["remind_at"])
                time_str = dt.strftime("%I:%M %p")
                items.append(f"{r['task']} at {time_str}")
            except Exception:
                items.append(r["task"])

        msg = f"You have {len(reminders)} reminder(s). " + ". ".join(items)
        return AgentResult(success=True, message=msg)

    def _reminder_checker(self):
        """Background thread that checks for due reminders every 30 seconds."""
        while True:
            try:
                pending = self.db.get_pending_reminders()
                for reminder in pending:
                    msg = f"Reminder: {reminder['task']}"
                    logger.info(msg)
                    if self.tts_callback:
                        self.tts_callback(msg)
                    self.db.mark_reminder_notified(reminder["id"])
            except Exception as e:
                logger.debug(f"Reminder check error: {e}")

            time.sleep(30)

    def get_capabilities(self) -> list[str]:
        return [
            "SET_TIMER", "SET_REMINDER", "SET_ALARM",
            "CREATE_NOTE", "ADD_TODO", "LIST_TODOS", "LIST_REMINDERS",
        ]
