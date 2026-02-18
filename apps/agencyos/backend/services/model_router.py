"""
AgencyOS Model Router

Routes AI requests to the appropriate model based on tier.
Chief = premium, Dept Heads = mid, Workers = local (Ollama), Tools = deterministic.

Uses OpenWebUI's internal generate_chat_completion when available,
falls back to direct API calls otherwise.
"""

import json
import logging
import yaml
import httpx
from pathlib import Path
from typing import Optional, AsyncGenerator

logger = logging.getLogger("agencyos.model_router")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class ModelRouter:
    """
    Selects the right AI model based on role/tier.
    Handles fallback chains when a tier is unavailable.
    """

    def __init__(self):
        self.tiers = self._load_config()
        self._http_client = None
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

    @property
    def http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=120.0)
        return self._http_client

    def get_model_config(self, tier: str) -> Optional[dict]:
        """Get the model configuration for a given tier."""
        tier_config = self.tiers.get(tier)
        if not tier_config:
            logger.warning(f"Unknown tier: {tier}")
            return None

        providers = tier_config.get("providers", [])
        if not providers:
            if tier == "deterministic":
                return {"provider": "deterministic", "model": None}
            return None

        primary = sorted(providers, key=lambda p: p.get("priority", 99))[0]
        return {
            "provider": primary["provider"],
            "model": primary["model"],
            "max_tokens": tier_config.get("max_tokens", 4096),
            "temperature": tier_config.get("temperature", 0.5),
        }

    def get_fallback_config(self, tier: str) -> Optional[dict]:
        """Get the fallback model if primary tier is unavailable."""
        tier_config = self.tiers.get(tier, {})
        fallback_tier = tier_config.get("fallback")
        if fallback_tier:
            return self.get_model_config(fallback_tier)
        return None

    async def generate(
        self,
        tier: str,
        messages: list[dict],
        system_prompt: str = "",
        stream: bool = False,
        **kwargs,
    ) -> dict | AsyncGenerator[str, None]:
        """
        Generate a chat completion using the appropriate model for the tier.
        
        Args:
            tier: Model tier (premium, mid, local, deterministic)
            messages: List of message dicts [{"role": "user", "content": "..."}]
            system_prompt: Department/role-specific system prompt
            stream: Whether to stream the response
            
        Returns:
            dict with 'content' key containing the response text,
            or an async generator of content chunks if streaming.
        """
        config = self.get_model_config(tier)
        if not config:
            return {"content": "Error: No model configured for this tier.", "error": True}

        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        try:
            result = await self._call_model(config, messages, stream, **kwargs)
            return result
        except Exception as e:
            logger.error(f"Model call failed for tier {tier}: {e}")
            # Try fallback
            fallback = self.get_fallback_config(tier)
            if fallback:
                logger.info(f"Falling back from {tier} to fallback tier")
                try:
                    return await self._call_model(fallback, messages, stream, **kwargs)
                except Exception as fe:
                    logger.error(f"Fallback also failed: {fe}")

            return {"content": f"Error generating response: {e}", "error": True}

    async def _call_model(
        self,
        config: dict,
        messages: list[dict],
        stream: bool = False,
        **kwargs,
    ) -> dict:
        """
        Make the actual API call to a model provider.
        
        For now, routes through OpenWebUI's internal API to leverage
        its existing provider connections and API key management.
        """
        provider = config["provider"]
        model = config["model"]
        max_tokens = config.get("max_tokens", 4096)
        temperature = config.get("temperature", 0.5)

        # Route through OpenWebUI's internal chat completions endpoint
        # This leverages OpenWebUI's existing API key management and provider routing
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,  # Non-streaming for orchestrator use
        }
        payload.update(kwargs)

        try:
            # Try using OpenWebUI's internal function directly
            return await self._call_via_openwebui(payload)
        except Exception as e:
            logger.warning(f"Internal call failed: {e}, trying direct API")
            return await self._call_direct(provider, model, messages, max_tokens, temperature)

    async def _call_via_openwebui(self, payload: dict) -> dict:
        """
        Call through OpenWebUI's internal API endpoint.
        This is the preferred method as it uses OpenWebUI's configured
        API keys and provider connections.
        """
        # Make an internal HTTP call to OpenWebUI's chat completion endpoint
        response = await self.http_client.post(
            "http://localhost:8080/api/chat/completions",
            json=payload,
            headers={"Authorization": "Bearer 0p3n-w3bu!"},  # Default internal token
        )
        response.raise_for_status()
        data = response.json()

        # Extract content from OpenAI-format response
        if "choices" in data and data["choices"]:
            content = data["choices"][0].get("message", {}).get("content", "")
            return {
                "content": content,
                "model": data.get("model", payload["model"]),
                "usage": data.get("usage", {}),
            }
        return {"content": str(data), "error": True}

    async def _call_direct(
        self,
        provider: str,
        model: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> dict:
        """
        Direct API call to provider (fallback if OpenWebUI internal call fails).
        Reads API keys from OpenWebUI's environment.
        """
        import os

        if provider == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            response = await self.http_client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("content", [{}])[0].get("text", "")
            return {"content": content, "model": model, "usage": data.get("usage", {})}

        elif provider == "google":
            api_key = os.environ.get("GOOGLE_API_KEY", "")
            # Gemini API format
            gemini_messages = []
            system_text = ""
            for msg in messages:
                if msg["role"] == "system":
                    system_text += msg["content"] + "\n"
                else:
                    gemini_messages.append({
                        "role": "user" if msg["role"] == "user" else "model",
                        "parts": [{"text": msg["content"]}],
                    })

            payload = {"contents": gemini_messages}
            if system_text:
                payload["systemInstruction"] = {"parts": [{"text": system_text.strip()}]}
            payload["generationConfig"] = {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            }

            response = await self.http_client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            return {"content": content, "model": model}

        elif provider == "ollama":
            ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            response = await self.http_client.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")
            return {"content": content, "model": model}

        else:
            return {"content": f"Unknown provider: {provider}", "error": True}

    async def close(self):
        """Clean up HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
