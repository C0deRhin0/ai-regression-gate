import json
import urllib.error
import urllib.request
from typing import Protocol

from argate.models import AIResponse


class ProviderError(Exception):
    """Safe provider error; never includes request, key, or response body."""


class Provider(Protocol):
    def analyze(self, prompt: str) -> AIResponse: ...


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("Provider redirects are disabled")


def post_json(url: str, payload: dict, timeout: float, api_key: str | None = None,
              max_payload_bytes: int = 1_000_000) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    encoded = json.dumps(payload).encode()
    if len(encoded) > max_payload_bytes:
        raise ProviderError("Provider request exceeds configured payload limit")
    request = urllib.request.Request(url, data=encoded, headers=headers, method="POST")
    # Ignore ambient proxies; do not route local source through a configured external proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(1_000_001)
        if len(body) > 1_000_000:
            raise ProviderError("Provider response exceeds safety limit")
        value = json.loads(body)
        if not isinstance(value, dict):
            raise ProviderError("Provider returned an invalid response")
        return value
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ProviderError("Provider unavailable, timed out, or returned invalid JSON") from exc


class DeterministicOnlyProvider:
    def analyze(self, prompt: str) -> AIResponse:
        return AIResponse(summary="Deterministic analysis only")
