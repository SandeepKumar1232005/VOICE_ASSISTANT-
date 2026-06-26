"""
Nexus AI — Fast Local Intent Router

Lightweight, zero-latency intent classifier that runs entirely locally.
Handles simple commands (open apps, system controls, browser shortcuts)
without calling the Nemotron API, reducing response time from ~35s to <1ms.

Only forwards complex/AI-requiring commands to ConversationAgent + Nemotron.
"""

import re
from typing import Optional

from nexus_ai.utils.logger import get_logger

logger = get_logger("IntentRouter")


class IntentRouter:
    """
    Fast local intent router.
    
    Classifies user commands into:
    - LOCAL: handled instantly via regex/keyword matching
    - NEMOTRON: requires AI reasoning, forwarded to ConversationAgent
    
    Returns the same structured dict format as ConversationAgent.understand()
    so the rest of the pipeline is unchanged.
    """

    def __init__(self):
        # Precompile all regex patterns for speed
        self._compile_patterns()
        logger.info("IntentRouter initialized (local fast-path enabled)")

    def _compile_patterns(self):
        """Precompile all regex patterns at init time."""

        # ─── System Control (exact/fuzzy keyword matches) ──────────
        self._system_commands = {
            # WiFi
            r"\b(turn\s+on|enable|switch\s+on|activate)\s+(the\s+)?wi[-\s]?fi\b": ("WIFI_ON", {}, "Turning on WiFi."),
            r"\b(turn\s+off|disable|switch\s+off|deactivate)\s+(the\s+)?wi[-\s]?fi\b": ("WIFI_OFF", {}, "Turning off WiFi."),
            r"\bwi[-\s]?fi\s+(on|enable)\b": ("WIFI_ON", {}, "Turning on WiFi."),
            r"\bwi[-\s]?fi\s+(off|disable)\b": ("WIFI_OFF", {}, "Turning off WiFi."),

            # Bluetooth
            r"\b(turn\s+on|enable|switch\s+on|activate)\s+(the\s+)?bluetooth\b": ("BLUETOOTH_ON", {}, "Turning on Bluetooth."),
            r"\b(turn\s+off|disable|switch\s+off|deactivate)\s+(the\s+)?bluetooth\b": ("BLUETOOTH_OFF", {}, "Turning off Bluetooth."),
            r"\bbluetooth\s+(on|enable)\b": ("BLUETOOTH_ON", {}, "Turning on Bluetooth."),
            r"\bbluetooth\s+(off|disable)\b": ("BLUETOOTH_OFF", {}, "Turning off Bluetooth."),

            # Volume
            r"\b(increase|raise|turn\s+up|up)\s+(the\s+)?volume\b": ("VOLUME_UP", {}, "Increasing volume."),
            r"\bvolume\s+(up|increase|raise|higher)\b": ("VOLUME_UP", {}, "Increasing volume."),
            r"\b(decrease|lower|turn\s+down|down|reduce)\s+(the\s+)?volume\b": ("VOLUME_DOWN", {}, "Decreasing volume."),
            r"\bvolume\s+(down|decrease|lower|reduce)\b": ("VOLUME_DOWN", {}, "Decreasing volume."),
            r"\b(mute|silence)\s*(the\s+)?(volume|sound|audio)?\b": ("VOLUME_MUTE", {}, "Muting volume."),
            r"\b(unmute)\s*(the\s+)?(volume|sound|audio)?\b": ("VOLUME_UP", {}, "Unmuting."),

            # Brightness
            r"\b(increase|raise|turn\s+up|up)\s+(the\s+)?brightness\b": ("BRIGHTNESS_UP", {}, "Increasing brightness."),
            r"\bbrightness\s+(up|increase|raise|higher)\b": ("BRIGHTNESS_UP", {}, "Increasing brightness."),
            r"\b(decrease|lower|turn\s+down|down|reduce|dim)\s+(the\s+)?brightness\b": ("BRIGHTNESS_DOWN", {}, "Decreasing brightness."),
            r"\bbrightness\s+(down|decrease|lower|reduce)\b": ("BRIGHTNESS_DOWN", {}, "Decreasing brightness."),

            # Night mode
            r"\b(turn\s+on|enable|activate)\s+(the\s+)?(night\s*mode|dark\s*mode|night\s*light)\b": ("NIGHT_MODE_ON", {}, "Enabling night mode."),
            r"\b(turn\s+off|disable|deactivate)\s+(the\s+)?(night\s*mode|dark\s*mode|night\s*light)\b": ("NIGHT_MODE_OFF", {}, "Disabling night mode."),

            # Screenshot
            r"\b(take\s+a?\s*)?screenshot\b": ("SCREENSHOT", {}, "Taking a screenshot."),
            r"\bcapture\s+(the\s+)?screen\b": ("SCREENSHOT", {}, "Taking a screenshot."),

            # Power
            r"\b(shut\s*down|power\s+off)\s*(the\s+)?(computer|pc|system)?\b": ("SHUTDOWN", {}, "Shutting down."),
            r"\brestart\s*(the\s+)?(computer|pc|system)?\b": ("RESTART", {}, "Restarting."),
            r"\breboot\s*(the\s+)?(computer|pc|system)?\b": ("RESTART", {}, "Restarting."),
            r"\b(go\s+to\s+)?sleep\s*(mode)?\b": ("SLEEP", {}, "Going to sleep."),
            r"\block\s+(the\s+)?(screen|computer|pc)\b": ("LOCK_SCREEN", {}, "Locking the screen."),
            r"\b(log\s*out|sign\s*out)\b": ("LOGOUT", {}, "Logging out."),

            # System info
            r"\b(check|what'?s?|how'?s?|show)\s+(the\s+)?(my\s+)?battery\b": ("CHECK_BATTERY", {}, "Checking battery."),
            r"\bbattery\s+(percentage|level|status|life)\b": ("CHECK_BATTERY", {}, "Checking battery."),
            r"\b(check|what'?s?|how'?s?|show)\s+(the\s+)?(my\s+)?ram\b": ("CHECK_RAM", {}, "Checking RAM usage."),
            r"\b(how\s+much\s+)?ram\s*(usage|used)?\b": ("CHECK_RAM", {}, "Checking RAM usage."),
            r"\b(check|what'?s?|how'?s?|show)\s+(the\s+)?(my\s+)?(storage|disk)\b": ("CHECK_STORAGE", {}, "Checking storage."),
            r"\b(disk|storage)\s+(space|usage|info)\b": ("CHECK_STORAGE", {}, "Checking storage."),

            # Monitor
            r"\b(system\s+)?health\s*(check|report|status)?\b": ("SYSTEM_HEALTH", {}, "Checking system health."),
            r"\b(check|show|what'?s?)\s+(the\s+)?(my\s+)?cpu\b": ("CHECK_CPU", {}, "Checking CPU usage."),
            r"\bcpu\s+(usage|load|percent)\b": ("CHECK_CPU", {}, "Checking CPU usage."),
            r"\b(check|show|what'?s?)\s+(the\s+)?(my\s+)?gpu\b": ("CHECK_GPU", {}, "Checking GPU info."),
            r"\b(check|show|what'?s?)\s+(the\s+)?(my\s+)?network\b": ("CHECK_NETWORK", {}, "Checking network status."),
            r"\b(check|show|what'?s?)\s+(the\s+)?(my\s+)?temperature\b": ("CHECK_TEMPERATURE", {}, "Checking system temperature."),

            # Memory agent
            r"\bempty\s+(the\s+)?recycle\s*bin\b": ("EMPTY_RECYCLE_BIN", {}, "Emptying recycle bin."),

            # List actions
            r"\b(list|show)\s+(my\s+)?(running|open)\s+(apps|applications|programs)\b": ("LIST_RUNNING_APPS", {}, "Listing running applications."),
            r"\b(what'?s?|which)\s+(apps?|applications?)\s+(are\s+)?(running|open)\b": ("LIST_RUNNING_APPS", {}, "Listing running applications."),
            r"\b(list|show)\s+(my\s+)?to\s*-?\s*do\s*(list|items|s)?\b": ("LIST_TODOS", {}, "Listing your to-do items."),
            r"\b(list|show)\s+(my\s+)?reminders?\b": ("LIST_REMINDERS", {}, "Listing your reminders."),
            r"\b(list|show)\s+(my\s+)?workflows?\b": ("LIST_WORKFLOWS", {}, "Listing your workflows."),
            r"\b(list|show)\s+(my\s+)?plugins?\b": ("LIST_PLUGINS", {}, "Listing plugins."),

            # Privacy
            r"\b(enable|turn\s+on|activate)\s+(the\s+)?stealth\s*mode\b": ("ENABLE_STEALTH_MODE", {}, "Enabling stealth mode."),
            r"\b(disable|turn\s+off|deactivate)\s+(the\s+)?stealth\s*mode\b": ("DISABLE_STEALTH_MODE", {}, "Disabling stealth mode."),
        }

        # Compile system patterns
        self._compiled_system = [
            (re.compile(pattern, re.IGNORECASE), action, params, response)
            for pattern, (action, params, response) in self._system_commands.items()
        ]

        # ─── App open/close/restart patterns ───────────────────────
        self._app_open_re = re.compile(
            r"^(?:please\s+)?(?:open|launch|start|run)\s+(?:the\s+)?(?:app\s+)?(.+?)\.?$",
            re.IGNORECASE,
        )
        self._app_close_re = re.compile(
            r"^(?:please\s+)?(?:close|quit|exit|kill|stop)\s+(?:the\s+)?(?:app\s+)?(.+?)\.?$",
            re.IGNORECASE,
        )
        self._app_restart_re = re.compile(
            r"^(?:please\s+)?(?:restart|relaunch)\s+(?:the\s+)?(?:app\s+)?(.+?)\.?$",
            re.IGNORECASE,
        )

        # ─── Browser patterns ─────────────────────────────────────
        self._search_re = re.compile(
            r"^(?:please\s+)?(?:search|google|look\s+up)(?:\s+(?:for|about))?\s+(.+?)\.?$",
            re.IGNORECASE,
        )
        self._open_website_re = re.compile(
            r"^(?:please\s+)?(?:open|go\s+to|visit|navigate\s+to)\s+(?:the\s+)?(?:website\s+)?(\S+\.(?:com|org|net|io|dev|ai|edu|gov|co)\S*)\.?$",
            re.IGNORECASE,
        )
        self._youtube_search_re = re.compile(
            r"^(?:please\s+)?(?:play|search|find|open)\s+(?:on\s+)?youtube\s+(.+?)\.?$",
            re.IGNORECASE,
        )
        self._youtube_open_re = re.compile(
            r"^(?:please\s+)?open\s+(?:the\s+)?youtube\.?$",
            re.IGNORECASE,
        )
        self._gmail_re = re.compile(r"^(?:please\s+)?open\s+(?:the\s+)?(?:my\s+)?g\s*mail\.?$", re.IGNORECASE)
        self._github_re = re.compile(r"^(?:please\s+)?open\s+(?:the\s+)?(?:my\s+)?github\.?$", re.IGNORECASE)

        # ─── File patterns ─────────────────────────────────────────
        self._open_folder_re = re.compile(
            r"^(?:please\s+)?open\s+(?:the\s+)?(?:my\s+)?(?:folder\s+)?(?:in\s+)?(desktop|documents|downloads|music|pictures|videos)\.?$",
            re.IGNORECASE,
        )
        self._find_file_re = re.compile(
            r"^(?:please\s+)?(?:find|search\s+for|locate)\s+(?:the\s+)?(?:file\s+)?(.+?)\.?$",
            re.IGNORECASE,
        )

        # ─── Productivity patterns ─────────────────────────────────
        self._timer_re = re.compile(
            r"^(?:please\s+)?set\s+(?:a\s+)?timer\s+(?:for\s+)?(\d+)\s*(seconds?|minutes?|hours?)\.?$",
            re.IGNORECASE,
        )
        self._reminder_re = re.compile(
            r"^(?:please\s+)?(?:remind\s+me\s+to|set\s+(?:a\s+)?reminder\s+(?:to\s+)?)(.+?)\.?$",
            re.IGNORECASE,
        )
        self._note_re = re.compile(
            r"^(?:please\s+)?(?:create\s+(?:a\s+)?note|take\s+(?:a\s+)?note|note\s+down)\s*[:;]?\s*(.+?)\.?$",
            re.IGNORECASE,
        )
        self._todo_re = re.compile(
            r"^(?:please\s+)?(?:add\s+(?:a\s+)?to\s*-?\s*do|add\s+to\s+(?:my\s+)?to\s*-?\s*do\s*(?:list)?)\s*[:;]?\s*(.+?)\.?$",
            re.IGNORECASE,
        )

        # ─── Workflow patterns ─────────────────────────────────────
        self._workflow_re = re.compile(
            r"^(?:please\s+)?(?:start|run|execute|activate|launch)\s+(?:the\s+)?(.+?)\s*(?:mode|workflow)\.?$",
            re.IGNORECASE,
        )

        # ─── AI-requiring keywords (if these appear, skip local routing) ──
        self._ai_keywords = re.compile(
            r"\b(?:explain|describe|what\s+is|what\s+are|how\s+(?:does|do|to|can)|why\s+(?:does|do|is|are)|"
            r"write|generate|create\s+(?:a\s+)?(?:code|script|program|function)|code\s+for|"
            r"summarize|summarise|translate|draft\s+(?:an?\s+)?email|"
            r"tell\s+me\s+about|can\s+you\s+(?:explain|help|write)|"
            r"compare|difference\s+between|advantages?\s+of|disadvantages?\s+of|"
            r"review\s+(?:this|my)\s+code|debug|fix\s+(?:this|my)|"
            r"plan\s+(?:my|a)|schedule|recommend|suggest|"
            r"who\s+(?:is|was|are|were)|when\s+(?:did|was|is)|where\s+(?:is|are|was)|"
            r"what\s+happened|meaning\s+of|define)\b",
            re.IGNORECASE,
        )

    def classify(self, text: str) -> Optional[dict]:
        """
        Classify user command locally.
        
        Returns:
            Structured dict (same format as ConversationAgent.understand())
            if the command can be handled locally, or None if it requires Nemotron.
        """
        if not text or not text.strip():
            return None

        text = text.strip()
        
        # Strip trailing punctuation (like ! or ?) that Whisper might add,
        # which breaks our strict $ regex anchors.
        text = re.sub(r'[.,!?]+$', '', text).strip()

        # Quick check: if text contains AI-requiring keywords, skip local routing
        # UNLESS it also matches a very specific system command pattern
        has_ai_keywords = bool(self._ai_keywords.search(text))

        # ─── 1. System commands (highest priority, most specific) ──
        for pattern, action, params, response in self._compiled_system:
            if pattern.search(text):
                dangerous = action in ("SHUTDOWN", "RESTART", "LOGOUT", "EMPTY_RECYCLE_BIN")
                logger.info(f"LOCAL route: '{text}' -> {action}")
                return self._make_result(action, params, response, dangerous)

        # If AI keywords detected and no system command matched, defer to Nemotron
        if has_ai_keywords:
            logger.debug(f"AI keywords detected, deferring to Nemotron: '{text}'")
            return None

        # ─── 2. Workflow triggers (check before apps) ──────────────
        m = self._workflow_re.match(text)
        if m:
            workflow_name = m.group(1).strip().title() + " Mode"
            # Check for well-known workflows
            known_workflows = {
                "Coding Mode", "Study Mode", "Movie Mode",
                "Meeting Mode", "Gaming Mode", "Travel Mode",
            }
            # Normalize: "coding" -> "Coding Mode"
            normalized = m.group(1).strip().title()
            if normalized + " Mode" in known_workflows:
                workflow_name = normalized + " Mode"
            elif normalized in known_workflows:
                workflow_name = normalized

            logger.info(f"LOCAL route: '{text}' -> EXECUTE_WORKFLOW({workflow_name})")
            return self._make_result(
                "EXECUTE_WORKFLOW",
                {"name": workflow_name, "trigger": text.lower()},
                f"Starting {workflow_name}.",
            )

        # ─── 3. App open/close/restart ─────────────────────────────
        m = self._app_open_re.match(text)
        if m:
            app_name = m.group(1).strip()
            # Don't locally route "open" if app_name looks like a website
            if not re.search(r"\.\w{2,4}$", app_name):
                logger.info(f"LOCAL route: '{text}' -> OPEN_APP({app_name})")
                return self._make_result(
                    "OPEN_APP",
                    {"app_name": app_name},
                    f"Opening {app_name}.",
                )

        m = self._app_close_re.match(text)
        if m:
            app_name = m.group(1).strip()
            logger.info(f"LOCAL route: '{text}' -> CLOSE_APP({app_name})")
            return self._make_result(
                "CLOSE_APP",
                {"app_name": app_name},
                f"Closing {app_name}.",
            )

        m = self._app_restart_re.match(text)
        if m:
            app_name = m.group(1).strip()
            logger.info(f"LOCAL route: '{text}' -> RESTART_APP({app_name})")
            return self._make_result(
                "RESTART_APP",
                {"app_name": app_name},
                f"Restarting {app_name}.",
            )

        # ─── 4. Browser shortcuts ──────────────────────────────────
        if self._gmail_re.match(text):
            logger.info(f"LOCAL route: '{text}' -> OPEN_GMAIL")
            return self._make_result("OPEN_GMAIL", {}, "Opening Gmail.")

        if self._github_re.match(text):
            logger.info(f"LOCAL route: '{text}' -> OPEN_GITHUB")
            return self._make_result("OPEN_GITHUB", {}, "Opening GitHub.")

        if self._youtube_open_re.match(text):
            logger.info(f"LOCAL route: '{text}' -> OPEN_YOUTUBE")
            return self._make_result("OPEN_YOUTUBE", {}, "Opening YouTube.")

        m = self._youtube_search_re.match(text)
        if m:
            query = m.group(1).strip()
            logger.info(f"LOCAL route: '{text}' -> OPEN_YOUTUBE({query})")
            return self._make_result("OPEN_YOUTUBE", {"search": query}, f"Searching YouTube for {query}.")

        m = self._open_website_re.match(text)
        if m:
            url = m.group(1).strip()
            if not url.startswith("http"):
                url = f"https://{url}"
            logger.info(f"LOCAL route: '{text}' -> OPEN_WEBSITE({url})")
            return self._make_result("OPEN_WEBSITE", {"url": url}, f"Opening {url}.")

        m = self._search_re.match(text)
        if m:
            query = m.group(1).strip()
            logger.info(f"LOCAL route: '{text}' -> SEARCH_WEB({query})")
            return self._make_result("SEARCH_WEB", {"query": query}, f"Searching for {query}.")

        # ─── 5. File operations ────────────────────────────────────
        m = self._open_folder_re.match(text)
        if m:
            folder = m.group(1).strip()
            logger.info(f"LOCAL route: '{text}' -> OPEN_FOLDER({folder})")
            return self._make_result("OPEN_FOLDER", {"path": folder}, f"Opening {folder}.")

        # ─── 6. Productivity ───────────────────────────────────────
        m = self._timer_re.match(text)
        if m:
            duration = int(m.group(1))
            unit = m.group(2).rstrip("s")  # normalize: "minutes" -> "minute"
            if not unit.endswith("s"):
                unit = unit  # keep singular
            logger.info(f"LOCAL route: '{text}' -> SET_TIMER({duration} {unit})")
            return self._make_result(
                "SET_TIMER",
                {"duration": duration, "unit": unit},
                f"Setting a timer for {duration} {m.group(2)}.",
            )

        m = self._reminder_re.match(text)
        if m:
            task = m.group(1).strip()
            logger.info(f"LOCAL route: '{text}' -> SET_REMINDER({task})")
            return self._make_result(
                "SET_REMINDER",
                {"task": task},
                f"I'll remind you to {task}.",
            )

        m = self._note_re.match(text)
        if m:
            content = m.group(1).strip()
            logger.info(f"LOCAL route: '{text}' -> CREATE_NOTE")
            return self._make_result(
                "CREATE_NOTE",
                {"content": content},
                "Note created.",
            )

        m = self._todo_re.match(text)
        if m:
            task = m.group(1).strip()
            logger.info(f"LOCAL route: '{text}' -> ADD_TODO")
            return self._make_result(
                "ADD_TODO",
                {"task": task},
                f"Added to your to-do list: {task}.",
            )

        # ─── No local match -> defer to Nemotron ───────────────────
        logger.debug(f"No local match for: '{text}' -> forwarding to Nemotron")
        return None

    def _make_result(
        self,
        action: str,
        parameters: dict,
        response: str,
        requires_confirmation: bool = False,
    ) -> dict:
        """Build a result dict matching ConversationAgent.understand() format."""
        return {
            "understood": True,
            "intent_summary": f"{action.replace('_', ' ').title()}",
            "tasks": [
                {
                    "action": action,
                    "parameters": parameters,
                    "requires_confirmation": requires_confirmation,
                }
            ],
            "response": response,
            "clarification": None,
            "_routed_locally": True,  # Flag for main.py to skip response generation
        }
