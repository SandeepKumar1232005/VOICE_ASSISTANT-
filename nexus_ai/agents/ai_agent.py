"""
Nexus AI — AI Assistant Agent

General-purpose AI capabilities powered by Nemotron API.
Handles Q&A, code help, translation, summarization, and email drafting.
"""

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.services.nemotron_api import NemotronClient
from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.helpers import sanitize_for_speech, truncate_text

logger = get_logger("AIAgent")

# Specialized system prompts for different AI task types
TASK_PROMPTS = {
    "ASK_AI": (
        "You are Nexus, a helpful voice assistant. Answer the user's question concisely "
        "and conversationally. Keep responses under 3 sentences since they will be spoken aloud. "
        "Do not use markdown, bullet points, or formatting."
    ),
    "EXPLAIN_CODE": (
        "You are Nexus, a coding assistant. Explain the given code clearly and concisely. "
        "Focus on what the code does, not line-by-line details. Keep it brief for voice output."
    ),
    "GENERATE_CODE": (
        "You are Nexus, a coding assistant. Generate clean, well-commented code for the request. "
        "Include only the code and a brief explanation."
    ),
    "TRANSLATE": (
        "You are Nexus, a translation assistant. Translate the given text accurately. "
        "Provide only the translation without explanations."
    ),
    "SUMMARIZE": (
        "You are Nexus, a summarization assistant. Provide a brief, clear summary "
        "in 2-3 sentences suitable for spoken output."
    ),
    "DRAFT_EMAIL": (
        "You are Nexus, an email drafting assistant. Write a professional, clear email "
        "based on the user's requirements. Include subject line and body."
    ),
    "CHECK_WEATHER": (
        "You are Nexus, a voice assistant. The user is asking about weather. "
        "Since you don't have real-time weather data, suggest they check a weather app or website. "
        "Be helpful and brief."
    ),
}


class AIAgent(BaseAgent):
    """
    AI Assistant Agent — General AI capabilities.
    
    Capabilities:
        - Answer questions (ASK_AI)
        - Explain code (EXPLAIN_CODE)
        - Generate code (GENERATE_CODE)
        - Translate text (TRANSLATE)
        - Summarize content (SUMMARIZE)
        - Draft emails (DRAFT_EMAIL)
        - Weather info (CHECK_WEATHER)
    """

    def __init__(self, nemotron: NemotronClient):
        super().__init__("AIAgent")
        self.nemotron = nemotron

    async def execute(self, task: dict) -> AgentResult:
        action = task.get("action", "")
        params = task.get("parameters", {})

        if not self.nemotron.is_available():
            return AgentResult(
                success=False,
                message="AI features are unavailable. Please configure your Nemotron API key.",
            )

        system_prompt = TASK_PROMPTS.get(action, TASK_PROMPTS["ASK_AI"])

        # Build the user message based on action type
        user_message = self._build_user_message(action, params)

        try:
            response = self.nemotron.generate_response(
                user_input=user_message,
                system_prompt=system_prompt,
                temperature=0.7 if action in ("GENERATE_CODE", "DRAFT_EMAIL") else 0.5,
                max_tokens=1024 if action in ("GENERATE_CODE", "DRAFT_EMAIL") else 512,
            )

            # Clean for speech output
            spoken_response = sanitize_for_speech(response)
            spoken_response = truncate_text(spoken_response, 500)

            logger.info(f"AI response generated for {action} ({len(response)} chars)")

            return AgentResult(
                success=True,
                message=spoken_response,
                data={"full_response": response, "action": action},
            )

        except Exception as e:
            logger.error(f"AI generation error: {e}")
            return AgentResult(
                success=False,
                message="I'm having trouble connecting to my AI engine right now.",
                error=str(e),
            )

    def _build_user_message(self, action: str, params: dict) -> str:
        """Build the user message based on the action type."""
        if action == "ASK_AI":
            return params.get("query", "")

        elif action == "EXPLAIN_CODE":
            return f"Explain this code:\n{params.get('query', '')}"

        elif action == "GENERATE_CODE":
            lang = params.get("language", "Python")
            return f"Generate {lang} code for: {params.get('query', '')}"

        elif action == "TRANSLATE":
            target = params.get("target_language", "English")
            return f"Translate the following to {target}:\n{params.get('text', '')}"

        elif action == "SUMMARIZE":
            return f"Summarize this:\n{params.get('query', '')}"

        elif action == "DRAFT_EMAIL":
            subject = params.get("subject", "")
            recipient = params.get("recipient", "")
            hint = params.get("body_hint", "")
            return (
                f"Draft an email"
                f"{' about ' + subject if subject else ''}"
                f"{' to ' + recipient if recipient else ''}"
                f"{'. ' + hint if hint else ''}"
            )

        elif action == "CHECK_WEATHER":
            return "The user is asking about the weather."

        return params.get("query", str(params))

    def get_capabilities(self) -> list[str]:
        return [
            "ASK_AI", "EXPLAIN_CODE", "GENERATE_CODE",
            "TRANSLATE", "SUMMARIZE", "DRAFT_EMAIL",
            "CHECK_WEATHER",
        ]
