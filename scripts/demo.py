"""Produce real BLOCKED/READY reports in an isolated fresh Git clone."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def command(args, root, expected=0):
    result = subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=90)
    if result.returncode != expected:
        raise RuntimeError(f"Demo command failed ({result.returncode}): {result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def commit(root, message):
    command(["git", "add", "."], root)
    command(["git", "-c", "user.name=ARGate Demo", "-c", "user.email=demo@example.invalid",
             "commit", "-m", message], root)
    return command(["git", "rev-parse", "HEAD"], root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=Path("reports/demo"))
    args = parser.parse_args()
    destination = args.report_dir.resolve()
    source = Path(__file__).resolve().parents[1] / "examples" / "appointment-service"
    # Ensure subprocess test commands resolve the same interpreter as this script.
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    with tempfile.TemporaryDirectory(prefix="argate-demo-") as temporary:
        temporary = Path(temporary)
        seed = temporary / "seed"
        shutil.copytree(source, seed, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "reports"))
        command(["git", "init", "-b", "main"], seed)
        baseline = commit(seed, "Baseline: reject duplicate provider appointments")
        checkout = temporary / "checkout"
        command(["git", "clone", "--quiet", str(seed), str(checkout)], temporary)
        application = checkout / "backend" / "app.py"
        original = application.read_text()
        application.write_text(original.replace("if duplicate:  # DEMO_DUPLICATE_GUARD",
                                                "if False:  # DEMO_DUPLICATE_GUARD"))
        command(["git", "switch", "-c", "demo/regression"], checkout)
        regression = commit(checkout, "Regression: accidentally allow duplicate appointments")
        for label, head, expected_code, expected_status in [
            ("blocked", regression, 1, "BLOCKED"),
            ("ready", None, 0, "READY"),
        ]:
            if label == "ready":
                application.write_text(original)
                commit(checkout, "Fix: restore duplicate appointment validation")
                head = "HEAD"
                base = regression
            else:
                base = baseline
            report_dir = destination / label
            output = command([sys.executable, "-m", "argate.cli", "evaluate", "--base", base,
                              "--head", head, "--report-dir", str(report_dir)], checkout, expected=expected_code)
            report = json.loads((report_dir / "report.json").read_text())
            assert report["gate_decision"]["status"] == expected_status, report["gate_decision"]
            assert report["affected_components"] == ["scheduling"]
            assert report["selected_tests"][0]["name"] == "scheduling-regression"
            expected_test = "FAIL" if label == "blocked" else "PASS"
            assert report["test_results"][0]["status"] == expected_test
            print(f"\n{label.upper()} scenario\n{output}")
    print(f"\nVerified regression exit=1/BLOCKED and fix exit=0/READY. Reports: {destination}")


if __name__ == "__main__":
    main()
