"""
Background job queue — turns the long-running /add pipeline into a
submit-then-poll flow so an HTTP client (or browser) never has to hold a
connection open for five minutes.

Design decisions and why:

  • SINGLE worker thread, not a pool. This is deliberate. Two pipelines running
    at once would collide on three shared resources:
      1. the local Qdrant store, which allows only one writer,
      2. the scraper's fixed `temp_stream.mp3` filename,
      3. the module-level embedding/reranker model singletons.
    Serialising the work sidesteps all three without a rewrite. Throughput is
    not the bottleneck here — a single video takes minutes and is dominated by
    network and LLM latency, not CPU contention.

  • In-memory registry + a JSON snapshot on disk. The snapshot lets a frontend
    still list past jobs after a server restart. Jobs that were mid-flight when
    the process died are marked `interrupted` on load rather than silently
    reappearing as `running`, which would be a lie.

  • Cancellation is cooperative. A queued job is dropped before it starts; a
    running job stops at the next step boundary. There is no way to kill a
    Gemini call mid-flight, so we do not pretend otherwise.

  • Per-job log capture. Pipeline steps already print progress to stdout, so we
    tee stdout into the job's ring buffer while it runs. The frontend gets real
    progress text for free, and the terminal still shows it too.
"""

import io
import json
import os
import queue
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# ─── STATUS CONSTANTS ──────────────────────────────────────────────────────────

QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"
INTERRUPTED = "interrupted"   # process died while the job was queued or running

TERMINAL_STATES = {DONE, FAILED, CANCELLED, INTERRUPTED}

# Keep finished jobs around this long so a frontend can still read the result.
JOB_RETENTION_SECONDS = 24 * 3600
MAX_LOG_LINES = 400


class JobCancelled(Exception):
    """Raised inside a worker when the job has been cancelled between steps."""


# ─── JOB ───────────────────────────────────────────────────────────────────────

@dataclass
class Job:
    id: str
    kind: str                        # e.g. "add_video"
    params: dict[str, Any]
    steps: list[str]                 # ordered human-readable step names
    status: str = QUEUED
    step_index: int = 0              # how many steps are COMPLETE
    current_step: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    log: list[str] = field(default_factory=list)

    _cancel: bool = field(default=False, repr=False)
    # Back-reference to the owning store, set at submit time. Needed so progress
    # updates persist to the right snapshot instead of a module-level default.
    _owner: Any = field(default=None, repr=False, compare=False)

    # ── progress reporting, called from inside the worker function ──

    def _persist(self) -> None:
        if self._owner is not None:
            self._owner._touch(self)

    def start_step(self, name: str) -> None:
        """Mark a named step as in progress. Raises JobCancelled if cancelled."""
        self.check_cancelled()
        self.current_step = name
        self._persist()

    def finish_step(self) -> None:
        """Mark the current step complete and advance the progress counter."""
        self.step_index = min(self.step_index + 1, len(self.steps))
        self._persist()

    def log_line(self, text: str) -> None:
        """Append a line to the job log, trimming the oldest when full."""
        for line in str(text).splitlines():
            line = line.rstrip()
            if not line:
                continue
            self.log.append(line)
        if len(self.log) > MAX_LOG_LINES:
            del self.log[: len(self.log) - MAX_LOG_LINES]

    def check_cancelled(self) -> None:
        if self._cancel:
            raise JobCancelled(f"job {self.id} cancelled")

    # ── serialisation for the API ──

    @property
    def progress(self) -> int:
        """Completed steps as a percentage (0-100)."""
        if not self.steps:
            return 100 if self.status == DONE else 0
        return int(100 * self.step_index / len(self.steps))

    def to_dict(self, include_log: bool = True) -> dict[str, Any]:
        d = {
            "job_id": self.id,
            "kind": self.kind,
            "params": self.params,
            "status": self.status,
            "steps": self.steps,
            "step_index": self.step_index,
            "current_step": self.current_step,
            "progress": self.progress,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": (
                round((self.finished_at or time.time()) - self.started_at, 1)
                if self.started_at else None
            ),
            "error": self.error,
            "result": self.result,
        }
        if include_log:
            d["log"] = self.log[-60:]   # tail only; full log via ?full_log=true
        return d


