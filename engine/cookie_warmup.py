"""
Cookie Warmup Module (Backward-Compatibility Facade)
Re-exports modularized components from engine.warmup.
"""

from engine.warmup import (
    BiomechanicalMotor,
    BiGramTypingEngine,
    get_lognormal_delay,
    SemanticBannerResolver,
    COMMON_COOKIE_SELECTORS,
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
    WarmupConfig,
    CookieWarmupRobot,
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
