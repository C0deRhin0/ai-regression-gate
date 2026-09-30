import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from argate.analysis.secrets import safe_text
from argate.execution.result_parser import parse_counts
from argate.models import TestGroup, TestResult

OUTPUT_LIMIT = 8000


def tail(stream) -> str:
    stream.flush()
    size = stream.tell()
    # Sanitize the complete output before truncating: a secret can straddle the tail boundary.
    stream.seek(0)
    if size > 8_000_000:
        return "[Output exceeds safety limit; omitted]"
    return safe_text(stream.read().decode("utf-8", errors="replace"))[-OUTPUT_LIMIT:]


def stop_process_tree(process):
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass  # Child exited between timeout and termination.
    process.wait()


def run_group(group: TestGroup, root: Path) -> TestResult:
    started = time.monotonic()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            environment = os.environ.copy()
            environment.pop("GITHUB_STEP_SUMMARY", None)  # Only the enclosing evaluation owns its summary.
            process = subprocess.Popen(
                group.command, shell=True, cwd=root, stdout=stdout, stderr=stderr,
                start_new_session=os.name == "posix", env=environment,
            )
            try:
                exit_code = process.wait(timeout=group.timeout_seconds)
                status = "PASS" if exit_code == 0 else "FAIL"
                if os.name == "posix":
                    stop_process_tree(process)  # Clean up background descendants even after shell exit.
            except subprocess.TimeoutExpired:
                stop_process_tree(process)
                status, exit_code = "TIMEOUT", process.returncode
            except BaseException:
                stop_process_tree(process)
                raise
            out, err = tail(stdout), tail(stderr)
            return TestResult(
                group=group.name, status=status, exit_code=exit_code,
                duration=round(time.monotonic() - started, 3),
                stdout_tail=out, stderr_tail=err, **parse_counts(out + "\n" + err),
            )
        except OSError:
            return TestResult(group=group.name, status="ERROR",
                              duration=round(time.monotonic() - started, 3),
                              stderr_tail="Unable to start test command")


def run_tests(groups: list[TestGroup], root: Path) -> list[TestResult]:
    return [run_group(group, root) for group in groups]
