from contextvars import ContextVar
import threading
import time

import pytest

from backend.ingest.parallel_extraction import ordered_extract


def test_out_of_order_completion_preserves_identity_and_context():
    config = ContextVar('test_config'); config.set('selected-model')
    lock = threading.Lock(); active = 0; peak = 0; finished = []
    def extract(index, value):
        nonlocal active, peak
        assert config.get() == 'selected-model'
        with lock:
            active += 1; peak = max(peak, active)
        time.sleep(.04 if index == 0 else .005)
        with lock: active -= 1
        return value * 2
    values = ordered_extract([3, 4, 5], extract, max_workers=2, completed=lambda i, v: finished.append(i))
    assert values == [6, 8, 10] and peak == 2 and finished[0] == 1


def test_failure_does_not_become_a_partial_success():
    def extract(index, value):
        if index == 1: raise ValueError('actual extraction failed')
        return value
    with pytest.raises(ValueError, match='actual extraction'):
        ordered_extract([1, 2], extract)
