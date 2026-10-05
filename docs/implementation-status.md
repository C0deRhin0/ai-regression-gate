# Implementation and handoff

The implementation follows phases 0–8 of `AI_Regression_Gate_Implementation_Plan.md`.
Optional stretch features and an HTTP interface for the gate are intentionally
outside the required scope.

| Phase | Delivered | Verification |
|---|---|---|
| 0 Foundation | Installable package, Typer commands, Pydantic config, structured logs | Install, CLI help, config validation; schema unit tests |
| 1 Git | Validated SHAs, status, rename/binary support, line counts and patches | Temporary-repository integration tests |
| 2 Impact/risk | Component globs, configurable risk rules, sensitive classification | Mapping/risk/path tests, quoted-path integration test |
| 3 Tests | Required/path/policy/advisory selection, commands, timeouts and safe output | Runner PASS/FAIL/TIMEOUT/ERROR, selection tests |
| 4 Policy | READY/WARNING/BLOCKED, deterministic reasons, coverage and exit codes | Policy matrix and CLI tests for all states |
| 5 Reports | Markdown, JSON schema version, IDs, hashes, commands/results/audit metadata | All-state report assertions, secret exclusion checks |
| 6 AI | Deterministic provider, Ollama, OpenAI-compatible adapter, sanitized structured advice | Mock responses, actual local HTTP transport, malformed/timeouts/unavailable/redirect tests; fallback gate equivalence |
| 7 CI | PR head checkout, Python setup, install/validate/evaluate, summary, always-upload artifacts, required check on main | Hosted main/PR CI passed; intentional regression produced a failed check and BLOCKED merge state; restored PR passed |
| 8 Demo/polish | FastAPI appointment service, temporary Git regression/fix commits, demo script, docs and README diagram | Fresh-clone installation and full demo; duplicate regression FAIL/BLOCKED/1 and fix PASS/READY/0 |

## Verified results

- Python 3.12.15: 82 tests passed; 97.97% gate coverage, exceeding the configured 80% minimum.
- Python 3.14.7: 82 tests passed.
- Ruff and Git whitespace checks passed; tracked worktree clean after commits.
- Fresh Git clone installed with the documented `dev,demo` extras: configuration
  validation, full suite, full demo, and self-evaluation passed.
- Built wheel installed as a non-editable package in a separate environment;
  the packaged report template and both demo outcomes worked.
- Self-evaluation: appointment-regression PASS (9 tests), core PASS (82 tests),
  demo PASS, coverage 97.97%, decision READY.
- Demo: duplicate regression FAIL (2 failed, 7 passed), BLOCKED/exit 1; restored
  validation PASS (9 passed), READY/exit 0. Both changed only the application file.
- No real credentials were added; synthetic secret strings exist only to test the
  redaction boundary. No `.env`, key, or credential files are tracked.

Local evidence is retained under `reports/self-evaluation`, `reports/demo`,
`reports/wheel-demo`, `reports/packaging`, and `reports/hosted-verification` (ignored
by Git). Hosted run links and branch-rule details are in `ci-smoke-test.md`.
Repeat verification on a committed feature branch:

```bash
ruff check .
python -m pytest --cov=argate --cov-report=xml --cov-fail-under=80 -q
python scripts/demo.py
git fetch origin
argate evaluate --base origin/main --head HEAD --report-dir reports/self-evaluation
```

## Repository setup completed

The repository is published at https://github.com/C0deRhin0/ai-regression-gate.
Actions is enabled. PR #1 verified green, intentional red, and restored green
results, including downloaded report artifacts. Main requires a PR and an
up-to-date successful `Release readiness` check from GitHub Actions, including
for admins. Direct appointment tests are now included in the root gate.

## Optional setup

1. Optional: start Docker Desktop and build the provided Dockerfile. The local
   Docker daemon was stopped during implementation, so a container build/run was
   not verified here. Package installation and tests were verified independently.
2. Optional: choose/install a local model, or explicitly opt in to an external
   provider and set its API key environment variable. The complete deterministic
   workflow and demo require neither a model nor credentials.

For another project, adapt `.argate.example.yml` to its components and real test
commands. Treat config/test code as trusted code; see `security.md` before opting
in to an external model or executing untrusted PR commands.
