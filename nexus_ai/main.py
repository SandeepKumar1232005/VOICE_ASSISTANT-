"""
Nexus AI — Main Orchestrator

Entry point for the voice assistant. Ties all 11 agents together
into a unified workflow:

    Wake Word → STT → Conversation Agent → Planner → Router → Agents → TTS

Usage:
    cd f:\\PROJECT\\VOICEASSISTANT
    python -m nexus_ai.main
"""

import asyncio
import sys
import os
import time
import winsound

# Ensure the parent directory is in the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.database import Database
from nexus_ai.utils.helpers import load_json_config

from nexus_ai.services.nemotron_api import NemotronClient
from nexus_ai.services.text_to_speech import TextToSpeechService
from nexus_ai.services.task_router import TaskRouter

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
from nexus_ai.agents.document_agent import DocumentAgent
from nexus_ai.agents.coding_agent import CodingAgent
from nexus_ai.agents.monitor_agent import MonitorAgent
from nexus_ai.agents.plugin_agent import PluginAgent
from nexus_ai.agents.learning_agent import LearningAgent
from nexus_ai.agents.privacy_agent import PrivacyAgent
from nexus_ai.services.suggestion_engine import SuggestionEngine
from nexus_ai.services.settings_manager import SettingsManager
from nexus_ai.api.server import run_server, manager

logger = get_logger("Nexus")


