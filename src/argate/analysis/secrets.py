import re

from argate.analysis.impact import any_match
from argate.config import Config
from argate.models import ChangeSet, SecurityMetadata

SENSITIVE_PATHS = [
    "**/.env", "**/.env.*", "**/*.pem", "**/*.key", "**/*.p12", "**/*.pfx",
    "**/id_rsa*", "**/id_ed25519*", "**/secrets.*", "**/credentials.*",
    "**/secrets/**", "**/.ssh/**", "**/.git/**", "**/.npmrc", "**/.netrc",
]
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|secret|password|passwd|client[_-]?secret)\s*[=:]\s*[\"']?[^\s\"',;]{4,}"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{16,})\b"),
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@[^\s]+"),
]


def redact(text: str) -> tuple[str, bool]:
    triggered = False
    for pattern in SECRET_PATTERNS:
        text, count = pattern.subn("[REDACTED]", text)
        triggered |= count > 0
    return text, triggered


def safe_text(text: str) -> str:
    text = redact(text)[0]
    # Remove terminal escapes and control characters from command output and model text.
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return "".join(char for char in text if char in "\n\t" or ord(char) >= 32)


def git_quoted_path(path: str) -> str:
    """Reconstruct Git's core.quotePath=true header encoding without ambiguous parsing."""
    encoded = ""
    quoted = False
    escapes = {7: "\\a", 8: "\\b", 9: "\\t", 10: "\\n", 11: "\\v", 12: "\\f", 13: "\\r",
               34: '\\"', 92: "\\\\"}
    for byte in path.encode("utf-8"):
        if byte in escapes:
            encoded += escapes[byte]
            quoted = True
        elif byte < 32 or byte >= 127:
            encoded += f"\\{byte:03o}"
            quoted = True
        else:
            encoded += chr(byte)
    return f'"{encoded}"' if quoted else encoded


def sanitize(changes: ChangeSet, config: Config) -> tuple[str, SecurityMetadata]:
    metadata = SecurityMetadata()
    sensitive = set()
    for file in changes.changed_files:
        file.sensitive = any(any_match(path, SENSITIVE_PATHS + config.security.sensitive_paths)
                             for path in [file.path, file.old_path] if path)
        (metadata.excluded_files if file.sensitive else metadata.included_files).append(file.path)
        if file.sensitive:
            sensitive.add(file.path)
    # Match exact Git-encoded headers, rather than assuming status and patch ordering.
    sections = re.split(r"(?m)(?=^diff --git )", changes.diff_text)
    sections = [section for section in sections if section.startswith("diff --git ")]
    headers = {}
    for file in changes.changed_files:
        old = file.old_path or file.path
        header = f"diff --git {git_quoted_path('a/' + old)} {git_quoted_path('b/' + file.path)}"
        if header in headers:
            metadata.external_ai_allowed = False
            return "", metadata
        headers[header] = file.path
    matched = [(headers.get(section.split('\n', 1)[0]), section) for section in sections]
    if len(sections) != len(changes.changed_files) or any(path is None for path, _ in matched):
        # Empty/binary-only differences can be valid, but never guess transmission scope.
        metadata.external_ai_allowed = False
        return "", metadata
    candidate = "".join(section for path, section in matched if path not in sensitive)
    candidate, metadata.redaction_triggered = redact(candidate)
    metadata.external_ai_allowed = not metadata.redaction_triggered or config.ai.allow_redacted_external
    if redact(candidate)[1]:
        metadata.external_ai_allowed = False
        candidate = ""
    encoded = candidate.encode("utf-8")
    metadata.payload_truncated = len(encoded) > config.ai.max_payload_bytes
    candidate = encoded[:config.ai.max_payload_bytes].decode("utf-8", errors="ignore")
    return candidate, metadata
