import os
import json
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from main import (
    get_user_thumb,
    set_user_thumb,
    del_user_thumb,
    get_user_caption_template,
    set_user_caption_template,
    del_user_caption_template,
    apply_caption_template,
    check_file_size_limit,
    generate_video_thumbnail,
    start_web_server,
    setthumb_handler,
    delthumb_handler,
    showthumb_handler,
    setcaption_handler,
    delcaption_handler,
    showcaption_handler,
    owner_ids,
    MAX_BOT_FILE_SIZE,
)


def test_thumbnail_management_lifecycle(tmp_path):
    user_id = 998877
    sample_img = tmp_path / "sample.jpg"
    sample_img.write_text("fake image data")

    # Set thumbnail
    set_user_thumb(user_id, str(sample_img))
    retrieved = get_user_thumb(user_id)
    assert retrieved is not None
    assert os.path.exists(retrieved)

    # Delete thumbnail
    deleted = del_user_thumb(user_id)
    assert deleted is True
    assert get_user_thumb(user_id) is None

    # Deleting non-existent returns False
    assert del_user_thumb(user_id) is False


def test_caption_template_lifecycle():
    user_id = 112233
    template = "📁 File: {filename}\n\n📝 Details:\n{caption}\n\n🤖 By Bot"

    set_user_caption_template(user_id, template)
    assert get_user_caption_template(user_id) == template

    # Formatting with variables
    formatted = apply_caption_template(user_id, "Sample caption text", "document.pdf")
    assert "📁 File: document.pdf" in formatted
    assert "Sample caption text" in formatted
    assert "🤖 By Bot" in formatted

    # Deleting caption template
    assert del_user_caption_template(user_id) is True
    assert get_user_caption_template(user_id) is None

    # Fallback to original caption when no template is set
    original = "Just normal caption"
    assert apply_caption_template(user_id, original, "test.mp4") == original


def test_file_size_limit():
    msg_normal = MagicMock()
    msg_normal.document.file_size = 500 * 1024 * 1024  # 500 MB
    msg_normal.video = None
    msg_normal.audio = None

    is_over, size = check_file_size_limit(msg_normal)
    assert not is_over
    assert size == 500 * 1024 * 1024

    msg_oversized = MagicMock()
    msg_oversized.document.file_size = 2500 * 1024 * 1024  # 2.5 GB
    msg_oversized.video = None
    msg_oversized.audio = None

    is_over, size = check_file_size_limit(msg_oversized)
    assert is_over
    assert size == 2500 * 1024 * 1024


@pytest.mark.asyncio
async def test_cloud_web_health_server():
    import urllib.request

    port = 18999
    server = await start_web_server(port)
    assert server is not None

    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        await writer.drain()

        response = await reader.read(1024)
        writer.close()
        await writer.wait_closed()

        res_str = response.decode("utf-8")
        assert "200 OK" in res_str
        assert '"status": "ok"' in res_str
        assert '"uptime"' in res_str
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_setthumb_and_showthumb_commands(tmp_path):
    owner_id = list(owner_ids)[0] if owner_ids else 12345
    fake_img = tmp_path / "mock_thumb.jpg"
    fake_img.write_text("photo binary data")

    with patch("main.owner_ids", {owner_id}):
        # 1. /setthumb without photo
        msg_no_photo = MagicMock()
        msg_no_photo.chat.id = 100
        msg_no_photo.id = 200
        msg_no_photo.from_user.id = owner_id
        msg_no_photo.photo = None
        msg_no_photo.reply_to_message = None

        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await setthumb_handler(MagicMock(), msg_no_photo)
            assert "reply to a photo" in mock_send.call_args[0][1]

        # 2. /setthumb with photo attached
        msg_with_photo = MagicMock()
        msg_with_photo.chat.id = 100
        msg_with_photo.id = 201
        msg_with_photo.from_user.id = owner_id
        msg_with_photo.photo = MagicMock()
        msg_with_photo.reply_to_message = None

        with patch("main.bot.download_media", new_callable=AsyncMock, return_value=str(fake_img)), \
             patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:

            await setthumb_handler(MagicMock(), msg_with_photo)
            assert "saved successfully" in mock_send.call_args[0][1]

        # 3. /showthumb shows the photo
        with patch("main.bot.send_photo", new_callable=AsyncMock) as mock_send_photo:
            await showthumb_handler(MagicMock(), msg_with_photo)
            mock_send_photo.assert_called_once()
            assert "Your Current Custom Thumbnail" in mock_send_photo.call_args[1]["caption"]

        # 4. /delthumb removes it
        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await delthumb_handler(MagicMock(), msg_with_photo)
            assert "deleted" in mock_send.call_args[0][1]