# ─── THREAD-AWARE STDOUT CAPTURE ───────────────────────────────────────────────
#
# The pipeline steps report progress with print(), and we want that text in the
# job log. The obvious tool, contextlib.redirect_stdout, is the wrong one: it
# replaces sys.stdout for the WHOLE process, so a concurrent /chat request's
# output would be swallowed into whichever job happened to be running.
#
# Instead we install one proxy on sys.stdout for the lifetime of the process and
# route each write by the calling thread. Only the worker thread's writes are
# teed into a job log; every other thread passes straight through untouched.

_current_job = threading.local()


class _ThreadRoutedStdout(io.TextIOBase):
    """sys.stdout proxy that tees to a job log only for threads running a job."""

    def __init__(self, real):
        self._real = real
        self._buffers: dict[int, str] = {}

    def write(self, s: str) -> int:
        try:
            self._real.write(s)
        except Exception:
            pass

        job = getattr(_current_job, "job", None)
        if job is None:
            return len(s)

        # Accumulate and emit whole lines. \r is treated as a line end so
        # yt-dlp/tqdm style progress updates still land in the log.
        tid = threading.get_ident()
        buf = self._buffers.get(tid, "") + s
        while True:
            positions = [i for i in (buf.find("\n"), buf.find("\r")) if i != -1]
            if not positions:
                break
            idx = min(positions)
            line, buf = buf[:idx], buf[idx + 1:]
            if line.strip():
                job.log_line(line)
        self._buffers[tid] = buf[-4096:]   # bound the partial-line buffer
        return len(s)

    def flush(self) -> None:
        try:
            self._real.flush()
        except Exception:
            pass

    def isatty(self) -> bool:
        try:
            return self._real.isatty()
        except Exception:
            return False


_stdout_install_lock = threading.Lock()


def _install_stdout_proxy() -> None:
    """
    Ensure sys.stdout is our routing proxy.

    Re-checks rather than installing once, because test runners (pytest capsys)
    and notebook kernels legitimately replace sys.stdout underneath us. If the
    current stdout is not our proxy, we wrap whatever is there now.
    """
    with _stdout_install_lock:
        if not isinstance(sys.stdout, _ThreadRoutedStdout):
            sys.stdout = _ThreadRoutedStdout(sys.stdout)


class _capture_into:
    """Context manager binding the current thread's prints to a job's log."""

    def __init__(self, job: Job):
        self._job = job

    def __enter__(self):
        _install_stdout_proxy()
        _current_job.job = self._job
        return self._job

    def __exit__(self, *exc):
        try:
            sys.stdout.flush()
        except Exception:
            pass
        _current_job.job = None
        return False


# ─── STORE + WORKER ────────────────────────────────────────────────────────────

