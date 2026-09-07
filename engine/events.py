import sys
import time
import asyncio
import logging
import weakref
import inspect
from enum import Enum
from typing import Callable, Dict, List, Any, Optional, Union, Tuple, Set

logger = logging.getLogger("EventBus")


class Channel(str, Enum):
    """Standardized event channels for SoxBot."""
    SYSTEM = "system"
    BROWSER_CDP = "browser_cdp"
    TELEMETRY = "telemetry"
    UI = "ui"
    AI_SWARM = "ai_swarm"
    WARMUP = "warmup"
    PROXY = "proxy"
    CAPTCHA = "captcha"


class WeakCallbackWrapper:
    """
    Wraps a callable with weak reference semantics:
    - Automatically handles instance methods using WeakMethod
    - Handles standard functions and closures with weakref.ref
    - Cleans up silently when the subscriber target is garbage collected
    """
    def __init__(self, callback: Callable[..., Any], on_dead: Optional[Callable[['WeakCallbackWrapper'], None]] = None):
        self._is_method = inspect.ismethod(callback)
        self._on_dead = on_dead

        if self._is_method:
            self._ref = weakref.WeakMethod(callback, self._cleanup_callback)
        else:
            try:
                self._ref = weakref.ref(callback, self._cleanup_callback)
            except TypeError:
                # Built-in or un-weakreferenceable callable: hold strong ref
                self._ref = lambda: callback

    def _cleanup_callback(self, _):
        if self._on_dead:
            self._on_dead(self)

    def is_alive(self) -> bool:
        return self._ref() is not None

    def call(self, *args, **kwargs) -> Tuple[bool, Any]:
        """Invokes the callback if target is alive. Returns (was_alive, result)."""
        cb = self._ref()
        if cb is None:
            return False, None
        try:
            res = cb(*args, **kwargs)
            return True, res
        except Exception as e:
            logger.debug(f"[EventBus] Callback error: {e}")
            return True, None

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WeakCallbackWrapper):
            return self._ref() == other._ref()
        if callable(other):
            return self._ref() == other
        return False


