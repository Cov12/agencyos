"""
AgencyOS Model Router

Routes AI requests to the appropriate model based on tier.
Chief = premium, Dept Heads = mid, Workers = local (Ollama), Tools = deterministic.
"""

import logging
import yaml
from pathlib import Path
from typing import Optional

logger = logging.getLogger("agencyos.model_router")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class ModelRouter:
    """
    Selects the right AI model based on role/tier.
    Handles fallback chains when a tier is unavailable.
    """

    def __init__(self):
        self.tiers = self._load_config()
        logger.info(f"ModelRouter initialized with {len(self.tiers)} tiers")

    def _load_config(self) -> dict:
        """Load model tier configuration."""
        config_path = CONFIG_DIR / "model_tiers.yaml"
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f)
                return config.get("tiers", {})
        logger.warning("No model_tiers.yaml found")
        return {}

    def get_model(self, tier: str) -> Optional[dict]:
        """
        Get the best available model for a given tier.
        Returns provider + model info, or falls back to next tier.
        """
        tier_config = self.tiers.get(tier)
        if not tier_config:
            logger.warning(f"Unknown tier: {tier}")
            return None

        providers = tier_config.get("providers", [])
        if not providers:
            if tier == "deterministic":
                return {"provider": "deterministic", "model": None}
            return None

        # Return highest priority provider
        # TODO: Add health checking — if provider is down, try next
        # TODO: Add rate limit awareness
        # TODO: Add cost tracking per org
        primary = sorted(providers, key=lambda p: p.get("priority", 99))[0]

        logger.debug(f"Tier {tier} → {primary['provider']}/{primary['model']}")
        return {
            "provider": primary["provider"],
            "model": primary["model"],
            "max_tokens": tier_config.get("max_tokens", 4096),
            "temperature": tier_config.get("temperature", 0.5),
        }

    def get_fallback(self, tier: str) -> Optional[dict]:
        """Get the fallback model if primary tier is unavailable."""
        tier_config = self.tiers.get(tier, {})
        fallback_tier = tier_config.get("fallback")
        if fallback_tier:
            return self.get_model(fallback_tier)
        return None
