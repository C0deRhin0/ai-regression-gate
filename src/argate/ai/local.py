from argate.ai.base import ProviderError, post_json
from argate.config import AIConfig
from argate.models import AIResponse


class OllamaProvider:
    def __init__(self, config: AIConfig):
        self.config = config

    def analyze(self, prompt: str) -> AIResponse:
        response = post_json(self.config.endpoint.rstrip("/") + "/api/generate", {
            "model": self.config.model, "prompt": prompt, "stream": False,
            "format": AIResponse.model_json_schema(), "options": {"temperature": 0},
        }, self.config.timeout_seconds, None, self.config.max_payload_bytes)
        try:
            return AIResponse.model_validate_json(response["response"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ProviderError("Provider returned an invalid structured advisory response") from exc
