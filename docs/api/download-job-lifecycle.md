# Download Job Lifecycle

```text
queued -> downloading -> completed
                     \-> failed
queued -> cancelled
downloading -> cancelled
```

Jobs are retained for 24 hours after completion (override via top-level `download_job_retention_hours` in `unshackle.yaml`). The server runs up to 2 concurrent download jobs by default; override via top-level `max_concurrent_downloads`. This is independent of `serve.downloads`, which controls parallel tracks **within** a single job.

Remote sessions are managed by `SessionStore` (`unshackle/core/api/session_store.py`); idle sessions and their `InputBridge` instances are cleaned up by a background loop started/stopped with the app lifecycle.
