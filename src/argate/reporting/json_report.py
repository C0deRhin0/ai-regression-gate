from argate.analysis.secrets import safe_text
from argate.models import EvaluationReport


def render_json(report: EvaluationReport) -> str:
    # Redact individual strings before JSON encoding; replacing JSON text can corrupt syntax.
    def sanitize(value):
        if isinstance(value, str):
            return safe_text(value)
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, dict):
            return {key: sanitize(item) for key, item in value.items()}
        return value

    import json
    return json.dumps(sanitize(report.model_dump(mode="json")), indent=2, sort_keys=True) + "\n"
