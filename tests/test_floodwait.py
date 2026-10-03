import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pyrogram.errors import FloodWait
from main import retry_on_floodwait, call_with_floodwait, wrap_client_with_floodwait, FLOODWAIT_METHODS


@pytest.mark.asyncio
async def test_retry_on_floodwait_success_after_retries():
    attempts = 0
    sleep_calls = []

    async def mock_sleep(seconds):
        sleep_calls.append(seconds)

    @retry_on_floodwait
    async def flappy_operation():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise FloodWait(value=2)
        elif attempts == 2:
            raise FloodWait(value=1)
        return "success"

    with patch("asyncio.sleep", side_effect=mock_sleep):
        result = await flappy_operation()

    assert result == "success"
    assert attempts == 3
    # Duration waited must be e.value + 1
    assert sleep_calls == [3, 2]


@pytest.mark.asyncio
async def test_call_with_floodwait():
    attempts = 0
    sleep_calls = []

    async def mock_sleep(seconds):
        sleep_calls.append(seconds)

    async def flappy_operation():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise FloodWait(value=3)
        return "done"

    with patch("asyncio.sleep", side_effect=mock_sleep):
        result = await call_with_floodwait(flappy_operation)

    assert result == "done"
    assert attempts == 2
    assert sleep_calls == [4]


def test_wrap_client_with_floodwait():
    mock_client = MagicMock()
    for method_name in FLOODWAIT_METHODS:
        setattr(mock_client, method_name, AsyncMock(return_value="ok"))

    wrapped_client = wrap_client_with_floodwait(mock_client)
    assert wrapped_client is mock_client

    # Verify each method was wrapped
    for method_name in FLOODWAIT_METHODS:
        method = getattr(wrapped_client, method_name)
        assert getattr(method, "_is_floodwait_wrapped", False) is True


@pytest.mark.asyncio
async def test_client_wrapped_method_executes_floodwait_retry():
    mock_client = MagicMock()
    attempts = 0
    sleep_calls = []

    async def mock_sleep(seconds):
        sleep_calls.append(seconds)

    async def fake_copy_message(chat_id, from_chat_id, message_id, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise FloodWait(value=5)
        return MagicMock(id=message_id)

    mock_client.copy_message = fake_copy_message
    wrap_client_with_floodwait(mock_client)

    with patch("asyncio.sleep", side_effect=mock_sleep):
        res = await mock_client.copy_message(123, 456, 789)

    assert res.id == 789
    assert attempts == 2
    assert sleep_calls == [6]  # 5 + 1


@pytest.mark.asyncio
async def test_batch_worker_resilience_under_floodwait():
    """Verify that multiple concurrent operations undergoing FloodWait all succeed without failing the batch."""
    sleep_calls = []

    async def mock_sleep(seconds):
        sleep_calls.append(seconds)

    tasks_completed = []

    @retry_on_floodwait
    async def worker_task(task_id, flood_wait_secs):
        if flood_wait_secs > 0:
            # Simulate flood wait on first attempt
            if task_id not in tasks_completed:
                tasks_completed.append(task_id)
                raise FloodWait(value=flood_wait_secs)
        return f"result_{task_id}"

    with patch("asyncio.sleep", side_effect=mock_sleep):
        batch = [
            worker_task(1, 2),
            worker_task(2, 0),
            worker_task(3, 4),
            worker_task(4, 0),
        ]
        results = await asyncio.gather(*batch)

    assert results == ["result_1", "result_2", "result_3", "result_4"]
    assert 3 in sleep_calls  # 2 + 1
    assert 5 in sleep_calls  # 4 + 1
