"""SoxBot Warmup Subsystem - Modular Humanoid Automation & AI Trajectory Engines."""

from engine.warmup.stochastic_motion import (
    HumanoidTrajectoryGenerator,
    CurvedScrollGenerator,
    OrnsteinUhlenbeckTremor,
)
from engine.warmup.human_motion import (
    BiomechanicalMotor,
    BiGramTypingEngine,
    get_lognormal_delay,
)
from engine.warmup.consent_solver import (
    SemanticBannerResolver,
    COMMON_COOKIE_SELECTORS,
)
from engine.warmup.trajectory_planner import (
    WARMUP_CATEGORIES,
    DEFAULT_WARMUP_URLS,
    DEFAULT_SEARCH_QUERIES,
    PERSONA_PROFILES,
    WarmupKnowledgeStore,
    LoginAuthDetector,
    BrowserVerificationSuite,
    SitePortalEngine,
    PlatformInteractionAdapters,
    ContentAwareReader,
    PersonaTrajectoryEngine,
)
from engine.warmup.orchestrator import (
    WarmupConfig,
    CookieWarmupRobot,
)
from engine.honeypot_detector import (
    HoneypotDetector,
    HoneypotScanResult,
)

__all__ = [
    "BiomechanicalMotor",
    "BiGramTypingEngine",
    "get_lognormal_delay",
    "SemanticBannerResolver",
    "COMMON_COOKIE_SELECTORS",
    "WARMUP_CATEGORIES",
    "DEFAULT_WARMUP_URLS",
    "DEFAULT_SEARCH_QUERIES",
    "PERSONA_PROFILES",
    "WarmupKnowledgeStore",
    "LoginAuthDetector",
    "BrowserVerificationSuite",
    "SitePortalEngine",
    "PlatformInteractionAdapters",
    "ContentAwareReader",
    "PersonaTrajectoryEngine",
    "WarmupConfig",
    "CookieWarmupRobot",
    "HoneypotDetector",
    "HoneypotScanResult",
]