class AsyncEventBus:
    """
    Enterprise-Grade Asynchronous Pub/Sub EventBus for SoxBot:
    - Weak reference subscriber registration to prevent UI & Agent memory leaks.
    - Decoupled asyncio.Queue worker loop with backpressure protection.
    - Multi-Channel routing (System, Browser CDP, Telemetry, UI, Swarm, Warmup).
    - Thread-safe emission bridge (emit_sync) for background threads.
    - Debounce and throttle capabilities for high-frequency telemetry.
    """
    _instance: Optional['AsyncEventBus'] = None

    def __init__(self, max_queue_size: int = 5000):
        self._subscribers: Dict[str, List[WeakCallbackWrapper]] = {}
        self._channel_subscribers: Dict[str, List[WeakCallbackWrapper]] = {}
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._worker_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._throttle_timestamps: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> 'AsyncEventBus':
        if cls._instance is None:
            cls._instance = AsyncEventBus()
        return cls._instance

    def _ensure_worker_running(self):
        try:
            running_loop = asyncio.get_running_loop()
            self._loop = running_loop
            if self._worker_task is None or self._worker_task.done():
                self._worker_task = running_loop.create_task(self._process_queue_worker())
        except RuntimeError:
            pass

    async def _process_queue_worker(self):
        """Dedicated consumer worker to dispatch events asynchronously without blocking callers."""
        while True:
            try:
                event_name, channel, kwargs = await self._queue.get()
                await self._dispatch_event(event_name, channel, kwargs)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[EventBus] Queue worker processing exception: {e}")

    async def _dispatch_event(self, event_name: str, channel: Optional[str], kwargs: Dict[str, Any]):
        """Dispatches an event to matching name and channel subscribers."""
        dead_wrappers: List[WeakCallbackWrapper] = []

        # 1. Named Event Subscribers
        target_list = list(self._subscribers.get(event_name, []))
        for wrapper in target_list:
            if not wrapper.is_alive():
                dead_wrappers.append(wrapper)
                continue
            alive, res = wrapper.call(**kwargs)
            if alive and inspect.isawaitable(res):
                try:
                    asyncio.ensure_future(res)
                except Exception as ex:
                    logger.debug(f"[EventBus] Async callback schedule error: {ex}")

        # 2. Channel Subscribers
        if channel:
            ch_key = channel.lower()
            ch_list = list(self._channel_subscribers.get(ch_key, []))
            for wrapper in ch_list:
                if not wrapper.is_alive():
                    if wrapper not in dead_wrappers:
                        dead_wrappers.append(wrapper)
                    continue
                alive, res = wrapper.call(event_name=event_name, **kwargs)
                if alive and inspect.isawaitable(res):
                    try:
                        asyncio.ensure_future(res)
                    except Exception as ex:
                        logger.debug(f"[EventBus] Async channel callback schedule error: {ex}")

        # Clean dead wrappers
        if dead_wrappers:
            if event_name in self._subscribers:
                self._subscribers[event_name] = [w for w in self._subscribers[event_name] if w.is_alive()]
            if channel and channel in self._channel_subscribers:
                self._channel_subscribers[channel] = [w for w in self._channel_subscribers[channel] if w.is_alive()]

    def subscribe(self, event_name: str, callback: Callable[..., Any]):
        """Subscribes a callback to a named event with weak reference memory protection."""
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []

        # Check if already subscribed
        wrapper = WeakCallbackWrapper(callback)
        if wrapper not in self._subscribers[event_name]:
            self._subscribers[event_name].append(wrapper)
        self._ensure_worker_running()

    def subscribe_channel(self, channel: Union[Channel, str], callback: Callable[..., Any]):
        """Subscribes a callback to all events occurring on a specific channel."""
        ch_key = (channel.value if isinstance(channel, Channel) else channel).lower()
        if ch_key not in self._channel_subscribers:
            self._channel_subscribers[ch_key] = []

        wrapper = WeakCallbackWrapper(callback)
        if wrapper not in self._channel_subscribers[ch_key]:
            self._channel_subscribers[ch_key].append(wrapper)
        self._ensure_worker_running()

    def unsubscribe(self, event_name: str, callback: Callable[..., Any]):
        """Removes a subscribed callback from a named event."""
        if event_name in self._subscribers:
            self._subscribers[event_name] = [w for w in self._subscribers[event_name] if w != callback]

    def unsubscribe_channel(self, channel: Union[Channel, str], callback: Callable[..., Any]):
        """Removes a subscribed callback from a channel."""
        ch_key = (channel.value if isinstance(channel, Channel) else channel).lower()
        if ch_key in self._channel_subscribers:
            self._channel_subscribers[ch_key] = [w for w in self._channel_subscribers[ch_key] if w != callback]

    async def emit(self, event_name: str, channel: Optional[Union[Channel, str]] = None, **kwargs):
        """Asynchronously enqueues an event for non-blocking dispatch."""
        self._ensure_worker_running()
        ch_str = channel.value if isinstance(channel, Channel) else channel
        try:
            self._queue.put_nowait((event_name, ch_str, kwargs))
        except asyncio.QueueFull:
            # Under extreme backpressure, discard oldest telemetry or dispatch directly
            logger.warning(f"[EventBus] Queue full! Dropping event {event_name}")

    def emit_sync(self, event_name: str, channel: Optional[Union[Channel, str]] = None, **kwargs):
        """Thread-safe synchronous bridge for background worker threads."""
        ch_str = channel.value if isinstance(channel, Channel) else channel
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.emit(event_name, ch_str, **kwargs))
            )
        else:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(self.emit(event_name, ch_str, **kwargs))
                    )
            except Exception:
                pass

    def emit_throttled(self, event_name: str, min_interval_sec: float = 0.1, channel: Optional[Union[Channel, str]] = None, **kwargs):
        """Emits an event only if min_interval_sec has elapsed since the last emission of this event name."""
        now = time.time()
        last_t = self._throttle_timestamps.get(event_name, 0.0)
        if (now - last_t) >= min_interval_sec:
            self._throttle_timestamps[event_name] = now
            self.emit_sync(event_name, channel=channel, **kwargs)

    async def shutdown(self):
        """Gracefully shuts down the background queue worker."""
        if self._worker_task and not self._worker_task.done():
            try:
                self._worker_task.cancel()
                await self._worker_task
            except (asyncio.CancelledError, RuntimeError):
                pass
        self._worker_task = None
        self._subscribers.clear()
        self._channel_subscribers.clear()
