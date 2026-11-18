from compback_worker.main import run


def test_worker_single_iteration_runs() -> None:
    assert run(once=True) == 0
