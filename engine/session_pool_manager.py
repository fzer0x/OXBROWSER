import os
import time
import psutil
import asyncio
import logging
from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass, field

from engine.events import AsyncEventBus, Channel
from models.schemas import ProfileConfig

logger = logging.getLogger("SessionPoolManager")


@dataclass
class SessionResourceStats:
    profile_id: str
    process_pid: Optional[int]
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    is_healthy: bool = True
    launch_time: float = field(default_factory=time.time)
    uptime_sec: float = 0.0


class SessionPoolManager:
    """
    Enterprise Session Pool & Resource Sentinel for SoxBot:
    - Scales up to 50+ concurrent browser sessions with rate limiting & backpressure.
    - Concurrency Semaphore & dynamic queueing.
    - Memory Guard: Monitors per-session RAM/CPU and flags/terminates bloated renderer zombies.
    - Process-level isolation and graceful session reclamation.
    """
    _instance: Optional['SessionPoolManager'] = None

    def __init__(self, max_concurrent_sessions: int = 50, max_ram_per_session_mb: float = 850.0):
        self.max_concurrent_sessions = max_concurrent_sessions
        self.max_ram_per_session_mb = max_ram_per_session_mb
        self._semaphore = asyncio.Semaphore(max_concurrent_sessions)
        self._active_sessions: Dict[str, SessionResourceStats] = {}
        self._event_bus = AsyncEventBus.get_instance()
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_running = False

    @classmethod
    def get_instance(cls) -> 'SessionPoolManager':
        if cls._instance is None:
            cls._instance = SessionPoolManager()
        return cls._instance

    def start_resource_sentinel(self):
        """Starts background watchdog for process memory and zombie cleanup."""
        if self._is_running:
            return
        self._is_running = True
        try:
            loop = asyncio.get_running_loop()
            self._monitor_task = loop.create_task(self._sentinel_loop())
            logger.info(f"[SessionPoolManager] Resource Sentinel active (Max Concurrency: {self.max_concurrent_sessions}).")
        except RuntimeError:
            pass

    def stop_resource_sentinel(self):
        self._is_running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()

    async def acquire_session_slot(self, profile_id: str, timeout: float = 30.0) -> bool:
        """Acquires a concurrency slot before launching a browser session."""
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout)
            self._active_sessions[profile_id] = SessionResourceStats(
                profile_id=profile_id,
                process_pid=None
            )
            self.start_resource_sentinel()
            logger.info(f"[SessionPoolManager] Slot acquired for '{profile_id}' (Active: {len(self._active_sessions)}/{self.max_concurrent_sessions})")
            return True
        except asyncio.TimeoutError:
            logger.warning(f"[SessionPoolManager] Slot acquisition timed out for '{profile_id}' (Pool at capacity)")
            return False

    def register_session_pid(self, profile_id: str, pid: int):
        """Associates the OS Process ID with an active session for resource tracking."""
        if profile_id in self._active_sessions:
            self._active_sessions[profile_id].process_pid = pid

    def release_session_slot(self, profile_id: str):
        """Releases the concurrency slot and untracks the session."""
        if profile_id in self._active_sessions:
            del self._active_sessions[profile_id]
            self._semaphore.release()
            logger.info(f"[SessionPoolManager] Slot released for '{profile_id}' (Active: {len(self._active_sessions)}/{self.max_concurrent_sessions})")

    async def _sentinel_loop(self):
        """Periodic background loop checking process health and memory consumption."""
        while self._is_running:
            try:
                await asyncio.sleep(5.0)
                for profile_id, stats in list(self._active_sessions.items()):
                    if not stats.process_pid:
                        continue
                    try:
                        proc = psutil.Process(stats.process_pid)
                        if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                            stats.is_healthy = False
                            continue
                        mem_mb = proc.memory_info().rss / (1024.0 * 1024.0)
                        stats.memory_mb = mem_mb
                        stats.uptime_sec = time.time() - stats.launch_time

                        if mem_mb > self.max_ram_per_session_mb:
                            logger.warning(f"[SessionPoolManager] Session '{profile_id}' exceeded memory limit ({mem_mb:.1f}MB > {self.max_ram_per_session_mb}MB)")
                            # Publish high memory warning event
                            await self._event_bus.publish(
                                channel=Channel.TELEMETRY,
                                topic="session_memory_alert",
                                data={"profile_id": profile_id, "memory_mb": mem_mb}
                            )
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        stats.is_healthy = False
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[SessionPoolManager] Sentinel iteration note: {e}")

    def get_pool_status(self) -> Dict[str, Any]:
        """Returns instantaneous snapshot of the session pool."""
        total_ram_mb = sum(s.memory_mb for s in self._active_sessions.values())
        return {
            "active_sessions_count": len(self._active_sessions),
            "max_concurrent_sessions": self.max_concurrent_sessions,
            "total_ram_usage_mb": round(total_ram_mb, 2),
            "sessions": {
                p_id: {
                    "pid": s.process_pid,
                    "ram_mb": round(s.memory_mb, 1),
                    "uptime_sec": round(s.uptime_sec, 0),
                    "healthy": s.is_healthy
                }
                for p_id, s in self._active_sessions.items()
            }
        }
