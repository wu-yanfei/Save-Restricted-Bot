import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from main import (
    send_start,
    help_handler,
    nav_callback_handler,
    build_start_text,
    build_guide_text,
    build_commands_text,
    owner_ids,
)


@pytest.mark.asyncio
async def test_send_start_authorized():
    owner_id = list(owner_ids)[0] if owner_ids else 12345
    with patch("main.owner_ids", {owner_id}):
        user_msg = MagicMock()
        user_msg.chat.id = 1001
        user_msg.id = 2001
        user_msg.from_user.id = owner_id
        user_msg.from_user.mention = "TestUser"

        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await send_start(MagicMock(), user_msg)

            mock_send.assert_called_once()
            call_kwargs = mock_send.call_args[1]
            assert "Save Restricted Bot" in mock_send.call_args[0][1]
            assert "Quick Formats:" in mock_send.call_args[0][1]
            assert call_kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_help_handler_authorized():
    owner_id = list(owner_ids)[0] if owner_ids else 12345
    with patch("main.owner_ids", {owner_id}):
        user_msg = MagicMock()
        user_msg.chat.id = 1001
        user_msg.id = 2001
        user_msg.from_user.id = owner_id

        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await help_handler(MagicMock(), user_msg)

            mock_send.assert_called_once()
            assert "Detailed Usage Guide" in mock_send.call_args[0][1]


@pytest.mark.asyncio
async def test_nav_callback_guide_and_back():
    owner_id = list(owner_ids)[0] if owner_ids else 12345
    with patch("main.owner_ids", {owner_id}):
        query = MagicMock()
        query.data = "nav_guide"
        query.from_user.id = owner_id
        query.from_user.mention = "TestUser"
        query.answer = AsyncMock()

        with patch("main.callback_query", create=True):
            query.edit_message_text = AsyncMock()
            await nav_callback_handler(MagicMock(), query)

            query.answer.assert_called_once()
            query.edit_message_text.assert_called_once()
            assert "Detailed Usage Guide" in query.edit_message_text.call_args[0][0]


def test_parse_tme_link_bot_start():
    from main import parse_tme_link
    res = parse_tme_link("https://t.me/SnipyFileStore_iBot?start=batch_Z28Ltoo1")
    assert res is not None
    assert res["type"] == "bot_start"
    assert res["bot_username"] == "SnipyFileStore_iBot"
    assert res["start_param"] == "batch_Z28Ltoo1"


@pytest.mark.asyncio
async def test_botmedia_handler_help_text():
    from main import botmedia_handler
    owner_id = list(owner_ids)[0] if owner_ids else 12345
    with patch("main.owner_ids", {owner_id}):
        user_msg = MagicMock()
        user_msg.chat.id = 1001
        user_msg.id = 2001
        user_msg.text = "/botmedia"
        user_msg.from_user.id = owner_id

        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await botmedia_handler(MagicMock(), user_msg)
            mock_send.assert_called_once()
            assert "Usage:" in mock_send.call_args[0][1]


def test_parse_selection_indices():
    from main import parse_selection_indices
    assert parse_selection_indices("1-5", 10) == [0, 1, 2, 3, 4]
    assert parse_selection_indices("2, 4, 6", 10) == [1, 3, 5]
    assert parse_selection_indices("5-2", 10) == [1, 2, 3, 4]
    assert parse_selection_indices("1-3, 7, 9", 10) == [0, 1, 2, 6, 8]
    assert parse_selection_indices("50", 10) == []
    assert parse_selection_indices("", 10) == []
    assert parse_selection_indices("invalid", 10) == []


def test_media_classification():
    from main import is_video_message, is_doc_message, is_photo_message, get_media_item_icon

    vid_msg = MagicMock()
    vid_msg.video = MagicMock()
    vid_msg.document = None
    vid_msg.photo = None
    assert is_video_message(vid_msg) is True
    assert is_doc_message(vid_msg) is False
    assert get_media_item_icon(vid_msg) == "🎬"

    doc_vid_msg = MagicMock()
    doc_vid_msg.video = None
    doc_vid_msg.document = MagicMock()
    doc_vid_msg.document.mime_type = "video/mp4"
    doc_vid_msg.document.file_name = "movie.mkv"
    doc_vid_msg.photo = None
    assert is_video_message(doc_vid_msg) is True
    assert is_doc_message(doc_vid_msg) is False

    doc_msg = MagicMock()
    doc_msg.video = None
    doc_msg.document = MagicMock()
    doc_msg.document.mime_type = "application/pdf"
    doc_msg.document.file_name = "notes.pdf"
    doc_msg.photo = None
    assert is_video_message(doc_msg) is False
    assert is_doc_message(doc_msg) is True
    assert get_media_item_icon(doc_msg) == "📄"

    photo_msg = MagicMock()
    photo_msg.video = None
    photo_msg.document = None
    photo_msg.photo = MagicMock()
    assert is_photo_message(photo_msg) is True
    assert is_video_message(photo_msg) is False
    assert is_doc_message(photo_msg) is False
    assert get_media_item_icon(photo_msg) == "🖼️"


