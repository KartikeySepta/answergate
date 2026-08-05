"""
Tests for the background job queue — offline, no network, no LLM calls.

  python3 -m pytest rag/tests/test_jobs.py -v
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.jobs import (CANCELLED, DONE, FAILED, INTERRUPTED, QUEUED, RUNNING,
                       Job, JobStore)


def _wait_for(predicate, timeout=5.0, interval=0.01):
    """Poll until predicate() is truthy or timeout elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


@pytest.fixture
def store(tmp_path):
    return JobStore(snapshot_path=tmp_path / "jobs.json")


# ─── HAPPY PATH ────────────────────────────────────────────────────────────────

def test_submit_returns_immediately_and_completes(store):
    """The whole point: submit must not block on the work."""
    def handler(job):
        for step in ("a", "b", "c"):
            job.start_step(step)
            time.sleep(0.02)
            job.finish_step()
        return {"ok": True}

    store.register("demo", handler)

    t0 = time.time()
    job = store.submit("demo", {"x": 1}, ["a", "b", "c"])
    submit_elapsed = time.time() - t0

    assert submit_elapsed < 0.05, "submit() must return without waiting for the work"
    # The worker may already have picked it up — either state proves submit didn't block.
    assert job.status in (QUEUED, RUNNING)

    assert _wait_for(lambda: job.status == DONE), f"job stuck in {job.status}"
    assert job.result == {"ok": True}
    assert job.progress == 100
    assert job.step_index == 3
    assert job.to_dict()["duration_seconds"] >= 0


def test_progress_advances_through_steps(store):
    gate = threading.Event()
    seen = []

    def handler(job):
        job.start_step("one")
        job.finish_step()
        seen.append(job.progress)
        gate.wait(2)
        job.start_step("two")
        job.finish_step()
        return {}

    store.register("demo", handler)
    job = store.submit("demo", {}, ["one", "two"])

    assert _wait_for(lambda: job.step_index == 1)
    assert job.progress == 50, "one of two steps done should read 50%"
    assert job.status == RUNNING
    gate.set()
    assert _wait_for(lambda: job.status == DONE)
    assert job.progress == 100


def test_stdout_is_captured_into_job_log(store):
    def handler(job):
        print("downloading audio")
        print("indexing chunks")
        return {}

    store.register("demo", handler)
    job = store.submit("demo", {}, ["only"])
    assert _wait_for(lambda: job.status == DONE)

    assert "downloading audio" in job.log
    assert "indexing chunks" in job.log


def test_other_threads_output_does_not_leak_into_job_log(store):
    """
    Regression: an earlier version used contextlib.redirect_stdout, which swaps
    sys.stdout process-wide. A concurrent /chat request's prints ended up inside
    whichever job was running. Capture must be per-thread.
    """
    job_running = threading.Event()
    outsider_done = threading.Event()

    def handler(job):
        print("job-own-line")
        job_running.set()
        outsider_done.wait(3)
        return {}

    store.register("demo", handler)
    job = store.submit("demo", {}, ["only"])

    assert job_running.wait(2)

    def outsider():
        print("UNRELATED-REQUEST-OUTPUT")
        outsider_done.set()

    t = threading.Thread(target=outsider)
    t.start()
    t.join(2)

    assert _wait_for(lambda: job.status == DONE)
    assert "job-own-line" in job.log
    assert not any("UNRELATED-REQUEST-OUTPUT" in line for line in job.log), \
        "another thread's stdout leaked into the job log"


# ─── FAILURE HANDLING ──────────────────────────────────────────────────────────

def test_failure_is_recorded_not_raised(store):
    def handler(job):
        raise ValueError("boom")

    store.register("demo", handler)
    job = store.submit("demo", {}, ["only"])
    assert _wait_for(lambda: job.status == FAILED)
    assert "ValueError: boom" in job.error


def test_worker_survives_a_failing_job(store):
    def bad(job):
        raise RuntimeError("nope")

    def good(job):
        return {"fine": True}

    store.register("bad", bad)
    store.register("good", good)

    j1 = store.submit("bad", {}, ["only"])
    j2 = store.submit("good", {}, ["only"])

    assert _wait_for(lambda: j1.status == FAILED)
    assert _wait_for(lambda: j2.status == DONE), "worker died after a failing job"


# ─── CANCELLATION ──────────────────────────────────────────────────────────────

def test_cancel_queued_job_never_runs(store):
    started = threading.Event()
    release = threading.Event()

    def blocker(job):
        started.set()
        release.wait(3)
        return {}

    ran = []

    def second(job):
        ran.append(True)
        return {}

    store.register("blocker", blocker)
    store.register("second", second)

    store.submit("blocker", {}, ["only"])
    assert started.wait(2)

    queued = store.submit("second", {}, ["only"])
    assert queued.status == QUEUED
    assert store.cancel(queued.id) is True
    assert queued.status == CANCELLED

    release.set()
    time.sleep(0.2)
    assert ran == [], "a cancelled queued job must never execute"


