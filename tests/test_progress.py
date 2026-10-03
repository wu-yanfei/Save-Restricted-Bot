import asyncio
import pytest
from main import (
    make_progress_bar,
    format_size,
    format_speed,
    format_eta,
    render_progress_text,
    EDIT_THROTTLE_SECONDS,
)


def test_make_progress_bar():
    # 0%
    bar_0 = make_progress_bar(0.0, length=12)
    assert bar_0 == "[▱▱▱▱▱▱▱▱▱▱▱▱] 0.0%"

    # 100%
    bar_100 = make_progress_bar(100.0, length=12)
    assert bar_100 == "[▰▰▰▰▰▰▰▰▰▰▰▰] 100.0%"

    # 50%
    bar_50 = make_progress_bar(50.0, length=12)
    assert bar_50 == "[▰▰▰▰▰▰▱▱▱▱▱▱] 50.0%"

    # 65% (8 filled, 4 empty)
    bar_65 = make_progress_bar(65.0, length=12)
    assert bar_65 == "[▰▰▰▰▰▰▰▰▱▱▱▱] 65.0%"

    # Clamping negative and over-100 values
    bar_neg = make_progress_bar(-10.0, length=12)
    assert bar_neg == "[▱▱▱▱▱▱▱▱▱▱▱▱] 0.0%"
    bar_over = make_progress_bar(150.0, length=12)
    assert bar_over == "[▰▰▰▰▰▰▰▰▰▰▰▰] 100.0%"


def test_format_size():
    # 0 or negative or None
    assert format_size(0) == "0 B"
    assert format_size(-50) == "0 B"
    assert format_size(None) == "0 B"

    # Bytes
    assert format_size(512) == "512 B"

    # Kilobytes
    assert format_size(1024) == "1.00 KB"
    assert format_size(1536) == "1.50 KB"

    # Megabytes
    assert format_size(1024 * 1024) == "1.00 MB"
    assert format_size(int(12.5 * 1024 * 1024)) == "12.50 MB"

    # Gigabytes
    assert format_size(int(2.45 * 1024 * 1024 * 1024)) == "2.45 GB"

    # Terabytes
    assert format_size(int(1.1 * 1024 * 1024 * 1024 * 1024)) == "1.10 TB"


def test_format_speed():
    # 0 or negative or None
    assert format_speed(0) == "0 B/s"
    assert format_speed(-100) == "0 B/s"
    assert format_speed(None) == "0 B/s"

    # Bytes / sec
    assert format_speed(256) == "256 B/s"

    # KB / sec
    assert format_speed(1024) == "1.0 KB/s"

    # MB / sec (e.g. 4.2 MB/s)
    speed_bytes = 4.2 * 1024 * 1024
    assert format_speed(speed_bytes) == "4.2 MB/s"

    # GB / sec
    speed_gb = 1.5 * 1024 * 1024 * 1024
    assert format_speed(speed_gb) == "1.5 GB/s"


def test_format_eta():
    # 0 or negative or None
    assert format_eta(0) == "00:00"
    assert format_eta(-5) == "00:00"
    assert format_eta(None) == "00:00"

    # Seconds only
    assert format_eta(5) == "00:05"
    assert format_eta(59) == "00:59"

    # Minutes and seconds (e.g. 83s -> 01:23)
    assert format_eta(83) == "01:23"
    assert format_eta(125) == "02:05"

    # 1 hour
    assert format_eta(3600) == "60:00"


def test_render_progress_text():
    text = render_progress_text(
        action="Downloading",
        current=int(12.5 * 1024 * 1024),
        total=int(20.0 * 1024 * 1024),
        speed=4.2 * 1024 * 1024,
        eta=83,
        elapsed=15.0,
        file_name="example_video.mp4",
        media_type="Video",
    )
    assert "📥 **Downloading Content...**" in text
    assert "📄 **File:** `example_video.mp4`" in text
    assert "📁 `Video`" in text
    assert "[▰▰▰▰▰▰▱▱▱▱] 62.5%" in text
    assert "⚡ **Speed:** `4.2 MB/s`" in text
    assert "⏳ **ETA:** `01:23`" in text
    assert "⏱ **Elapsed:** `00:15`" in text
    assert "📊 **Progress:** `12.50 MB` / `20.00 MB`" in text
    assert "Fast MTProto Stream" in text


def test_edit_throttle_range():
    # Verify throttle interval is fast, responsive, and within safe Telegram rate-limiting guidelines (1.0s to 3.0s)
    assert 1.0 <= EDIT_THROTTLE_SECONDS <= 3.0


def test_init_status_tracker():
    from main import init_status_tracker, STATUS_TRACKER
    key = init_status_tracker(
        chat_id=12345,
        message_id=6789,
        type_str="down",
        total=20000000,
        task_id="test_task_1",
        file_name="video.mp4",
        media_type="Video",
    )
    assert key == (12345, 6789, "down")
    assert key in STATUS_TRACKER
    entry = STATUS_TRACKER[key]
    assert entry["total"] == 20000000
    assert entry["file_name"] == "video.mp4"
    assert entry["media_type"] == "Video"
    assert entry["current"] == 0
    assert entry["speed"] == 0.0
    STATUS_TRACKER.pop(key, None)


@pytest.mark.asyncio
async def test_status_updater_edits_photo_caption():
    from unittest.mock import AsyncMock, MagicMock, patch
    from main import status_updater, init_status_tracker, STATUS_TRACKER

    key = (111, 222, "down")
    init_status_tracker(111, 222, "down", total=1000, file_name="clip.mp4", media_type="Video")

    mock_msg = MagicMock()
    mock_msg.chat.id = 111
    mock_msg.id = 222
    mock_msg.photo = MagicMock()  # Simulates photo message with caption

    with patch("main.bot.edit_message_caption", new_callable=AsyncMock) as mock_edit_caption, \
         patch("main.bot.edit_message_text", new_callable=AsyncMock) as mock_edit_text, \
         patch("main.EDIT_THROTTLE_SECONDS", 0.01):
        
        task = asyncio.create_task(status_updater(key, mock_msg, "Downloading", task_id="t_photo"))
        await asyncio.sleep(0.05)
        STATUS_TRACKER.pop(key, None)
        await task

        mock_edit_caption.assert_called()
        mock_edit_text.assert_not_called()

