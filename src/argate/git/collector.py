import subprocess
from pathlib import Path

from argate.git.diff_parser import apply_numstat, parse_name_status
from argate.models import ChangeSet


def git(root: Path, *args: str) -> bytes:
    try:
        process = subprocess.run(
            ["git", "-C", str(root), "-c", "core.quotePath=true", *args],
            capture_output=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Git could not run or timed out") from exc
    if process.returncode:
        raise ValueError("Git operation failed; verify repository and commit references")
    return process.stdout


def repository_root(path: Path) -> Path:
    return Path(git(path, "rev-parse", "--show-toplevel").decode().strip()).resolve()


def resolve_commit(root: Path, ref: str) -> str:
    return git(root, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").decode().strip()


def collect(root: Path, base: str, head: str) -> ChangeSet:
    base_sha, head_sha = resolve_commit(root, base), resolve_commit(root, head)
    flags = ["--no-ext-diff", "--no-textconv", "--find-renames", base_sha, head_sha, "--"]
    files = parse_name_status(git(root, "diff", "--name-status", "-z", *flags))
    apply_numstat(files, git(root, "diff", "--numstat", "-z", *flags))
    patch = git(root, "diff", "--unified=3", *flags).decode("utf-8", errors="replace")
    return ChangeSet(
        base_sha=base_sha, head_sha=head_sha, changed_files=files,
        insertions=sum(file.insertions for file in files),
        deletions=sum(file.deletions for file in files), diff_text=patch,
    )


def verify_execution_tree(root: Path, head_sha: str) -> None:
    if resolve_commit(root, "HEAD") != head_sha:
        raise ValueError("Test execution requires --head to be the checked-out HEAD commit")
    if git(root, "status", "--porcelain", "--untracked-files=no").strip():
        raise ValueError("Commit or stash tracked changes before executing tests for an audited commit")
