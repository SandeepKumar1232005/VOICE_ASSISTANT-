"""
Nexus AI — Utility Helpers

Common utility functions used across agents and services.
"""

import os
import json
import uuid
import platform
from pathlib import Path
from datetime import datetime
from typing import Optional, Any


# ─── Path Utilities ────────────────────────────────────────────────

def get_project_root() -> Path:
    """Get the nexus_ai project root directory."""
    return Path(__file__).parent.parent


def get_config_path(filename: str) -> Path:
    """Get the path to a config file."""
    return get_project_root() / "config" / filename


def get_user_directory(name: str) -> Path:
    """
    Get common user directories.
    
    Args:
        name: One of 'desktop', 'documents', 'downloads', 'music', 'pictures', 'videos'
    
    Returns:
        Path to the user directory
    """
    home = Path.home()
    directories = {
        "desktop": home / "Desktop",
        "documents": home / "Documents",
        "downloads": home / "Downloads",
        "music": home / "Music",
        "pictures": home / "Pictures",
        "videos": home / "Videos",
        "home": home,
    }
    return directories.get(name.lower(), home / name)


# ─── Config Utilities ──────────────────────────────────────────────

def load_json_config(filename: str) -> dict:
    """Load a JSON config file from the config directory."""
    config_path = get_config_path(filename)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"[Config Error] Invalid JSON in {filename}: {e}")
        return {}


def save_json_config(filename: str, data: dict):
    """Save data to a JSON config file."""
    config_path = get_config_path(filename)
    os.makedirs(config_path.parent, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ─── Task Utilities ────────────────────────────────────────────────

def generate_task_id() -> str:
    """Generate a unique task ID."""
    return str(uuid.uuid4())[:8]


def create_task(
    action: str,
    parameters: Optional[dict] = None,
    requires_confirmation: bool = False,
    priority: int = 1,
) -> dict:
    """
    Create a standardized task dictionary.
    
    Args:
        action: The action type (e.g., 'OPEN_APP', 'WIFI_ON')
        parameters: Action-specific parameters
        requires_confirmation: Whether security confirmation is needed
        priority: Execution priority (1 = highest)
    
    Returns:
        Structured task dictionary
    """
    return {
        "task_id": generate_task_id(),
        "action": action,
        "parameters": parameters or {},
        "requires_confirmation": requires_confirmation,
        "priority": priority,
        "created_at": datetime.now().isoformat(),
    }


# ─── Text Utilities ────────────────────────────────────────────────

def sanitize_for_speech(text: str) -> str:
    """
    Clean text for TTS output.
    Removes markdown, URLs, code blocks, and other non-speakable content.
    """
    import re

    # Remove markdown formatting
    text = re.sub(r"```[\s\S]*?```", " code block omitted ", text)  # Code blocks
    text = re.sub(r"`([^`]+)`", r"\1", text)  # Inline code
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # Bold
    text = re.sub(r"\*([^*]+)\*", r"\1", text)  # Italic
    text = re.sub(r"#+\s+", "", text)  # Headers
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # Links
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)  # Images
    text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)  # Bullet points
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)  # Numbered lists

    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)

    # Clean up whitespace
    text = re.sub(r"\n+", ". ", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    return text


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text to a maximum length, adding ellipsis."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


# ─── System Info Utilities ─────────────────────────────────────────

def get_system_info() -> dict:
    """Get basic system information."""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "hostname": platform.node(),
    }


def format_bytes(size_bytes: int) -> str:
    """Format bytes to human-readable string."""
    if size_bytes == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f} {units[i]}"


def format_duration(seconds: int) -> str:
    """Format seconds to human-readable duration."""
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        parts = [f"{hours} hour{'s' if hours != 1 else ''}"]
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        return " and ".join(parts)


# ─── Sensitive Data Masking ────────────────────────────────────────

SENSITIVE_PATTERNS = [
    "api_key", "api-key", "apikey",
    "password", "passwd", "pwd",
    "token", "secret", "credential",
    "cookie", "session",
]


def contains_sensitive_data(text: str) -> bool:
    """Check if text contains potentially sensitive information."""
    text_lower = text.lower()
    return any(pattern in text_lower for pattern in SENSITIVE_PATTERNS)


def mask_sensitive(text: str) -> str:
    """Mask potentially sensitive values in text."""
    import re
    # Mask API keys, tokens, etc.
    text = re.sub(
        r'(["\']?(?:api[_-]?key|token|secret|password|credential)["\']?\s*[:=]\s*["\']?)([^"\'\s,}]+)',
        r"\1****REDACTED****",
        text,
        flags=re.IGNORECASE,
    )
    return text