def test_cancel_running_job_stops_at_next_step(store):
    at_step_one = threading.Event()
    completed_steps = []

    def handler(job):
        job.start_step("one")
        job.finish_step()
        completed_steps.append("one")
        at_step_one.set()
        time.sleep(0.3)          # cancellation arrives during this window
        job.start_step("two")    # start_step raises JobCancelled
        job.finish_step()
        completed_steps.append("two")
        return {}

    store.register("demo", handler)
    job = store.submit("demo", {}, ["one", "two"])

    assert at_step_one.wait(2)
    store.cancel(job.id)

    assert _wait_for(lambda: job.status == CANCELLED)
    assert completed_steps == ["one"], "step after cancellation must not complete"


def test_cancel_finished_job_returns_false(store):
    store.register("demo", lambda job: {})
    job = store.submit("demo", {}, ["only"])
    assert _wait_for(lambda: job.status == DONE)
    assert store.cancel(job.id) is False


# ─── SERIALISATION GUARANTEE ───────────────────────────────────────────────────

def test_jobs_run_one_at_a_time(store):
    """
    Concurrency safety rests on this: only one pipeline may touch Qdrant, the
    scraper temp file, and the shared models at a time.
    """
    concurrent = []
    active = {"n": 0}
    lock = threading.Lock()

    def handler(job):
        with lock:
            active["n"] += 1
            concurrent.append(active["n"])
        time.sleep(0.05)
        with lock:
            active["n"] -= 1
        return {}

    store.register("demo", handler)
    jobs = [store.submit("demo", {}, ["only"]) for _ in range(5)]

    assert _wait_for(lambda: all(j.status == DONE for j in jobs), timeout=10)
    assert max(concurrent) == 1, f"jobs overlapped: peak concurrency {max(concurrent)}"


# ─── PERSISTENCE ───────────────────────────────────────────────────────────────

def test_snapshot_written_to_disk(tmp_path):
    import json

    snap = tmp_path / "jobs.json"
    store = JobStore(snapshot_path=snap)
    store.register("demo", lambda job: {"v": 1})
    job = store.submit("demo", {"url": "u"}, ["only"])
    assert _wait_for(lambda: job.status == DONE)

    # Terminal status and snapshot are published together, so once the job reads
    # DONE in memory the file must already agree.
    def file_has_done():
        if not snap.exists():
            return False
        rows = json.loads(snap.read_text())
        return any(r["job_id"] == job.id and r["status"] == DONE for r in rows)

    assert file_has_done(), "snapshot on disk disagreed with in-memory terminal status"


def test_progress_is_persisted_between_steps(tmp_path):
    """A restart-safe frontend reads progress from the snapshot, not just memory."""
    import json

    snap = tmp_path / "jobs.json"
    store = JobStore(snapshot_path=snap)
    gate = threading.Event()

    def handler(job):
        job.start_step("one")
        job.finish_step()
        gate.wait(3)
        return {}

    store.register("demo", handler)
    job = store.submit("demo", {}, ["one", "two"])
    assert _wait_for(lambda: job.step_index == 1)

    rows = json.loads(snap.read_text())
    row = next(r for r in rows if r["job_id"] == job.id)
    assert row["step_index"] == 1, "mid-flight progress was not persisted"
    assert row["progress"] == 50
    gate.set()
    assert _wait_for(lambda: job.status == DONE)


def test_interrupted_jobs_marked_on_reload(tmp_path):
    """A job that was running when the process died must not reappear as running."""
    import json
    snap = tmp_path / "jobs.json"
    snap.write_text(json.dumps([
        {"job_id": "aaa", "kind": "add_video", "params": {}, "steps": ["scrape"],
         "status": "running", "step_index": 0, "created_at": time.time()},
        {"job_id": "bbb", "kind": "add_video", "params": {}, "steps": ["scrape"],
         "status": "queued", "step_index": 0, "created_at": time.time()},
        {"job_id": "ccc", "kind": "add_video", "params": {}, "steps": ["scrape"],
         "status": "done", "step_index": 1, "created_at": time.time()},
    ]))

    store = JobStore(snapshot_path=snap)
    store.load_snapshot()

    assert store.get("aaa").status == INTERRUPTED
    assert store.get("bbb").status == INTERRUPTED
    assert store.get("ccc").status == DONE
    assert "restarted" in store.get("aaa").error.lower()


# ─── REGISTRY ──────────────────────────────────────────────────────────────────

def test_unknown_kind_rejected(store):
    with pytest.raises(KeyError):
        store.submit("never_registered", {}, ["only"])


def test_list_and_filter(store):
    store.register("demo", lambda job: {})
    jobs = [store.submit("demo", {}, ["only"]) for _ in range(3)]
    assert _wait_for(lambda: all(j.status == DONE for j in jobs))

    assert len(store.list()) == 3
    assert len(store.list(status=DONE)) == 3
    assert len(store.list(status=FAILED)) == 0
    assert len(store.list(limit=2)) == 2


def test_to_dict_shape_is_frontend_ready(store):
    store.register("demo", lambda job: {"workspace_id": "ws"})
    job = store.submit("demo", {"url": "u"}, ["a", "b"])
    assert _wait_for(lambda: job.status == DONE)

    d = job.to_dict()
    for key in ("job_id", "status", "steps", "step_index", "current_step",
                "progress", "created_at", "started_at", "finished_at",
                "duration_seconds", "error", "result", "log"):
        assert key in d, f"missing key '{key}' in job payload"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
