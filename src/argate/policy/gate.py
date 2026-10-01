from argate.analysis.impact import any_match
from argate.config import Config
from argate.models import (
    AIAnalysisMetadata, ChangeSet, CoverageResult, GateDecision, QualityGateResult,
    RiskFinding, TestGroup, TestResult,
)


def evaluate_policy(
    config: Config, changes: ChangeSet, findings: list[RiskFinding], groups: list[TestGroup],
    results: list[TestResult], coverage: CoverageResult, ai: AIAnalysisMetadata,
) -> GateDecision:
    gates = []
    result_map = {result.group: result for result in results}
    selected = {group.name: group for group in groups}
    required = {name for name, group in config.test_groups.items() if group.required}
    required.update(config.quality_gates.mandatory_test_groups)

    def check(name, passed, detail, blocking=True):
        gates.append(QualityGateResult(name=name, passed=passed, detail=detail, blocking=blocking))

    for name in sorted(required):
        result = result_map.get(name)
        # A required failure always blocks, even if missing-execution checking is disabled.
        executed = result is not None and result.status != "SKIPPED"
        check(f"Required test: {name}", executed and result.status == "PASS",
              f"{name}: {result.status if result else 'NOT EXECUTED'}",
              blocking=executed or config.quality_gates.require_all_required_tests
              or name in config.quality_gates.mandatory_test_groups)
    for name, group in selected.items():
        if name not in required:
            result = result_map.get(name)
            check(f"Optional test: {name}", result is not None and result.status == "PASS",
                  f"{name}: {result.status if result else 'NOT EXECUTED'}", blocking=False)
    if config.quality_gates.block_on_high_risk_without_tests:
        for finding in findings:
            if finding.source != "deterministic" or finding.severity not in {"high", "critical"}:
                continue
            file = next((file for file in changes.changed_files if file.path == finding.file), None)
            mapped = set()
            if file:
                for component in file.components:
                    mapped.update(config.components[component].tests)
                    mapped.update(name for name, group in config.test_groups.items() if group.component == component)
            passed = any(name in required and name in result_map and result_map[name].status == "PASS"
                         for name in mapped)
            check(f"High-risk verification: {finding.file}", passed,
                  f"{finding.file}: {'mapped required test passed' if passed else 'no passing mapped required test'}")
    blockers = [file.path for file in changes.changed_files
                if any(any_match(path, config.quality_gates.blocker_paths)
                       for path in [file.path, file.old_path] if path)]
    check("Explicit blocker paths", not blockers,
          "Blocked paths changed: " + ", ".join(blockers) if blockers else "No configured blocker paths changed")
    if coverage.enabled:
        check("Coverage report", coverage.error is None and coverage.current is not None,
              coverage.error or f"Coverage: {coverage.current}%")
        minimum = config.coverage.minimum
        if minimum is None:
            minimum = config.quality_gates.minimum_coverage
        maximum_drop = config.coverage.maximum_drop
        if maximum_drop is None:
            maximum_drop = config.quality_gates.maximum_coverage_drop
        if minimum is not None:
            check("Minimum coverage", coverage.current is not None and coverage.current >= minimum,
                  f"Coverage {coverage.current}% must be >= {minimum}%")
        if maximum_drop is not None:
            check("Maximum coverage drop", coverage.drop is not None and coverage.drop <= maximum_drop,
                  f"Coverage drop {coverage.drop} points must be <= {maximum_drop}; baseline required")
        if coverage.drop is not None and coverage.drop > 0:
            check("Coverage trend", False, f"Coverage dropped {coverage.drop} percentage points", blocking=False)
    if ai.status in {"unavailable", "blocked"} and config.quality_gates.block_on_ai_unavailable:
        check("Configured AI availability", False, "AI unavailable under explicit availability policy")
    # LLM findings never determine approval or a hard block. They may surface advisory warnings.
    if any(finding.source == "llm" and finding.severity in {"medium", "high", "critical"}
           for finding in findings):
        check("Advisory edge cases", False, "AI suggested edge cases; review suggested verification", blocking=False)
    failures = [gate for gate in gates if not gate.passed]
    blocked = any(gate.blocking for gate in failures)
    if failures and config.quality_gates.warnings_as_errors:
        blocked = True
    status = "BLOCKED" if blocked else "WARNING" if failures else "READY"
    return GateDecision(status=status, reasons=[gate.detail for gate in failures] or ["All configured gates passed"],
                        quality_gate_results=gates)