def test_build_batch_preview_and_keyboard():
    from main import build_batch_preview_text, build_batch_keyboard

    m1 = MagicMock()
    m1.video = MagicMock()
    m1.document = None
    m1.photo = None
    m1.video.file_name = "Ep1.mp4"
    m1.video.file_size = 500 * 1024 * 1024

    m2 = MagicMock()
    m2.video = None
    m2.document = None
    m2.photo = MagicMock()

    messages = [m1, m2]
    preview_text = build_batch_preview_text("TestBot", messages)
    assert "Batch Received from @TestBot" in preview_text
    assert "🎬 **Videos:** 1" in preview_text
    assert "🖼️ **Photos (banners/ads):** 1" in preview_text

    kb = build_batch_keyboard("batch123", messages)
    button_texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("Videos Only (1)" in t for t in button_texts)
    assert any("Download All (2)" in t for t in button_texts)
    assert any("Cancel" in t for t in button_texts)


@pytest.mark.asyncio
async def test_batch_download_callback_handler_filter_videos():
    import time
    from main import (
        batch_download_callback_handler,
        PENDING_BOT_BATCHES,
        BATCH_MSG_MAP,
    )
    owner_id = list(owner_ids)[0] if owner_ids else 12345

    m_vid = MagicMock()
    m_vid.video = MagicMock()
    m_vid.document = None
    m_vid.photo = None

    m_photo = MagicMock()
    m_photo.video = None
    m_photo.document = None
    m_photo.photo = MagicMock()

    batch_id = "test_b1"
    trigger_msg = MagicMock()
    trigger_msg.chat.id = 1001
    trigger_msg.id = 2001

    PENDING_BOT_BATCHES[batch_id] = {
        "batch_id": batch_id,
        "user_id": owner_id,
        "chat_id": 1001,
        "bot_username": "TestBot",
        "messages": [m_photo, m_vid],
        "status_msg_id": 999,
        "trigger_message": trigger_msg,
        "created_at": time.time(),
    }
    BATCH_MSG_MAP[999] = batch_id

    query = MagicMock()
    query.data = f"b_dl:{batch_id}:videos"
    query.from_user.id = owner_id
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    with patch("main.download_selected_batch", new_callable=AsyncMock) as mock_download:
        await batch_download_callback_handler(MagicMock(), query)

        query.answer.assert_called_once()
        assert "Starting 1 downloads" in query.answer.call_args[0][0]
        # Batch should be popped from pending dict
        assert batch_id not in PENDING_BOT_BATCHES
        assert 999 not in BATCH_MSG_MAP
        # download_selected_batch is called with only the video message (photo excluded!)
        mock_download.assert_called_once_with(trigger_msg, [m_vid], None)


@pytest.mark.asyncio
async def test_save_reply_to_batch_range():
    import time
    from main import save, PENDING_BOT_BATCHES, BATCH_MSG_MAP
    owner_id = list(owner_ids)[0] if owner_ids else 12345

    m1 = MagicMock()
    m2 = MagicMock()
    m3 = MagicMock()

    batch_id = "test_b2"
    trigger_msg = MagicMock()
    trigger_msg.chat.id = 1001
    trigger_msg.id = 2001

    PENDING_BOT_BATCHES[batch_id] = {
        "batch_id": batch_id,
        "user_id": owner_id,
        "chat_id": 1001,
        "bot_username": "TestBot",
        "messages": [m1, m2, m3],
        "status_msg_id": 888,
        "trigger_message": trigger_msg,
        "created_at": time.time(),
    }
    BATCH_MSG_MAP[888] = batch_id

    reply_msg = MagicMock()
    reply_msg.chat.id = 1001
    reply_msg.id = 3001
    reply_msg.text = "2-3"
    reply_msg.from_user.id = owner_id
    reply_msg.reply_to_message = MagicMock()
    reply_msg.reply_to_message.id = 888

    with patch("main.owner_ids", {owner_id}):
        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send, \
             patch("main.download_selected_batch", new_callable=AsyncMock) as mock_download:
            mock_send.return_value = MagicMock(id=9999)
            await save(MagicMock(), reply_msg)

            assert batch_id not in PENDING_BOT_BATCHES
            assert 888 not in BATCH_MSG_MAP
            mock_download.assert_called_once_with(reply_msg, [m2, m3], 9999)


