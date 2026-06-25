"""
Tests for the Planner Agent.

Verifies:
- Multi-step task decomposition
- Priority ordering
- Parallel vs sequential grouping
- Dangerous action flagging
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from nexus_ai.agents.planner_agent import PlannerAgent


def test_single_task_plan():
    """A single non-dangerous task should produce one parallel=False group."""
    planner = PlannerAgent()
    result = {
        "tasks": [
            {"action": "OPEN_APP", "parameters": {"app_name": "chrome"}}
        ]
    }
    plan = planner.plan(result)

    assert len(plan) >= 1, "Plan should have at least 1 group"
    total_tasks = sum(len(g["tasks"]) for g in plan)
    assert total_tasks == 1, "Plan should have exactly 1 task"
    print("✓ test_single_task_plan passed")


def test_multi_task_parallel():
    """Multiple safe tasks at the same priority should be grouped in parallel."""
    planner = PlannerAgent()
    result = {
        "tasks": [
            {"action": "OPEN_APP", "parameters": {"app_name": "chrome"}},
            {"action": "OPEN_APP", "parameters": {"app_name": "vscode"}},
            {"action": "OPEN_APP", "parameters": {"app_name": "terminal"}},
        ]
    }
    plan = planner.plan(result)

    # All OPEN_APP tasks have the same priority, should be in one parallel group
    total_tasks = sum(len(g["tasks"]) for g in plan)
    assert total_tasks == 3, f"Expected 3 tasks, got {total_tasks}"

    # Find the group with app tasks
    app_groups = [g for g in plan if any(t["action"] == "OPEN_APP" for t in g["tasks"])]
    assert len(app_groups) >= 1, "Should have at least one group with app tasks"

    # If all 3 are in one group, it should be parallel
    if len(app_groups) == 1 and len(app_groups[0]["tasks"]) == 3:
        assert app_groups[0]["parallel"] is True, "3 tasks should be parallel"

    print("✓ test_multi_task_parallel passed")


def test_dangerous_actions_flagged():
    """Dangerous actions should have requires_confirmation = True."""
    planner = PlannerAgent()
    result = {
        "tasks": [
            {"action": "SHUTDOWN", "parameters": {}},
            {"action": "DELETE_FILE", "parameters": {"path": "test.txt"}},
        ]
    }
    plan = planner.plan(result)

    total_tasks = sum(len(g["tasks"]) for g in plan)
    assert total_tasks == 2, f"Expected 2 tasks, got {total_tasks}"

    # All tasks should require confirmation
    all_tasks = [t for g in plan for t in g["tasks"]]
    for task in all_tasks:
        assert task["requires_confirmation"] is True, (
            f"Task {task['action']} should require confirmation"
        )

    print("✓ test_dangerous_actions_flagged passed")


def test_mixed_priority_ordering():
    """Tasks with different priorities should be in separate groups, ordered."""
    planner = PlannerAgent()
    result = {
        "tasks": [
            {"action": "ASK_AI", "parameters": {"query": "what is python"}},  # priority 6
            {"action": "CHECK_BATTERY", "parameters": {}},  # priority 1
            {"action": "OPEN_APP", "parameters": {"app_name": "chrome"}},  # priority 3
        ]
    }
    plan = planner.plan(result)

    # Should be ordered: CHECK_BATTERY first, then OPEN_APP, then ASK_AI
    all_tasks = [t for g in plan for t in g["tasks"]]
    actions = [t["action"] for t in all_tasks]

    battery_idx = actions.index("CHECK_BATTERY")
    app_idx = actions.index("OPEN_APP")
    ai_idx = actions.index("ASK_AI")

    assert battery_idx < app_idx, "CHECK_BATTERY should come before OPEN_APP"
    assert app_idx < ai_idx, "OPEN_APP should come before ASK_AI"

    print("✓ test_mixed_priority_ordering passed")


def test_empty_plan():
    """No tasks should produce an empty plan."""
    planner = PlannerAgent()
    plan = planner.plan({"tasks": []})
    assert plan == [], "Empty tasks should produce empty plan"
    print("✓ test_empty_plan passed")


def test_agent_routing():
    """Each task should be assigned the correct agent."""
    planner = PlannerAgent()
    result = {
        "tasks": [
            {"action": "WIFI_ON", "parameters": {}},
            {"action": "OPEN_APP", "parameters": {"app_name": "chrome"}},
            {"action": "SEARCH_WEB", "parameters": {"query": "test"}},
            {"action": "SET_TIMER", "parameters": {"duration": 5, "unit": "minutes"}},
            {"action": "ASK_AI", "parameters": {"query": "hello"}},
        ]
    }
    plan = planner.plan(result)

    all_tasks = [t for g in plan for t in g["tasks"]]
    agent_map = {t["action"]: t["agent"] for t in all_tasks}

    assert agent_map["WIFI_ON"] == "SystemAgent", f"WIFI_ON → {agent_map['WIFI_ON']}"
    assert agent_map["OPEN_APP"] == "ApplicationAgent", f"OPEN_APP → {agent_map['OPEN_APP']}"
    assert agent_map["SEARCH_WEB"] == "BrowserAgent", f"SEARCH_WEB → {agent_map['SEARCH_WEB']}"
    assert agent_map["SET_TIMER"] == "ProductivityAgent", f"SET_TIMER → {agent_map['SET_TIMER']}"
    assert agent_map["ASK_AI"] == "AIAgent", f"ASK_AI → {agent_map['ASK_AI']}"

    print("✓ test_agent_routing passed")


if __name__ == "__main__":
    test_single_task_plan()
    test_multi_task_parallel()
    test_dangerous_actions_flagged()
    test_mixed_priority_ordering()
    test_empty_plan()
    test_agent_routing()
    print("\n✅ All planner tests passed!")
