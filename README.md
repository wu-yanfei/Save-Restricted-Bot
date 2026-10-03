# Save Restricted Bot

*A modern Telegram Bot to save and download restricted content, media stores, private posts, and channels with interactive previews.*

---

## Key Features

- **Save Restricted Content**: Download posts and media from restricted public/private channels, groups, and bot conversations.
- **Interactive Carousel / Slider Preview**: Browse multi-item batches with an image slider, item counter `[1/N]`, file size, filename, and Next / Previous pagination buttons.
- **Selective Batch Downloads**: Inspect FileStore / deep links before downloading. Download individual items selectively or download all with one click.
- **Deep Link & `/botmedia` Support**: Handles `https://t.me/BotUsername?start=batch_...` links seamlessly using user-session resolution.
- **Modern Transfer Progress UI**: Real-time progress bar dashboard with download speed, ETA, elapsed time, and thumbnail preview during transfer.
- **Completion Summary Cards**: Separate clean cards detailing completed file transfers, file sizes, and download/upload elapsed duration.
- **Custom Thumbnails & Captions**: Personalize your uploaded documents and videos with custom thumbnails and caption templates (`{filename}`, `{caption}`).
- **Anti-Ban Protections**: Intelligent batch pacing, rate-limit backoffs, and invite-link cooldowns to protect user sessions from FloodWait.
- **System Diagnostics**: Built-in `/ping`, `/stats`, and `/status` monitoring CPU, RAM, disk, active tasks, and session health.

---

## Variables

Set the following variables in `config.json` or as environment variables:

| Variable | Description |
|---|---|
| `TOKEN` | Telegram Bot token from [@BotFather](https://t.me/BotFather) |
| `ID` | Telegram API ID from [my.telegram.org](https://my.telegram.org) |
| `HASH` | Telegram API Hash from [my.telegram.org](https://my.telegram.org) |
| `STRING` | Pyrogram User Session string (required for private/restricted content & bot chats) |
| `OWNER_ID` | Array of authorized Telegram user IDs allowed to use the bot |

---

## Configuration & Deployment

### 1. Configure the bot

Copy the sample configuration file and fill in your credentials:

```bash
cp config.example.json config.json
```

```json
{
    "TOKEN": "your_bot_token",
    "ID": "your_api_id",
    "HASH": "your_api_hash",
    "STRING": "your_pyrogram_session_string",
    "OWNER_ID": [
        123456789,
        987654321
    ]
}
```

> **Note:** `STRING` is required for accessing restricted channels, private groups, and bot file stores.

### 2. Run directly with Python

```bash
pip install -r requirements.txt
python main.py
```

### 3. Run with Docker Compose

Build and start the container:

```bash
docker compose up -d --build
```

View logs:

```bash
docker compose logs -f bot
```

Stop the container:

```bash
docker compose down
```

### 4. Deploy on InstaCloud (24/7 Cloud Hosting)

This repository includes native [InstaCloud](https://instacloud.io) support for zero-config 24/7 worker deployment.

1. **Install Insta CLI & Login**:
   ```bash
   npm install -g @instacloud/cli
   insta login
   ```

2. **Set Environment Secrets**:
   Bind your credentials into the compute environment:
   ```bash
   insta secrets set TOKEN="your_bot_token"
   insta secrets set ID="your_api_id"
   insta secrets set HASH="your_api_hash"
   insta secrets set STRING="your_session_string"
   insta secrets set OWNER_ID="123456789,987654321"
   ```

3. **Deploy Service**:
   ```bash
   insta deploy
   ```

4. **Monitor Logs**:
   ```bash
   insta logs -s bot -f
   ```

---

## Usage Guide

Send any supported Telegram link directly to the bot:

### Public channels / groups
Send any standard message link:
```text
https://t.me/channelname/123
```

### Private channels / groups / restricted content
If the user session hasn't joined the target chat yet, send the invite link first:
```text
https://t.me/+invite_code
```
Then send the post link:
```text
https://t.me/c/123456789/123
```

### Bot chat messages & Deep Links
- **Direct bot message link**:
  ```text
  https://t.me/b/botusername/4321
  ```
- **Bot FileStore batch deep link**:
  ```text
  https://t.me/SnipyFileStore_iBot?start=batch_Z28Ltoo1
  ```
  *(Launches interactive preview slider with selective item download and preview cards)*
- **Via command**:
  ```text
  /botmedia @BotUsername batch_code
  ```

### Multiple messages / Batch range
Specify `start_id-end_id` in the message link:
```text
https://t.me/channelname/1001-1010
https://t.me/c/123456789/101-120
```

---

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome card with interactive quick-action buttons and feature overview |
| `/help` | Detailed guide on supported link formats and commands |
| `/ping` | Measure Telegram Bot response latency |
| `/stats` or `/status` | View real-time system metrics (RAM, CPU, disk, uptime, active workers, session status) |
| `/setthumb` | Reply to any photo to set it as your custom thumbnail |
| `/delthumb` | Remove your custom saved thumbnail |
| `/showthumb` | Display your current custom thumbnail |
| `/setcaption <template>` | Set custom caption template (supports `{filename}` and `{caption}`) |
| `/delcaption` | Delete your custom caption template |
| `/showcaption` | View your active custom caption template |
| `/cancel` | Cancel an ongoing batch download in progress |

---

## Running Tests

Run the full automated test suite:

```bash
pytest
```
