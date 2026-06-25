"""
Tests for individual agents (unit-level).

Verifies:
- Database CRUD operations
- Memory Agent store/recall
- Conversation Agent basic parsing (offline mode)
- Helpers utility functions
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from nexus_ai.utils.database import Database
from nexus_ai.utils.helpers import (
    create_task, sanitize_for_speech, format_bytes,
    format_duration, contains_sensitive_data,
)


def test_database_memory():
    """Test database memory CRUD operations."""
    db = Database(db_path=":memory:")

    # Set
    db.set_memory("name", "Sandeep", "personal")
    db.set_memory("favorite_browser", "Chrome", "preference")

    # Get
    assert db.get_memory("name") == "Sandeep"
    assert db.get_memory("favorite_browser") == "Chrome"
    assert db.get_memory("nonexistent") is None

    # Update
    db.set_memory("name", "Sandeep Kumar", "personal")
    assert db.get_memory("name") == "Sandeep Kumar"

    # Delete
    assert db.delete_memory("name") is True
    assert db.get_memory("name") is None
    assert db.delete_memory("name") is False  # Already deleted

    # Category query
    prefs = db.get_memories_by_category("preference")
    assert len(prefs) == 1
    assert prefs[0]["key"] == "favorite_browser"

    db.close()
    print("✓ test_database_memory passed")


def test_database_todos():
    """Test to-do list operations."""
    db = Database(db_path=":memory:")

    # Add
    id1 = db.add_todo("Buy groceries")
    id2 = db.add_todo("Submit project")
    assert id1 > 0
    assert id2 > 0

    # List
    todos = db.get_todos()
    assert len(todos) == 2

    # Complete
    db.complete_todo(id1)
    active = db.get_todos(include_completed=False)
    assert len(active) == 1
    assert active[0]["task"] == "Submit project"

    # Delete
    db.delete_todo(id2)
    remaining = db.get_todos(include_completed=True)
    assert len(remaining) == 1  # Only the completed one

    db.close()
    print("✓ test_database_todos passed")


def test_database_notes():
    """Test notes operations."""
    db = Database(db_path=":memory:")

    note_id = db.create_note("Meeting notes from today", "Team Meeting")
    assert note_id > 0

    notes = db.get_notes()
    assert len(notes) == 1
    assert notes[0]["title"] == "Team Meeting"

    db.delete_note(note_id)
    assert len(db.get_notes()) == 0

    db.close()
    print("✓ test_database_notes passed")


def test_database_conversation():
    """Test conversation history."""
    db = Database(db_path=":memory:")

    db.add_conversation("user", "Hello")
    db.add_conversation("assistant", "Hi there!")
    db.add_conversation("user", "Open Chrome")

    history = db.get_conversation_history(limit=10)
    assert len(history) == 3
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"
    assert history[-1]["content"] == "Open Chrome"

    db.clear_conversation_history()
    assert len(db.get_conversation_history()) == 0

    db.close()
    print("✓ test_database_conversation passed")


def test_database_app_tracking():
    """Test app usage tracking."""
    db = Database(db_path=":memory:")

    db.track_app_usage("chrome")
    db.track_app_usage("chrome")
    db.track_app_usage("vscode")

    apps = db.get_frequent_apps()
    assert len(apps) == 2
    assert apps[0]["app_name"] == "chrome"
    assert apps[0]["open_count"] == 2

    db.close()
    print("✓ test_database_app_tracking passed")


def test_create_task():
    """Test task creation utility."""
    task = create_task("OPEN_APP", {"app_name": "chrome"}, requires_confirmation=False)
    assert task["action"] == "OPEN_APP"
    assert task["parameters"]["app_name"] == "chrome"
    assert task["requires_confirmation"] is False
    assert "task_id" in task
    assert len(task["task_id"]) == 8

    print("✓ test_create_task passed")


def test_sanitize_for_speech():
    """Test text sanitization for TTS."""
    # Markdown removal
    assert "code block omitted" in sanitize_for_speech("```python\nprint('hi')\n```")
    assert "**" not in sanitize_for_speech("This is **bold** text")
    assert "#" not in sanitize_for_speech("# Header")

    # URL removal
    assert "https://" not in sanitize_for_speech("Visit https://google.com for more")

    # Whitespace cleanup
    result = sanitize_for_speech("Line1\n\n\nLine2   Line3")
    assert "\n" not in result

    print("✓ test_sanitize_for_speech passed")


def test_format_bytes():
    """Test byte formatting."""
    assert format_bytes(0) == "0 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1024 * 1024) == "1.0 MB"
    assert format_bytes(1024 * 1024 * 1024) == "1.0 GB"

    print("✓ test_format_bytes passed")


def test_format_duration():
    """Test duration formatting."""
    assert format_duration(30) == "30 seconds"
    assert format_duration(60) == "1 minute"
    assert format_duration(90) == "1 minute"  # 90s rounds to 1 minute
    assert format_duration(3600) == "1 hour"
    assert format_duration(3660) == "1 hour and 1 minute"

    print("✓ test_format_duration passed")


def test_sensitive_data_detection():
    """Test sensitive data detection."""
    assert contains_sensitive_data("my api_key is abc123")
    assert contains_sensitive_data("password: secret")
    assert contains_sensitive_data("Bearer token: xyz")
    assert not contains_sensitive_data("open chrome")
    assert not contains_sensitive_data("what is the weather")

    print("✓ test_sensitive_data_detection passed")


def test_conversation_agent_basic_parse():
    """Test the basic keyword parser (offline fallback)."""
    from nexus_ai.agents.conversation_agent import ConversationAgent
    from nexus_ai.services.nemotron_api import NemotronClient
    from nexus_ai.utils.database import Database

    db = Database(db_path=":memory:")
    nemotron = NemotronClient(api_key=None)  # Will be unavailable
    agent = ConversationAgent(nemotron, db)

    # Test keyword matching
    result = agent.understand("turn on wifi")
    assert result["understood"] is True
    assert result["tasks"][0]["action"] == "WIFI_ON"

    # Test app opening
    result = agent.understand("open chrome")
    assert result["tasks"][0]["action"] == "OPEN_APP"
    assert result["tasks"][0]["parameters"]["app_name"] == "chrome"

    # Test search
    result = agent.understand("search for latest AI news")
    assert result["tasks"][0]["action"] == "SEARCH_WEB"

    # Test fallback to AI
    result = agent.understand("what is quantum computing")
    assert result["tasks"][0]["action"] == "ASK_AI"

    db.close()
    print("✓ test_conversation_agent_basic_parse passed")


if __name__ == "__main__":
    test_database_memory()
    test_database_todos()
    test_database_notes()
    test_database_conversation()
    test_database_app_tracking()
    test_create_task()
    test_sanitize_for_speech()
    test_format_bytes()
    test_format_duration()
    test_sensitive_data_detection()
    test_conversation_agent_basic_parse()
    print("\n✅ All agent tests passed!")
