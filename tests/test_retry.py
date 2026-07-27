import pytest

from src.utils.retry import async_retry


@pytest.mark.asyncio
async def test_retry_success_first_attempt():
    calls = 0

    @async_retry(max_retries=3, base_delay=0.01)
    async def sample_func():
        nonlocal calls
        calls += 1
        return "success"

    res = await sample_func()
    assert res == "success"
    assert calls == 1


@pytest.mark.asyncio
async def test_retry_success_after_failure():
    calls = 0

    @async_retry(max_retries=3, base_delay=0.001)
    async def sample_func():
        nonlocal calls
        calls += 1
        if calls < 2:
            raise ValueError("Failure")
        return "recovered"

    res = await sample_func()
    assert res == "recovered"
    assert calls == 2


@pytest.mark.asyncio
async def test_retry_exhausted():
    calls = 0

    @async_retry(max_retries=2, base_delay=0.001)
    async def sample_func():
        nonlocal calls
        calls += 1
        raise ValueError("Constant Failure")

    with pytest.raises(ValueError):
        await sample_func()
    assert calls == 2
