import os
import json
import logging
import time
from typing import Dict, List, Any, Optional
import config
from engine.warmup.orchestrator import WarmupConfig

logger = logging.getLogger("WarmupCampaignManager")

DEFAULT_CAMPAIGNS: Dict[str, Dict[str, Any]] = {
    "ecommerce_trust_builder": {
        "name": "E-Commerce Trust Builder",
        "description": "High-reputation shopping & e-commerce browsing trajectory to establish legitimate consumer cookies and trust scores.",
        "category": "ecommerce",
        "persona": "shopper",
        "mode": "standard",
        "ai_model": "qwen2.5:1.5b",
        "motor_model": "min_jerk",
        "typing_model": "bigram",
        "content_aware_dwell": True,
        "auto_evade_traps": True,
        "enable_honeypot_shield": True,
        "enable_captcha_solver": True,
        "captcha_strategy": "audio_first",
        "max_pages": 6,
        "dwell_time": 9.0,
        "click_depth": 2,
        "concurrency": 1,
        "enable_search": True,
        "dismiss_banners": True,
        "urls": [
            "https://www.amazon.com",
            "https://www.ebay.com",
            "https://www.walmart.com",
            "https://www.target.com",
            "https://www.bestbuy.com"
        ],
        "search_queries": [
            "best noise cancelling headphones 2026",
            "ergonomic mechanical keyboard review",
            "summer sale deals electronics",
            "top rated smart home gadgets"
        ],
        "custom_keywords": [
            "shopping", "deals", "reviews", "ratings", "cart", "products", "discounts"
        ],
        "custom_websites": [],
        "session_intent_topic": "Online Consumer Electronics & Tech Gadget Buying",
        "headless": False
    },
    "crypto_web3_explorer": {
        "name": "Crypto & Web3 Explorer",
        "description": "Organic researcher persona visiting cryptocurrency, DeFi tracking, blockchain analytics, and tech forums.",
        "category": "tech",
        "persona": "crypto_trader",
        "mode": "standard",
        "ai_model": "qwen2.5:1.5b",
        "motor_model": "min_jerk",
        "typing_model": "bigram",
        "content_aware_dwell": True,
        "auto_evade_traps": True,
        "enable_honeypot_shield": True,
        "enable_captcha_solver": True,
        "captcha_strategy": "audio_first",
        "max_pages": 5,
        "dwell_time": 8.0,
        "click_depth": 1,
        "concurrency": 1,
        "enable_search": True,
        "dismiss_banners": True,
        "urls": [
            "https://coinmarketcap.com",
            "https://coingecko.com",
            "https://defillama.com",
            "https://etherscan.io",
            "https://cointelegraph.com"
        ],
        "search_queries": [
            "ethereum layer 2 rollup transaction fees",
            "defi liquidity staking derivatives yield",
            "bitcoin market trend analysis 2026",
            "crypto news and regulatory updates"
        ],
        "custom_keywords": [
            "crypto", "bitcoin", "ethereum", "blockchain", "market cap", "defi", "trading"
        ],
        "custom_websites": [],
        "session_intent_topic": "Cryptocurrency Analytics and Web3 Research",
        "headless": False
    },
    "google_search_news_trajectory": {
        "name": "Google Search & News Trajectory",
        "description": "Authentic organic query exploration across search engines, news publications, and encyclopedia knowledge portals.",
        "category": "news",
        "persona": "news_researcher",
        "mode": "standard",
        "ai_model": "qwen2.5:1.5b",
        "motor_model": "min_jerk",
        "typing_model": "bigram",
        "content_aware_dwell": True,
        "auto_evade_traps": True,
        "enable_honeypot_shield": True,
        "enable_captcha_solver": True,
        "captcha_strategy": "audio_first",
        "max_pages": 7,
        "dwell_time": 7.5,
        "click_depth": 2,
        "concurrency": 1,
        "enable_search": True,
        "dismiss_banners": True,
        "urls": [
            "https://news.google.com",
            "https://www.reuters.com",
            "https://en.wikipedia.org/wiki/Special:Random",
            "https://www.bbc.com",
            "https://apnews.com"
        ],
        "search_queries": [
            "global economic outlook tech market",
            "renewable energy breakthrough battery storage",
            "science advances astronomy space exploration",
            "artificial intelligence developments 2026"
        ],
        "custom_keywords": [
            "news", "world", "technology", "science", "global", "economy", "updates"
        ],
        "custom_websites": [],
        "session_intent_topic": "Current Global Affairs and Technology News",
        "headless": False
    },
    "social_media_high_dwell": {
        "name": "Social Media & Media Dwell",
        "description": "Interactive engagement on social discovery sites, forums, and developer discussions with extended dwell times.",
        "category": "social",
        "persona": "social_browser",
        "mode": "standard",
        "ai_model": "qwen2.5:1.5b",
        "motor_model": "min_jerk",
        "typing_model": "bigram",
        "content_aware_dwell": True,
        "auto_evade_traps": True,
        "enable_honeypot_shield": True,
        "enable_captcha_solver": True,
        "captcha_strategy": "audio_first",
        "max_pages": 5,
        "dwell_time": 10.0,
        "click_depth": 2,
        "concurrency": 1,
        "enable_search": True,
        "dismiss_banners": True,
        "urls": [
            "https://www.reddit.com/r/technology/",
            "https://news.ycombinator.com",
            "https://github.com/trending",
            "https://medium.com"
        ],
        "search_queries": [
            "popular open source ai projects github",
            "hacker news top tech discussions today",
            "reddit best productivity software recommendations"
        ],
        "custom_keywords": [
            "community", "discussion", "trending", "comments", "articles", "software"
        ],
        "custom_websites": [],
        "session_intent_topic": "Tech Community Discussions and Trending Repositories",
        "headless": False
    }
}


