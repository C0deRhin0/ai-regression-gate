import sys
import time

import pytest
from pydantic import ValidationError

from argate.analysis.deterministic import analyze
from argate.analysis.impact import map_components, matches
from argate.analysis.risk import overall_risk
from argate.analysis.secrets import redact, safe_text, sanitize
from argate.config import Config, configuration_hash, load_config
from argate.execution.coverage import collect_coverage, read_cobertura
from argate.execution.result_parser import parse_counts
from argate.execution.runner import run_group
from argate.models import ChangeSet, ChangedFile, TestGroup as Group
from argate.selection.test_selector import select_tests


def changes(*paths):
    return ChangeSet(base_sha="a", head_sha="b", changed_files=[ChangedFile(path=p, status="M") for p in paths])


@pytest.mark.parametrize("path,pattern,expected", [
    ("backend/a.py", "backend/**", True), ("backend/deep/a.py", "backend/*", False),
    ("a.py", "**/*.py", True), ("a/b.py", "**/*.py", True),
    ("a/b.py", "*.py", False), ("a/x.py", "./a/?.py", True),
    (".env", "**/.env", True), ("a/.env.local", "**/.env.*", True),
])
def test_globs(path, pattern, expected):
    assert matches(path, pattern) == expected


def test_mapping_selection_and_rename():
    cfg = Config.model_validate({
        "components": {"backend": {"paths": ["backend/**"], "tests": ["unit"]},
                       "frontend": {"paths": ["frontend/**"], "tests": ["web"]}},
        "test_groups": {"unit": {"command": "true", "required": True},
                        "web": {"command": "true"}, "contract": {"command": "true", "component": "backend"}},
        "quality_gates": {"mandatory_test_groups": ["contract"]},
    })
    cs = changes("frontend/a.py")
    cs.changed_files[0].old_path = "backend/a.py"
    affected = map_components(cs, cfg)
    assert affected == ["backend", "frontend"]
    groups = select_tests(cfg, affected, ["unknown", "web"])
    assert [group.name for group in groups] == ["contract", "unit", "web"]
    assert groups[0].required
    assert "AI advisory recommendation" in groups[2].reasons


@pytest.mark.parametrize("data", [
    {"components": {"x": {"paths": ["**"], "tests": ["missing"]}}},
    {"test_groups": {"x": {"command": "true", "timeout_seconds": 0}}},
    {"test_groups": {"x": {"command": "true", "component": "missing"}}},
    {"quality_gates": {"minimum_coverage": 80}}, {"coverage": {"format": "unknown"}},
    {"unknown": True}, {"ai": {"mode": "external_llm"}},
    {"ai": {"mode": "local_llm", "model": "test", "endpoint": "https://remote.invalid"}},
    {"ai": {"mode": "external_llm", "model": "test", "endpoint": "http://remote.invalid"}},
    {"ai": {"mode": "local_llm", "model": "test", "endpoint": "http://user:pass@localhost"}},
    {"ai": {"mode": "local_llm", "model": "test", "endpoint": "http://localhost/?token=x"}},
    {"ai": {"provider": "other"}}, {"ai": {"mode": "other"}},
])
def test_config_rejects_invalid(data):
    with pytest.raises(ValidationError):
        Config.model_validate(data)


def test_load_config_and_hash(tmp_path):
    path = tmp_path / ".argate.yml"
    path.write_text("project:\n  name: test\n")
    cfg = load_config(path)
    assert cfg.project.name == "test"
    assert configuration_hash(cfg) == configuration_hash(Config.model_validate(cfg.model_dump()))
    path.write_text("[not, a, mapping]")
    with pytest.raises(ValueError, match="Invalid configuration"):
        load_config(path)
    path.write_text("broken: [")
    with pytest.raises(ValueError):
        load_config(path)
    path.write_text("ai:\n  mode: deterministic_only\n  mode: external_llm\n")
    with pytest.raises(ValueError):
        load_config(path)


@pytest.mark.parametrize("path,severity", [
    ("README.md", "low"), ("tests/test_a.py", "low"), ("style.css", "low"),
    ("backend/a.py", "medium"), ("package.json", "medium"), ("config.yaml", "medium"),
    ("backend/auth/login.py", "high"), ("migrations/001.sql", "high"),
    ("schemas/model.py", "high"), ("payments/charge.py", "high"), (".github/workflows/ci.yml", "high"),
])
def test_risks(path, severity):
    assert overall_risk(analyze(changes(path), Config())) == severity


