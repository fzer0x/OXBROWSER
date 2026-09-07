"""
EngineSecurityAdvisor: Centralized security profile evaluation for browser engines.

Camoufox  → Primary engine, Firefox-based, C++ native sandbox.  No --no-sandbox. ✅
Nodriver  → Optional Chromium, --no-sandbox required. ⚠️ HIGH risk.
Playwright → Optional Chromium, --no-sandbox in args. 🔷 MEDIUM risk.
Selenium Driverless → Optional Chromium, --no-sandbox. ⚠️ HIGH risk, legacy.
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger("EngineSecurityAdvisor")


class EngineSecurityProfile:
    """Security metadata for a browser engine."""

    def __init__(
        self,
        engine_id: str,
        display_name: str,
        sandbox_type: str,
        risk_level: str,          # "LOW", "MEDIUM", "HIGH"
        warnings: List[str],
        recommendation: str,
        is_primary: bool = False,
    ):
        self.engine_id = engine_id
        self.display_name = display_name
        self.sandbox_type = sandbox_type
        self.risk_level = risk_level
        self.warnings = warnings
        self.recommendation = recommendation
        self.is_primary = is_primary

    @property
    def risk_color(self) -> str:
        """Returns a hex color for UI risk badges."""
        return {"LOW": "#34d399", "MEDIUM": "#fbbf24", "HIGH": "#f87171"}.get(
            self.risk_level, "#94a3b8"
        )

    @property
    def risk_icon(self) -> str:
        return {"LOW": "✅", "MEDIUM": "🔷", "HIGH": "⚠️"}.get(self.risk_level, "ℹ️")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "display_name": self.display_name,
            "sandbox_type": self.sandbox_type,
            "risk_level": self.risk_level,
            "warnings": self.warnings,
            "recommendation": self.recommendation,
            "is_primary": self.is_primary,
        }


# ── Security Profiles ─────────────────────────────────────────────────────────

_PROFILES: Dict[str, EngineSecurityProfile] = {

    "camoufox": EngineSecurityProfile(
        engine_id="camoufox",
        display_name="Camoufox (Firefox Anti-Detect)",
        sandbox_type="Native C++ Firefox Sandbox",
        risk_level="LOW",
        warnings=[],
        recommendation="✅ Empfohlen – Primärer Engine für alle Profile",
        is_primary=True,
    ),

    "nodriver": EngineSecurityProfile(
        engine_id="nodriver",
        display_name="Nodriver (Chromium CDP)",
        sandbox_type="Keine (--no-sandbox, --disable-setuid-sandbox)",
        risk_level="HIGH",
        warnings=[
            "⚠️ Chromium OS-Sandbox vollständig deaktiviert (--no-sandbox)",
            "⚠️ Erhöhtes RCE-Risiko durch malicious Web Content",
            "⚠️ Nicht empfohlen für sensible Accounts oder Produktionsumgebungen",
        ],
        recommendation="🔶 Nur für Testing / nicht-sensitive Profile verwenden. "
                       "Für Anti-Detect: Camoufox bevorzugen.",
    ),

    "selenium_driverless": EngineSecurityProfile(
        engine_id="selenium_driverless",
        display_name="Selenium Driverless (Chromium)",
        sandbox_type="Keine (--no-sandbox, --disable-setuid-sandbox)",
        risk_level="HIGH",
        warnings=[
            "⚠️ Chromium OS-Sandbox vollständig deaktiviert (--no-sandbox)",
            "⚠️ Legacy-Engine – Selenium-Automation-Artefakte via CDP detektierbar",
            "⚠️ Nicht empfohlen für Anti-Detect-Szenarien",
        ],
        recommendation="🔶 Legacy-Engine. Für Anti-Detect: Camoufox oder Nodriver verwenden.",
    ),

    "playwright": EngineSecurityProfile(
        engine_id="playwright",
        display_name="Playwright (Chromium)",
        sandbox_type="Teilweise (--no-sandbox via chromium_args)",
        risk_level="MEDIUM",
        warnings=[
            "🔷 --no-sandbox in chromium_args aktiviert",
            "ℹ️ Playwright hat starke Netzwerk-Interception, aber keinen Browser-Stealth",
            "ℹ️ Automatisierungs-Signaturen sind per CDP detektierbar",
        ],
        recommendation="🔷 Akzeptabel für API-Automation. Nicht für Anti-Detect empfohlen.",
    ),
}


class EngineSecurityAdvisor:
    """
    Evaluates and reports the security posture of a browser engine configuration.
    Provides UI-ready security badges and log-level warnings.
    """

    @classmethod
    def get_profile(cls, engine_id: str) -> EngineSecurityProfile:
        """Returns the security profile for the given engine ID."""
        normalized = engine_id.lower().strip().replace("-", "_")
        return _PROFILES.get(normalized) or _PROFILES["nodriver"]  # Default to high-risk profile

    @classmethod
    def emit_startup_warnings(cls, engine_id: str, profile_id: str = ""):
        """
        Emits appropriate log-level warnings when a non-primary engine is launched.
        Camoufox (primary) emits nothing. Optional engines emit WARNING logs.
        """
        profile = cls.get_profile(engine_id)
        if profile.is_primary:
            # Primary engine: no warnings needed
            return

        prefix = f"[SECURITY] Engine '{profile.display_name}'"
        if profile_id:
            prefix += f" for profile '{profile_id}'"

        logger.warning(
            f"{prefix} – Risk Level: {profile.risk_level} | "
            f"Sandbox: {profile.sandbox_type}"
        )
        for warning in profile.warnings:
            logger.warning(f"{prefix}: {warning}")
        logger.warning(f"{prefix}: {profile.recommendation}")

    @classmethod
    def get_badge_text(cls, engine_id: str) -> str:
        """Returns a short badge text for Settings UI display."""
        profile = cls.get_profile(engine_id)
        if profile.is_primary:
            return f"✅ Primär – {profile.sandbox_type}"
        return f"{profile.risk_icon} {profile.risk_level}: {profile.sandbox_type}"

    @classmethod
    def get_tooltip(cls, engine_id: str) -> str:
        """Returns a full tooltip string for Settings UI hover text."""
        profile = cls.get_profile(engine_id)
        lines = [profile.recommendation, ""]
        if profile.warnings:
            lines.extend(profile.warnings)
        return "\n".join(lines)

    @classmethod
    def all_profiles(cls) -> Dict[str, EngineSecurityProfile]:
        """Returns all registered engine security profiles."""
        return dict(_PROFILES)
