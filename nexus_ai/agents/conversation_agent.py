"""
Nexus AI — Conversation Agent

The natural language understanding layer. Uses Nemotron API to understand
user intent, maintain conversation context, and handle follow-ups.
Replaces the old keyword-based IntentParser entirely.
"""

from typing import Optional

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.services.nemotron_api import NemotronClient
from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.database import Database
from nexus_ai.utils.helpers import load_json_config

logger = get_logger("ConversationAgent")

# System prompt that defines Nexus's understanding capabilities
SYSTEM_PROMPT = """You are Nexus, an intelligent desktop voice assistant's language understanding engine.

Your job is to analyze the user's spoken command and output a STRUCTURED JSON response.

## Available Actions (capabilities):

### System Control
- WIFI_ON, WIFI_OFF — Enable/disable WiFi
- BLUETOOTH_ON, BLUETOOTH_OFF — Enable/disable Bluetooth
- VOLUME_UP, VOLUME_DOWN, VOLUME_MUTE — Volume control
- BRIGHTNESS_UP, BRIGHTNESS_DOWN — Brightness control
- NIGHT_MODE_ON, NIGHT_MODE_OFF — Night/dark mode
- SCREENSHOT — Take a screenshot

### Power
- SHUTDOWN — Shut down computer (DANGEROUS)
- RESTART — Restart computer (DANGEROUS)
- SLEEP — Put computer to sleep
- LOCK_SCREEN — Lock the screen
- LOGOUT — Log out of current session

### Applications
- OPEN_APP — Open an application. Parameters: {"app_name": "..."}
- CLOSE_APP — Close an application. Parameters: {"app_name": "..."}
- RESTART_APP — Restart an application. Parameters: {"app_name": "..."}
- LIST_RUNNING_APPS — List all running applications

### File Management
- OPEN_FOLDER — Open a folder. Parameters: {"path": "..."}
- FIND_FILE — Search for a file. Parameters: {"query": "...", "location": "..."}
- CREATE_FOLDER — Create a folder. Parameters: {"name": "...", "path": "..."}
- DELETE_FILE — Delete a file (DANGEROUS). Parameters: {"path": "..."}
- MOVE_FILE — Move a file. Parameters: {"source": "...", "destination": "..."}
- COPY_FILE — Copy a file. Parameters: {"source": "...", "destination": "..."}
- RENAME_FILE — Rename a file. Parameters: {"path": "...", "new_name": "..."}
- COMPRESS_FILE — Zip a file/folder. Parameters: {"path": "..."}
- EXTRACT_FILE — Extract a zip. Parameters: {"path": "..."}
- EMPTY_RECYCLE_BIN — Empty recycle bin (DANGEROUS)

### Browser
- OPEN_WEBSITE — Open a website. Parameters: {"url": "...", "site_name": "..."}
- SEARCH_WEB — Search Google. Parameters: {"query": "..."}
- OPEN_YOUTUBE — Open YouTube. Parameters: {"search": "..." (optional)}
- OPEN_GMAIL — Open Gmail
- OPEN_GITHUB — Open GitHub

### Productivity
- SET_TIMER — Set a timer. Parameters: {"duration": ..., "unit": "minutes/seconds/hours"}
- SET_REMINDER — Set a reminder. Parameters: {"task": "...", "time": "..." (optional)}
- SET_ALARM — Set an alarm. Parameters: {"time": "..."}
- CREATE_NOTE — Create a note. Parameters: {"content": "...", "title": "..." (optional)}
- ADD_TODO — Add a to-do item. Parameters: {"task": "...", "due_date": "..." (optional)}
- LIST_TODOS — List all to-do items
- LIST_REMINDERS — List all reminders

### AI / Knowledge
- ASK_AI — General question/conversation. Parameters: {"query": "..."}
- EXPLAIN_CODE — Explain code. Parameters: {"query": "..."}
- GENERATE_CODE — Generate code. Parameters: {"query": "...", "language": "..."}
- TRANSLATE — Translate text. Parameters: {"text": "...", "target_language": "..."}
- SUMMARIZE — Summarize content. Parameters: {"query": "..."}
- DRAFT_EMAIL — Draft an email. Parameters: {"subject": "...", "recipient": "...", "body_hint": "..."}

### System Info
- CHECK_BATTERY — Get battery percentage
- CHECK_RAM — Get RAM usage
- CHECK_STORAGE — Get storage info
- CHECK_WEATHER — Get weather (via web search)

### Memory
- REMEMBER — Store user preference. Parameters: {"key": "...", "value": "..."}
- RECALL — Recall stored info. Parameters: {"key": "..."}

### Workflows
- EXECUTE_WORKFLOW — Run a predefined or custom workflow. Parameters: {"name": "...", "trigger": "..."}
  Available workflows: Coding Mode, Study Mode, Movie Mode, Meeting Mode, Gaming Mode, Travel Mode
  Example: "Start coding mode" → EXECUTE_WORKFLOW with name="Coding Mode"
- CREATE_WORKFLOW — Create a custom workflow. Parameters: {"name": "...", "trigger": "...", "description": "...", "steps": [{"action": "...", "parameters": {...}}]}
  Example: "Create a workflow called College Mode that opens Chrome, Gmail and my Notes folder"
- LIST_WORKFLOWS — List all available workflows
- DELETE_WORKFLOW — Delete a workflow. Parameters: {"name": "..."}

### Documents
- READ_DOCUMENT — Read and process a document file. Parameters: {"path": "...", "operation": "summarize|explain|translate|rewrite|notes|qa|keypoints", "query": "..." (for qa)}
  Supported formats: PDF, DOCX, TXT, Markdown

### Coding
- GIT_STATUS — Check git status of a project. Parameters: {"path": "..."}
- GIT_PULL — Pull latest changes. Parameters: {"path": "..."}
- GIT_COMMIT — Commit changes. Parameters: {"path": "...", "message": "..."}
- CODE_REVIEW — Review code. Parameters: {"query": "...", "language": "..."}
- PROJECT_SCAFFOLD — Generate project template. Parameters: {"name": "...", "type": "python|web|api", "path": "..."}

### System Monitoring
- SYSTEM_HEALTH — Get full system health report (CPU, RAM, Disk, Battery, Network)
- CHECK_CPU — Get CPU usage
- CHECK_GPU — Get GPU info
- CHECK_NETWORK — Get network status
- CHECK_TEMPERATURE — Get system temperature

## IMPORTANT Rules:
1. One user command can map to MULTIPLE actions. Analyze the intent carefully.
   Example: "I'm going to college" → CHECK_WEATHER + CHECK_BATTERY + OPEN_APP(maps) + OPEN_APP(spotify)
2. "Prepare my coding environment" → OPEN_APP(vscode) + OPEN_APP(chrome) + OPEN_APP(terminal)
3. Always use the EXACT action names from the list above.
4. If the command is conversational (chat, question), use ASK_AI.
5. If the command is ambiguous, include a "clarification" field.
6. For dangerous operations, set "requires_confirmation": true.

## Output Format (strict JSON):
{
    "understood": true,
    "intent_summary": "Brief description of what the user wants",
    "tasks": [
        {
            "action": "ACTION_NAME",
            "parameters": {},
            "requires_confirmation": false
        }
    ],
    "response": "What to say to the user",
    "clarification": null
}

If you don't understand the command:
{
    "understood": false,
    "intent_summary": null,
    "tasks": [],
    "response": "I didn't understand that. Could you rephrase?",
    "clarification": "What specific part was unclear"
}
"""


