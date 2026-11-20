"""Only one process per container runs the scheduler and the job worker."""
import multiprocessing as mp

from app.core import leader


def _try(path, q):
    q.put(leader.acquire_leadership(path))


def test_second_process_is_not_leader(tmp_path, monkeypatch):
    path = str(tmp_path / "leader.lock")
    monkeypatch.setattr(leader, "_lock_fd", None)
    assert leader.acquire_leadership(path) is True
    assert leader.acquire_leadership(path) is True       # idempotent in-process
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    p = ctx.Process(target=_try, args=(path, q))
    p.start(); p.join(30)
    assert q.get(timeout=5) is False                       # another process: no
    leader.release_leadership()
    p2 = ctx.Process(target=_try, args=(path, q))
    p2.start(); p2.join(30)
    assert q.get(timeout=5) is True                        # released → taken over