def test_custom_risk_and_empty():
    cfg = Config.model_validate({"risk_rules": [{"paths": ["**"], "severity": "critical",
                                                "category": "custom", "description": "Manual rule"}]})
    assert overall_risk(analyze(changes("a.py"), cfg)) == "critical"
    assert overall_risk([]) == "low"


@pytest.mark.parametrize("secret", [
    "Bearer abcdefghijkl", "api_key=abcdefgh", "password: example-secret", "AKIAABCDEFGHIJKLMNOP",
    "ghp_abcdefghijklmnopqrstuvwxyz123", "postgres://user:password@localhost/db",
    "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
])
def test_secret_redaction(secret):
    redacted, triggered = redact(secret)
    assert triggered and secret not in redacted
    assert "[REDACTED]" in redacted


def test_sanitization():
    cs = changes(".env", "backend/app.py")
    cs.diff_text = "diff --git a/.env b/.env\n+hidden\ndiff --git a/backend/app.py b/backend/app.py\n+api_key=example-secret\n"
    diff, metadata = sanitize(cs, Config())
    assert "hidden" not in diff and "example-secret" not in diff
    assert metadata.excluded_files == [".env"]
    assert metadata.redaction_triggered and not metadata.external_ai_allowed
    cfg = Config.model_validate({"ai": {"allow_redacted_external": True}})
    assert sanitize(cs, cfg)[1].external_ai_allowed
    cs.diff_text = "invalid"
    assert not sanitize(cs, Config())[1].external_ai_allowed
    assert safe_text("\x1b[31mhi\x00") == "hi"


def test_rename_to_safe_is_still_sensitive():
    cs = changes("backend/file.py")
    cs.changed_files[0].old_path = ".env"
    cs.diff_text = "diff --git a/.env b/backend/file.py\n+hidden"
    diff, meta = sanitize(cs, Config())
    assert not diff and meta.excluded_files == ["backend/file.py"]


@pytest.mark.parametrize("script,status", [("print('3 passed, 1 skipped')", "PASS"),
                                          ("raise SystemExit(2)", "FAIL"),
                                          ("import time; time.sleep(10)", "TIMEOUT")])
def test_runner(tmp_path, script, status):
    group = Group(name="fixture", command=f"'{sys.executable}' -c \"{script}\"", timeout_seconds=0.2)
    result = run_group(group, tmp_path)
    assert result.status == status and result.exit_code is not None
    if status == "PASS":
        assert result.passed == 3 and result.skipped == 1
    assert result.duration < 5


def test_runner_redacts_and_truncates(tmp_path):
    result = run_group(Group(name="x", command=f"'{sys.executable}' -c \"print('x' * 10000); print('password=unsafe-value')\""), tmp_path)
    assert len(result.stdout_tail) <= 8000 and "unsafe-value" not in result.stdout_tail
    assert parse_counts("not pytest") == {"passed": None, "failed": None, "skipped": None}
    assert run_group(Group(name="x", command="true"), tmp_path / "missing").status == "ERROR"


def test_runner_does_not_pollute_parent_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "parent.md"))
    result = run_group(Group(name="x", command=f"'{sys.executable}' -c \"import os; assert 'GITHUB_STEP_SUMMARY' not in os.environ\""), tmp_path)
    assert result.status == "PASS"


def test_coverage(tmp_path):
    path = tmp_path / "coverage.xml"
    started = time.time() - 1
    path.write_text('<coverage line-rate="0.85"/>')
    cfg = Config.model_validate({"coverage": {"enabled": True, "baseline": 90}})
    result = collect_coverage(cfg.coverage, tmp_path, started)
    assert result.current == 85 and result.drop == 5
    assert collect_coverage(cfg.coverage, tmp_path, time.time() + 1).error
    path.write_text('<coverage line-rate="NaN"/>')
    assert collect_coverage(cfg.coverage, tmp_path, started).error
    path.write_text('<!DOCTYPE coverage><coverage line-rate="1"/>')
    with pytest.raises(ValueError):
        read_cobertura(path)
    assert not collect_coverage(Config().coverage, tmp_path, started).enabled
