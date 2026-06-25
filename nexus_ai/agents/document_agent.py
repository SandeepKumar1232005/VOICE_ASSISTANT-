"""
Nexus AI — Document Agent

Reads and processes documents (PDF, DOCX, TXT, Markdown)
Uses Nemotron AI to summarize, extract key points, explain, translate,
rewrite, and answer questions based on the document's content.
"""

import os
from typing import Optional

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.services.nemotron_api import NemotronClient
from nexus_ai.utils.logger import get_logger

logger = get_logger("DocumentAgent")


class DocumentAgent(BaseAgent):
    """
    Document Agent — File content analysis and generation.

    Capabilities:
        - Read PDF, DOCX, TXT, MD files
        - Summarize document
        - Explain complex topics from document
        - Extract key points
        - Q&A based on document content
        - Translate document
        - Rewrite/improve document
    """

    def __init__(self, nemotron: NemotronClient):
        super().__init__("DocumentAgent")
        self.nemotron = nemotron

    async def execute(self, task: dict) -> AgentResult:
        action = task.get("action", "")
        params = task.get("parameters", {})

        if action == "READ_DOCUMENT":
            return self._process_document(params)

        return AgentResult(success=False, message=f"Unknown document action: {action}")

    def _process_document(self, params: dict) -> AgentResult:
        path = params.get("path", "").strip()
        operation = params.get("operation", "summarize").lower()
        query = params.get("query", "").strip()

        if not path:
            return AgentResult(
                success=False,
                message="Please specify the path to the document you want me to read.",
            )

        if not os.path.exists(path):
            return AgentResult(
                success=False,
                message=f"I couldn't find the file at {path}.",
            )

        # 1. Extract Text
        content = self._extract_text(path)
        if not content:
            return AgentResult(
                success=False,
                message=f"I couldn't read any text from {os.path.basename(path)}. "
                        f"Make sure it's a valid PDF, Word document, or text file.",
            )

        logger.info(f"Read {len(content)} characters from {os.path.basename(path)}")

        # 2. Build Prompt based on Operation
        filename = os.path.basename(path)
        prompt = self._build_prompt(operation, filename, content, query)

        if not prompt:
            return AgentResult(
                success=False,
                message=f"I don't know how to perform the operation: '{operation}'.",
            )

        # 3. Call Nemotron
        if not self.nemotron.is_available():
            return AgentResult(
                success=False,
                message="AI features are currently unavailable because the Nemotron API is not configured.",
            )

        try:
            logger.info(f"Processing document via Nemotron: operation={operation}")
            # Use max_tokens=1500 for a solid response, truncate input slightly if it's massive
            # (Nemotron handles large contexts well, but we'll limit to ~20k chars for safety here)
            MAX_CHARS = 20000
            if len(content) > MAX_CHARS:
                logger.warning(f"Document is very large ({len(content)} chars), truncating for AI processing.")
                content = content[:MAX_CHARS] + "\n...[Content truncated due to length]..."

            # Re-build prompt with potentially truncated content
            prompt = self._build_prompt(operation, filename, content, query)

            system_instruction = "You are an expert document analysis AI. Provide clear, concise, and accurate responses based strictly on the provided document text."
            
            response = self.nemotron.generate_response(
                user_input=prompt,
                system_prompt=system_instruction,
                temperature=0.4,  # Lower temp for factual document tasks
                max_tokens=1500,
            )

            return AgentResult(
                success=True,
                message=f"Here is what I found in {filename}:",
                data={"result": response, "operation": operation, "filename": filename},
            )

        except Exception as e:
            logger.error(f"Document processing error: {e}")
            return AgentResult(
                success=False,
                message=f"I encountered an error while processing the document: {str(e)}",
            )

    def _extract_text(self, path: str) -> Optional[str]:
        """Extract text from supported file types."""
        ext = os.path.splitext(path)[1].lower()

        try:
            if ext == ".pdf":
                return self._extract_pdf(path)
            elif ext in (".docx", ".doc"):
                return self._extract_docx(path)
            elif ext in (".txt", ".md", ".csv", ".json", ".py", ".html"):
                return self._extract_text_file(path)
            else:
                logger.warning(f"Unsupported document extension: {ext}")
                return None
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return None

    def _extract_pdf(self, path: str) -> str:
        import PyPDF2
        text_parts = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n".join(text_parts)

    def _extract_docx(self, path: str) -> str:
        import docx
        doc = docx.Document(path)
        return "\n".join([para.text for para in doc.paragraphs])

    def _extract_text_file(self, path: str) -> str:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _build_prompt(self, operation: str, filename: str, content: str, query: str) -> Optional[str]:
        """Build the specific prompt based on the requested operation."""
        base_prompt = f"Document Name: {filename}\n\nDocument Content:\n\"\"\"{content}\"\"\"\n\n---\n"

        if operation == "summarize":
            return base_prompt + "Task: Please provide a comprehensive but concise summary of this document."
        elif operation == "explain":
            return base_prompt + "Task: Explain the main concepts of this document as if explaining to a beginner. Break down any complex topics."
        elif operation == "keypoints":
            return base_prompt + "Task: Extract the key points, main arguments, or most important facts from this document as a bulleted list."
        elif operation == "notes":
            return base_prompt + "Task: Generate structured study notes from this document, organized by headings and subheadings."
        elif operation == "translate":
            target_lang = query if query else "English"
            return base_prompt + f"Task: Translate the core content of this document into {target_lang}."
        elif operation == "rewrite":
            style = query if query else "professional and clear"
            return base_prompt + f"Task: Rewrite the document to be more {style}."
        elif operation == "qa":
            if not query:
                return base_prompt + "Task: What is this document about?"
            return base_prompt + f"Task: Based strictly on the document above, answer the following question:\nQuestion: {query}"
        else:
            return None

    def get_capabilities(self) -> list[str]:
        return ["READ_DOCUMENT"]
