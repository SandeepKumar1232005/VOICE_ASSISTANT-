"""
Nexus AI — Main Orchestrator

Entry point for the voice assistant. Ties all agents together
into a unified workflow:

    Wake Word → STT → Intent Router (local fast-path) → Planner → Router → Agents → TTS

    Simple commands bypass Nemotron entirely for <1s response time.
    Complex/AI commands go through the full Nemotron pipeline.

Usage:
    cd f:\\PROJECT\\VOICEASSISTANT
    python -m nexus_ai.main
"""

import asyncio
import sys
import os
import time
import threading
import winsound

# Configure UTF-8 encoding for standard output and error to prevent UnicodeEncodeError on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure the parent directory is in the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.database import Database
from nexus_ai.utils.helpers import load_json_config
from nexus_ai.utils.perf_timer import PerfTimer, store_metrics

from nexus_ai.services.nemotron_api import NemotronClient
from nexus_ai.services.text_to_speech import TextToSpeechService
from nexus_ai.services.task_router import TaskRouter
from nexus_ai.services.intent_router import IntentRouter

from nexus_ai.agents.voice_agent import VoiceAgent
from nexus_ai.agents.conversation_agent import ConversationAgent
from nexus_ai.agents.planner_agent import PlannerAgent
from nexus_ai.agents.system_agent import SystemAgent
from nexus_ai.agents.application_agent import ApplicationAgent
from nexus_ai.agents.file_agent import FileAgent
from nexus_ai.agents.browser_agent import BrowserAgent
from nexus_ai.agents.productivity_agent import ProductivityAgent
from nexus_ai.agents.ai_agent import AIAgent
from nexus_ai.agents.memory_agent import MemoryAgent
from nexus_ai.agents.security_agent import SecurityAgent
from nexus_ai.agents.workflow_agent import WorkflowAgent

from nexus_ai.api.server import run_server, manager

logger = get_logger("Nexus")

# ─── Shared settings cache ────────────────────────────────────────
_settings_cache = None

def get_settings() -> dict:
    """Get cached settings (loaded once)."""
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = load_json_config("settings.json")
    return _settings_cache