class WarmupCampaignManager:
    """Manages persistent Warmup Campaigns and presets stored as JSON in storage/warmup_campaigns."""

    _instance: Optional['WarmupCampaignManager'] = None

    def __init__(self, campaigns_dir: Optional[str] = None):
        if campaigns_dir is None:
            self.campaigns_dir = os.path.join(config.BASE_DIR, "storage", "warmup_campaigns")
        else:
            self.campaigns_dir = campaigns_dir
        
        os.makedirs(self.campaigns_dir, exist_ok=True)
        self._ensure_default_campaigns()

    @classmethod
    def get_instance(cls) -> 'WarmupCampaignManager':
        if cls._instance is None:
            cls._instance = WarmupCampaignManager()
        return cls._instance

    def _ensure_default_campaigns(self):
        """Initializes default campaign templates on first launch."""
        for key, campaign in DEFAULT_CAMPAIGNS.items():
            file_path = os.path.join(self.campaigns_dir, f"{key}.json")
            if not os.path.exists(file_path):
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(campaign, f, indent=4)
                except Exception as e:
                    logger.warning(f"Could not write default campaign '{key}': {e}")

    def list_campaigns(self) -> List[Dict[str, Any]]:
        """Returns a list of all stored campaigns with metadata."""
        campaigns = []
        if not os.path.exists(self.campaigns_dir):
            return campaigns

        for fname in sorted(os.listdir(self.campaigns_dir)):
            if fname.endswith(".json"):
                fpath = os.path.join(self.campaigns_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["id"] = os.path.splitext(fname)[0]
                    campaigns.append(data)
                except Exception as e:
                    logger.error(f"Error loading campaign file '{fname}': {e}")
        return campaigns

    def get_campaign(self, campaign_id_or_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a campaign by ID or case-insensitive name."""
        clean_id = campaign_id_or_name.lower().strip().replace(" ", "_").replace("-", "_")
        fpath = os.path.join(self.campaigns_dir, f"{clean_id}.json")
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["id"] = clean_id
                return data
            except Exception as e:
                logger.error(f"Error loading campaign '{clean_id}': {e}")

        # Search by display name
        for c in self.list_campaigns():
            if c.get("name", "").lower() == campaign_id_or_name.lower() or c.get("id") == clean_id:
                return c
        return None

    def save_campaign(self, name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves or updates a warmup campaign JSON."""
        clean_id = name.lower().strip().replace(" ", "_").replace("-", "_")
        if not clean_id:
            clean_id = f"campaign_{int(time.time())}"

        data["id"] = clean_id
        if "name" not in data or not data["name"]:
            data["name"] = name.replace("_", " ").title()

        data["updated_at"] = time.time()
        file_path = os.path.join(self.campaigns_dir, f"{clean_id}.json")

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        logger.info(f"[WarmupCampaignManager] Saved campaign '{clean_id}' to {file_path}")
        return data

    def delete_campaign(self, campaign_id: str) -> bool:
        """Deletes a campaign JSON file."""
        clean_id = campaign_id.lower().strip().replace(" ", "_").replace("-", "_")
        file_path = os.path.join(self.campaigns_dir, f"{clean_id}.json")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"[WarmupCampaignManager] Deleted campaign '{clean_id}'")
                return True
            except Exception as e:
                logger.error(f"Failed to delete campaign '{clean_id}': {e}")
        return False

    @staticmethod
    def to_warmup_config(data: Dict[str, Any]) -> WarmupConfig:
        """Converts a campaign dictionary into a WarmupConfig dataclass."""
        cfg = WarmupConfig()
        cfg.category = data.get("category", "general")
        cfg.persona = data.get("persona", "general")
        cfg.mode = data.get("mode", "standard")
        cfg.ai_model = data.get("ai_model", "qwen2.5:1.5b")
        cfg.motor_model = data.get("motor_model", "min_jerk")
        cfg.typing_model = data.get("typing_model", "bigram")
        cfg.content_aware_dwell = data.get("content_aware_dwell", True)
        cfg.auto_evade_traps = data.get("auto_evade_traps", True)
        cfg.enable_honeypot_shield = data.get("enable_honeypot_shield", True)
        cfg.honeypot_model = data.get("honeypot_model", "auto")
        cfg.self_learning_memory = data.get("self_learning_memory", True)
        cfg.enable_verification_audit = data.get("enable_verification_audit", True)
        cfg.enable_captcha_solver = data.get("enable_captcha_solver", True)
        cfg.captcha_strategy = data.get("captcha_strategy", "audio_first")
        cfg.captcha_vision_model = data.get("captcha_vision_model", "llava:7b")
        cfg.max_pages = int(data.get("max_pages", 5))
        cfg.dwell_time = float(data.get("dwell_time", 8.0))
        cfg.click_depth = int(data.get("click_depth", 1))
        cfg.concurrency = int(data.get("concurrency", 1))
        cfg.enable_search = data.get("enable_search", True)
        cfg.dismiss_banners = data.get("dismiss_banners", True)
        cfg.urls = list(data.get("urls", []))
        cfg.search_queries = list(data.get("search_queries", []))
        cfg.custom_keywords = list(data.get("custom_keywords", []))
        cfg.custom_websites = list(data.get("custom_websites", []))
        cfg.session_intent_topic = data.get("session_intent_topic", "")
        cfg.headless = data.get("headless", False)
        return cfg
