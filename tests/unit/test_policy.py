import pytest

from argate.config import Config
from argate.models import (
    AIAnalysisMetadata, ChangeSet, ChangedFile, CoverageResult, RiskFinding,
    TestGroup as Group, TestResult as Result,
)
from argate.policy.gate import evaluate_policy


def decision(status="PASS", required=True, config_extra=None, coverage=None, findings=None, ai=None):
    data = {"test_groups": {"unit": {"command": "true", "required": required}}, **(config_extra or {})}
    cfg = Config.model_validate(data)
    return evaluate_policy(cfg, ChangeSet(base_sha="a", head_sha="b"), findings or [],
                           [Group(name="unit", command="true", required=required)],
                           [] if status == "MISSING" else [Result(group="unit", status=status)],
                           coverage or CoverageResult(), ai or AIAnalysisMetadata())


@pytest.mark.parametrize("status,required,expected", [
    ("PASS", True, "READY"), ("FAIL", True, "BLOCKED"), ("TIMEOUT", True, "BLOCKED"),
    ("ERROR", True, "BLOCKED"), ("SKIPPED", True, "BLOCKED"), ("MISSING", True, "BLOCKED"),
    ("FAIL", False, "WARNING"), ("SKIPPED", False, "WARNING"), ("MISSING", False, "WARNING"),
])
def test_states(status, required, expected):
    assert decision(status, required).status == expected


def test_no_llm_override():
    assert decision("FAIL", ai=AIAnalysisMetadata(status="available", summary="Approved!")).status == "BLOCKED"
    assert decision(ai=AIAnalysisMetadata(status="unavailable")).status == "READY"
    assert decision(ai=AIAnalysisMetadata(status="blocked")).status == "READY"
    assert decision(config_extra={"quality_gates": {"block_on_ai_unavailable": True}},
                    ai=AIAnalysisMetadata(status="unavailable")).status == "BLOCKED"


def test_advisory_and_warning_escalation():
    risk = RiskFinding(id="AI-1", source="llm", severity="high", category="advisory", description="Risk")
    assert decision(findings=[risk]).status == "WARNING"
    assert decision("FAIL", False, {"quality_gates": {"warnings_as_errors": True}}).status == "BLOCKED"
    assert decision("FAIL", True, {"quality_gates": {"require_all_required_tests": False}}).status == "BLOCKED"
    assert decision("MISSING", True, {"quality_gates": {"require_all_required_tests": False}}).status == "WARNING"


def test_coverage_gates():
    cfg = {"coverage": {"enabled": True, "minimum": 80, "maximum_drop": 2}}
    assert decision(config_extra=cfg, coverage=CoverageResult(enabled=True, current=79, drop=1)).status == "BLOCKED"
    assert decision(config_extra=cfg, coverage=CoverageResult(enabled=True, current=85, drop=1)).status == "WARNING"
    assert decision(config_extra=cfg, coverage=CoverageResult(enabled=True, current=85, drop=0)).status == "READY"
    assert decision(config_extra=cfg, coverage=CoverageResult(enabled=True, current=85, drop=3)).status == "BLOCKED"
    assert decision(config_extra=cfg, coverage=CoverageResult(enabled=True, current=85)).status == "BLOCKED"
    assert decision(config_extra=cfg, coverage=CoverageResult(enabled=True, error="missing")).status == "BLOCKED"


def test_high_risk_and_blocker_paths():
    cfg = Config.model_validate({"components": {"auth": {"paths": ["auth/**"], "tests": ["unit"]}},
                                 "test_groups": {"unit": {"command": "true", "required": True}},
                                 "quality_gates": {"blocker_paths": ["blocked/**"]}})
    cs = ChangeSet(base_sha="a", head_sha="b", changed_files=[ChangedFile(path="auth/a.py", status="M", components=["auth"])])
    risks = [RiskFinding(id="1", severity="high", category="auth", file="auth/a.py", description="Auth changed")]
    args = [cfg, cs, risks, [Group(name="unit", command="true", required=True)],
            [Result(group="unit", status="PASS")], CoverageResult(), AIAnalysisMetadata()]
    assert evaluate_policy(*args).status == "READY"
    cs.changed_files[0].components = []
    assert evaluate_policy(*args).status == "BLOCKED"
    cs.changed_files.append(ChangedFile(path="blocked/a.py", status="A"))
    assert "blocked/a.py" in str(evaluate_policy(*args).reasons)
