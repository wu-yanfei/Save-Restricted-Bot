import os
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import pyrogram
from main import (
    TaskContext,
    register_task,
    unregister_task,
    get_task,
    get_task_by_smsg,
    is_task_cancelled,
    get_cancel_button,
    cancel_callback_handler,
    progress,
    remove_file,
    owner_ids,
)


def test_task_context_lifecycle_and_file_cleanup(tmp_path):
    # Create temporary files
    file1 = tmp_path / "part_download.mp4"
    file1.write_text("dummy data")
    file2 = tmp_path / "thumb.jpg"
    file2.write_text("dummy thumb")

    assert file1.exists()
    assert file2.exists()

    task_ctx = TaskContext(task_id="t123", initiator_id=1001, chat_id=2001, smsg_id=3001)
    task_ctx.track_file(str(file1))
    task_ctx.track_file(str(file2))

    register_task(task_ctx)
    assert get_task("t123") is task_ctx
    assert get_task_by_smsg(2001, 3001) is task_ctx
    assert not is_task_cancelled("t123")

    # Cancel the task context
    task_ctx.cancel()
    assert task_ctx.is_cancelled is True
    assert is_task_cancelled("t123") is True

    # Files must have been purged from disk
    assert not file1.exists()
    assert not file2.exists()

    unregister_task("t123")
    assert get_task("t123") is None
    assert get_task_by_smsg(2001, 3001) is None


def test_get_cancel_button():
    kb = get_cancel_button("task_abc")
    assert len(kb.inline_keyboard) == 1
    button = kb.inline_keyboard[0][0]
    assert button.text == "❌ Cancel"
    assert button.callback_data == "cancel_task_abc"


@pytest.mark.asyncio
async def test_progress_aborts_when_task_cancelled():
    task_ctx = TaskContext(task_id="cancel_test", initiator_id=100, chat_id=200, smsg_id=300)
    register_task(task_ctx)

    smsg = MagicMock()
    smsg.chat.id = 200
    smsg.id = 300

    # Normal progress when active
    progress(100, 1000, smsg, "down", task_id="cancel_test")

    # Cancel task
    task_ctx.cancel()

    # Next progress update must raise StopTransmission
    with pytest.raises(pyrogram.StopTransmission):
        progress(200, 1000, smsg, "down", task_id="cancel_test")

    unregister_task("cancel_test")


@pytest.mark.asyncio
async def test_cancel_callback_handler_authorization():
    task_ctx = TaskContext(task_id="auth_test", initiator_id=1111, chat_id=2222, smsg_id=3333)
    register_task(task_ctx)

    client = MagicMock()

    # 1. Stranger user (unauthorized)
    query_stranger = MagicMock()
    query_stranger.data = "cancel_auth_test"
    query_stranger.from_user.id = 9999  # Not initiator, not owner
    query_stranger.answer = AsyncMock()

    await cancel_callback_handler(client, query_stranger)
    query_stranger.answer.assert_called_once_with("⛔ You are not authorized to cancel this task.", show_alert=True)
    assert not task_ctx.is_cancelled

    # 2. Initiator user (authorized)
    query_initiator = MagicMock()
    query_initiator.data = "cancel_auth_test"
    query_initiator.from_user.id = 1111  # Initiator
    query_initiator.answer = AsyncMock()

    with patch("main.bot.edit_message_text", new_callable=AsyncMock) as mock_edit:
        await cancel_callback_handler(client, query_initiator)

    query_initiator.answer.assert_called_once_with("❌ Task cancelled.", show_alert=False)
    assert task_ctx.is_cancelled is True
    mock_edit.assert_called_once_with(2222, 3333, "❌ **Task Cancelled by user.**", reply_markup=None)

    unregister_task("auth_test")


@pytest.mark.asyncio
async def test_cancel_callback_handler_owner_override():
    # If the initiator was another user but a bot owner clicks cancel, allow it
    owner_ids.add(7777)
    task_ctx = TaskContext(task_id="owner_test", initiator_id=5555, chat_id=6666, smsg_id=7777)
    register_task(task_ctx)

    client = MagicMock()
    query_owner = MagicMock()
    query_owner.data = "cancel_owner_test"
    query_owner.from_user.id = 7777  # Owner
    query_owner.answer = AsyncMock()

    with patch("main.bot.edit_message_text", new_callable=AsyncMock) as mock_edit:
        await cancel_callback_handler(client, query_owner)

    query_owner.answer.assert_called_once_with("❌ Task cancelled.", show_alert=False)
    assert task_ctx.is_cancelled is True

    unregister_task("owner_test")


@pytest.mark.asyncio
async def test_cancel_callback_already_completed():
    client = MagicMock()
    query = MagicMock()
    query.data = "cancel_nonexistent"
    query.from_user.id = 1234
    query.answer = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()

    await cancel_callback_handler(client, query)
    query.answer.assert_called_once_with("⚠️ Task has already completed or expired.", show_alert=False)
    query.edit_message_reply_markup.assert_called_once_with(reply_markup=None)


@pytest.mark.asyncio
async def test_batch_isolation_during_cancellation(tmp_path):
    """Cancelling task 1 does not affect concurrent task 2."""
    file1 = tmp_path / "task1.dat"
    file1.write_text("task 1 data")
    file2 = tmp_path / "task2.dat"
    file2.write_text("task 2 data")

    t1 = TaskContext("t1", 100, 200, 301)
    t1.track_file(str(file1))
    register_task(t1)

    t2 = TaskContext("t2", 100, 200, 302)
    t2.track_file(str(file2))
    register_task(t2)

    # Cancel only t1
    t1.cancel()

    assert t1.is_cancelled is True
    assert not file1.exists()

    assert t2.is_cancelled is False
    assert file2.exists()

    unregister_task("t1")
    unregister_task("t2")
