import os
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import pyrogram
from main import (
    handle_private_message,
    handle_private_media_group,
    cancel_callback_handler,
    get_task,
    ACTIVE_TASKS,
    STATUS_TRACKER,
    remove_file,
)


@pytest.mark.asyncio
async def test_handle_private_message_happy_path(tmp_path):
    # Setup test file
    dummy_file = tmp_path / "test_doc.pdf"
    dummy_file.write_text("sample content")

    user_msg = MagicMock()
    user_msg.chat.id = 1111
    user_msg.id = 2222
    user_msg.from_user.id = 3333

    telegram_msg = MagicMock()
    telegram_msg.document = MagicMock()
    telegram_msg.document.thumbs = []
    telegram_msg.caption = "Test Caption"
    telegram_msg.caption_entities = None

    status_msg = MagicMock()
    status_msg.chat.id = 1111
    status_msg.id = 9999

    with patch("main.bot.send_message", new_callable=AsyncMock, return_value=status_msg) as mock_send_msg, \
         patch("main.bot.edit_message_text", new_callable=AsyncMock) as mock_edit_msg, \
         patch("main.bot.send_document", new_callable=AsyncMock) as mock_send_doc, \
         patch("main.bot.delete_messages", new_callable=AsyncMock) as mock_del_msg, \
         patch("main.acc.download_media", new_callable=AsyncMock, return_value=str(dummy_file)) as mock_dl:

        await handle_private_message(user_msg, telegram_msg)

        # Status message was created with Cancel button, followed by completion report
        assert mock_send_msg.call_count == 2
        first_args, first_kwargs = mock_send_msg.call_args_list[0]
        assert first_kwargs.get("reply_markup") is not None
        assert "❌ Cancel" in first_kwargs["reply_markup"].inline_keyboard[0][0].text

        second_args, second_kwargs = mock_send_msg.call_args_list[1]
        assert "Download Completed!" in second_kwargs.get("text", "")
        assert "Download Time:" in second_kwargs.get("text", "")

        # Media was downloaded and sent
        mock_dl.assert_called_once()
        mock_send_doc.assert_called_once()

        # Status message deleted at end of successful transfer
        mock_del_msg.assert_called_once_with(1111, [9999])

        # Temporary file deleted after sending
        assert not dummy_file.exists()


@pytest.mark.asyncio
async def test_handle_private_message_cancelled_during_upload(tmp_path):
    # Downloaded file on disk
    downloaded_file = tmp_path / "downloaded_video.mp4"
    downloaded_file.write_text("video content")

    user_msg = MagicMock()
    user_msg.chat.id = 1111
    user_msg.id = 2222
    user_msg.from_user.id = 3333

    telegram_msg = MagicMock()
    telegram_msg.document = None
    telegram_msg.animation = None
    telegram_msg.sticker = None
    telegram_msg.voice = None
    telegram_msg.audio = None
    telegram_msg.photo = None
    telegram_msg.text = None
    telegram_msg.video = MagicMock()
    telegram_msg.video.duration = 10
    telegram_msg.video.width = 1920
    telegram_msg.video.height = 1080
    telegram_msg.video.thumbs = []
    telegram_msg.caption = "Test Video"
    telegram_msg.caption_entities = None

    status_msg = MagicMock()
    status_msg.chat.id = 1111
    status_msg.id = 9999

    upload_started = asyncio.Event()

    async def fake_send_video(*args, **kwargs):
        upload_started.set()
        # Simulate long-running upload that gets cancelled
        await asyncio.sleep(2.0)

    with patch("main.bot.send_message", new_callable=AsyncMock, return_value=status_msg) as mock_send_msg, \
         patch("main.bot.edit_message_text", new_callable=AsyncMock) as mock_edit_msg, \
         patch("main.bot.send_video", side_effect=fake_send_video) as mock_send_vid, \
         patch("main.bot.delete_messages", new_callable=AsyncMock) as mock_del_msg, \
         patch("main.acc.download_media", new_callable=AsyncMock, return_value=str(downloaded_file)):

        # Launch transfer task
        transfer_task = asyncio.create_task(handle_private_message(user_msg, telegram_msg))

        # Wait until upload starts
        await upload_started.wait()

        # Find the active task
        assert len(ACTIVE_TASKS) > 0
        task_id = list(ACTIVE_TASKS.keys())[0]

        # Simulate user clicking Cancel button
        query = MagicMock()
        query.data = f"cancel_{task_id}"
        query.from_user.id = 3333
        query.answer = AsyncMock()

        await cancel_callback_handler(MagicMock(), query)

        # Wait for transfer task to complete
        try:
            await transfer_task
        except asyncio.CancelledError:
            pass

        # Cancellation message was displayed
        cancellation_edits = [c for c in mock_edit_msg.call_args_list if "❌ **Task Cancelled" in str(c)]
        assert len(cancellation_edits) > 0

        # Downloaded file was purged from disk
        assert not downloaded_file.exists()


