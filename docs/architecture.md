# Architecture

The CLI delegates to `workflow.run`. Pydantic schemas reject unknown fields and
broken references before any command executes. The normalized configuration is
hashed with SHA-256; each evaluation gets a UTC timestamp and unique ID.

1. **Collection** resolves base/head to commit SHAs and uses a direct two-commit
   diff, not an implicit merge-base diff. Git runs without external diff drivers
   or text conversion. NUL-delimited status/numstat preserve spaces, tabs and
   renames. Binary statistics are marked unknown (zero numeric line counts).
2. **Impact** maps both old and new paths on renames to configured components.
   Path globs have segment-aware `*`, cross-directory `**`, and `?` semantics.
3. **Risk** uses the first matching user rule, then first matching default rule,
   then medium source risk. Overall risk is the maximum deterministic severity.
4. **AI boundary** excludes sensitive paths, scans/redacts candidate diff,
   caps the payload, and validates model JSON. AI can add known groups; it
   cannot remove selections, execute invented commands, or approve releases.
5. **Selection** unions all globally required groups, affected component mappings,
   component-owned groups, policy mandatory groups, and known AI recommendations.
   Ordering is stable and selection reasons are preserved.
6. **Execution** requires a clean tracked tree at the exact head SHA. Commands
   run sequentially in the repository root, independently even after failure.
   Per-group timeouts terminate the process group on POSIX. Background descendants
   are cleaned even after shell completion. Child commands do not inherit
   `GITHUB_STEP_SUMMARY`, keeping the enclosing evaluation's CI summary concise.
   Output is captured
   in temporary files, sanitized, bounded, and cleaned up. Exit status decides
   PASS/FAIL; pytest counts are best-effort information only.
7. **Policy** checks required results, mandatory execution, per-path high-risk
   verification, explicit blocker paths, and coverage. Optional failures and
   advisory risks warn. Required failures always block. AI outages have no gate
   effect unless `block_on_ai_unavailable` is explicitly enabled.
8. **Reporting** emits versioned JSON and a packaged Jinja Markdown template.
   Source patches are never persisted. JSON event logs persist even without verbose
   console output. GitHub summary writes require no API.

`analyze` uses SKIPPED results and never claims release readiness. `test` exits
based on required test results; full readiness requires `evaluate`. Operational
errors return exit 1 with a concise diagnostic rather than a false readiness
report. Configuration/test commands are trusted repository code, not a sandbox.

The same deterministic inputs produce the same mappings, risk and policy results.
IDs, timestamps, durations and captured command output naturally differ. Schema
version `1.0` identifies the JSON contract; future incompatible changes must bump
it. Coverage uses a fresh Cobertura report produced during this evaluation and
an optional supplied baseline, not historical analytics.
<!-- Refine the surrounding context for architecture documentation -->
