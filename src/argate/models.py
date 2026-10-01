from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high", "critical"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)


class ChangedFile(Model):
    path: str
    old_path: str | None = None
    status: str
    insertions: int = 0
    deletions: int = 0
    binary: bool = False
    components: list[str] = Field(default_factory=list)
    sensitive: bool = False


class ChangeSet(Model):
    base_sha: str
    head_sha: str
    changed_files: list[ChangedFile] = Field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    diff_text: str = ""


class RiskFinding(Model):
    id: str
    source: Literal["deterministic", "llm", "policy"] = "deterministic"
    severity: Severity
    category: str
    file: str | None = None
    description: str
    evidence: str = ""
    suggested_test: str = ""


class TestGroup(Model):
    name: str
    command: str
    required: bool = False
    timeout_seconds: float = 120
    component: str | None = None
    reasons: list[str] = Field(default_factory=list)


class TestResult(Model):
    group: str
    status: Literal["PASS", "FAIL", "TIMEOUT", "ERROR", "SKIPPED"]
    duration: float = 0
    exit_code: int | None = None
    passed: int | None = None
    failed: int | None = None
    skipped: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""


class QualityGateResult(Model):
    name: str
    passed: bool
    blocking: bool = True
    detail: str


class GateDecision(Model):
    status: Literal["READY", "WARNING", "BLOCKED"]
    reasons: list[str]
    quality_gate_results: list[QualityGateResult]


class CoverageResult(Model):
    enabled: bool = False
    current: float | None = None
    baseline: float | None = None
    drop: float | None = None
    error: str | None = None


class AIRisk(Model):
    severity: Severity
    file: str | None = None
    description: str = Field(max_length=2000)
    reason: str = Field(default="", max_length=2000)
    suggested_test: str = Field(default="", max_length=2000)


class AIResponse(Model):
    summary: str = Field(max_length=4000)
    risks: list[AIRisk] = Field(default_factory=list, max_length=100)
    edge_cases: list[str] = Field(default_factory=list, max_length=100)
    recommended_test_groups: list[str] = Field(default_factory=list, max_length=100)


class AIAnalysisMetadata(Model):
    mode: str = "deterministic_only"
    provider: str = "none"
    status: Literal["disabled", "available", "unavailable", "blocked"] = "disabled"
    detail: str = "AI is advisory only."
    summary: str = ""
    edge_cases: list[str] = Field(default_factory=list)


class SecurityMetadata(Model):
    redaction_triggered: bool = False
    excluded_files: list[str] = Field(default_factory=list)
    included_files: list[str] = Field(default_factory=list)
    external_ai_allowed: bool = True
    payload_truncated: bool = False


class AuditMetadata(Model):
    evaluation_id: str
    timestamp: str
    configuration_hash: str
    project: str
    version: str
    operation: Literal["evaluate", "analyze", "test"]


class EvaluationReport(Model):
    schema_version: str = "1.0"
    metadata: AuditMetadata
    change_summary: ChangeSet
    affected_components: list[str]
    overall_risk: Severity
    risk_findings: list[RiskFinding]
    selected_tests: list[TestGroup]
    test_results: list[TestResult]
    coverage: CoverageResult
    gate_decision: GateDecision
    ai_analysis_metadata: AIAnalysisMetadata
    security_metadata: SecurityMetadata