def test_build_slider_caption_and_keyboard():
    from main import build_slider_caption, build_slider_keyboard

    m1 = MagicMock()
    m1.id = 5551
    m1.video = MagicMock()
    m1.document = None
    m1.photo = None
    m1.caption = "Episode 1 in 1080p"
    m1.video.file_name = "Ep1.mp4"
    m1.video.file_size = 50 * 1024 * 1024

    m2 = MagicMock()
    m2.id = 5552
    m2.video = None
    m2.document = None
    m2.photo = MagicMock()
    m2.caption = "Join our sponsor"

    messages = [m1, m2]

    caption0 = build_slider_caption("SnipyBot", messages, 0)
    assert "[ 1 / 2 ]" in caption0
    assert "Ep1.mp4" in caption0
    assert "5551" in caption0
    assert "50.00 MB" in caption0
    assert "Video" in caption0
    assert "Episode 1 in 1080p" in caption0

    caption1 = build_slider_caption("SnipyBot", messages, 1)
    assert "[ 2 / 2 ]" in caption1
    assert "Banner / Ad" in caption1
    assert "5552" in caption1

    kb0 = build_slider_keyboard("batch99", messages, 0)
    btns0 = [b.text for r in kb0.inline_keyboard for b in r]
    assert any("1 / 2" in t for t in btns0)
    assert any("Next ➡️" in t for t in btns0)
    assert any("Download This File (#1)" in t for t in btns0)
    assert any("Download Videos (1)" in t for t in btns0)


@pytest.mark.asyncio
async def test_batch_slider_callback_handler_slide_next():
    import time
    from main import batch_slider_callback_handler, PENDING_BOT_BATCHES
    owner_id = list(owner_ids)[0] if owner_ids else 12345

    m1 = MagicMock(id=101, video=MagicMock(), document=None, photo=None, caption=None)
    m1.video.file_name = "vid1.mp4"
    m1.video.file_size = 1000
    m1.video.thumbs = None

    m2 = MagicMock(id=102, video=MagicMock(), document=None, photo=None, caption=None)
    m2.video.file_name = "vid2.mp4"
    m2.video.file_size = 2000
    m2.video.thumbs = None

    batch_id = "slide_b1"
    PENDING_BOT_BATCHES[batch_id] = {
        "batch_id": batch_id,
        "user_id": owner_id,
        "chat_id": 1001,
        "bot_username": "SnipyBot",
        "messages": [m1, m2],
        "status_msg_id": 777,
        "trigger_message": MagicMock(),
        "current_index": 0,
        "created_at": time.time(),
    }

    query = MagicMock()
    query.data = f"b_slide:{batch_id}:1"
    query.from_user.id = owner_id
    query.answer = AsyncMock()
    query.edit_message_media = AsyncMock()

    await batch_slider_callback_handler(MagicMock(), query)

    query.answer.assert_called_once()
    assert PENDING_BOT_BATCHES[batch_id]["current_index"] == 1
    query.edit_message_media.assert_called_once()


@pytest.mark.asyncio
async def test_batch_download_single_callback_handler():
    import time
    from main import batch_download_single_callback_handler, PENDING_BOT_BATCHES
    owner_id = list(owner_ids)[0] if owner_ids else 12345

    m1 = MagicMock(id=201, video=MagicMock(), document=None, photo=None, caption=None)
    m1.video.file_name = "video1.mp4"
    m1.video.file_size = 1000

    m2 = MagicMock(id=202, video=MagicMock(), document=None, photo=None, caption=None)
    m2.video.file_name = "video2.mp4"
    m2.video.file_size = 2000

    trigger_msg = MagicMock()
    batch_id = "single_b1"
    PENDING_BOT_BATCHES[batch_id] = {
        "batch_id": batch_id,
        "user_id": owner_id,
        "chat_id": 1001,
        "bot_username": "SnipyBot",
        "messages": [m1, m2],
        "status_msg_id": 666,
        "trigger_message": trigger_msg,
        "current_index": 1,
        "created_at": time.time(),
    }

    query = MagicMock()
    query.data = f"b_dl_single:{batch_id}:1"
    query.from_user.id = owner_id
    query.answer = AsyncMock()

    with patch("main.download_selected_batch", new_callable=AsyncMock) as mock_download:
        await batch_download_single_callback_handler(MagicMock(), query)

        query.answer.assert_called_once()
        assert "Starting download" in query.answer.call_args[0][0]
        # Downloaded item 1 (m2) specifically
        mock_download.assert_called_once_with(trigger_msg, [m2], None)
        # Batch should still remain in pending for user to continue browsing!
        assert batch_id in PENDING_BOT_BATCHES




