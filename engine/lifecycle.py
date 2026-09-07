import os
import sys
import signal
import asyncio
import logging
import contextlib
import psutil
from typing import Set, Dict, Any, Optional, Callable, Coroutine, List, Tuple

logger = logging.getLogger("GlobalLifecycle")


class GlobalLifecycleManager:
    """
    Central Lifecycle & Resource Governor for SoxBot.
    - Manages AsyncExitStack for asynchronous servers, listeners, and tunnels.
    - Captures OS signals (SIGINT, SIGTERM, SIGHUP) for graceful cascading shutdown.
    - Tracks all spawned browser processes, sub-processes, and proxy tunnels.
    - Employs psutil process-tree killing to prevent orphaned Chromium/Camoufox instances and zombie sockets.
    """
    _instance: Optional['GlobalLifecycleManager'] = None

    def __init__(self):
        self.exit_stack = contextlib.AsyncExitStack()
        self._tracked_pids: Set[int] = set()
        self._async_cleanup_tasks: List[Callable[[], Coroutine[Any, Any, Any]]] = []
        self._sync_cleanup_tasks: List[Callable[[], Any]] = []
        self._is_shutting_down = False
        self._shutdown_event = asyncio.Event()
        self._signals_registered = False

    @classmethod
    def get_instance(cls) -> 'GlobalLifecycleManager':
        if cls._instance is None:
            cls._instance = GlobalLifecycleManager()
        return cls._instance

    def register_signal_handlers(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Registers signal handlers for graceful shutdown on Windows, Linux, and macOS."""
        if self._signals_registered:
            return

        if sys.platform != "win32":
            target_loop = loop or asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                try:
                    target_loop.add_signal_handler(
                        sig,
                        lambda s=sig: asyncio.create_task(self.request_shutdown(f"Received signal {s.name}"))
                    )
                except (NotImplementedError, RuntimeError) as e:
                    logger.debug(f"Signal {sig} could not be registered with event loop: {e}")
        else:
            # Windows signal handling fallback via standard signal module
            def _win_sig_handler(signum, frame):
                logger.info(f"[Lifecycle] Received Windows signal {signum}, requesting shutdown...")
                self._shutdown_event.set()
                try:
                    target_loop = loop or asyncio.get_event_loop()
                    if target_loop.is_running():
                        target_loop.call_soon_threadsafe(
                            lambda: asyncio.create_task(self.request_shutdown(f"Received signal {signum}"))
                        )
                except Exception:
                    pass

            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    signal.signal(sig, _win_sig_handler)
                except Exception:
                    pass

        self._signals_registered = True
        logger.debug("GlobalLifecycleManager signal handlers registered.")

    def track_pid(self, pid: int):
        """Registers a process ID to be forcefully cleaned up if still running during shutdown."""
        if pid and pid > 0 and pid != os.getpid():
            self._tracked_pids.add(pid)
            logger.debug(f"Tracking child process PID {pid}")

    def untrack_pid(self, pid: int):
        """Removes a process ID from tracked child processes."""
        self._tracked_pids.discard(pid)

    def register_async_cleanup(self, coro_func: Callable[[], Coroutine[Any, Any, Any]]):
        """Registers an asynchronous cleanup coroutine callback."""
        if coro_func not in self._async_cleanup_tasks:
            self._async_cleanup_tasks.append(coro_func)

    def register_sync_cleanup(self, func: Callable[[], Any]):
        """Registers a synchronous cleanup callback."""
        if func not in self._sync_cleanup_tasks:
            self._sync_cleanup_tasks.append(func)

    async def request_shutdown(self, reason: str = "Explicit shutdown requested"):
        """Triggers the full graceful teardown sequence."""
        if self._is_shutting_down:
            return

        self._is_shutting_down = True
        logger.info(f"[Lifecycle] Shutdown sequence initiated: {reason}")
        self._shutdown_event.set()

        # 1. Execute asynchronous registered cleanup tasks
        for async_task in self._async_cleanup_tasks:
            try:
                await asyncio.wait_for(async_task(), timeout=5.0)
            except Exception as e:
                logger.warning(f"[Lifecycle] Error executing async cleanup task: {e}")

        # 2. Unwind contextlib AsyncExitStack
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            logger.warning(f"[Lifecycle] Error closing AsyncExitStack: {e}")

        # 3. Terminate tracked subprocesses via psutil tree kill
        self._kill_tracked_processes()

        # 4. Execute synchronous cleanup tasks
        for sync_task in self._sync_cleanup_tasks:
            try:
                sync_task()
            except Exception as e:
                logger.warning(f"[Lifecycle] Error executing sync cleanup task: {e}")

        logger.info("[Lifecycle] Graceful shutdown sequence completed successfully.")

    def _kill_tracked_processes(self, timeout_sec: float = 2.5):
        """Ensures all child processes and their descendant subprocesses are cleanly killed."""
        current_pid = os.getpid()
        all_pids = set(self._tracked_pids)

        # Also inspect direct children of current process
        try:
            parent = psutil.Process(current_pid)
            for child in parent.children(recursive=True):
                all_pids.add(child.pid)
        except Exception:
            pass

        surviving_procs: List[psutil.Process] = []
        for pid in all_pids:
            if pid == current_pid:
                continue
            try:
                proc = psutil.Process(pid)
                if proc.is_running():
                    proc.terminate()
                    surviving_procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if surviving_procs:
            # Wait gracefully
            gone, alive = psutil.wait_procs(surviving_procs, timeout=timeout_sec)
            for proc in alive:
                try:
                    logger.warning(f"[Lifecycle] Force killing stubborn process PID {proc.pid}")
                    proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        self._tracked_pids.clear()

    @property
    def is_shutting_down(self) -> bool:
        return self._is_shutting_down

    @property
    def shutdown_event(self) -> asyncio.Event:
        return self._shutdown_event

    @staticmethod
    def check_system_headroom(min_free_ram_mb: int = 600) -> Tuple[bool, str, Dict[str, float]]:
        """
        Checks physical memory and CPU headroom to ensure host stability before spawning browser instances.
        Prevents Linux Out-Of-Memory (OOM) killer crashes during high-concurrency multi-profile runs.
        Returns: (has_headroom: bool, reason: str, metrics: Dict[str, float])
        """
        try:
            mem = psutil.virtual_memory()
            available_mb = mem.available / (1024 * 1024)
            total_mb = mem.total / (1024 * 1024)
            cpu_pct = psutil.cpu_percent(interval=None)

            metrics = {
                "available_ram_mb": round(available_mb, 1),
                "total_ram_mb": round(total_mb, 1),
                "ram_percent": mem.percent,
                "cpu_percent": cpu_pct
            }

            if available_mb < min_free_ram_mb:
                msg = (
                    f"Insufficient RAM: {available_mb:.0f} MB available, but minimum {min_free_ram_mb} MB required. "
                    f"Host RAM usage is at {mem.percent}%."
                )
                logger.warning(f"[ResourceGovernor] Headroom check warning: {msg}")
                return False, msg, metrics

            return True, "Host has sufficient memory headroom.", metrics
        except Exception as e:
            logger.debug(f"[ResourceGovernor] System headroom evaluation notice: {e}")
            return True, "Headroom check bypassed on exception.", {}
