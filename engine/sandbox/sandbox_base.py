import abc
import logging
from typing import Dict, Tuple, Optional, Any

logger = logging.getLogger("SandboxEngine")

class BaseSandbox(abc.ABC):
    """Abstract Base Class for Browser Profile Sandboxes."""

    def __init__(self, profile_id: str, profile_data: Dict[str, Any], user_data_dir: str, debug_port: int):
        self.profile_id = profile_id
        self.profile_data = profile_data
        self.user_data_dir = user_data_dir
        self.debug_port = debug_port
        self.container_or_vm_id: Optional[str] = None
        self.is_active = False

    @abc.abstractmethod
    async def start(self) -> Tuple[bool, str, int]:
        """Starts the sandbox instance and returns (success, message/info, debug_port)."""
        pass

    @abc.abstractmethod
    async def stop(self) -> bool:
        """Stops and cleans up the sandbox instance."""
        pass

    @abc.abstractmethod
    async def is_running(self) -> bool:
        """Checks if the sandbox process/container is currently active."""
        pass

    @abc.abstractmethod
    async def get_logs(self) -> str:
        """Retrieves stdout/stderr logs from the sandbox environment."""
        pass
