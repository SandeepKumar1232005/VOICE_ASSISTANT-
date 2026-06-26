"""
Nexus AI — Performance Timer

Lightweight timing infrastructure for measuring pipeline stage latency.
Used across the system to identify and track bottlenecks.
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

from nexus_ai.utils.logger import get_logger

logger = get_logger("Perf")


@dataclass
class PipelineMetrics:
    """Stores timing data for a single command pipeline execution."""
    stt_ms: float = 0
    intent_ms: float = 0
    plan_ms: float = 0
    execute_ms: float = 0
    response_ms: float = 0
    tts_ms: float = 0
    total_ms: float = 0
    route: str = ""  # "local" or "nemotron"

    def summary(self) -> str:
        parts = []
        if self.stt_ms:
            parts.append(f"STT:{self.stt_ms:.0f}ms")
        if self.intent_ms:
            parts.append(f"Intent:{self.intent_ms:.0f}ms")
        if self.plan_ms:
            parts.append(f"Plan:{self.plan_ms:.0f}ms")
        if self.execute_ms:
            parts.append(f"Exec:{self.execute_ms:.0f}ms")
        if self.response_ms:
            parts.append(f"Resp:{self.response_ms:.0f}ms")
        if self.tts_ms:
            parts.append(f"TTS:{self.tts_ms:.0f}ms")
        if self.route:
            parts.append(f"Route:{self.route}")
        parts.append(f"TOTAL:{self.total_ms:.0f}ms")
        return " | ".join(parts)


class PerfTimer:
    """
    Pipeline performance timer.
    
    Usage:
        timer = PerfTimer()
        with timer.measure("stt"):
            text = stt.transcribe(...)
        with timer.measure("intent"):
            result = router.classify(...)
        timer.finish()  # logs the summary
    """

    def __init__(self):
        self.metrics = PipelineMetrics()
        self._start_time = time.perf_counter()

    @contextmanager
    def measure(self, stage: str):
        """Context manager to time a pipeline stage."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            if hasattr(self.metrics, f"{stage}_ms"):
                setattr(self.metrics, f"{stage}_ms", elapsed_ms)
            else:
                # Store unknown stages as part of execute
                self.metrics.execute_ms += elapsed_ms

    def set_route(self, route: str):
        """Record whether this command was routed locally or via API."""
        self.metrics.route = route

    def finish(self) -> PipelineMetrics:
        """Finalize timing and log the summary."""
        self.metrics.total_ms = (time.perf_counter() - self._start_time) * 1000
        logger.info(f"⚡ {self.metrics.summary()}")
        return self.metrics

    def get_metrics_dict(self) -> dict:
        """Return metrics as a dict (for API/UI)."""
        return {
            "stt_ms": round(self.metrics.stt_ms, 1),
            "intent_ms": round(self.metrics.intent_ms, 1),
            "plan_ms": round(self.metrics.plan_ms, 1),
            "execute_ms": round(self.metrics.execute_ms, 1),
            "response_ms": round(self.metrics.response_ms, 1),
            "tts_ms": round(self.metrics.tts_ms, 1),
            "total_ms": round(self.metrics.total_ms, 1),
            "route": self.metrics.route,
        }


# ─── Global last-metrics store (for API endpoint) ──────────────────
_last_metrics: Optional[dict] = None


def store_metrics(metrics: dict):
    """Store the most recent pipeline metrics for the API."""
    global _last_metrics
    _last_metrics = metrics


def get_last_metrics() -> Optional[dict]:
    """Retrieve the most recent pipeline metrics."""
    return _last_metrics
