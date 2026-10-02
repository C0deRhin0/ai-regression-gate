import json
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from argate.cli import app
from argate.analysis.secrets import sanitize
from argate.config import Config
from argate.git.collector import collect, resolve_commit, verify_execution_tree
from argate.workflow import run

runner = CliRunner()


def fixture_repo(repo, commit, command="python -c 'print(\"2 passed\")'", required=True):
    command = command.replace("python ", f"'{sys.executable}' ")
    (repo / ".argate.yml").write_text(
        "project:\n  name: fixture\ncomponents:\n  backend:\n    paths: ['backend/**']\n    tests: [unit]\n"
        f"test_groups:\n  unit:\n    command: {json.dumps(command)}\n    required: {str(required).lower()}\n"
    )
    (repo / "backend").mkdir()
    (repo / "backend" / "app.py").write_text("original = True\n")
    base = commit(repo)
    (repo / "backend" / "app.py").write_text("original = False\nnew = True\n")
    head = commit(repo)
    return base, head


def test_git_status_counts_and_rename(repo, commit):
    (repo / "original name.py").write_text("one\ntwo\nthree\n")
    (repo / "delete.py").write_text("gone\n")
    (repo / "binary").write_bytes(b"\0data")
    base = commit(repo)
    (repo / "original name.py").rename(repo / "renamed name.py")
    (repo / "delete.py").unlink()
    (repo / "new.py").write_text("new\n")
    (repo / "binary").write_bytes(b"\0changed")
    head = commit(repo)
    cs = collect(repo, base, head)
    assert cs.insertions == 1 and cs.deletions == 1
    assert {file.status for file in cs.changed_files} == {"A", "D", "R", "M"}
    assert next(file for file in cs.changed_files if file.status == "R").old_path == "original name.py"
    assert next(file for file in cs.changed_files if file.path == "binary").binary
    assert "diff --git" in cs.diff_text
    with pytest.raises(ValueError):
        resolve_commit(repo, "--bad-ref")


def test_git_quoted_sensitive_paths(repo, commit):
    (repo / 'nested "quotes"').mkdir()
    sensitive = repo / 'nested "quotes"' / '.env.local'
    sensitive.write_text("hidden-value\n")
    safe = repo / "café\tfile.py"
    safe.write_text("old\n")
    base = commit(repo)
    sensitive.write_text("hidden-value-changed\n")
    safe.write_text("new\n")
    head = commit(repo)
    cs = collect(repo, base, head)
    patch, metadata = sanitize(cs, Config())
    assert metadata.external_ai_allowed
    assert "hidden-value" not in patch and "new" in patch
    assert metadata.excluded_files == ['nested "quotes"/.env.local']


def test_ai_failure_same_deterministic_gate(repo, commit, monkeypatch):
    from argate.ai.base import ProviderError
    from argate.ai.local import OllamaProvider
    base, _ = fixture_repo(repo, commit)
    with (repo / ".argate.yml").open("a") as stream:
        stream.write("ai:\n  mode: local_llm\n  provider: ollama\n  model: test\n  endpoint: http://127.0.0.1:11434\n")
    head = commit(repo)
    def unavailable(*args):
        raise ProviderError("down")
    monkeypatch.setattr(OllamaProvider, "analyze", unavailable)
    report = run("evaluate", base, head, repo / ".argate.yml", repo / "reports", no_ai=False)
    deterministic = run("evaluate", base, head, repo / ".argate.yml", repo / "reports", no_ai=True)
    assert report.ai_analysis_metadata.status == "unavailable"
    assert report.gate_decision == deterministic.gate_decision
    assert report.gate_decision.status == "READY"


@pytest.mark.parametrize("command,required,status,exit_code", [
    ("python -c 'print(\"2 passed\")'", True, "READY", 0),
    ("python -c 'raise SystemExit(1)'", True, "BLOCKED", 1),
    ("python -c 'raise SystemExit(1)'", False, "WARNING", 0),
])
def test_cli_reports_all_states(repo, commit, monkeypatch, command, required, status, exit_code):
    base, head = fixture_repo(repo, commit, command, required)
    monkeypatch.chdir(repo)
    summary = repo / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    result = runner.invoke(app, ["evaluate", "--base", base, "--head", head, "--verbose"])
    assert result.exit_code == exit_code, result.output
    data = json.loads((repo / "reports/report.json").read_text())
    assert data["gate_decision"]["status"] == status
    assert data["affected_components"] == ["backend"]
    assert data["selected_tests"][0]["name"] == "unit"
    assert data["change_summary"]["diff_text"] == ""
    assert len(data["metadata"]["configuration_hash"]) == 64
    assert data["metadata"]["evaluation_id"].startswith("ARG-")
    assert summary.read_text() == (repo / "reports/report.md").read_text() + "\n"
    assert "Quality Gates" in summary.read_text()
    events = [json.loads(line) for line in (repo / "reports/events.jsonl").read_text().splitlines()]
    assert [event["event"] for event in events] == ["evaluation_started", "evaluation_finished"]
    assert events[-1]["decision"] == status


def test_analyze_test_validate_and_errors(repo, commit, monkeypatch):
    base, head = fixture_repo(repo, commit)
    monkeypatch.chdir(repo)
    assert runner.invoke(app, ["--help"]).exit_code == 0
    assert runner.invoke(app, ["config", "validate"]).exit_code == 0
    assert runner.invoke(app, ["analyze", "--base", base]).exit_code == 0
    data = json.loads((repo / "reports/report.json").read_text())
    assert data["test_results"][0]["status"] == "SKIPPED"
    assert runner.invoke(app, ["test", "--base", base]).exit_code == 0
    assert runner.invoke(app, ["evaluate", "--base", "missing"]).exit_code == 1
    assert runner.invoke(app, ["config", "validate", "--config", "missing"]).exit_code == 1
    (repo / "backend/app.py").write_text("dirty\n")
    assert runner.invoke(app, ["evaluate", "--base", base]).exit_code == 1
    with pytest.raises(ValueError):
        verify_execution_tree(repo, base)


def test_report_redacts_secrets(repo, commit):
    base, head = fixture_repo(repo, commit, "python -c 'print(\"password=do-not-persist\")'")
    (repo / ".env").write_text("password=private-value\n")
    head = commit(repo)
    report = run("evaluate", base, head, repo / ".argate.yml", repo / "reports")
    for path in (repo / "reports").iterdir():
        assert "do-not-persist" not in path.read_text()
        assert "private-value" not in path.read_text()
    assert report.security_metadata.excluded_files == [".env"]


def test_demo_script(tmp_path):
    from pathlib import Path
    import sys
    script = Path(__file__).resolve().parents[2] / "scripts/demo.py"
    result = subprocess.run([sys.executable, str(script), "--report-dir", str(tmp_path)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((tmp_path / "blocked/report.json").read_text())["gate_decision"]["status"] == "BLOCKED"
    assert json.loads((tmp_path / "ready/report.json").read_text())["gate_decision"]["status"] == "READY"