class NexusAssistant:
    """
    Nexus AI — Multi-Agent Desktop Voice Assistant
    
    The main orchestrator that initializes all 11 agents and runs
    the voice-command-execution loop.
    
    Architecture:
        User speaks → Voice Agent (STT) → Conversation Agent (NLU)
        → Planner Agent → Task Router → Specialized Agents
        → Result Collection → Conversation Agent (response)
        → TTS output
    """

    def __init__(self):
        logger.info("=" * 60)
        logger.info("  NEXUS AI — Initializing Multi-Agent System")
        logger.info("=" * 60)

        # Load settings
        self.settings = load_json_config("settings.json")
        self.assistant_name = self.settings.get("assistant_name", "Nexus")

        # ─── Core Services ─────────────────────────────────────
        logger.info("Loading core services...")

        # Database
        self.db = Database()

        # Nemotron API Client
        self.nemotron = NemotronClient()

        # Text-to-Speech
        self.tts = TextToSpeechService()

        # ─── Initialize All 11 Agents ─────────────────────────
        logger.info("Initializing agents...")

        # 1. Voice Agent
        self.voice_agent = VoiceAgent()

        # 2. Conversation Agent
        self.conversation_agent = ConversationAgent(self.nemotron, self.db)

        # 3. Planner Agent
        self.planner_agent = PlannerAgent(self.nemotron)

        # 4. System Control Agent
        self.system_agent = SystemAgent()

        # 5. Application Agent
        self.application_agent = ApplicationAgent(self.db)

        # 6. File Management Agent
        self.file_agent = FileAgent()

        # 7. Browser Agent
        self.browser_agent = BrowserAgent()

        # 8. Productivity Agent
        self.productivity_agent = ProductivityAgent(
            self.db,
            tts_callback=self.tts.speak,
        )

        # 9. AI Assistant Agent
        self.ai_agent = AIAgent(self.nemotron)

        # 10. Memory Agent
        self.memory_agent = MemoryAgent(self.db)

        # 11. Workflow Agent
        self.workflow_agent = WorkflowAgent(self.db)

        # 12. Document Agent
        self.document_agent = DocumentAgent(self.nemotron)

        # 13. Coding Agent
        self.coding_agent = CodingAgent(self.nemotron)

        # 14. Monitor Agent
        self.monitor_agent = MonitorAgent(self.db)
        
        # 15. Plugin Agent
        self.plugin_agent = PluginAgent()
        
        # 16. Learning Agent
        self.learning_agent = LearningAgent(self.db)

        # 17. Privacy Agent
        self.privacy_agent = PrivacyAgent()

        # 18. Security Agent
        self.security_agent = SecurityAgent(self.db)

        # ─── Background Services ───────────────────────────────
        self.settings_manager = SettingsManager()
        self.suggestion_engine = SuggestionEngine(self.db, self.tts.speak)

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
        self.router.register_agent("DocumentAgent", self.document_agent)
        self.router.register_agent("CodingAgent", self.coding_agent)
        self.router.register_agent("MonitorAgent", self.monitor_agent)
        self.router.register_agent("PluginAgent", self.plugin_agent)
        self.router.register_agent("LearningAgent", self.learning_agent)
        self.router.register_agent("PrivacyAgent", self.privacy_agent)
        self.router.register_security_agent(self.security_agent)

        # ─── API & UI Server ───────────────────────────────────
        logger.info("Starting API Server...")
        self.server_thread = run_server(self, port=8000)

        # ─── Ready ─────────────────────────────────────────────
        logger.info("=" * 60)
        logger.info(f"  {self.assistant_name} AI is READY")
        logger.info(f"  Wake words: {self.settings.get('wake_words', ['nexus'])}")
        logger.info(f"  Nemotron API: {'Connected' if self.nemotron.is_available() else 'Not configured'}")
        logger.info("=" * 60)

        self.tts.speak(
            f"Hello! I am {self.assistant_name}, your AI assistant. "
            f"Say my name to wake me up.",
            block=True,
        )

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
        Process a single voice command through the full pipeline.
        
        Flow:
            1. Conversation Agent understands the command
            2. Planner Agent creates execution plan
            3. Task Router dispatches to agents (via Security Agent)
            4. Conversation Agent generates response
            5. TTS speaks the response
        """
        if not command_text:
            return

        # Broadcast user command back to UI if it came from voice
        asyncio.create_task(manager.broadcast({"event": "user_command", "text": command_text}))

        logger.info(f"Processing command: '{command_text}'")

        # Step 1: Understand the command
        understanding = self.conversation_agent.understand(command_text)

        if not understanding.get("understood", False):
            self.tts.speak(
                understanding.get("response", "I didn't understand that. Could you try again?")
            )
            return

        logger.info(f"Intent: {understanding.get('intent_summary', '?')}")
        tasks = understanding.get("tasks", [])

        if not tasks:
            # Pure conversational response (no actions needed)
            self.tts.speak(understanding.get("response", "I'm not sure what to do."))
            return

        # Step 2: Plan execution
        execution_plan = self.planner_agent.plan(understanding)

        if not execution_plan:
            self.tts.speak("I understood what you said, but I'm not sure how to do it yet.")
            return

        # Step 3: Execute through router (with security validation)
        results = await self.router.execute_plan(
            execution_plan,
            voice_confirm_callback=self._voice_confirm,
        )

        # Step 4: Generate natural response
        if results:
            response = self.conversation_agent.generate_response(
                results,
                original_intent=understanding.get("intent_summary", command_text),
            )

            # Sanitize through security agent
            response = self.security_agent.sanitize_output(response)

            # Step 5: Speak the response
            self.tts.speak(response)
            
            # Broadcast to UI
            asyncio.create_task(manager.broadcast({"event": "response", "text": response}))
        else:
            self.tts.speak("Done.")
            asyncio.create_task(manager.broadcast({"event": "response", "text": "Done."}))

    def run(self):
        """
        Main loop: Listen for wake word → Capture command → Process.
        """
        logger.info("Starting main voice loop...")

        try:
            while True:
                # 1. Listen for wake word
                print(f"\n  👂 Listening for '{self.assistant_name}'...\n")
                wake_detected = self.voice_agent.listen_for_wake_word()

                if wake_detected:
                    # Play acknowledgment beep
                    try:
                        winsound.Beep(800, 150)
                    except Exception:
                        pass

                    self.tts.speak("Yes?", block=True)

                    # 2. Capture command
                    command_text = self.voice_agent.capture_command()

                    if command_text:
                        # 3. Process command
                        asyncio.run(self.process_command(command_text))
                    else:
                        self.tts.speak("I didn't hear a command. Try again.")

                time.sleep(0.05)  # Prevent CPU hogging

        except KeyboardInterrupt:
            logger.info("Shutting down Nexus AI...")
            self.tts.speak("Goodbye!", block=True)
            self.db.close()
            print("\n  👋 Nexus AI shut down.\n")


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