class ConversationAgent(BaseAgent):
    """
    Conversation Agent — Natural Language Understanding via Nemotron.
    
    Responsibilities:
        - Understand user commands naturally (not keyword matching)
        - Maintain conversation context across turns
        - Handle follow-up questions
        - Generate structured task lists from natural language
    """

    def __init__(self, nemotron: NemotronClient, db: Database):
        super().__init__("ConversationAgent")
        self.nemotron = nemotron
        self.db = db

        settings = load_json_config("settings.json")
        conv_config = settings.get("conversation", {})
        self.max_history = conv_config.get("max_history", 20)
        self.temperature = conv_config.get("nemotron_temperature", 0.6)
        self.max_tokens = conv_config.get("nemotron_max_tokens", 1024)

    def understand(self, user_text: str) -> dict:
        """
        Process user's spoken text and return structured understanding.
        
        This is the main entry point used by the orchestrator.
        
        Args:
            user_text: The transcribed user command
        
        Returns:
            Structured dict with intent, tasks, and response
        """
        if not self.nemotron.is_available():
            logger.warning("Nemotron API unavailable, using basic parsing")
            return self._basic_parse(user_text)

        # Store user message in history
        self.db.add_conversation("user", user_text)

        # Build messages with context
        messages = self._build_messages(user_text)

        try:
            result = self.nemotron.chat_json(
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            # Validate the response structure
            result = self._validate_response(result)

            # Store assistant understanding in history
            self.db.add_conversation(
                "assistant",
                result.get("response", "Understood."),
            )

            logger.info(
                f"Understood: {result.get('intent_summary', 'Unknown')} "
                f"→ {len(result.get('tasks', []))} task(s)"
            )
            return result

        except Exception as e:
            logger.error(f"NLU error: {e}")
            return {
                "understood": False,
                "intent_summary": None,
                "tasks": [],
                "response": "I had trouble understanding that. Could you try again?",
                "clarification": str(e),
            }

    def _build_messages(self, user_text: str) -> list[dict]:
        """Build the message list with system prompt, history, and user input."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add user memories/preferences as context
        memories = self.db.get_all_memories()
        if memories:
            memory_context = "User preferences and stored information:\n"
            for mem in memories[:20]:  # Limit to avoid token overflow
                memory_context += f"- {mem['key']}: {mem['value']}\n"
            messages.append({"role": "system", "content": memory_context})

        # Add conversation history
        history = self.db.get_conversation_history(limit=self.max_history)
        for turn in history:
            messages.append({
                "role": turn["role"],
                "content": turn["content"],
            })

        # Add current user input
        messages.append({"role": "user", "content": user_text})

        return messages

    def _validate_response(self, response: dict) -> dict:
        """Ensure the response has all required fields."""
        defaults = {
            "understood": True,
            "intent_summary": "Understood",
            "tasks": [],
            "response": "Okay.",
            "clarification": None,
        }

        for key, default in defaults.items():
            if key not in response:
                response[key] = default

        # Validate each task
        validated_tasks = []
        for task in response.get("tasks", []):
            if "action" in task:
                if "parameters" not in task:
                    task["parameters"] = {}
                if "requires_confirmation" not in task:
                    task["requires_confirmation"] = False
                validated_tasks.append(task)

        response["tasks"] = validated_tasks
        return response

    def generate_response(self, results: list[AgentResult], original_intent: str) -> str:
        """
        Generate a natural language response summarizing task results.
        
        Called after all tasks have been executed to produce the final
        spoken response.
        
        Args:
            results: List of AgentResults from executed tasks
            original_intent: The original user intent summary
        
        Returns:
            Natural language response for TTS
        """
        if not self.nemotron.is_available():
            # Fallback: just concatenate result messages
            messages = [r.message for r in results if r.message]
            return " ".join(messages) if messages else "Done."

        # Build a summary of what happened
        result_summary = []
        for r in results:
            status = "✓" if r.success else "✗"
            result_summary.append(f"{status} [{r.agent}]: {r.message}")

        prompt = f"""The user asked: "{original_intent}"

Here are the results of the executed tasks:
{chr(10).join(result_summary)}

Generate a brief, conversational, spoken response summarizing what happened.
Keep it under 3 sentences. Be natural and friendly. Do NOT use markdown or special formatting.
"""

        try:
            response = self.nemotron.chat(
                messages=[
                    {"role": "system", "content": "You are Nexus, a friendly voice assistant. Generate brief spoken responses. No markdown."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=200,
            )
            return response
        except Exception:
            # Fallback
            messages = [r.message for r in results if r.message]
            return " ".join(messages) if messages else "Done."

    def _basic_parse(self, text: str) -> dict:
        """
        Basic keyword-based parsing when Nemotron is unavailable.
        Simplified version of the old IntentParser logic.
        """
        text_lower = text.lower().strip()

        # Direct keyword mappings
        keyword_actions = {
            "wifi on": "WIFI_ON", "enable wifi": "WIFI_ON", "turn on wifi": "WIFI_ON",
            "wifi off": "WIFI_OFF", "disable wifi": "WIFI_OFF", "turn off wifi": "WIFI_OFF",
            "bluetooth on": "BLUETOOTH_ON", "enable bluetooth": "BLUETOOTH_ON",
            "bluetooth off": "BLUETOOTH_OFF", "disable bluetooth": "BLUETOOTH_OFF",
            "volume up": "VOLUME_UP", "increase volume": "VOLUME_UP",
            "volume down": "VOLUME_DOWN", "decrease volume": "VOLUME_DOWN",
            "mute": "VOLUME_MUTE",
            "brightness up": "BRIGHTNESS_UP", "increase brightness": "BRIGHTNESS_UP",
            "brightness down": "BRIGHTNESS_DOWN", "decrease brightness": "BRIGHTNESS_DOWN",
            "lock screen": "LOCK_SCREEN", "lock computer": "LOCK_SCREEN",
            "shut down": "SHUTDOWN", "shutdown": "SHUTDOWN",
            "restart": "RESTART", "reboot": "RESTART",
            "sleep": "SLEEP",
            "screenshot": "SCREENSHOT", "take screenshot": "SCREENSHOT",
            "battery": "CHECK_BATTERY", "battery percentage": "CHECK_BATTERY",
            "ram usage": "CHECK_RAM", "how much ram": "CHECK_RAM",
            "storage": "CHECK_STORAGE", "disk space": "CHECK_STORAGE",
            "empty recycle bin": "EMPTY_RECYCLE_BIN",
        }

        # Check direct matches
        for phrase, action in keyword_actions.items():
            if phrase in text_lower:
                dangerous = action in ["SHUTDOWN", "RESTART", "EMPTY_RECYCLE_BIN"]
                return {
                    "understood": True,
                    "intent_summary": phrase,
                    "tasks": [{
                        "action": action,
                        "parameters": {},
                        "requires_confirmation": dangerous,
                    }],
                    "response": f"Executing {phrase}.",
                    "clarification": None,
                }

        # App commands
        import re
        app_match = re.search(r'(open|launch|start)\s+(.+)', text_lower)
        if app_match:
            app_name = app_match.group(2).strip()
            return {
                "understood": True,
                "intent_summary": f"Open {app_name}",
                "tasks": [{
                    "action": "OPEN_APP",
                    "parameters": {"app_name": app_name},
                    "requires_confirmation": False,
                }],
                "response": f"Opening {app_name}.",
                "clarification": None,
            }

        close_match = re.search(r'(close|quit|exit|kill)\s+(.+)', text_lower)
        if close_match:
            app_name = close_match.group(2).strip()
            return {
                "understood": True,
                "intent_summary": f"Close {app_name}",
                "tasks": [{
                    "action": "CLOSE_APP",
                    "parameters": {"app_name": app_name},
                    "requires_confirmation": False,
                }],
                "response": f"Closing {app_name}.",
                "clarification": None,
            }

        # Search
        search_match = re.search(r'search\s+(?:for\s+)?(.+)', text_lower)
        if search_match:
            query = search_match.group(1).strip()
            return {
                "understood": True,
                "intent_summary": f"Search for {query}",
                "tasks": [{
                    "action": "SEARCH_WEB",
                    "parameters": {"query": query},
                    "requires_confirmation": False,
                }],
                "response": f"Searching for {query}.",
                "clarification": None,
            }

        # Default: treat as AI question
        return {
            "understood": True,
            "intent_summary": "AI question",
            "tasks": [{
                "action": "ASK_AI",
                "parameters": {"query": text},
                "requires_confirmation": False,
            }],
            "response": "Let me think about that.",
            "clarification": None,
        }

    async def execute(self, task: dict) -> AgentResult:
        """Execute a conversation task."""
        action = task.get("action", "")
        params = task.get("parameters", {})

        if action == "UNDERSTAND":
            text = params.get("text", "")
            result = self.understand(text)
            return AgentResult(
                success=result.get("understood", False),
                message=result.get("response", ""),
                data=result,
            )

        return AgentResult(success=False, message=f"Unknown action: {action}")

    def get_capabilities(self) -> list[str]:
        return ["UNDERSTAND"]
