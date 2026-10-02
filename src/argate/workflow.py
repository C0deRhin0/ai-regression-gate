import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from argate import __version__
from argate.ai.advisory import analyze_advisory
from argate.analysis.deterministic import analyze
from argate.analysis.impact import map_components
from argate.analysis.risk import overall_risk
from argate.analysis.secrets import sanitize
from argate.config import configuration_hash, load_config
from argate.execution.coverage import collect_coverage
from argate.execution.runner import run_tests
from argate.git.collector import collect, repository_root, verify_execution_tree
from argate.integrations.github import write_summary
from argate.logging import event
from argate.models import AuditMetadata, CoverageResult, EvaluationReport, TestResult
from argate.policy.gate import evaluate_policy
from argate.reporting.json_report import render_json
from argate.reporting.markdown import render_markdown
from argate.selection.test_selector import select_tests


def run(operation: str, base: str, head: str, config_path: Path, report_dir: Path,
        no_ai: bool = False) -> EvaluationReport:
    config_path = config_path.resolve()
    config = load_config(config_path)
    root = repository_root(config_path.parent)
    changes = collect(root, base, head)
    affected = map_components(changes, config)
    findings = analyze(changes, config)
    risk = overall_risk(findings)
    sanitized_diff, security = sanitize(changes, config)
    ai, advisory, recommendations = analyze_advisory(config, changes, sanitized_diff, findings, security,
                                                    no_ai=no_ai or operation == "test")
    groups = select_tests(config, affected, recommendations)
    now = datetime.now(timezone.utc)
    evaluation_id = f"ARG-{now:%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
    report_dir.mkdir(parents=True, exist_ok=True)
    audit_log = report_dir / "events.jsonl"
    event("evaluation_started", audit_log=audit_log, evaluation_id=evaluation_id,
          base=changes.base_sha, head=changes.head_sha,
          components=affected, tests=[group.name for group in groups], provider_mode=ai.mode)
    started = time.time()
    if operation != "analyze":
        verify_execution_tree(root, changes.head_sha)
        results = run_tests(groups, root)
        coverage = collect_coverage(config.coverage, root, started)
    else:
        results = [TestResult(group=group.name, status="SKIPPED") for group in groups]
        coverage = CoverageResult(enabled=config.coverage.enabled, error="Analysis only; coverage not collected")
    decision = evaluate_policy(config, changes, findings + advisory, groups, results, coverage, ai)
    if operation != "evaluate" and decision.status == "READY":
        decision.status = "WARNING"
        decision.reasons = [f"{operation.title()} only; release policy requires a full evaluation"]
    # Source content is never persisted. Paths/statistics suffice for the audit.
    changes.diff_text = ""
    report = EvaluationReport(
        metadata=AuditMetadata(evaluation_id=evaluation_id, timestamp=now.isoformat(),
                               configuration_hash=configuration_hash(config), project=config.project.name,
                               version=__version__, operation=operation),
        change_summary=changes, affected_components=affected, overall_risk=risk,
        risk_findings=findings + advisory, selected_tests=groups, test_results=results,
        coverage=coverage, gate_decision=decision, ai_analysis_metadata=ai, security_metadata=security,
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(report)
    (report_dir / "report.md").write_text(markdown, encoding="utf-8")
    (report_dir / "report.json").write_text(render_json(report), encoding="utf-8")
    write_summary(markdown)
    event("evaluation_finished", audit_log=audit_log, evaluation_id=evaluation_id, decision=decision.status,
          durations={result.group: result.duration for result in results})
    return report
