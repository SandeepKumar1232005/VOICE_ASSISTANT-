"""
Nexus AI — NVIDIA Nemotron API Client

Centralized client for all Nemotron API interactions.
Uses OpenAI-compatible SDK to communicate with NVIDIA's inference endpoint.
Used by: Conversation Agent, Planner Agent, AI Assistant Agent.
"""

import json
from typing import Optional

from openai import OpenAI

from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.helpers import load_json_config, mask_sensitive

logger = get_logger("NemotronAPI")


class NemotronClient:
    """
    Client wrapper for NVIDIA Nemotron API.
    
    Uses the OpenAI-compatible endpoint at integrate.api.nvidia.com.
    Provides both free-form chat and structured JSON response modes.
    """

    BASE_URL = "https://integrate.api.nvidia.com/v1"
    DEFAULT_MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the Nemotron client.
        
        Args:
            api_key: NVIDIA API key. If None, loads from settings.json.
            model: Model identifier. Defaults to Nemotron Super.
        """
        if api_key is None:
            settings = load_json_config("settings.json")
            api_key = settings.get("nemotron_api_key", "")

        if not api_key:
            logger.warning("No Nemotron API key configured! AI features will be unavailable.")
            self.client = None
            self.available = False
            return

        self.client = OpenAI(
            base_url=self.BASE_URL,
            api_key=api_key,
        )
        self.model = model or self.DEFAULT_MODEL
        self.available = True
        logger.info(f"Nemotron client initialized with model: {self.model}")

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.6,
        max_tokens: int = 1024,
        stream: bool = False,
    ) -> str:
        """
        Send a chat completion request and return the response text.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
            max_tokens: Maximum response tokens
            stream: Whether to stream the response
        
        Returns:
            Response text string
        
        Raises:
            RuntimeError: If API key is not configured
        """
        if not self.available:
            raise RuntimeError("Nemotron API is not available. Please configure your API key in settings.json")

        try:
            logger.debug(f"Sending chat request ({len(messages)} messages, temp={temperature})")

            if stream:
                return self._chat_stream(messages, temperature, max_tokens)

            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                top_p=0.95,
                max_tokens=max_tokens,
            )

            response_text = completion.choices[0].message.content
            logger.debug(f"Received response: {len(response_text)} chars")
            return response_text.strip()

        except Exception as e:
            error_msg = mask_sensitive(str(e))
            logger.error(f"Nemotron API error: {error_msg}")
            raise RuntimeError(f"AI engine error: {error_msg}")

    def _chat_stream(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Stream a chat response and collect the full text."""
        full_response = []

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            top_p=0.95,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in completion:
            if chunk.choices[0].delta.content is not None:
                full_response.append(chunk.choices[0].delta.content)

        return "".join(full_response).strip()

    def chat_json(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> dict:
        """
        Send a chat request expecting a JSON response.
        
        Uses lower temperature for more deterministic structured output.
        Parses the response as JSON, with fallback extraction if the model
        wraps the JSON in markdown code blocks.
        
        Args:
            messages: List of message dicts
            temperature: Lower default for structured output
            max_tokens: Maximum response tokens
        
        Returns:
            Parsed JSON dictionary
        
        Raises:
            ValueError: If response cannot be parsed as JSON
        """
        response_text = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return self._extract_json(response_text)

    def _extract_json(self, text: str) -> dict:
        """
        Extract JSON from a response that may contain markdown code blocks
        or other wrapping text.
        """
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        import re
        json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding JSON object/array boundaries
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start_idx = text.find(start_char)
            end_idx = text.rfind(end_char)
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                try:
                    return json.loads(text[start_idx : end_idx + 1])
                except json.JSONDecodeError:
                    continue

        logger.error(f"Failed to parse JSON from response: {text[:200]}...")
        raise ValueError(f"Could not extract valid JSON from API response")

    def generate_response(
        self,
        user_input: str,
        system_prompt: str,
        conversation_history: Optional[list[dict]] = None,
        temperature: float = 0.6,
        max_tokens: int = 1024,
    ) -> str:
        """
        Convenience method for generating a response with system prompt and history.
        
        Args:
            user_input: The user's current input
            system_prompt: System-level instructions
            conversation_history: Previous turns for context
            temperature: Sampling temperature
            max_tokens: Max response tokens
        
        Returns:
            Response text
        """
        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_input})

        return self.chat(messages, temperature=temperature, max_tokens=max_tokens)

    def is_available(self) -> bool:
        """Check if the Nemotron API is configured and available."""
        return self.available
