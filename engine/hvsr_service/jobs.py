"""Background job manager: thread pool, progress, cooperative cancellation."""

from __future__ import annotations

import datetime as _dt
import logging
import os
import threading
import time
import traceback
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

log = logging.getLogger("hvsr_service.jobs")

STATUSES = ("queued", "running", "done", "failed", "cancelled")


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Job:
    def __init__(self, kind: str, meta: dict | None = None):
        self.id = uuid.uuid4().hex
        self.kind = kind
        self.status = "queued"
        self.progress = 0.0
        self.message = "queued"
        self.result: Any = None
        self.error: dict | None = None
        self.meta = meta or {}
        self.created_at = _now()
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.cancel_event = threading.Event()
        self._last_progress_emit = 0.0
        self._lock = threading.Lock()

    def report(self, fraction: float, message: str | None = None) -> None:
        """Progress callback handed to the engine (throttled to ~10 Hz)."""
        now = time.monotonic()
        with self._lock:
            changed_msg = message is not None and message != self.message
            if not changed_msg and now - self._last_progress_emit < 0.1 and fraction < 1.0:
                return
            self.progress = max(0.0, min(1.0, float(fraction)))
            if message is not None:
                self.message = str(message)
            self._last_progress_emit = now

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "status": self.status, "progress": round(self.progress, 4),
            "message": self.message, "result": self.result, "error": self.error, "meta": self.meta,
            "created_at": self.created_at, "started_at": self.started_at, "finished_at": self.finished_at,
        }


class JobManager:
    def __init__(self, max_workers: int | None = None, keep: int = 200):
        if max_workers is None:
            max_workers = max(1, (os.cpu_count() or 2) // 2)
        self.max_workers = max_workers
        self.keep = keep
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="hvsr-job")
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._lock = threading.Lock()
        self._running = 0

    # ------------------------------------------------------------------ public
    def submit(self, kind: str, fn: Callable[[Job], Any], meta: dict | None = None) -> Job:
        """`fn(job)` runs on the pool; it may call `job.report()` and must honour `job.cancel_event`."""
        job = Job(kind, meta)
        with self._lock:
            self._jobs[job.id] = job
            self._trim()
        self._pool.submit(self._run, job, fn)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, limit: int = 50) -> list[dict]:
        with self._lock:
            items = list(self._jobs.values())[-limit:]
        return [j.to_dict() for j in reversed(items)]

    def cancel(self, job_id: str) -> Job | None:
        job = self.get(job_id)
        if job is None:
            return None
        if job.status in ("queued", "running"):
            job.cancel_event.set()
            if job.status == "queued":
                job.status = "cancelled"
                job.message = "cancelled before start"
                job.finished_at = _now()
        return job

    @property
    def running(self) -> int:
        return self._running

    def shutdown(self) -> None:
        for job in list(self._jobs.values()):
            job.cancel_event.set()
        self._pool.shutdown(wait=False, cancel_futures=True)

    # ----------------------------------------------------------------- private
    def _trim(self) -> None:
        while len(self._jobs) > self.keep:
            oldest_id, oldest = next(iter(self._jobs.items()))
            if oldest.status in ("queued", "running"):
                break
            self._jobs.pop(oldest_id)

    def _run(self, job: Job, fn: Callable[[Job], Any]) -> None:
        if job.cancel_event.is_set():
            job.status = "cancelled"
            job.finished_at = job.finished_at or _now()
            return
        job.status = "running"
        job.started_at = _now()
        job.message = "running"
        with self._lock:
            self._running += 1
        try:
            result = fn(job)
            if job.cancel_event.is_set():
                job.status = "cancelled"
                job.message = "cancelled"
            else:
                job.result = result
                job.progress = 1.0
                job.status = "done"
                job.message = "done"
        except BaseException as exc:  # noqa: BLE001 - a job must never kill the worker
            try:
                from hvsr_engine.errors import CancelledError
            except Exception:  # pragma: no cover
                CancelledError = ()  # type: ignore
            if (CancelledError and isinstance(exc, CancelledError)) or job.cancel_event.is_set():
                job.status = "cancelled"
                job.message = "cancelled"
            else:
                from .errors import translate_exception

                err = translate_exception(exc)
                job.status = "failed"
                job.message = f"failed: {err.message}"
                job.error = {"code": err.code, "message": err.message, "details": err.details,
                             "traceback": traceback.format_exc()[-4000:]}
                log.warning("Job %s (%s) failed: %s", job.id, job.kind, err.message)
        finally:
            job.finished_at = _now()
            with self._lock:
                self._running -= 1
