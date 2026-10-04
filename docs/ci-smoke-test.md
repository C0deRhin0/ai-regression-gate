# Hosted CI verification

The initial `main` build passed on Python 3.12 and 3.14, including the package
build and the isolated duplicate-appointment regression/fix demonstration:

https://github.com/C0deRhin0/ai-regression-gate/actions/runs/37205067039

The verification PR exercises the hosted `Release readiness` check against its
actual base and head commits. The initial PR evaluation passed with 82 core tests,
the isolated demo, 97.97% coverage, and downloadable Markdown/JSON artifacts:

https://github.com/C0deRhin0/ai-regression-gate/pull/1

https://github.com/C0deRhin0/ai-regression-gate/actions/runs/37205326236

The same PR verified an intentional appointment-validation regression. The hosted
gate returned BLOCKED/exit 1 and GitHub reported the PR's merge state as BLOCKED:

https://github.com/C0deRhin0/ai-regression-gate/actions/runs/37205629261

That run's `appointment-regression` result contains the two expected failed
assertions (duplicate provider/time and equivalent timezone), with seven passing
appointment tests. The original validation is restored in the final PR revision.
Only the restored, passing version is eligible for merging.

The root gate also runs the appointment regression tests directly. This ensures
an already-broken fixture produces explicit duplicate-booking assertion failures
in the parent PR report, even when the isolated demo cannot create its expected
baseline/regression commits.

`main` now requires a pull request, an up-to-date branch, and a successful
`Release readiness` check from GitHub Actions (app ID 15368). The rule also applies
to administrators; force pushes and branch deletion are disabled. No independent
reviewer is required for this solo-maintained repository.

GitHub logs and downloaded report artifacts were inspected through the CLI/API.
The job-summary rendering could not be visually inspected because no browser was
connected during verification.
