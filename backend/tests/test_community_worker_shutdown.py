"""社区消费者在 RQ 正常退出后不重新领任务。"""
from types import SimpleNamespace

from backend.community import worker


def test_warm_shutdown_does_not_restart_consumer(monkeypatch):
    from backend.community import service
    events = []
    connection = SimpleNamespace(close=lambda: events.append("closed"))
    monkeypatch.setenv("REDIS_URL", "redis://isolated:6379")
    monkeypatch.setattr(worker.Redis, "from_url", lambda *a, **kw: connection)
    monkeypatch.setattr(service, "reconcile", lambda: events.append("reconcile"))
    class FakeWorker:
        def __init__(self, *a, **kw):
            events.append("created")
            assert events.count("created") == 1
            self._shutdown_requested_date = None
        def work(self, **kw):
            self._shutdown_requested_date = "requested"
    monkeypatch.setattr(worker, "Worker", FakeWorker)
    monkeypatch.setattr(worker, "SpawnWorker", FakeWorker)
    worker.consume()
    assert events == ["reconcile", "created", "closed"]
