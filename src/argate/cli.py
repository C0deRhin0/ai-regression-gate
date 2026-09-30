from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from argate.analysis.secrets import safe_text
from argate.config import load_config
from argate.logging import configure
from argate.workflow import run

app = typer.Typer(help="AI Regression Gate — deterministic release readiness, optional AI advice.",
                  no_args_is_help=True)
config_app = typer.Typer(help="Configuration tools")
app.add_typer(config_app, name="config")
console = Console(highlight=False)


@config_app.command("validate")
def validate(config: Annotated[Path, typer.Option("--config")] = Path(".argate.yml")):
    try:
        load_config(config)
    except ValueError as exc:
        console.print(safe_text(str(exc)), style="red", markup=False)
        raise typer.Exit(1) from exc
    console.print("Configuration valid", style="green")


def execute(operation, base, head, config, report_dir, no_ai, verbose):
    configure(verbose)
    try:
        report = run(operation, base, head, config, report_dir, no_ai)
    except (ValueError, OSError) as exc:
        console.print(f"Evaluation error: {safe_text(str(exc))}", style="red", markup=False)
        raise typer.Exit(1) from exc
    console.print("AI Regression Gate", style="bold")
    console.print(f"Change: {len(report.change_summary.changed_files)} files; "
                  f"+{report.change_summary.insertions}/-{report.change_summary.deletions}", markup=False)
    console.print(f"Components: {', '.join(report.affected_components) or 'none'}", markup=False)
    console.print(f"Risk: {report.overall_risk.upper()}")
    for group in report.selected_tests:
        console.print(f"Selected: {group.name} — {'; '.join(group.reasons)}", markup=False)
    for result in report.test_results:
        console.print(f"{result.status:7} {result.group} {result.duration}s; passed={result.passed}", markup=False)
    if report.coverage.enabled:
        console.print(f"Coverage: {report.coverage.current}%")
    decision = report.gate_decision.status
    label = "READY FOR STAGING" if decision == "READY" else decision
    console.print(f"Decision: {label}", style="green" if decision == "READY" else "yellow" if decision == "WARNING" else "red")
    for reason in report.gate_decision.reasons:
        console.print(f"  {safe_text(reason)}", markup=False)
    console.print(f"Report: {report_dir / 'report.md'}", markup=False)
    if operation == "analyze":
        code = 0
    elif operation == "test":
        required = {group.name for group in report.selected_tests if group.required}
        code = int(any(result.group in required and result.status != "PASS" for result in report.test_results))
    else:
        code = int(decision == "BLOCKED")
    raise typer.Exit(code)


@app.command()
def evaluate(
    base: Annotated[str, typer.Option()] = "origin/main",
    head: Annotated[str, typer.Option()] = "HEAD",
    config: Annotated[Path, typer.Option()] = Path(".argate.yml"),
    report_dir: Annotated[Path, typer.Option()] = Path("reports"),
    no_ai: Annotated[bool, typer.Option()] = False,
    verbose: Annotated[bool, typer.Option()] = False,
):
    """Collect, analyze, test, and evaluate release policy."""
    execute("evaluate", base, head, config, report_dir, no_ai, verbose)


@app.command()
def analyze(
    base: Annotated[str, typer.Option()] = "origin/main",
    head: Annotated[str, typer.Option()] = "HEAD",
    config: Annotated[Path, typer.Option()] = Path(".argate.yml"),
    report_dir: Annotated[Path, typer.Option()] = Path("reports"),
    no_ai: Annotated[bool, typer.Option()] = False,
    verbose: Annotated[bool, typer.Option()] = False,
):
    """Analyze changes and selections without executing commands."""
    execute("analyze", base, head, config, report_dir, no_ai, verbose)


@app.command("test")
def test_only(
    base: Annotated[str, typer.Option()] = "origin/main",
    head: Annotated[str, typer.Option()] = "HEAD",
    config: Annotated[Path, typer.Option()] = Path(".argate.yml"),
    report_dir: Annotated[Path, typer.Option()] = Path("reports"),
    no_ai: Annotated[bool, typer.Option()] = True,
    verbose: Annotated[bool, typer.Option()] = False,
):
    """Select and run tests; does not certify release readiness."""
    execute("test", base, head, config, report_dir, no_ai, verbose)


if __name__ == "__main__":
    app()
