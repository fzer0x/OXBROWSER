"""
port_utils.py – Thread-safe TCP port allocation for SoxBot engine.

Shared between engine.browser and engine.proxy_tunnel to avoid circular imports.
Uses a process-wide reservation set so concurrent profile launches don't
race to the same port.
"""
import socket
import threading
from typing import Optional

_RESERVED_PORTS: set = set()
_PORT_LOCK = threading.Lock()


def find_free_port() -> int:
    """
    Finds an unused, bindable TCP port on localhost and registers it in the
    process-wide reservation set to prevent concurrent allocation collisions.
    """
    global _RESERVED_PORTS
    with _PORT_LOCK:
        for _ in range(100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind(("127.0.0.1", 0))
                    port = s.getsockname()[1]
                    if port not in _RESERVED_PORTS and port >= 1024:
                        _RESERVED_PORTS.add(port)
                        return port
            except Exception:
                pass

        import random
        for _ in range(50):
            port = random.randint(32000, 64000)
            if port not in _RESERVED_PORTS:
                _RESERVED_PORTS.add(port)
                return port

        port = random.randint(32000, 64000)
        _RESERVED_PORTS.add(port)
        return port


def release_port(port: Optional[int]) -> None:
    """Removes a port from the reservation set once it is no longer in use."""
    if not port or not isinstance(port, int):
        return
    with _PORT_LOCK:
        _RESERVED_PORTS.discard(port)
