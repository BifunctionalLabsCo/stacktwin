from stacktwin.pipeline.job import _tensor_parallel_size


def test_tensor_parallelism_uses_local_tier_setting(monkeypatch):
    monkeypatch.setenv("STACKTWIN_LOCAL_JOB_TENSOR_PARALLEL_SIZE", "1")

    assert _tensor_parallel_size("local") == 1


def test_tensor_parallelism_uses_cloud_tier_setting(monkeypatch):
    monkeypatch.setenv("STACKTWIN_CLOUD_JOB_TENSOR_PARALLEL_SIZE", "8")

    assert _tensor_parallel_size("cloud") == 8


def test_tensor_parallelism_rejects_invalid_setting(monkeypatch):
    monkeypatch.setenv("STACKTWIN_CLOUD_JOB_TENSOR_PARALLEL_SIZE", "0")

    try:
        _tensor_parallel_size("cloud")
    except ValueError as error:
        assert "positive integer" in str(error)
    else:
        raise AssertionError("Expected an invalid tensor-parallel setting to fail")
