import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from argate.ai.advisory import analyze_advisory
from argate.ai.base import DeterministicOnlyProvider, ProviderError, post_json
from argate.ai.local import OllamaProvider
from argate.ai.openai_compatible import OpenAICompatibleProvider
from argate.config import Config
from argate.models import AIResponse, ChangeSet, ChangedFile, SecurityMetadata


def config(mode="local_llm", provider="openai_compatible"):
    return Config.model_validate({"ai": {"mode": mode, "provider": provider, "model": "test",
                                          "endpoint": "https://example.invalid/v1" if mode == "external_llm"
                                          else "http://127.0.0.1:11434"},
                                  "test_groups": {"unit": {"command": "true", "required": True}}})


def test_structured_response_and_selection(monkeypatch):
    response = AIResponse(summary="Likely retry risk", risks=[{"severity": "medium", "file": "app.py",
                             "description": "Retry", "reason": "changed", "suggested_test": "timeout"},
                            {"severity": "high", "file": "unknown.py", "description": "invented"}],
                          edge_cases=["duplicate"], recommended_test_groups=["unit", "unknown"])
    monkeypatch.setattr(OpenAICompatibleProvider, "analyze", lambda *args: response)
    changes = ChangeSet(base_sha="a", head_sha="b", changed_files=[ChangedFile(path="app.py", status="M")])
    meta, risks, tests = analyze_advisory(config(), changes, "safe diff", [], SecurityMetadata(included_files=["app.py"]))
    assert meta.status == "available" and meta.edge_cases == ["duplicate"]
    assert len(risks) == 1 and risks[0].source == "llm" and tests == ["unit"]


def test_external_guard_prevents_any_call(monkeypatch):
    def forbidden(*args):
        pytest.fail("Provider must not be contacted")
    monkeypatch.setattr(OpenAICompatibleProvider, "analyze", forbidden)
    changes = ChangeSet(base_sha="a", head_sha="b")
    meta, _, _ = analyze_advisory(config("external_llm"), changes, "", [],
                                  SecurityMetadata(external_ai_allowed=False, redaction_triggered=True))
    assert meta.status == "blocked"


def test_metadata_secret_blocks_and_payload_limit(monkeypatch):
    def forbidden(*args):
        pytest.fail("Provider must not be contacted")
    monkeypatch.setattr(OpenAICompatibleProvider, "analyze", forbidden)
    changes = ChangeSet(base_sha="a", head_sha="b")
    meta, _, _ = analyze_advisory(config("external_llm"), changes, "", [],
                                  SecurityMetadata(included_files=["password=unsafe-value"]))
    assert meta.status == "blocked"
    with pytest.raises(ProviderError, match="payload limit"):
        post_json("http://localhost", {"data": "x" * 1000}, 1, max_payload_bytes=256)


def test_fallback_and_disabled(monkeypatch):
    def unavailable(*args):
        raise ProviderError("timeout")
    monkeypatch.setattr(OpenAICompatibleProvider, "analyze", unavailable)
    args = [config(), ChangeSet(base_sha="a", head_sha="b"), "", [], SecurityMetadata()]
    assert analyze_advisory(*args)[0].status == "unavailable"
    assert analyze_advisory(*args, no_ai=True)[0].status == "disabled"
    cfg = config()
    cfg.ai.max_payload_bytes = 256
    args[0] = cfg
    assert analyze_advisory(*args)[0].status == "blocked"
    assert DeterministicOnlyProvider().analyze("").risks == []


@pytest.mark.parametrize("provider,module,response", [
    (OpenAICompatibleProvider, "argate.ai.openai_compatible", {"choices": [{"message": {"content": '{"summary":"ok"}'}}]}),
    (OllamaProvider, "argate.ai.local", {"response": '{"summary":"ok"}'}),
])
def test_adapters_valid_and_invalid(monkeypatch, provider, module, response):
    monkeypatch.setattr(module + ".post_json", lambda *args: response)
    assert provider(config().ai).analyze("safe").summary == "ok"
    monkeypatch.setattr(module + ".post_json", lambda *args: {})
    with pytest.raises(ProviderError):
        provider(config().ai).analyze("safe")
    malformed = {"response": "{broken", "choices": [{"message": {"content": "{broken"}}]}
    monkeypatch.setattr(module + ".post_json", lambda *args: malformed)
    with pytest.raises(ProviderError):
        provider(config().ai).analyze("safe")


def test_missing_key(monkeypatch):
    cfg = config().ai
    cfg.api_key_env = "ARGATE_TEST_MISSING_KEY"
    monkeypatch.delenv(cfg.api_key_env, raising=False)
    with pytest.raises(ProviderError, match="missing"):
        OpenAICompatibleProvider(cfg).analyze("safe")


@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        mode = "valid"
        auth = None

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            Handler.auth = self.headers.get("Authorization")
            if self.mode == "redirect":
                self.send_response(302)
                self.send_header("Location", "https://example.invalid")
                self.end_headers()
                return
            body = {"valid": b'{"ok":true}', "invalid": b'bad json', "list": b'[]',
                    "oversized": b'x' * 1_000_001}[self.mode]
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    http = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{http.server_port}", Handler
    http.shutdown()
    http.server_close()
    thread.join()


def test_http_provider_security(server):
    url, handler = server
    assert post_json(url, {}, 1, "test-key") == {"ok": True}
    assert handler.auth == "Bearer test-key"
    for mode in ["invalid", "list", "oversized", "redirect"]:
        handler.mode = mode
        with pytest.raises(ProviderError):
            post_json(url, {}, 1)


def test_provider_unavailable():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with pytest.raises(ProviderError):
        post_json(f"http://127.0.0.1:{port}", {}, 0.1)


def test_provider_timeout(monkeypatch):
    class Opener:
        def open(self, *args, **kwargs):
            raise TimeoutError("secret response must not escape")
    monkeypatch.setattr("urllib.request.build_opener", lambda *args: Opener())
    with pytest.raises(ProviderError) as exc:
        post_json("http://localhost", {}, 0.1)
    assert "secret response" not in str(exc.value)