class JobStore:
    """Thread-safe job registry with one serial background worker."""

    def __init__(self, snapshot_path: Path | None = None):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.RLock()
        self._queue: queue.Queue[str] = queue.Queue()
        self._fns: dict[str, Callable[[Job], dict[str, Any]]] = {}
        self._worker: threading.Thread | None = None
        self._snapshot_path = snapshot_path
        self._loaded = False

    # ── snapshot persistence ──

    def _snapshot(self) -> None:
        """Write all jobs to disk atomically (temp file + rename)."""
        if not self._snapshot_path:
            return
        try:
            with self._lock:   # RLock: safe to call from inside a locked section
                payload = [j.to_dict(include_log=False) for j in self._jobs.values()]
            self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._snapshot_path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp, self._snapshot_path)   # atomic on POSIX
        except Exception:
            pass  # never let bookkeeping break a running pipeline

    def load_snapshot(self) -> None:
        """Restore past jobs; anything left mid-flight becomes `interrupted`."""
        if self._loaded or not self._snapshot_path or not self._snapshot_path.exists():
            self._loaded = True
            return
        try:
            with open(self._snapshot_path, encoding="utf-8") as f:
                rows = json.load(f)
            with self._lock:
                for r in rows:
                    status = r.get("status", INTERRUPTED)
                    if status in (QUEUED, RUNNING):
                        status = INTERRUPTED
                    job = Job(
                        id=r["job_id"], kind=r.get("kind", "?"), params=r.get("params", {}),
                        steps=r.get("steps", []), status=status,
                        step_index=r.get("step_index", 0), current_step=r.get("current_step"),
                        created_at=r.get("created_at", time.time()),
                        started_at=r.get("started_at"), finished_at=r.get("finished_at"),
                        error=r.get("error") or ("Server restarted while this job was in flight."
                                                 if status == INTERRUPTED else None),
                        result=r.get("result"),
                    )
                    self._jobs[job.id] = job
        except Exception:
            pass
        self._loaded = True

    def _touch(self, job: Job) -> None:
        self._snapshot()

    # ── registration + submission ──

    def register(self, kind: str, fn: Callable[[Job], dict[str, Any]]) -> None:
        """Bind a job kind to the function that executes it."""
        self._fns[kind] = fn

    def submit(self, kind: str, params: dict[str, Any], steps: list[str]) -> Job:
        """Create a job, put it on the queue, and return it immediately."""
        if kind not in self._fns:
            raise KeyError(f"No handler registered for job kind '{kind}'")

        job = Job(id=uuid.uuid4().hex[:12], kind=kind, params=params, steps=steps, _owner=self)
        with self._lock:
            self._prune_locked()
            self._jobs[job.id] = job
        self._queue.put(job.id)
        self._ensure_worker()
        self._snapshot()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, status: str | None = None, limit: int = 50) -> list[Job]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs[:limit]

    def queue_depth(self) -> int:
        return self._queue.qsize()

    def cancel(self, job_id: str) -> bool:
        """Cancel a queued job outright, or ask a running job to stop at the next step."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status in TERMINAL_STATES:
                return False
            job._cancel = True
            if job.status == QUEUED:
                job.status = CANCELLED
                job.finished_at = time.time()
        self._snapshot()
        return True

    def _prune_locked(self) -> None:
        """Drop finished jobs older than the retention window."""
        cutoff = time.time() - JOB_RETENTION_SECONDS
        stale = [
            jid for jid, j in self._jobs.items()
            if j.status in TERMINAL_STATES and (j.finished_at or j.created_at) < cutoff
        ]
        for jid in stale:
            del self._jobs[jid]

    # ── worker ──

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._worker = threading.Thread(target=self._run_forever, name="job-worker", daemon=True)
            self._worker.start()

    def _run_forever(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self._run_one(job_id)
            except Exception:
                pass  # a crash in one job must not kill the worker
            finally:
                self._queue.task_done()

    def _run_one(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None or job.status in TERMINAL_STATES:
            return  # cancelled while queued

        with self._lock:
            job.status = RUNNING
            job.started_at = time.time()
        self._snapshot()

        fn = self._fns[job.kind]
        status, error, result = DONE, None, None
        try:
            with _capture_into(job):
                result = fn(job)
        except JobCancelled:
            status, error = CANCELLED, "Cancelled by request."
        except Exception as e:
            status, error = FAILED, f"{type(e).__name__}: {e}"
            job.log_line(f"ERROR: {error}")

        # Publish the terminal state and persist it together, so an observer
        # reading the snapshot can never see a job that finished in memory but
        # is still recorded as running on disk.
        with self._lock:
            job.status = status
            job.error = error
            job.finished_at = time.time()
            if status == DONE:
                job.result = result
                job.step_index = len(job.steps)
                job.current_step = None
            self._snapshot()


# ─── MODULE SINGLETON ──────────────────────────────────────────────────────────

def _default_snapshot_path() -> Path:
    try:
        from core.config import DATA_DIR
        return Path(DATA_DIR) / "jobs.json"
    except Exception:
        return Path("data") / "jobs.json"


_store = JobStore(snapshot_path=_default_snapshot_path())


def get_store() -> JobStore:
    """The process-wide job store."""
    _store.load_snapshot()
    return _store
