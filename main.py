import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pyrogram
from pyrogram import Client, filters
from pyrogram.errors import InviteHashExpired, UserAlreadyParticipant, UsernameNotOccupied
from pyrogram.types import InputMediaAudio, InputMediaDocument, InputMediaPhoto, InputMediaVideo


def required_env(name):
    value = os.getenv(name)
    if not value or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()


def parse_owner_ids(raw_value):
    """Accept OWNER_ID as JSON ([123, 456]) or comma/space-separated IDs."""
    raw_value = raw_value.strip()
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed = None

    values = parsed if isinstance(parsed, list) else re.split(r"[,\s]+", raw_value)
    return {int(value) for value in values if str(value).strip()}


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok\n")
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, _format, *_args):
        # Render health checks are frequent; keep them out of the bot logs.
        return


def start_health_server():
    port = int(os.getenv("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(
        target=server.serve_forever,
        name="render-health-server",
        daemon=True,
    ).start()
    return server


owner_ids = parse_owner_ids(required_env("OWNER_ID"))
if not owner_ids:
    raise RuntimeError("OWNER_ID must contain at least one Telegram user ID")

bot_token = required_env("BOT_TOKEN")
api_hash = required_env("API_HASH")
api_id = int(required_env("API_ID"))
ss = os.getenv("STRING_SESSION", "").strip() or None

bot = Client("mybot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
health_server = start_health_server()

if ss is not None:
    acc = Client("myacc", api_id=api_id, api_hash=api_hash, session_string=ss)
    acc.start()
else:
    acc = None


MAX_MESSAGE_RANGE = 100


def remove_file(path):
    if path is not None and os.path.exists(path):
        os.remove(path)


def status_file(message, type):
    return f"{message.chat.id}_{message.id}_{type}status.txt"


def delete_status_message(message, smsg):
    try:
        bot.delete_messages(message.chat.id, [smsg.id])
    except Exception:
        pass


def downstatus(statusfile, message):
    while True:
        if os.path.exists(statusfile):
            break

    time.sleep(3)
    while os.path.exists(statusfile):
        with open(statusfile, "r") as downread:
            txt = downread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"__Downloaded__ : **{txt}**")
            time.sleep(10)
        except Exception:
            time.sleep(5)


def upstatus(statusfile, message):
    while True:
        if os.path.exists(statusfile):
            break

    time.sleep(3)
    while os.path.exists(statusfile):
        with open(statusfile, "r") as upread:
            txt = upread.read()
        try:
            bot.edit_message_text(message.chat.id, message.id, f"__Uploaded__ : **{txt}**")
            time.sleep(10)
        except Exception:
            time.sleep(5)


def progress(current, total, message, type):
    with open(status_file(message, type), "w") as fileup:
        fileup.write(f"{current * 100 / total:.1f}%")


def is_owner(message):
    return message.from_user is not None and message.from_user.id in owner_ids


def deny_access(message):
    bot.send_message(
        message.chat.id,
        "**You are not authorized to use this bot.**",
        reply_to_message_id=message.id,
    )


@bot.on_message(filters.command(["start"]))
def send_start(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    if not is_owner(message):
        deny_access(message)
        return
    bot.send_message(
        message.chat.id,
        f"__👋 Hi **{message.from_user.mention}**, I am Save Restricted Bot, I can send you restricted content by it's post link__\n\n{USAGE}",
        reply_to_message_id=message.id,
    )


def send_with_user_session(message, chatid, msgid, processed_media_groups):
    if acc is None:
        bot.send_message(message.chat.id, "**String Session is not Set**", reply_to_message_id=message.id)
        return
    handle_private(message, chatid, msgid, processed_media_groups)


def parse_tme_link(text):
    link = text.strip()

    invite_match = re.match(r"^https://t\.me/(?:\+|joinchat/)[^/\s]+/?$", link)
    if invite_match:
        return {"type": "invite", "link": link}

    match = re.match(r"^https://t\.me/(c|b)/([^/?#\s]+)/([0-9\s]+(?:-[0-9\s]+)?)(?:\?single)?$", link)
    if match:
        link_type, target, message_range = match.groups()
        parsed_range = parse_message_range(message_range)
        if parsed_range is None:
            return None
        from_id, to_id = parsed_range
        if link_type == "c":
            return {"type": "private", "chatid": int("-100" + target), "from_id": from_id, "to_id": to_id}
        return {"type": "bot", "chatid": target, "from_id": from_id, "to_id": to_id}

    match = re.match(r"^https://t\.me/([^/?#\s]+)/([0-9\s]+(?:-[0-9\s]+)?)(?:\?single)?$", link)
    if match:
        username, message_range = match.groups()
        parsed_range = parse_message_range(message_range)
        if parsed_range is None:
            return None
        from_id, to_id = parsed_range
        return {"type": "public", "chatid": username, "from_id": from_id, "to_id": to_id}

    return None


def parse_message_range(message_range):
    parts = [part.strip() for part in message_range.split("-", 1)]
    try:
        from_id = int(parts[0])
        to_id = int(parts[1]) if len(parts) == 2 else from_id
    except ValueError:
        return None
    return from_id, to_id


@bot.on_message(filters.text)
def save(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    if not is_owner(message):
        deny_access(message)
        return

    parsed_link = parse_tme_link(message.text)
    if parsed_link is None:
        bot.send_message(message.chat.id, "**Invalid Link**", reply_to_message_id=message.id)
        return

    if parsed_link["type"] == "invite":
        if acc is None:
            bot.send_message(message.chat.id, "**String Session is not Set**", reply_to_message_id=message.id)
            return

        try:
            acc.join_chat(parsed_link["link"])
            bot.send_message(message.chat.id, "**Chat Joined**", reply_to_message_id=message.id)
        except UserAlreadyParticipant:
            bot.send_message(message.chat.id, "**Chat alredy Joined**", reply_to_message_id=message.id)
        except InviteHashExpired:
            bot.send_message(message.chat.id, "**Invalid Link**", reply_to_message_id=message.id)
        except Exception as e:
            bot.send_message(message.chat.id, f"**Error** : __{e}__", reply_to_message_id=message.id)
        return

    from_id = parsed_link["from_id"]
    to_id = parsed_link["to_id"]
    if to_id < from_id:
        bot.send_message(message.chat.id, "**Invalid Range**", reply_to_message_id=message.id)
        return
    if to_id - from_id + 1 > MAX_MESSAGE_RANGE:
        bot.send_message(
            message.chat.id,
            f"**Range is too large. Maximum {MAX_MESSAGE_RANGE} messages allowed.**",
            reply_to_message_id=message.id,
        )
        return

    processed_media_groups = set()

    for msgid in range(from_id, to_id + 1):
        chatid = parsed_link["chatid"]

        if parsed_link["type"] in ("private", "bot"):
            try:
                send_with_user_session(message, chatid, msgid, processed_media_groups)
            except Exception as e:
                bot.send_message(message.chat.id, f"**Error** : __{e}__", reply_to_message_id=message.id)
        else:
            try:
                msg = bot.get_messages(chatid, msgid)
            except UsernameNotOccupied:
                bot.send_message(
                    message.chat.id,
                    "**The username is not occupied by anyone**",
                    reply_to_message_id=message.id,
                )
                return
            try:
                if getattr(msg, "media_group_id", None):
                    media_group_key = (msg.chat.id, msg.media_group_id)
                    if media_group_key in processed_media_groups:
                        continue
                    try:
                        bot.copy_media_group(message.chat.id, msg.chat.id, msg.id, reply_to_message_id=message.id)
                        processed_media_groups.add(media_group_key)
                    except ValueError:
                        bot.copy_message(message.chat.id, msg.chat.id, msg.id, reply_to_message_id=message.id)
                else:
                    bot.copy_message(message.chat.id, msg.chat.id, msg.id, reply_to_message_id=message.id)
            except Exception:
                try:
                    send_with_user_session(message, msg.chat.id, msgid, processed_media_groups)
                except Exception as e:
                    bot.send_message(message.chat.id, f"**Error** : __{e}__", reply_to_message_id=message.id)

        time.sleep(3)


@bot.on_message(filters.incoming & filters.media)
def save_media(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    if not is_owner(message):
        deny_access(message)
        return

    try:
        if message.media_group_id:
            # Telegram delivers each album item as a separate update.
            time.sleep(1)
            media_group = bot.get_media_group(message.chat.id, message.id)
            if message.id != media_group[0].id:
                return
            bot.copy_media_group(message.chat.id, message.chat.id, message.id, reply_to_message_id=message.id)
        else:
            bot.copy_message(message.chat.id, message.chat.id, message.id, reply_to_message_id=message.id)
    except Exception as e:
        bot.send_message(message.chat.id, f"**Error** : __{e}__", reply_to_message_id=message.id)


def handle_private(message: pyrogram.types.messages_and_media.message.Message, chatid: int, msgid: int, processed_media_groups=None):
    msg: pyrogram.types.messages_and_media.message.Message = acc.get_messages(chatid, msgid)
    media_group_id = getattr(msg, "media_group_id", None)

    if media_group_id:
        media_group_key = (chatid, media_group_id)
        if processed_media_groups is not None and media_group_key in processed_media_groups:
            return
        try:
            messages = acc.get_media_group(chatid, msgid)
        except ValueError:
            messages = [msg]
        if processed_media_groups is not None:
            processed_media_groups.add(media_group_key)
        if len(messages) > 1:
            handle_private_media_group(message, messages)
            return

    handle_private_message(message, msg)


def handle_private_message(message: pyrogram.types.messages_and_media.message.Message, msg: pyrogram.types.messages_and_media.message.Message):
    msg_type = get_message_type(msg)

    if "Text" == msg_type:
        bot.send_message(message.chat.id, msg.text, entities=msg.entities, reply_to_message_id=message.id)
        return
    if msg_type is None:
        bot.send_message(message.chat.id, "**Unsupported Message Type**", reply_to_message_id=message.id)
        return

    down_status_file = status_file(message, "down")
    up_status_file = status_file(message, "up")
    smsg = bot.send_message(message.chat.id, "__Downloading__", reply_to_message_id=message.id)
    threading.Thread(target=lambda: downstatus(down_status_file, smsg), daemon=True).start()
    file = None
    thumb = None

    try:
        file = acc.download_media(msg, progress=progress, progress_args=[message, "down"])
        remove_file(down_status_file)

        threading.Thread(target=lambda: upstatus(up_status_file, smsg), daemon=True).start()

        if "Document" == msg_type:
            try:
                thumb = acc.download_media(msg.document.thumbs[0].file_id)
            except Exception:
                thumb = None

            bot.send_document(message.chat.id, file, thumb=thumb, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id, progress=progress, progress_args=[message, "up"])

        elif "Video" == msg_type:
            try:
                thumb = acc.download_media(msg.video.thumbs[0].file_id)
            except Exception:
                thumb = None

            bot.send_video(message.chat.id, file, duration=msg.video.duration, width=msg.video.width, height=msg.video.height, thumb=thumb, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id, progress=progress, progress_args=[message, "up"])

        elif "Animation" == msg_type:
            bot.send_animation(message.chat.id, file, reply_to_message_id=message.id)

        elif "Sticker" == msg_type:
            bot.send_sticker(message.chat.id, file, reply_to_message_id=message.id)

        elif "Voice" == msg_type:
            bot.send_voice(message.chat.id, file, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id, progress=progress, progress_args=[message, "up"])

        elif "Audio" == msg_type:
            try:
                thumb = acc.download_media(msg.audio.thumbs[0].file_id)
            except Exception:
                thumb = None

            bot.send_audio(message.chat.id, file, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id, progress=progress, progress_args=[message, "up"])

        elif "Photo" == msg_type:
            bot.send_photo(message.chat.id, file, caption=msg.caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id)
    finally:
        remove_file(thumb)
        remove_file(file)
        remove_file(down_status_file)
        remove_file(up_status_file)
        delete_status_message(message, smsg)


def handle_private_media_group(message: pyrogram.types.messages_and_media.message.Message, messages):
    down_status_file = status_file(message, "down")
    smsg = bot.send_message(message.chat.id, "__Downloading__", reply_to_message_id=message.id)
    threading.Thread(target=lambda: downstatus(down_status_file, smsg), daemon=True).start()
    files = []
    thumbs = []
    media = []

    try:
        for msg in messages:
            msg_type = get_message_type(msg)
            if msg_type not in ("Photo", "Video", "Document", "Audio"):
                raise ValueError(f"Message type {msg_type} can't be sent in a media group.")

            file = acc.download_media(msg, progress=progress, progress_args=[message, "down"])
            files.append(file)
            caption = msg.caption or ""
            caption_entities = msg.caption_entities

            if "Photo" == msg_type:
                media.append(InputMediaPhoto(file, caption=caption, caption_entities=caption_entities))
            elif "Video" == msg_type:
                try:
                    thumb = acc.download_media(msg.video.thumbs[0].file_id)
                except Exception:
                    thumb = None
                thumbs.append(thumb)
                media.append(InputMediaVideo(file, thumb=thumb, caption=caption, caption_entities=caption_entities, duration=msg.video.duration or 0, width=msg.video.width or 0, height=msg.video.height or 0))
            elif "Document" == msg_type:
                try:
                    thumb = acc.download_media(msg.document.thumbs[0].file_id)
                except Exception:
                    thumb = None
                thumbs.append(thumb)
                media.append(InputMediaDocument(file, thumb=thumb, caption=caption, caption_entities=caption_entities))
            elif "Audio" == msg_type:
                try:
                    thumb = acc.download_media(msg.audio.thumbs[0].file_id)
                except Exception:
                    thumb = None
                thumbs.append(thumb)
                media.append(InputMediaAudio(file, thumb=thumb, caption=caption, caption_entities=caption_entities, duration=msg.audio.duration or 0, performer=msg.audio.performer or "", title=msg.audio.title or ""))

        remove_file(down_status_file)
        bot.edit_message_text(message.chat.id, smsg.id, "__Uploading__")
        bot.send_media_group(message.chat.id, media, reply_to_message_id=message.id)
    finally:
        for thumb in thumbs:
            remove_file(thumb)
        for file in files:
            remove_file(file)
        remove_file(down_status_file)
        delete_status_message(message, smsg)


def get_message_type(msg: pyrogram.types.messages_and_media.message.Message):
    if msg.document:
        return "Document"
    if msg.video:
        return "Video"
    if msg.animation:
        return "Animation"
    if msg.sticker:
        return "Sticker"
    if msg.voice:
        return "Voice"
    if msg.audio:
        return "Audio"
    if msg.photo:
        return "Photo"
    if msg.text:
        return "Text"
    return None


USAGE = """**How to use**

Send a Telegram message link and the bot will send the content back to you.

**Public channels / groups**

Send a normal post link:

```
https://t.me/channelname/123
```

**Private channels / groups / restricted content**

If the user session has not joined the target chat yet, send the invite link first:

```
https://t.me/+invite_code
```

Then send the post link:

```
https://t.me/c/123456789/123
```

These links require a valid `STRING_SESSION`.

**Bot chat messages**

Use the `/b/` format:

```
https://t.me/b/botusername/4321
```

These links also require a valid `STRING_SESSION`.

**Multiple messages**

Use `start_id-end_id` in the message ID position:

```
https://t.me/channelname/1001-1010

https://t.me/c/123456789/101-120
```

The bot processes up to 100 messages per request. Albums / media groups are sent as a group when possible.
"""


bot.run()
