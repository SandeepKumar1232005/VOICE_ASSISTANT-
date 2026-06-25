"""
Nexus AI — Browser Control

Open websites, search Google, navigate to known sites.
"""

import webbrowser
import urllib.parse
from nexus_ai.utils.logger import get_logger

logger = get_logger("Browser")


class BrowserController:
    """Controls web browser navigation."""

    # Known website shortcuts
    KNOWN_SITES = {
        "youtube": "https://www.youtube.com",
        "gmail": "https://mail.google.com",
        "google mail": "https://mail.google.com",
        "email": "https://mail.google.com",
        "github": "https://github.com",
        "chatgpt": "https://chat.openai.com",
        "google": "https://www.google.com",
        "google drive": "https://drive.google.com",
        "google docs": "https://docs.google.com",
        "google sheets": "https://sheets.google.com",
        "twitter": "https://twitter.com",
        "x": "https://twitter.com",
        "reddit": "https://www.reddit.com",
        "linkedin": "https://www.linkedin.com",
        "facebook": "https://www.facebook.com",
        "instagram": "https://www.instagram.com",
        "whatsapp": "https://web.whatsapp.com",
        "netflix": "https://www.netflix.com",
        "amazon": "https://www.amazon.com",
        "wikipedia": "https://www.wikipedia.org",
        "stackoverflow": "https://stackoverflow.com",
        "stack overflow": "https://stackoverflow.com",
        "figma": "https://www.figma.com",
        "notion": "https://www.notion.so",
        "slack": "https://slack.com",
        "teams": "https://teams.microsoft.com",
        "outlook": "https://outlook.live.com",
        "google classroom": "https://classroom.google.com",
        "canvas": "https://canvas.instructure.com",
    }

    def open_website(self, url: str = None, site_name: str = None) -> tuple[bool, str]:
        """
        Open a website by URL or known name.
        
        Args:
            url: Direct URL to open
            site_name: Name of a known site (e.g., "youtube")
        """
        if site_name:
            site_name_lower = site_name.lower().strip()
            if site_name_lower in self.KNOWN_SITES:
                url = self.KNOWN_SITES[site_name_lower]
            elif not url:
                # Try to construct URL
                url = f"https://www.{site_name_lower.replace(' ', '')}.com"

        if not url:
            return False, "No website specified."

        # Ensure URL has protocol
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            webbrowser.open(url)
            display_name = site_name or url
            logger.info(f"Opened website: {url}")
            return True, f"Opening {display_name}."
        except Exception as e:
            return False, f"Failed to open website: {e}"

    def search_web(self, query: str) -> tuple[bool, str]:
        """Search Google for a query."""
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://www.google.com/search?q={encoded}"
            webbrowser.open(url)
            logger.info(f"Google search: {query}")
            return True, f"Searching Google for '{query}'."
        except Exception as e:
            return False, f"Failed to search: {e}"

    def open_youtube(self, search: str = None) -> tuple[bool, str]:
        """Open YouTube, optionally with a search query."""
        try:
            if search:
                encoded = urllib.parse.quote_plus(search)
                url = f"https://www.youtube.com/results?search_query={encoded}"
                webbrowser.open(url)
                logger.info(f"YouTube search: {search}")
                return True, f"Searching YouTube for '{search}'."
            else:
                webbrowser.open("https://www.youtube.com")
                logger.info("Opened YouTube")
                return True, "Opening YouTube."
        except Exception as e:
            return False, f"Failed to open YouTube: {e}"

    def open_gmail(self) -> tuple[bool, str]:
        """Open Gmail."""
        return self.open_website(url="https://mail.google.com", site_name="Gmail")

    def open_github(self) -> tuple[bool, str]:
        """Open GitHub."""
        return self.open_website(url="https://github.com", site_name="GitHub")
