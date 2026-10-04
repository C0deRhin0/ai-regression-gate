# Security and the model boundary

`deterministic_only` is the default. No model request is created. `local_llm`
accepts only loopback hosts (`localhost`, `127.0.0.1`, `::1`); use a genuinely
local model server. `external_llm` is explicit opt-in and requires HTTPS.
Endpoints cannot embed credentials, query strings, or fragments. Redirects are
disabled and ambient proxy variables are ignored to preserve the chosen boundary.

The built-in exclusions cover nested `.env`/`.env.*`, private-key/certificate
files (`*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, `id_ed25519*`),
`secrets.*`, `credentials.*`, `secrets/`, `.ssh/`, `.git/`, `.npmrc`, and `.netrc`.
Custom `security.sensitive_paths` only adds exclusions. Renaming a sensitive file
to a public-looking path still excludes it. Excluded paths are audited, contents
are omitted. If patch boundaries cannot be matched safely, transmission fails closed.

Remaining candidate text is scanned for bearer tokens, common key/token formats,
password/key assignments, credential-bearing connection URLs and private-key
blocks. Detection replaces values with `[REDACTED]` and blocks external AI by
default. `allow_redacted_external: true` explicitly permits only the sanitized
payload after scanning; it never permits sensitive-file contents or raw secrets.
The guard is deliberately lightweight, not a full secret scanner. Add sensitive
paths for proprietary data and keep external mode disabled if confidentiality
requires stronger guarantees. Already committed secrets should be rotated.

The provider sees candidate file paths, sanitized diff, component names, configured
test-group names, deterministic findings for included files, and the output schema.
It receives no environment dump, test commands, test output, raw configuration, or
excluded file contents. The request size is capped, and oversized metadata fails
closed. Structured responses have bounded fields; unknown test recommendations
and risk paths are ignored. Untrusted diff instructions cannot change gate policy.

API credentials live in the environment variable named by `ai.api_key_env`.
They are not included in errors, logs or reports. Model responses and subprocess
output are sanitized too. Reports retain audit paths and test commands, but no
raw patch. Logs contain evaluation IDs, refs, selections, durations, provider mode
and decisions. `--verbose` never dumps requests, secrets or environment variables.

Configured shell commands execute with the current user's authority. Review
configuration and code before running an untrusted PR locally. The workflow uses
`pull_request`, read-only permissions and no external AI credentials; never change
it to a secret-bearing `pull_request_target` job that executes untrusted PR code.
GitHub-hosted runners isolate CI execution. For hostile-code isolation locally,
use a disposable environment; the CLI itself is not an execution sandbox.

Provider outages and malformed JSON are reported as unavailable while deterministic
checks continue. An explicit availability policy may block, but AI never overrides
required failures. Report output is bounded; unknown secret formats remain a
limitation of pattern-based sanitization. Reports are engineering evidence, not
regulatory certification.
<!-- Capture a cleanup item for security documentation -->
