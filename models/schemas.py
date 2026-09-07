import time
import uuid
import re
from enum import Enum
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class OSType(str, Enum):
    WINDOWS = "windows"
    MAC = "mac"
    LINUX = "linux"
    ANDROID = "android"
    IOS = "ios"


class BrowserEngineType(str, Enum):
    CAMOUFOX = "camoufox"
    CHROMIUM = "chromium"
    FIREFOX = "firefox"


class WebRTCMode(str, Enum):
    ALTERED = "altered"
    DISABLED = "disabled"
    REAL = "real"
    BLOCK_STUN = "block_stun"


class ProxyType(str, Enum):
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class StealthConfig(BaseModel):
    canvas_noise: bool = True
    audio_noise: bool = True
    webgl_vendor: str = "Google Inc. (NVIDIA)"
    webgl_renderer: str = "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"
    webrtc_mode: str = "altered"
    client_hints: bool = True
    fonts_mode: str = "auto"
    media_devices: bool = True
    battery_spoof: bool = True
    navigator_overrides: bool = True

    model_config = {"extra": "allow"}

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class LocationConfig(BaseModel):
    country: str = ""
    region: str = ""
    city: str = ""
    postal_code: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy: float = 100.0

    model_config = {"extra": "allow"}

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ProxyConfig(BaseModel):
    type: str = "socks5"
    host: str = ""
    port: int = 1080
    username: str = ""
    password: str = ""
    tls_preset: str = "auto"
    burst_protection: bool = True
    burst_stagger_ms: float = 20.0
    status: str = "Untested"
    latency_ms: float = 0.0
    last_tested: float = 0.0

    model_config = {"extra": "allow"}

    @field_validator("port", mode="before")
    @classmethod
    def validate_port(cls, v: Any) -> int:
        try:
            p = int(v)
            if not (1 <= p <= 65535):
                return 1080
            return p
        except (ValueError, TypeError):
            return 1080

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ProfileConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Profile"
    group: str = "Default"
    tags: List[str] = Field(default_factory=lambda: ["General"])
    notes: str = ""
    created_at: float = Field(default_factory=time.time)
    last_launch: float = 0.0
    status: str = "Stopped"
    engine: str = "camoufox"
    start_url: str = ""

    # Hardware & Fingerprint Specifications
    os: str = "windows"
    os_version: str = "10.0.0"
    device_vendor: str = "Google"
    device_model: str = "PC"
    user_agent: str = ""
    screen_resolution: str = "1920x1080"
    window_mode: str = "tile_grid"
    window_width: int = 1280
    window_height: int = 720
    window_pos_x: int = 0
    window_pos_y: int = 0
    color_depth: int = 24
    max_touch_points: int = 0
    hardware_concurrency: int = 8
    device_memory: int = 8
    language: str = "en-US,en;q=0.9"
    timezone: str = "auto"
    do_not_track: str = "null"

    # Sub-Configs
    stealth: StealthConfig = Field(default_factory=StealthConfig)
    location: LocationConfig = Field(default_factory=LocationConfig)
    proxy: Optional[ProxyConfig] = None

    # Storage & Security Flags
    ephemeral_ram: bool = False
    encrypted: bool = False
    network_killswitch: bool = True
    debug_port: Optional[int] = None

    model_config = {"extra": "allow"}

    @field_validator("screen_resolution")
    @classmethod
    def validate_resolution(cls, v: str) -> str:
        if re.match(r"^\d{3,5}x\d{3,5}$", str(v).strip()):
            return str(v).strip()
        return "1920x1080"

    @field_validator("hardware_concurrency", mode="before")
    @classmethod
    def validate_cores(cls, v: Any) -> int:
        try:
            val = int(v)
            return max(1, min(val, 64))
        except (ValueError, TypeError):
            return 8

    @field_validator("device_memory", mode="before")
    @classmethod
    def validate_memory(cls, v: Any) -> int:
        try:
            val = int(v)
            return max(1, min(val, 128))
        except (ValueError, TypeError):
            return 8

    # Dictionary Backward Compatibility Layer
    def __getitem__(self, item: str) -> Any:
        try:
            val = getattr(self, item)
            if isinstance(val, (StealthConfig, LocationConfig, ProxyConfig)):
                return val.to_dict()
            return val
        except AttributeError:
            if hasattr(self, "__pydantic_extra__") and self.__pydantic_extra__ and item in self.__pydantic_extra__:
                return self.__pydantic_extra__[item]
            raise KeyError(item)

    def __setitem__(self, key: str, value: Any):
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            if self.__pydantic_extra__ is None:
                self.__pydantic_extra__ = {}
            self.__pydantic_extra__[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except (KeyError, AttributeError):
            return default

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the model to a standard clean dictionary."""
        d = self.model_dump()
        if self.__pydantic_extra__:
            d.update(self.__pydantic_extra__)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProfileConfig':
        """Constructs and validates a ProfileConfig from a raw dictionary."""
        return cls.model_validate(data)


class WarmupCampaignConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Default Warmup Campaign"
    description: str = "Automated warmup and cookie seeding"
    category: str = "E-Commerce & Search"
    persona: str = "tech_shopper"
    max_pages: int = 15
    dwell_time: float = 12.0
    urls: List[str] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)
    custom_keywords: List[str] = Field(default_factory=list)
    session_intent_topic: str = "General"
    created_at: float = Field(default_factory=time.time)

    model_config = {"extra": "allow"}

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
