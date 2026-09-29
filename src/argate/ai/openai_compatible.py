import os

from argate.ai.base import ProviderError, post_json
from argate.config import AIConfig
from argate.models import AIResponse


class OpenAICompatibleProvider:
    def __init__(self, config: AIConfig):
        self.config = config

    def analyze(self, prompt: str) -> AIResponse:
        key = os.environ.get(self.config.api_key_env) if self.config.api_key_env else None
        if self.config.api_key_env and not key:
            raise ProviderError("Configured API key environment variable is missing")
        response = post_json(self.config.endpoint.rstrip("/") + "/chat/completions", {
            "model": self.config.model, "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }, self.config.timeout_seconds, key, self.config.max_payload_bytes)
        try:
            return AIResponse.model_validate_json(response["choices"][0]["message"]["content"])
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ProviderError("Provider returned an invalid structured advisory response") from exc