class NexusAssistant:
    """
    Nexus AI — Multi-Agent Desktop Voice Assistant

    The main orchestrator that initializes all agents and runs
    the voice-command-execution loop.

    Architecture (optimized):
        User speaks → Voice Agent (STT)
        → Intent Router (local fast-path for simple commands)
        → [if complex] Conversation Agent (NLU via Nemotron)
        → Planner Agent → Task Router → Specialized Agents
        → Response (static for simple, Nemotron for complex)
        → TTS output
    """

    def __init__(self):
        logger.info("=" * 60)
        logger.info("  NEXUS AI — Initializing Multi-Agent System")
        logger.info("=" * 60)

        # Load settings (cached)
        self.settings = get_settings()
        self.assistant_name = self.settings.get("assistant_name", "Nexus")

        # ─── Core Services ─────────────────────────────────────
        logger.info("Loading core services...")

        # Database
        self.db = Database()

        # Nemotron API Client
        self.nemotron = NemotronClient()

        # Text-to-Speech
        self.tts = TextToSpeechService()

        # Fast Intent Router (local, no API calls)
        self.intent_router = IntentRouter()

        # ─── Persistent async event loop ───────────────────────
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._run_event_loop, daemon=True
        )
        self._loop_thread.start()

        # ─── Initialize Core Agents ────────────────────────────
        logger.info("Initializing agents...")

        # Always-needed agents
        self.voice_agent = VoiceAgent()
        self.conversation_agent = ConversationAgent(self.nemotron, self.db)
        self.planner_agent = PlannerAgent(self.nemotron)
        self.system_agent = SystemAgent()
        self.application_agent = ApplicationAgent(self.db)
        self.file_agent = FileAgent()
        self.browser_agent = BrowserAgent()
        self.productivity_agent = ProductivityAgent(
            self.db,
            tts_callback=self.tts.speak,
        )
        self.ai_agent = AIAgent(self.nemotron)
        self.memory_agent = MemoryAgent(self.db)
        self.security_agent = SecurityAgent(self.db)
        self.workflow_agent = WorkflowAgent(self.db)

        # ─── Lazy-loaded agents (instantiated on first use) ────
        self._lazy_agents = {}

        # ─── Task Router Setup ─────────────────────────────────
        self.router = TaskRouter()
        self.router.register_agent("SystemAgent", self.system_agent)
        self.router.register_agent("ApplicationAgent", self.application_agent)
        self.router.register_agent("FileAgent", self.file_agent)
        self.router.register_agent("BrowserAgent", self.browser_agent)
        self.router.register_agent("ProductivityAgent", self.productivity_agent)
        self.router.register_agent("AIAgent", self.ai_agent)
        self.router.register_agent("MemoryAgent", self.memory_agent)
        self.router.register_agent("WorkflowAgent", self.workflow_agent)
        self.router.register_security_agent(self.security_agent)

        # Lazy agent registrations (will be instantiated on first task dispatch)
        self._register_lazy_agents()

        # ─── Background Services ───────────────────────────────
        from nexus_ai.services.settings_manager import SettingsManager
        from nexus_ai.services.suggestion_engine import SuggestionEngine

        self.settings_manager = SettingsManager()
        self.suggestion_engine = SuggestionEngine(self.db, self.tts.speak)

        # ─── API & UI Server ───────────────────────────────────
        logger.info("Starting API Server...")
        self.server_thread = run_server(self, port=8000)

        # ─── Ready ─────────────────────────────────────────────
        logger.info("=" * 60)
        logger.info(f"  {self.assistant_name} AI is READY")
        logger.info(f"  Wake words: {self.settings.get('wake_words', ['nexus'])}")
        logger.info(f"  Nemotron API: {'Connected' if self.nemotron.is_available() else 'Not configured'}")
        logger.info(f"  Fast Intent Router: ENABLED")
        logger.info("=" * 60)

        self.tts.speak(
            f"Hello! I am {self.assistant_name}, your AI assistant. "
            f"Say my name to wake me up.",
            block=True,
        )

    def _run_event_loop(self):
        """Run the persistent event loop on a background thread."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _register_lazy_agents(self):
        """Register lazy-loaded agents via proxy objects."""
        lazy_configs = {
            "DocumentAgent": ("nexus_ai.agents.document_agent", "DocumentAgent", (self.nemotron,)),
            "CodingAgent": ("nexus_ai.agents.coding_agent", "CodingAgent", (self.nemotron,)),
            "MonitorAgent": ("nexus_ai.agents.monitor_agent", "MonitorAgent", (self.db,)),
            "PluginAgent": ("nexus_ai.agents.plugin_agent", "PluginAgent", ()),
            "LearningAgent": ("nexus_ai.agents.learning_agent", "LearningAgent", (self.db,)),
            "PrivacyAgent": ("nexus_ai.agents.privacy_agent", "PrivacyAgent", ()),
        }

        for agent_name, (module_path, class_name, args) in lazy_configs.items():
            proxy = LazyAgentProxy(agent_name, module_path, class_name, args)
            self.router.register_agent(agent_name, proxy)

    def _broadcast(self, event: str, **kwargs):
        """Non-blocking broadcast to UI via WebSocket."""
        message = {"event": event, **kwargs}
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), self._loop)

    async def _voice_confirm(self, prompt: str) -> str:
        """
        Voice confirmation callback for the Security Agent.
        Speaks the prompt and captures the user's yes/no response.
        """
        self.tts.speak(prompt, block=True)

        # Listen for confirmation
        response = self.voice_agent.capture_command()
        return response

    async def process_command(self, command_text: str):
        """
        Process a single voice command through the optimized pipeline.

        Flow (simple commands):
            1. Intent Router classifies locally → DONE (no API call)
            2. Planner Agent creates plan (skipped for single tasks)
            3. Task Router dispatches to agent
            4. Static response via TTS

        Flow (complex commands):
            1. Intent Router → no match → forward to Nemotron
            2. Conversation Agent understands via Nemotron API
            3. Planner Agent creates execution plan
            4. Task Router dispatches
            5. Conversation Agent generates response via Nemotron
            6. TTS speaks the response
        """
        if not command_text:
            return

        timer = PerfTimer()

        # Broadcast user command to UI
        self._broadcast("user_command", text=command_text)
        self._broadcast("status", status="thinking")

        logger.info(f"Processing command: '{command_text}'")

        # ─── Step 1: Fast local intent routing ─────────────────
        with timer.measure("intent"):
            understanding = self.intent_router.classify(command_text)

        routed_locally = understanding is not None

        if not routed_locally:
            # ─── Fallback: Nemotron NLU ────────────────────────
            timer.set_route("nemotron")
            with timer.measure("intent"):
                understanding = self.conversation_agent.understand(command_text)
        else:
            timer.set_route("local")

        if not understanding or not understanding.get("understood", False):
            self.tts.speak(
                understanding.get("response", "I didn't understand that. Could you try again?")
                if understanding else "I didn't understand that. Could you try again?"
            )
            timer.finish()
            return

        logger.info(f"Intent: {understanding.get('intent_summary', '?')} (route: {timer.metrics.route})")
        tasks = understanding.get("tasks", [])

        if not tasks:
            # Pure conversational response (no actions needed)
            self.tts.speak(understanding.get("response", "I'm not sure what to do."))
            timer.finish()
            return

        # ─── Step 2: Plan execution ────────────────────────────
        with timer.measure("plan"):
            if len(tasks) == 1 and not tasks[0].get("requires_confirmation", False):
                # Single simple task: skip planner, build plan directly
                from nexus_ai.agents.planner_agent import ACTION_TO_AGENT
                from nexus_ai.utils.helpers import generate_task_id

                task = tasks[0]
                execution_plan = [{
                    "parallel": False,
                    "tasks": [{
                        "task_id": generate_task_id(),
                        "action": task["action"],
                        "parameters": task.get("parameters", {}),
                        "requires_confirmation": task.get("requires_confirmation", False),
                        "agent": ACTION_TO_AGENT.get(task["action"], "AIAgent"),
                        "priority": 5,
                    }],
                }]
                logger.debug(f"Fast plan: 1 task, skipping PlannerAgent")
            else:
                # Complex multi-task: use full planner
                execution_plan = self.planner_agent.plan(understanding)

        if not execution_plan:
            self.tts.speak("I understood what you said, but I'm not sure how to do it yet.")
            timer.finish()
            return

        # ─── Step 3: Execute through router ────────────────────
        self._broadcast("status", status="executing")

        with timer.measure("execute"):
            results = await self.router.execute_plan(
                execution_plan,
                voice_confirm_callback=self._voice_confirm,
            )

        # ─── Step 4: Generate response ─────────────────────────
        with timer.measure("response"):
            if routed_locally:
                # Simple commands: use static response (no API call)
                response = understanding.get("response", "Done.")

                # If execution failed, use the agent's error message instead
                if results and not results[0].success:
                    response = results[0].message
            else:
                # Complex commands: generate natural response via Nemotron
                if results:
                    response = self.conversation_agent.generate_response(
                        results,
                        original_intent=understanding.get("intent_summary", command_text),
                    )
                    # Sanitize through security agent
                    response = self.security_agent.sanitize_output(response)
                else:
                    response = "Done."

        # ─── Step 5: Speak the response ────────────────────────
        with timer.measure("tts"):
            self.tts.speak(response)

        # Broadcast to UI
        self._broadcast("response", text=response)

        # ─── Performance metrics ───────────────────────────────
        metrics = timer.finish()
        store_metrics(timer.get_metrics_dict())

    def run(self):
        """
        Main loop: Listen for wake word → Capture command → Process.
        """
        logger.info("Starting main voice loop...")

        try:
            while True:
                # 1. Listen for wake word (and potentially command)
                print(f"\n  👂 Listening for '{self.assistant_name}'...\n")
                self._broadcast("status", status="listening")
                
                command_text = self.voice_agent.listen_for_wake_word_and_command()
                
                if command_text == "[LOW_CONFIDENCE]":
                    self.tts.speak("I didn't clearly understand your command. Could you please repeat it?")
                    continue

                if not command_text:
                    # User just said wake word and paused. Fallback to 2-step process.
                    try:
                        winsound.Beep(800, 150)
                    except Exception:
                        pass

                    self.tts.speak("Yes?", block=True)
                    self._broadcast("status", status="listening_command")
                    command_text = self.voice_agent.capture_command()

                if command_text and command_text != "[LOW_CONFIDENCE]":
                    # 3. Process command via persistent event loop
                    future = asyncio.run_coroutine_threadsafe(
                        self.process_command(command_text),
                        self._loop,
                    )
                    # Wait for completion (blocking the voice loop is intentional here,
                    # so we don't listen for a new wake word during processing)
                    try:
                        future.result(timeout=120)
                    except Exception as e:
                        logger.error(f"Command processing error: {e}")
                        self.tts.speak("Sorry, something went wrong.")
                elif command_text == "[LOW_CONFIDENCE]":
                    self.tts.speak("I didn't clearly understand your command. Could you please repeat it?")
                else:
                    self.tts.speak("I didn't hear a command. Try again.")

                time.sleep(0.05)  # Prevent CPU hogging

        except KeyboardInterrupt:
            logger.info("Shutting down Nexus AI...")
            self.tts.speak("Goodbye!", block=True)
            self._loop.call_soon_threadsafe(self._loop.stop)
            self.db.close()
            print("\n  👋 Nexus AI shut down.\n")


class LazyAgentProxy:
    """
    Proxy that delays agent instantiation until first use.
    Implements the same interface as BaseAgent for the TaskRouter.
    """

    def __init__(self, name: str, module_path: str, class_name: str, args: tuple):
        self.name = name
        self._module_path = module_path
        self._class_name = class_name
        self._args = args
        self._instance = None
        self._lock = threading.Lock()

    def _ensure_loaded(self):
        """Lazily instantiate the actual agent."""
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    import importlib
                    logger.info(f"Lazy-loading agent: {self.name}")
                    module = importlib.import_module(self._module_path)
                    cls = getattr(module, self._class_name)
                    self._instance = cls(*self._args)

    async def safe_execute(self, task: dict):
        """Forward to the real agent's safe_execute."""
        self._ensure_loaded()
        return await self._instance.safe_execute(task)

    async def execute(self, task: dict):
        """Forward to the real agent's execute."""
        self._ensure_loaded()
        return await self._instance.execute(task)

    def get_capabilities(self):
        """Forward to the real agent's get_capabilities."""
        self._ensure_loaded()
        return self._instance.get_capabilities()


def main():
    """Entry point for the Nexus AI voice assistant."""
    print()
    print("  ╔═══════════════════════════════════════════╗")
    print("  ║         NEXUS AI — Voice Assistant         ║")
    print("  ║     Multi-Agent Desktop AI System          ║")
    print("  ╚═══════════════════════════════════════════╝")
    print()

    assistant = NexusAssistant()
    assistant.run()


if __name__ == "__main__":
    main()
