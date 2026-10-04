# Configuration reference

The default file is `.argate.yml`; `--config PATH` selects another file. Unknown
fields, duplicate YAML keys, invalid values and undefined group/component references are rejected.
All path patterns use Git-root-relative POSIX paths. `*` matches within a path
segment, `**` crosses directories, `**/` also matches zero directories, and `?`
matches one non-slash character. Bracket and brace expansion are not supported.
Commands and coverage paths resolve from the Git root, even if config is nested.

| Field | Default | Meaning |
|---|---|---|
| `project.name` | `unnamed-project` | Human-readable audit name |
| `components` | `{}` | Named component mappings |
| `components.<name>.paths` | required | Nonempty list of globs; rename old/new paths both match |
| `components.<name>.tests` | `[]` | Existing groups selected when this component changes |
| `test_groups` | `{}` | Named, trusted shell commands |
| `test_groups.<name>.command` | required | Nonempty command, executed at Git root |
| `test_groups.<name>.required` | `false` | Globally selected on every evaluation; failure blocks |
| `test_groups.<name>.timeout_seconds` | `120` | Positive timeout up to 86400 seconds |
| `test_groups.<name>.component` | null | Existing component that also selects this group |
| `risk_rules` | `[]` | User rules, evaluated in listed order before built-ins |
| `risk_rules[].paths` | required | Nonempty glob list |
| `risk_rules[].severity` | required | `low`, `medium`, `high`, `critical` |
| `risk_rules[].category` | required | Audit category |
| `risk_rules[].description` | required | Finding explanation |
| `risk_rules[].suggested_test` | empty | Suggested verification |
| `quality_gates.require_all_required_tests` | `true` | Missing required execution blocks; failures always block |
| `quality_gates.minimum_coverage` | null | Absolute percent threshold; coverage must be enabled |
| `quality_gates.maximum_coverage_drop` | null | Drop threshold in percentage points; baseline required |
| `quality_gates.block_on_high_risk_without_tests` | `true` | Each high/critical changed path needs a passing mapped required group |
| `quality_gates.mandatory_test_groups` | `[]` | Groups always selected and required, regardless of their own flag |
| `quality_gates.blocker_paths` | `[]` | Any changed old/new path matching a glob blocks |
| `quality_gates.block_on_ai_unavailable` | `false` | Explicitly require enabled AI availability; no effect for disabled AI |
| `quality_gates.warnings_as_errors` | `false` | Convert any warning to BLOCKED/exit 1 |
| `coverage.enabled` | `false` | Read fresh configured Cobertura report after tests |
| `coverage.format` | `cobertura` | Only supported format |
| `coverage.path` | `coverage.xml` | Current report path, must be updated during test execution |
| `coverage.minimum` | null | Percent threshold, overrides quality-gate threshold |
| `coverage.maximum_drop` | null | Percentage-point threshold, overrides quality-gate threshold |
| `coverage.baseline` | null | Optional numeric baseline percentage |
| `coverage.baseline_path` | null | Optional Cobertura baseline file; takes precedence over numeric baseline |
| `ai.mode` | `deterministic_only` | `deterministic_only`, `local_llm`, `external_llm` (lowercase) |
| `ai.provider` | `openai_compatible` | `ollama` or `openai_compatible` |
| `ai.endpoint` | null | Server base URL; required when enabled |
| `ai.model` | null | Provider model name; required when enabled |
| `ai.api_key_env` | null | Name of credential environment variable; missing configured key means unavailable |
| `ai.timeout_seconds` | `30` | Positive provider timeout, up to 300 seconds |
| `ai.max_payload_bytes` | `32000` | 256–1000000; diff cap and serialized request guard |
| `ai.allow_redacted_external` | `false` | Permit sanitized candidate after redaction; exclusions remain mandatory |
| `security.sensitive_paths` | `[]` | Additional exclusion globs |

Coverage percentages and drops are constrained to 0–100. Missing, invalid or stale
coverage blocks whenever collection is enabled. A maximum-drop policy without a
baseline also blocks. A positive drop within the permitted threshold warns.

Default risk rules classify documentation/tests/styles low, source/dependencies/
ordinary config medium, and auth/security, migrations, contracts, payments,
integration adapters and CI/deployment high. The first matching rule wins; add
user rules to adapt ordering and severity to your repository. A test merely being
globally required does not prove it verifies every high-risk path: map it through
the relevant component too.

Local Ollama example:

```yaml
ai:
  mode: local_llm
  provider: ollama
  endpoint: http://127.0.0.1:11434
  model: your-installed-model
```

For OpenAI-compatible servers, the endpoint includes the API prefix, for example
`http://127.0.0.1:8080/v1`; the adapter appends `/chat/completions`. Ollama appends
`/api/generate`. External servers use `external_llm`, HTTPS and optionally
`api_key_env: ARGATE_API_KEY`. Source transmission is an explicit user choice.

Exit codes: `evaluate` READY/WARNING=0, BLOCKED/errors=1; `analyze` successful
analysis=0, errors=1; `test` required failures/errors=1, otherwise 0. All commands
accept `--base`, `--head`, `--config`, `--report-dir`, `--no-ai`, `--verbose`.
`config validate` accepts `--config`. Analyze/test reports cannot certify readiness.
