# Appointment service fixture

Run from this directory after installing the gate's `demo` extra:

```bash
python -m pytest tests -q
python -m uvicorn backend.app:app --reload
```

Routes: `POST /appointments`, `GET /appointments/{id}`, `DELETE /appointments/{id}`.
Creation takes `patient_id`, `provider_id`, timezone-aware `scheduled_at`. Returned
appointments include an ID and `status: scheduled`. Duplicate provider/time returns
409; missing IDs return 404; invalid inputs return 422. Deletion frees the slot.

Storage is in-memory, protected by a lock, and resets when the process restarts.
Use the repository's `python scripts/demo.py` for an isolated regression/fix run
with real commits and reports. See `docs/demo.md` for the full walkthrough.
