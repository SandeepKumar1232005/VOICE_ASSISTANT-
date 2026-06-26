"""
Nexus AI — Structured Logging System

Provides per-agent colored console output and rotating file logs.
All agents use get_logger(agent_name) for consistent formatting.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime


# ─── Color Codes for Console ───────────────────────────────────────
COLORS = {
    "RESET": "\033[0m",
    "RED": "\033[91m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "BLUE": "\033[94m",
    "MAGENTA": "\033[95m",
    "CYAN": "\033[96m",
    "WHITE": "\033[97m",
    "GRAY": "\033[90m",
}

# Agent-specific colors for visual differentiation in console
AGENT_COLORS = {
    "VoiceAgent": "GREEN",
    "ConversationAgent": "BLUE",
    "PlannerAgent": "MAGENTA",
    "SystemAgent": "CYAN",
    "ApplicationAgent": "CYAN",
    "FileAgent": "YELLOW",
    "BrowserAgent": "YELLOW",
    "ProductivityAgent": "WHITE",
    "AIAgent": "BLUE",
    "MemoryAgent": "MAGENTA",
    "SecurityAgent": "RED",
    "TaskRouter": "GRAY",
    "Nexus": "GREEN",
    "NemotronAPI": "BLUE",
    "STT": "GREEN",
    "TTS": "GREEN",
    "IntentRouter": "CYAN",
    "Perf": "MAGENTA",
    "SuggestionEngine": "GRAY",
}


class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors to console output based on log level and agent name."""

    def __init__(self, agent_name: str = "Nexus"):
        self.agent_name = agent_name
        self.agent_color = COLORS.get(AGENT_COLORS.get(agent_name, "WHITE"), COLORS["WHITE"])
        super().__init__()

    def format(self, record):
        # Level color
        level_colors = {
            "DEBUG": COLORS["GRAY"],
            "INFO": COLORS["GREEN"],
            "WARNING": COLORS["YELLOW"],
            "ERROR": COLORS["RED"],
            "CRITICAL": COLORS["RED"],
        }
        level_color = level_colors.get(record.levelname, COLORS["WHITE"])

        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        
        formatted = (
            f"{COLORS['GRAY']}{timestamp}{COLORS['RESET']} "
            f"{level_color}{record.levelname:<8}{COLORS['RESET']} "
            f"{self.agent_color}[{self.agent_name}]{COLORS['RESET']} "
            f"{record.getMessage()}"
        )
        
        if record.exc_info and record.exc_info[0]:
            formatted += f"\n{level_color}{self.formatException(record.exc_info)}{COLORS['RESET']}"
        
        return formatted


class FileFormatter(logging.Formatter):
    """Clean formatter for log files (no color codes)."""

    def __init__(self, agent_name: str = "Nexus"):
        self.agent_name = agent_name
        super().__init__()

    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        formatted = f"{timestamp} {record.levelname:<8} [{self.agent_name}] {record.getMessage()}"
        
        if record.exc_info and record.exc_info[0]:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        return formatted


import queue
from logging.handlers import QueueHandler, QueueListener

# ─── Log directory setup ───────────────────────────────────────────
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)

# Track created loggers to avoid duplicate handlers
_loggers: dict[str, logging.Logger] = {}

# Shared async log queue and listener (non-blocking file I/O)
_log_queue = queue.Queue(-1)  # Unlimited queue
_queue_listener = None
_file_handlers = []


def _ensure_queue_listener():
    """Start the shared queue listener (once) for async file logging."""
    global _queue_listener
    if _queue_listener is not None:
        return

    # Per-agent file handlers are added dynamically, but the shared log
    # is always present
    shared_log_file = os.path.join(_LOG_DIR, "nexus.log")
    shared_handler = RotatingFileHandler(
        shared_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    shared_handler.setLevel(logging.DEBUG)
    shared_handler.setFormatter(FileFormatter("Nexus"))
    _file_handlers.append(shared_handler)

    _queue_listener = QueueListener(_log_queue, *_file_handlers, respect_handler_level=True)
    _queue_listener.start()


def get_logger(agent_name: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Get or create a logger for a specific agent.
    
    Each agent gets:
    - Colored console output (synchronous, fast)
    - Rotating file log via async queue (non-blocking)
    - Shared nexus.log via async queue (non-blocking)
    
    Args:
        agent_name: Name of the agent (used in log prefix and filename)
        level: Logging level (default DEBUG)
    
    Returns:
        Configured logger instance
    """
    if agent_name in _loggers:
        return _loggers[agent_name]

    logger = logging.getLogger(f"nexus.{agent_name}")
    logger.setLevel(level)
    logger.propagate = False  # Don't bubble up to root logger

    # Console handler (colored, synchronous — it's fast enough)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColoredFormatter(agent_name))
    logger.addHandler(console_handler)

    # Per-agent file handler (added to the async queue listener)
    agent_log_file = os.path.join(_LOG_DIR, f"{agent_name.lower()}.log")
    file_handler = RotatingFileHandler(
        agent_log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(FileFormatter(agent_name))
    _file_handlers.append(file_handler)

    # Use QueueHandler for non-blocking file writes
    queue_handler = QueueHandler(_log_queue)
    queue_handler.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)

    # Ensure the listener is running
    _ensure_queue_listener()

    # Restart listener to pick up new handler
    global _queue_listener
    if _queue_listener is not None:
        _queue_listener.stop()
        _queue_listener = QueueListener(_log_queue, *_file_handlers, respect_handler_level=True)
        _queue_listener.start()

    _loggers[agent_name] = logger
    return logger


def get_security_logger() -> logging.Logger:
    """
    Special logger for security events.
    Logs to a dedicated security.log file that should never be exposed.
    """
    name = "SecurityAudit"
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(f"nexus.{name}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Security-specific file (no console output for security events)
    security_log = os.path.join(_LOG_DIR, "security.log")
    handler = RotatingFileHandler(
        security_log,
        maxBytes=5 * 1024 * 1024,
        backupCount=10,  # Keep more backups for security audit trail
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(FileFormatter(name))
    logger.addHandler(handler)

    _loggers[name] = logger
    return logger
