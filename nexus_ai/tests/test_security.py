"""
Tests for the Security Agent.

Verifies:
- Blocked actions are rejected
- Dangerous actions require confirmation
- Safe actions pass through
- Output sanitization
"""

import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from nexus_ai.agents.security_agent import SecurityAgent
from nexus_ai.utils.database import Database


def get_test_db():
    """Create a temporary in-memory database for testing."""
    return Database(db_path=":memory:")


def test_blocked_actions():
    """Blocked actions should always be rejected."""
    db = get_test_db()
    security = SecurityAgent(db)

    blocked = ["FORMAT_DRIVE", "CHANGE_REGISTRY", "DISABLE_ANTIVIRUS", "FACTORY_RESET"]
    for action in blocked:
        task = {"task_id": "test", "action": action, "parameters": {}}
        result = asyncio.run(security.validate_task(task))
        assert not result.success, f"Action {action} should be blocked but was allowed"

    print("✓ test_blocked_actions passed")


def test_safe_actions_pass():
    """Safe actions should be allowed without confirmation."""
    db = get_test_db()
    security = SecurityAgent(db)

    safe_actions = ["OPEN_APP", "VOLUME_UP", "BRIGHTNESS_DOWN", "SEARCH_WEB", "ASK_AI"]
    for action in safe_actions:
        task = {"task_id": "test", "action": action, "parameters": {}}
        result = asyncio.run(security.validate_task(task))
        assert result.success, f"Safe action {action} should be allowed but was blocked"

    print("✓ test_safe_actions_pass passed")


def test_dangerous_without_callback():
    """Dangerous actions without a confirmation callback should be denied."""
    db = get_test_db()
    security = SecurityAgent(db)

    dangerous = ["SHUTDOWN", "RESTART", "DELETE_FILE"]
    for action in dangerous:
        task = {
            "task_id": "test",
            "action": action,
            "parameters": {},
            "requires_confirmation": True,
        }
        result = asyncio.run(security.validate_task(task, voice_confirm_callback=None))
        assert not result.success, (
            f"Dangerous action {action} should be denied without callback"
        )

    print("✓ test_dangerous_without_callback passed")


def test_dangerous_with_yes_callback():
    """Dangerous actions with 'yes' confirmation should be allowed."""
    db = get_test_db()
    security = SecurityAgent(db)

    async def yes_callback(prompt):
        return "yes"

    task = {
        "task_id": "test",
        "action": "SHUTDOWN",
        "parameters": {},
        "requires_confirmation": True,
    }
    result = asyncio.run(security.validate_task(task, voice_confirm_callback=yes_callback))
    assert result.success, "SHUTDOWN with 'yes' should be allowed"

    print("✓ test_dangerous_with_yes_callback passed")


def test_dangerous_with_no_callback():
    """Dangerous actions with 'no' confirmation should be denied."""
    db = get_test_db()
    security = SecurityAgent(db)

    async def no_callback(prompt):
        return "no"

    task = {
        "task_id": "test",
        "action": "DELETE_FILE",
        "parameters": {"path": "test.txt"},
        "requires_confirmation": True,
    }
    result = asyncio.run(security.validate_task(task, voice_confirm_callback=no_callback))
    assert not result.success, "DELETE_FILE with 'no' should be denied"

    print("✓ test_dangerous_with_no_callback passed")


def test_output_sanitization():
    """Sensitive data should be masked in output."""
    db = get_test_db()
    security = SecurityAgent(db)

    text_with_key = "Your api_key is sk-1234567890abcdef"
    sanitized = security.sanitize_output(text_with_key)
    assert "1234567890abcdef" not in sanitized, "API key should be redacted"

    print("✓ test_output_sanitization passed")


def test_affirmative_detection():
    """Various affirmative phrases should be recognized."""
    db = get_test_db()
    security = SecurityAgent(db)

    affirmatives = ["yes", "Yeah", "Sure", "go ahead", "OK", "do it", "yep"]
    for phrase in affirmatives:
        assert security._is_affirmative(phrase), f"'{phrase}' should be affirmative"

    negatives = ["no", "nope", "cancel", "stop", "don't"]
    for phrase in negatives:
        assert not security._is_affirmative(phrase), f"'{phrase}' should not be affirmative"

    print("✓ test_affirmative_detection passed")


def test_security_logging():
    """Security events should be logged to the database."""
    db = get_test_db()
    security = SecurityAgent(db)

    task = {"task_id": "test_log", "action": "OPEN_APP", "parameters": {}}
    asyncio.run(security.validate_task(task))

    logs = db.get_security_log(limit=10)
    assert len(logs) > 0, "Security log should have entries"
    assert logs[0]["action"] == "OPEN_APP", "Log should contain the action"

    print("✓ test_security_logging passed")


if __name__ == "__main__":
    test_blocked_actions()
    test_safe_actions_pass()
    test_dangerous_without_callback()
    test_dangerous_with_yes_callback()
    test_dangerous_with_no_callback()
    test_output_sanitization()
    test_affirmative_detection()
    test_security_logging()
    print("\n✅ All security tests passed!")