@pytest.mark.asyncio
async def test_handle_private_message_cancelled_during_download():
    user_msg = MagicMock()
    user_msg.chat.id = 1111
    user_msg.id = 2222
    user_msg.from_user.id = 3333

    telegram_msg = MagicMock()
    telegram_msg.document = MagicMock()
    telegram_msg.document.thumbs = []
    telegram_msg.caption = "Test"
    telegram_msg.caption_entities = None

    status_msg = MagicMock()
    status_msg.chat.id = 1111
    status_msg.id = 7777

    download_started = asyncio.Event()

    async def fake_download(*args, **kwargs):
        download_started.set()
        await asyncio.sleep(2.0)
        return "file.pdf"

    with patch("main.bot.send_message", new_callable=AsyncMock, return_value=status_msg), \
         patch("main.bot.edit_message_text", new_callable=AsyncMock) as mock_edit_msg, \
         patch("main.bot.send_document", new_callable=AsyncMock) as mock_send_doc, \
         patch("main.bot.delete_messages", new_callable=AsyncMock), \
         patch("main.acc.download_media", side_effect=fake_download):

        transfer_task = asyncio.create_task(handle_private_message(user_msg, telegram_msg))
        await download_started.wait()

        assert len(ACTIVE_TASKS) > 0
        task_id = list(ACTIVE_TASKS.keys())[0]

        query = MagicMock()
        query.data = f"cancel_{task_id}"
        query.from_user.id = 3333
        query.answer = AsyncMock()

        await cancel_callback_handler(MagicMock(), query)
        await transfer_task

        # Send document was never called
        mock_send_doc.assert_not_called()


@pytest.mark.asyncio
async def test_handle_private_media_group_cancellation(tmp_path):
    file1 = tmp_path / "item1.jpg"
    file1.write_text("item 1")
    file2 = tmp_path / "item2.jpg"
    file2.write_text("item 2")

    user_msg = MagicMock()
    user_msg.chat.id = 1111
    user_msg.id = 2222
    user_msg.from_user.id = 3333

    msg1 = MagicMock()
    msg1.photo = MagicMock()
    msg1.caption = "Photo 1"
    msg1.caption_entities = None

    msg2 = MagicMock()
    msg2.photo = MagicMock()
    msg2.caption = "Photo 2"
    msg2.caption_entities = None

    status_msg = MagicMock()
    status_msg.chat.id = 1111
    status_msg.id = 8888

    dl_call_count = 0

    async def fake_dl(msg, progress=None, progress_args=None):
        nonlocal dl_call_count
        dl_call_count += 1
        if dl_call_count == 1:
            return str(file1)
        # Cancel before completing second file
        assert len(ACTIVE_TASKS) > 0
        task_id = list(ACTIVE_TASKS.keys())[0]
        ACTIVE_TASKS[task_id].cancel()
        raise pyrogram.StopTransmission

    with patch("main.bot.send_message", new_callable=AsyncMock, return_value=status_msg), \
         patch("main.bot.edit_message_text", new_callable=AsyncMock), \
         patch("main.bot.send_media_group", new_callable=AsyncMock) as mock_send_mg, \
         patch("main.bot.delete_messages", new_callable=AsyncMock), \
         patch("main.acc.download_media", side_effect=fake_dl):

        transfer_task = asyncio.create_task(handle_private_media_group(user_msg, [msg1, msg2]))
        try:
            await transfer_task
        except asyncio.CancelledError:
            pass

        # Media group sending should not have happened
        mock_send_mg.assert_not_called()

        # Files cleaned up
        assert not file1.exists()
