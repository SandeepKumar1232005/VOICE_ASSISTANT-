"""
Nexus AI — Browser Agent

Handles web browsing operations via the BrowserController.
"""

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.system.browser import BrowserController
from nexus_ai.utils.logger import get_logger

logger = get_logger("BrowserAgent")


class BrowserAgent(BaseAgent):
    """
    Browser Agent — Web navigation and search.
    
    Capabilities:
        - Open websites by name or URL
        - Google search
        - YouTube search
        - Gmail, GitHub shortcuts
    """

    def __init__(self):
        super().__init__("BrowserAgent")
        self.browser = BrowserController()

    async def execute(self, task: dict) -> AgentResult:
        action = task.get("action", "")
        params = task.get("parameters", {})

        if action == "OPEN_WEBSITE":
            success, message = self.browser.open_website(
                url=params.get("url"),
                site_name=params.get("site_name"),
            )
            return AgentResult(success=success, message=message)

        elif action == "SEARCH_WEB":
            query = params.get("query", "")
            if not query:
                return AgentResult(success=False, message="No search query provided.")
            success, message = self.browser.search_web(query)
            return AgentResult(success=success, message=message)

        elif action == "OPEN_YOUTUBE":
            success, message = self.browser.open_youtube(
                search=params.get("search")
            )
            return AgentResult(success=success, message=message)

        elif action == "OPEN_GMAIL":
            success, message = self.browser.open_gmail()
            return AgentResult(success=success, message=message)

        elif action == "OPEN_GITHUB":
            success, message = self.browser.open_github()
            return AgentResult(success=success, message=message)

        return AgentResult(success=False, message=f"Unknown browser action: {action}")

    def get_capabilities(self) -> list[str]:
        return ["OPEN_WEBSITE", "SEARCH_WEB", "OPEN_YOUTUBE", "OPEN_GMAIL", "OPEN_GITHUB"]
