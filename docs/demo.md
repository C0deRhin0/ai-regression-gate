# Two-minute demo

From a fresh clone with Python 3.12+ and Git:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,demo]'
python scripts/demo.py
```

Say: “AI helps us develop quickly; staging movement still depends on deterministic
QA.” The script copies the appointment service to a temporary seed repository,
commits the baseline, then clones it into a separate temporary checkout. It
commits an accidental removal of duplicate-booking validation. The changed
`backend/app.py` maps to `scheduling`; its required regression test is selected.

The gate reports `BLOCKED`, exit 1. Open `reports/demo/blocked/report.md` and show
the failed duplicate-provider/time assertions, selected test reason, commit SHAs,
and policy result. The script restores validation, commits the fix, and evaluates
the regression commit against the fixed head. This reports `READY FOR STAGING`,
exit 0. Open `reports/demo/ready/report.md`; compare results and the audit metadata.

The script asserts statuses, exit codes, scheduling selection, and FAIL/PASS
results. Temporary repositories are cleaned even on error; reports survive in
your chosen `--report-dir`. It neither switches your branch nor modifies tracked
files. Both reports are uploaded by CI as artifacts.

For a manual code tour, open `examples/appointment-service/backend/app.py` at
`DEMO_DUPLICATE_GUARD`. The regression changes `if duplicate:` to `if False:`.
The fix restores `if duplicate:`. The tests also cover equivalent timezones,
different providers, cancelled slots, invalid input and missing appointments.

To run the API separately:

```bash
cd examples/appointment-service
python -m uvicorn backend.app:app --reload
```

Explore `/docs`. This in-memory API is only a test fixture. Close with:
“The release authority is explicit policy and executed tests; AI supplies context.”
<!-- Review follow-up details for demo documentation -->
