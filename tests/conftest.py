import subprocess

import pytest


@pytest.fixture(autouse=True)
def isolate_ci_summary(monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-b", "main", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    return tmp_path


@pytest.fixture
def commit():
    def make(root, message="fixture"):
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "--allow-empty", "-m", message],
                       check=True, capture_output=True)
        return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    return make