@pytest.mark.asyncio
async def test_caption_commands():
    owner_id = list(owner_ids)[0] if owner_ids else 12345
    with patch("main.owner_ids", {owner_id}):
        msg = MagicMock()
        msg.chat.id = 500
        msg.id = 600
        msg.from_user.id = owner_id

        # 1. /setcaption without arguments
        msg.text = "/setcaption"
        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await setcaption_handler(MagicMock(), msg)
            assert "Usage:" in mock_send.call_args[0][1]

        # 2. /setcaption with template
        msg.text = "/setcaption File: {filename} - {caption}"
        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await setcaption_handler(MagicMock(), msg)
            assert "updated" in mock_send.call_args[0][1]

        # 3. /showcaption
        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await showcaption_handler(MagicMock(), msg)
            assert "Active Caption Template" in mock_send.call_args[0][1]

        # 4. /delcaption
        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await delcaption_handler(MagicMock(), msg)
            assert "deleted" in mock_send.call_args[0][1]


def test_time_duration_formatting():
    from main import format_time_duration

    assert format_time_duration(0.45) == "0.45s"
    assert format_time_duration(4.2) == "4.2s"
    assert format_time_duration(59.9) == "59.9s"
    assert format_time_duration(75.4) == "1m 15.4s"
    assert format_time_duration(135.0) == "2m 15.0s"


def test_build_completion_message():
    from main import build_completion_message

    msg = build_completion_message(
        file_name="movie_2026.mp4",
        file_size=50 * 1024 * 1024,
        msg_type="Video",
        download_duration=5.0,
        upload_duration=2.5,
        bot_username="my_test_bot",
        custom_note="Enjoy watching!",
    )
    assert "✅ **Download Completed!**" in msg
    assert "movie_2026.mp4" in msg
    assert "50.00 MB" in msg
    assert "Video" in msg
    assert "Download Time:" in msg
    assert "5.0s" in msg
    assert "10.0 MB/s" in msg
    assert "Upload Time:" in msg
    assert "2.5s" in msg
    assert "Total Time:" in msg
    assert "7.5s" in msg
    assert "Enjoy watching!" in msg
    assert "@my_test_bot" in msg


def test_custom_message_lifecycle():
    from main import set_user_custom_msg, get_user_custom_msg, del_user_custom_msg

    user_id = 778899
    custom_text = "Thanks for downloading! Join @exclusive_channel"

    set_user_custom_msg(user_id, custom_text)
    assert get_user_custom_msg(user_id) == custom_text

    assert del_user_custom_msg(user_id) is True
    assert get_user_custom_msg(user_id) is None
    assert del_user_custom_msg(user_id) is False


@pytest.mark.asyncio
async def test_custom_message_commands():
    from main import setmsg_handler, delmsg_handler, showmsg_handler

    owner_id = list(owner_ids)[0] if owner_ids else 12345
    with patch("main.owner_ids", {owner_id}):
        msg = MagicMock()
        msg.chat.id = 500
        msg.id = 600
        msg.from_user.id = owner_id

        # 1. /setmsg without arguments
        msg.text = "/setmsg"
        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await setmsg_handler(MagicMock(), msg)
            assert "Usage:" in mock_send.call_args[0][1]

        # 2. /setmsg with custom note
        msg.text = "/setmsg Powered by @FastChannel"
        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await setmsg_handler(MagicMock(), msg)
            assert "Custom completion message saved" in mock_send.call_args[0][1]

        # 3. /showmsg
        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await showmsg_handler(MagicMock(), msg)
            assert "Powered by @FastChannel" in mock_send.call_args[0][1]

        # 4. /delmsg
        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await delmsg_handler(MagicMock(), msg)
            assert "deleted" in mock_send.call_args[0][1]


@pytest.mark.asyncio
async def test_send_completion_report_with_thumb(tmp_path):
    from main import send_completion_report

    thumb_file = tmp_path / "thumb_preview.jpg"
    thumb_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)

    with patch("main.bot.send_photo", new_callable=AsyncMock) as mock_send_photo, \
         patch("main.bot.send_message", new_callable=AsyncMock) as mock_send_msg:
        await send_completion_report(
            chat_id=1001,
            file_name="demo.mp4",
            file_size=1024 * 1024,
            msg_type="Video",
            download_duration=2.0,
            upload_duration=1.0,
            thumb_path=str(thumb_file),
            reply_to_message_id=555,
        )
        mock_send_photo.assert_not_called()
        mock_send_msg.assert_called_once()
        sent_text = mock_send_msg.call_args[1]["text"]
        assert "demo.mp4" in sent_text
        assert "Download Time:" in sent_text


@pytest.mark.asyncio
async def test_send_completion_report_fallback_text():
    from main import send_completion_report

    with patch("main.bot.send_photo", new_callable=AsyncMock) as mock_send_photo, \
         patch("main.bot.send_message", new_callable=AsyncMock) as mock_send_msg:
        await send_completion_report(
            chat_id=1001,
            file_name="document.pdf",
            file_size=2048,
            msg_type="Document",
            download_duration=1.5,
            upload_duration=0.5,
            thumb_path=None,
            reply_to_message_id=555,
        )
        mock_send_photo.assert_not_called()
        mock_send_msg.assert_called_once()
        assert "document.pdf" in mock_send_msg.call_args[1]["text"]
        assert "Download Time:" in mock_send_msg.call_args[1]["text"]
