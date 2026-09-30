from argate.models import RiskFinding, Severity

WEIGHTS = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def overall_risk(findings: list[RiskFinding]) -> Severity:
    return max((finding.severity for finding in findings), key=WEIGHTS.get, default="low")
