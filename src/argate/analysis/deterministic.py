from argate.analysis.impact import any_match
from argate.config import Config, RiskRule
from argate.models import ChangeSet, RiskFinding

DEFAULT_RULES = [
    RiskRule(paths=["**/auth/**", "**/authentication*", "**/authorization*", "**/security/**"],
             severity="high", category="security", description="Authentication or security behavior changed",
             suggested_test="Verify denied access, expired credentials, and privilege boundaries"),
    RiskRule(paths=["**/migrations/**", "**/migration*"], severity="high", category="migration",
             description="Database migration changed", suggested_test="Verify upgrade, rollback, and existing data"),
    RiskRule(paths=["**/schemas/**", "**/schema*", "**/openapi*", "**/*.proto"], severity="high",
             category="contract", description="API or data contract changed",
             suggested_test="Verify compatibility and invalid input handling"),
    RiskRule(paths=["**/payments/**", "**/integrations/**", "**/adapters/**"], severity="high",
             category="integration", description="External integration behavior changed",
             suggested_test="Verify upstream timeout, duplicate request, and retry behavior"),
    RiskRule(paths=[".github/**", "**/Dockerfile*", "**/deploy/**", "**/terraform/**"], severity="high",
             category="deployment", description="CI or deployment configuration changed",
             suggested_test="Verify pipeline and deployment configuration"),
    RiskRule(paths=["**/package*.json", "**/*lock*", "**/requirements*.txt", "**/pyproject.toml"],
             severity="medium", category="dependency", description="Dependencies or build configuration changed"),
    RiskRule(paths=["**/tests/**", "**/test_*", "**/*.test.*", "**/*.spec.*"], severity="low",
             category="tests", description="Test coverage or expectations changed"),
    RiskRule(paths=["**/*.md", "**/*.rst", "**/docs/**", "LICENSE"], severity="low",
             category="documentation", description="Documentation changed"),
    RiskRule(paths=["**/*.css", "**/*.scss"], severity="low", category="style",
             description="Stylesheet changed"),
    RiskRule(paths=["**/*.yml", "**/*.yaml", "**/*.toml", "**/*.ini", "**/*.json"],
             severity="medium", category="configuration", description="Runtime configuration changed"),
]


def analyze(changes: ChangeSet, config: Config) -> list[RiskFinding]:
    findings = []
    for index, file in enumerate(changes.changed_files, 1):
        paths = [path for path in [file.path, file.old_path] if path]
        rule = next((rule for rule in config.risk_rules + DEFAULT_RULES
                     if any(any_match(path, rule.paths) for path in paths)), None)
        findings.append(RiskFinding(
            id=f"DET-{index:04d}", severity=rule.severity if rule else "medium",
            category=rule.category if rule else "source", file=file.path,
            description=rule.description if rule else "Source behavior changed",
            evidence=f"Git status {file.status}; +{file.insertions}/-{file.deletions}",
            suggested_test=rule.suggested_test if rule else "Verify changed behavior and boundary inputs",
        ))
    return findings
