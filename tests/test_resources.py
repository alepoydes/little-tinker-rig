"""Resource workers must finish safely when their GUI receiver has gone away."""

from concurrent.futures import CancelledError

import pytest
from shiboken6 import delete, isValid

from little_tinker_rig.qt.resources import ResourceJob


def test_resource_job_emits_progress_and_result_with_live_signals(qt_app):
    events = []

    def action(*, progress, cancelled):
        assert not cancelled()
        progress(1, 2)
        return "ready"

    job = ResourceJob(action)
    job.signals.progress.connect(lambda current, total: events.append((current, total)))
    job.signals.ready.connect(lambda result, error: events.append((result, error)))
    job.run()
    assert events == [(1, 2), ("ready", "")]


@pytest.mark.parametrize("fails", [False, True])
def test_resource_job_finishes_after_gui_signals_are_destroyed(qt_app, fails):
    worked = []

    def action(*, progress, cancelled):
        progress(1, 2)
        worked.append(True)
        if fails:
            raise CancelledError("Parts loading cancelled")
        return "ready"

    job = ResourceJob(action)
    delete(job.signals)
    assert not isValid(job.signals)
    job.run()
    assert worked == [True]
