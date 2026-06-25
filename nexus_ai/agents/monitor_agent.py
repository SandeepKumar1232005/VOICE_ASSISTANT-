"""
Nexus AI — System Monitoring Agent

Actively monitors system health (CPU, RAM, Disk, Battery, Network).
Provides health reports and handles proactive alerts.
"""

import os
import psutil
from typing import Optional

from nexus_ai.agents.base_agent import BaseAgent, AgentResult
from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.database import Database

logger = get_logger("MonitorAgent")


class MonitorAgent(BaseAgent):
    """
    System Monitor Agent — Observability and health reporting.
    
    Capabilities:
        - Full system health report
        - CPU usage check
        - RAM usage check
        - Disk space check
        - Battery status check
        - Network connectivity check
        - Temperature check
    """

    def __init__(self, db: Database):
        super().__init__("MonitorAgent")
        self.db = db

    async def execute(self, task: dict) -> AgentResult:
        action = task.get("action", "")
        params = task.get("parameters", {})

        if action == "SYSTEM_HEALTH":
            return self._get_health_report()
        elif action == "CHECK_CPU":
            return self._check_cpu()
        elif action == "CHECK_RAM":
            return self._check_ram()
        elif action == "CHECK_STORAGE":
            return self._check_disk()
        elif action == "CHECK_BATTERY":
            return self._check_battery()
        elif action == "CHECK_NETWORK":
            return self._check_network()
        elif action == "CHECK_TEMPERATURE":
            return self._check_temperature()

        return AgentResult(success=False, message=f"Unknown monitoring action: {action}")

    def _get_health_report(self) -> AgentResult:
        """Generate a comprehensive system health report."""
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Battery (if available)
        battery_msg = ""
        has_battery = hasattr(psutil, "sensors_battery") and psutil.sensors_battery() is not None
        if has_battery:
            batt = psutil.sensors_battery()
            plugged = "Plugged in" if batt.power_plugged else "Discharging"
            battery_msg = f"Battery is at {int(batt.percent)}% ({plugged}). "
            
        # Network
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            net_status = "Online"
        except OSError:
            net_status = "Offline"

        # Format output
        report = (
            f"System Health Report:\n"
            f"- CPU Usage: {cpu}%\n"
            f"- RAM Usage: {ram.percent}% ({self._format_bytes(ram.used)} / {self._format_bytes(ram.total)})\n"
            f"- Disk Space: {disk.percent}% used ({self._format_bytes(disk.free)} free)\n"
            f"- Network: {net_status}\n"
        )
        if battery_msg:
            report += f"- {battery_msg}\n"
            
        # Save snapshot
        self.db.save_system_snapshot(
            cpu=cpu, 
            ram=ram.percent, 
            disk=disk.percent,
            battery=batt.percent if has_battery else None,
            plugged=batt.power_plugged if has_battery else None,
            network=(net_status == "Online")
        )
            
        # Simple analysis
        warnings = []
        if cpu > 85: warnings.append("CPU usage is high.")
        if ram.percent > 90: warnings.append("Memory is almost full.")
        if disk.percent > 90: warnings.append("Disk space is running low.")
        if has_battery and not batt.power_plugged and batt.percent < 20:
            warnings.append("Battery is low, please plug in soon.")
            
        if warnings:
            report += "\nWarnings: " + " ".join(warnings)
            return AgentResult(success=True, message=report, data={"warnings": True})
            
        return AgentResult(success=True, message="All systems are operating normally.\n\n" + report, data={"warnings": False})

    def _check_cpu(self) -> AgentResult:
        cpu = psutil.cpu_percent(interval=1.0)
        cores = psutil.cpu_count(logical=False)
        threads = psutil.cpu_count(logical=True)
        msg = f"CPU is currently at {cpu}% usage across {cores} cores and {threads} threads."
        return AgentResult(success=True, message=msg)

    def _check_ram(self) -> AgentResult:
        ram = psutil.virtual_memory()
        used = self._format_bytes(ram.used)
        total = self._format_bytes(ram.total)
        msg = f"Memory usage is at {ram.percent}%. You are using {used} out of {total}."
        return AgentResult(success=True, message=msg)

    def _check_disk(self) -> AgentResult:
        disk = psutil.disk_usage('/')
        free = self._format_bytes(disk.free)
        total = self._format_bytes(disk.total)
        msg = f"Your main drive is {disk.percent}% full, with {free} remaining out of {total}."
        return AgentResult(success=True, message=msg)

    def _check_battery(self) -> AgentResult:
        if not hasattr(psutil, "sensors_battery") or psutil.sensors_battery() is None:
            return AgentResult(success=True, message="This device does not appear to have a battery.")
            
        batt = psutil.sensors_battery()
        status = "plugged in and charging" if batt.power_plugged else "discharging"
        msg = f"Battery is at {int(batt.percent)}% and is currently {status}."
        
        if not batt.power_plugged and batt.percent < 15:
            msg += " You should connect your charger soon."
            
        return AgentResult(success=True, message=msg)
        
    def _check_network(self) -> AgentResult:
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            msg = "You are currently online with an active internet connection."
        except OSError:
            msg = "You appear to be offline. Internet connection is not available."
            
        return AgentResult(success=True, message=msg)
        
    def _check_temperature(self) -> AgentResult:
        if not hasattr(psutil, "sensors_temperatures"):
            return AgentResult(success=False, message="Temperature sensors are not supported on this operating system.")
            
        temps = psutil.sensors_temperatures()
        if not temps:
            return AgentResult(success=False, message="Could not read temperature sensors on this machine.")
            
        # Try to find CPU or core temps
        core_temps = []
        for name, entries in temps.items():
            if name.lower() in ("coretemp", "cpu_thermal", "k10temp"):
                for entry in entries:
                    core_temps.append(entry.current)
                    
        if core_temps:
            avg_temp = sum(core_temps) / len(core_temps)
            msg = f"Average CPU temperature is {avg_temp:.1f}°C."
            if avg_temp > 85:
                msg += " This is running quite hot."
            return AgentResult(success=True, message=msg)
            
        return AgentResult(success=False, message="Could not identify CPU temperature sensors.")

    def _format_bytes(self, size_bytes: int) -> str:
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

    def get_capabilities(self) -> list[str]:
        return ["SYSTEM_HEALTH", "CHECK_CPU", "CHECK_RAM", "CHECK_STORAGE", 
                "CHECK_BATTERY", "CHECK_NETWORK", "CHECK_TEMPERATURE"]
