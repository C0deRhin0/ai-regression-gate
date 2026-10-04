# GitHub Actions

The workflows live at the repository root's `.github/workflows/`. Publish the
`codebase` directory as the Git repository root (it contains this package and
the workflows). `regression-gate.yml` runs on PRs targeting `main`, checks out
the exact PR head, fetches full history, installs dependencies on Python 3.12,
validates `.argate.yml`, and evaluates the base SHA against head SHA.

The CLI writes its Markdown report to `$GITHUB_STEP_SUMMARY` automatically. The
evaluation step uses the CLI exit code unchanged. Artifacts upload with
`if: always()` so blocked evaluations remain auditable. `ci.yml` verifies the
gate itself, packaging, and both regression/fix scenarios on Python 3.12/3.14.

After pushing and opening a PR, add **Regression Gate / Release readiness** as a
required status check in your GitHub branch rules for `main`. The workflow's
job name is `Release readiness`; select the matching check shown by GitHub.
Enable Actions if repository policy disables it. No GitHub API token, PR comment
permission or model secret is needed. Repository policy/branch rules require
owner configuration; the tool does not change them.

Required checks should also be protected by code review on `.argate.yml`, tests,
and workflows. A PR can alter its own gate configuration, as with any repository
CI file. Use CODEOWNERS or repository rules appropriate to your organization.

To use this gate in a different repository, install the package and replace test
commands/component paths with that repository's checks. Preserve a full checkout,
use environment variables for SHA arguments, and install the languages/test tools
the configured commands require. No staging deployment is performed by this tool.
<!-- Clarify implementation notes for github actions documentation -->
