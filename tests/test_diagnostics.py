import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from main import (
    get_readable_time,
    get_system_stats,
    ping_handler,
    stats_handler,
    owner_ids,
)


def test_get_readable_time():
    assert get_readable_time(0) == "0s"
    assert get_readable_time(45) == "45s"
    assert get_readable_time(65) == "1m 5s"
    assert get_readable_time(3665) == "1h 1m 5s"
    assert get_readable_time(90065) == "1d 1h 1m 5s"
    assert get_readable_time(-10) == "0s"


def test_get_system_stats():
    stats = get_system_stats()
    assert isinstance(stats, dict)
    assert "uptime" in stats
    assert "active_tasks" in stats
    assert "disk" in stats
    assert "memory" in stats
    assert "cpu" in stats
    assert "python_version" in stats
    assert "pyrogram_version" in stats
    assert "user_session" in stats


@pytest.mark.asyncio
async def test_ping_command_authorized():
    owner_id = list(owner_ids)[0] if owner_ids else 12345
    with patch("main.owner_ids", {owner_id}):
        user_msg = MagicMock()
        user_msg.chat.id = 1001
        user_msg.id = 2001
        user_msg.from_user.id = owner_id

        reply_msg = MagicMock()
        reply_msg.chat.id = 1001
        reply_msg.id = 9999

        with patch("main.bot.send_message", new_callable=AsyncMock, return_value=reply_msg) as mock_send, \
             patch("main.bot.edit_message_text", new_callable=AsyncMock) as mock_edit:

            await ping_handler(MagicMock(), user_msg)

            mock_send.assert_called_once()
            assert "Pinging" in mock_send.call_args[0][1]

            mock_edit.assert_called_once()
            edited_text = mock_edit.call_args[0][2]
            assert "Pong!" in edited_text
            assert "Latency:" in edited_text


@pytest.mark.asyncio
async def test_ping_command_unauthorized():
    owner_id = 12345
    with patch("main.owner_ids", {owner_id}):
        user_msg = MagicMock()
        user_msg.chat.id = 1001
        user_msg.id = 2001
        user_msg.from_user.id = 99999  # Unauthorized

        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await ping_handler(MagicMock(), user_msg)

            mock_send.assert_called_once()
            assert "not authorized" in mock_send.call_args[0][1]


@pytest.mark.asyncio
async def test_stats_command_authorized():
    owner_id = list(owner_ids)[0] if owner_ids else 12345
    with patch("main.owner_ids", {owner_id}):
        user_msg = MagicMock()
        user_msg.chat.id = 1001
        user_msg.id = 2001
        user_msg.from_user.id = owner_id

        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await stats_handler(MagicMock(), user_msg)

            mock_send.assert_called_once()
            stats_text = mock_send.call_args[0][1]
            assert "Bot Diagnostics & System Stats" in stats_text
            assert "Uptime:" in stats_text
            assert "Memory:" in stats_text
            assert "CPU Usage:" in stats_text
            assert "Disk Space:" in stats_text
            assert "Python:" in stats_text


@pytest.mark.asyncio
async def test_stats_command_unauthorized():
    owner_id = 12345
    with patch("main.owner_ids", {owner_id}):
        user_msg = MagicMock()
        user_msg.chat.id = 1001
        user_msg.id = 2001
        user_msg.from_user.id = 99999  # Unauthorized

        with patch("main.bot.send_message", new_callable=AsyncMock) as mock_send:
            await stats_handler(MagicMock(), user_msg)

            mock_send.assert_called_once()
            assert "not authorized" in mock_send.call_args[0][1]
