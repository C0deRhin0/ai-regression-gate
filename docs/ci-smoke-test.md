# Hosted CI verification

The initial `main` build passed on Python 3.12 and 3.14, including the package
build and the isolated duplicate-appointment regression/fix demonstration:

https://github.com/C0deRhin0/ai-regression-gate/actions/runs/37205067039

The verification PR exercises the hosted `Release readiness` check against its
actual base and head commits. Acceptance requires a successful deterministic
evaluation, Markdown/JSON artifacts, and a visible job summary.

The same PR is used to verify an intentional appointment-validation regression
returns a failed required check before the original validation is restored.
Only the restored, passing version is eligible for merging.
