"""
Nexus AI — SQLite Database Wrapper

Thread-safe SQLite operations for memory, productivity, and conversation persistence.
Auto-creates tables on first initialization.
"""

import sqlite3
import os
import threading
from datetime import datetime
from typing import Optional

from nexus_ai.utils.logger import get_logger

logger = get_logger("Database")


class Database:
    """Thread-safe SQLite database wrapper for Nexus AI persistent storage."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "nexus.db")

        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()

        # Initialize schema
        self._initialize_tables()
        logger.info(f"Database initialized at {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path)
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA foreign_keys=ON")
        return self._local.connection

    def _initialize_tables(self):
        """Create all required tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # User memory / preferences
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_memory (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'preference',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Conversation history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # App usage tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_usage (
                app_name TEXT PRIMARY KEY,
                open_count INTEGER DEFAULT 1,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Notes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # To-do list
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                due_date TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Reminders
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                remind_at TIMESTAMP NOT NULL,
                notified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Security audit log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                result TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()

    # ─── User Memory Operations ────────────────────────────────────

    def set_memory(self, key: str, value: str, category: str = "preference"):
        """Store or update a user memory entry."""
        with self._lock:
            conn = self._get_connection()
            conn.execute(
                """
                INSERT INTO user_memory (key, value, category, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    updated_at = excluded.updated_at
                """,
                (key, value, category, datetime.now().isoformat()),
            )
            conn.commit()
            logger.debug(f"Memory set: {key} = {value} [{category}]")

    def get_memory(self, key: str) -> Optional[str]:
        """Retrieve a user memory value by key."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT value FROM user_memory WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def get_memories_by_category(self, category: str) -> list[dict]:
        """Get all memory entries for a given category."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT key, value, updated_at FROM user_memory WHERE category = ? ORDER BY updated_at DESC",
            (category,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_all_memories(self) -> list[dict]:
        """Get all stored user memories."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT key, value, category, updated_at FROM user_memory ORDER BY category, key"
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_memory(self, key: str) -> bool:
        """Delete a memory entry. Returns True if found and deleted."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("DELETE FROM user_memory WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount > 0

    # ─── Conversation History ──────────────────────────────────────

    def add_conversation(self, role: str, content: str):
        """Add a conversation turn to history."""
        with self._lock:
            conn = self._get_connection()
            conn.execute(
                "INSERT INTO conversation_history (role, content, timestamp) VALUES (?, ?, ?)",
                (role, content, datetime.now().isoformat()),
            )
            conn.commit()

    def get_conversation_history(self, limit: int = 20) -> list[dict]:
        """Get the last N conversation turns."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT role, content, timestamp FROM conversation_history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        # Return in chronological order
        return [dict(row) for row in reversed(rows)]

    def clear_conversation_history(self):
        """Clear all conversation history."""
        with self._lock:
            conn = self._get_connection()
            conn.execute("DELETE FROM conversation_history")
            conn.commit()

    # ─── App Usage Tracking ────────────────────────────────────────

    def track_app_usage(self, app_name: str):
        """Record that an app was opened."""
        with self._lock:
            conn = self._get_connection()
            conn.execute(
                """
                INSERT INTO app_usage (app_name, open_count, last_used)
                VALUES (?, 1, ?)
                ON CONFLICT(app_name) DO UPDATE SET
                    open_count = app_usage.open_count + 1,
                    last_used = excluded.last_used
                """,
                (app_name.lower(), datetime.now().isoformat()),
            )
            conn.commit()

    def get_frequent_apps(self, limit: int = 10) -> list[dict]:
        """Get the most frequently used apps."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT app_name, open_count, last_used FROM app_usage ORDER BY open_count DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    # ─── Notes ─────────────────────────────────────────────────────

    def create_note(self, content: str, title: Optional[str] = None) -> int:
        """Create a new note. Returns the note ID."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute(
                "INSERT INTO notes (title, content) VALUES (?, ?)",
                (title, content),
            )
            conn.commit()
            return cursor.lastrowid

    def get_notes(self, limit: int = 50) -> list[dict]:
        """Get recent notes."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT id, title, content, created_at FROM notes ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_note(self, note_id: int) -> bool:
        """Delete a note by ID."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ─── To-Do List ────────────────────────────────────────────────

    def add_todo(self, task: str, due_date: Optional[str] = None) -> int:
        """Add a to-do item. Returns the todo ID."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute(
                "INSERT INTO todos (task, due_date) VALUES (?, ?)",
                (task, due_date),
            )
            conn.commit()
            return cursor.lastrowid

    def get_todos(self, include_completed: bool = False) -> list[dict]:
        """Get to-do items."""
        conn = self._get_connection()
        if include_completed:
            rows = conn.execute(
                "SELECT id, task, completed, due_date, created_at FROM todos ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, task, completed, due_date, created_at FROM todos WHERE completed = 0 ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def complete_todo(self, todo_id: int) -> bool:
        """Mark a to-do item as completed."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute(
                "UPDATE todos SET completed = 1 WHERE id = ?", (todo_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_todo(self, todo_id: int) -> bool:
        """Delete a to-do item."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ─── Reminders ─────────────────────────────────────────────────

    def add_reminder(self, task: str, remind_at: str) -> int:
        """Add a reminder. Returns the reminder ID."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute(
                "INSERT INTO reminders (task, remind_at) VALUES (?, ?)",
                (task, remind_at),
            )
            conn.commit()
            return cursor.lastrowid

    def get_pending_reminders(self) -> list[dict]:
        """Get all reminders that haven't been notified yet and are due."""
        conn = self._get_connection()
        now = datetime.now().isoformat()
        rows = conn.execute(
            """
            SELECT id, task, remind_at, created_at 
            FROM reminders 
            WHERE notified = 0 AND remind_at <= ?
            ORDER BY remind_at ASC
            """,
            (now,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_all_reminders(self) -> list[dict]:
        """Get all active (unnotified) reminders."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT id, task, remind_at, created_at FROM reminders WHERE notified = 0 ORDER BY remind_at ASC"
        ).fetchall()
        return [dict(row) for row in rows]

    def mark_reminder_notified(self, reminder_id: int):
        """Mark a reminder as notified."""
        with self._lock:
            conn = self._get_connection()
            conn.execute(
                "UPDATE reminders SET notified = 1 WHERE id = ?", (reminder_id,)
            )
            conn.commit()

    # ─── Security Log ──────────────────────────────────────────────

    def log_security_event(self, action: str, result: str, details: str = ""):
        """Log a security-relevant event."""
        with self._lock:
            conn = self._get_connection()
            conn.execute(
                "INSERT INTO security_log (action, result, details, timestamp) VALUES (?, ?, ?, ?)",
                (action, result, details, datetime.now().isoformat()),
            )
            conn.commit()

    def get_security_log(self, limit: int = 100) -> list[dict]:
        """Get recent security events."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT action, result, details, timestamp FROM security_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    # ─── Cleanup ───────────────────────────────────────────────────

    def close(self):
        """Close the thread-local connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
