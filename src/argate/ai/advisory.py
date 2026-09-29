import json

from argate.ai.base import ProviderError
from argate.ai.local import OllamaProvider
from argate.ai.openai_compatible import OpenAICompatibleProvider
from argate.ai.prompts import build_prompt
from argate.analysis.secrets import redact, safe_text
from argate.config import Config
from argate.models import AIAnalysisMetadata, ChangeSet, RiskFinding, SecurityMetadata


def analyze_advisory(config: Config, changes: ChangeSet, diff: str, findings: list[RiskFinding],
                     security: SecurityMetadata, no_ai: bool = False):
    meta = AIAnalysisMetadata(mode=config.ai.mode, provider=config.ai.provider)
    if no_ai or config.ai.mode == "deterministic_only":
        meta.provider = "none"
        return meta, [], []
    if config.ai.mode == "external_llm" and not security.external_ai_allowed:
        meta.status, meta.detail = "blocked", "Source transmission blocked by security guard"
        return meta, [], []
    included = set(security.included_files)
    context = {
        "changed_files": sorted(included), "sanitized_diff": diff,
        "components": sorted({component for file in changes.changed_files if file.path in included
                               for component in file.components}),
        "test_groups": sorted(config.test_groups),
        "deterministic_findings": [finding.model_dump() for finding in findings if finding.file in included],
    }
    # The limit applies to the whole serialized request, including schema and metadata.
    prompt = build_prompt(context)
    prompt, redacted = redact(prompt)
    if redacted:
        security.redaction_triggered = True
        security.external_ai_allowed = config.ai.allow_redacted_external
        if config.ai.mode == "external_llm" and not security.external_ai_allowed:
            meta.status, meta.detail = "blocked", "Advisory metadata blocked by security guard"
            return meta, [], []
    if len(json.dumps({"prompt": prompt}).encode()) > config.ai.max_payload_bytes:
        meta.status, meta.detail = "blocked", "Sanitized advisory payload exceeds configured size limit"
        security.payload_truncated = True
        return meta, [], []
    provider = OllamaProvider(config.ai) if config.ai.provider == "ollama" else OpenAICompatibleProvider(config.ai)
    try:
        response = provider.analyze(prompt)
    except ProviderError:
        meta.status, meta.detail = "unavailable", "AI unavailable or invalid response; deterministic evaluation continues"
        return meta, [], []
    meta.status = "available"
    meta.summary = safe_text(response.summary)
    meta.edge_cases = [safe_text(case)[:2000] for case in response.edge_cases]
    advisory = [RiskFinding(
        id=f"AI-{index:04d}", source="llm", severity=risk.severity, category="advisory",
        file=risk.file, description=safe_text(risk.description), evidence=safe_text(risk.reason),
        suggested_test=safe_text(risk.suggested_test),
    ) for index, risk in enumerate(response.risks, 1) if risk.file is None or risk.file in included]
    return meta, advisory, [name for name in response.recommended_test_groups if name in config.test_groups]
