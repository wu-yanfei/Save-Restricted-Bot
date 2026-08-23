# Save Restricted Bot

A Telegram bot that can copy public posts and, when a user session is configured, retrieve content from private chats, bot chats, and restricted posts.

## Configuration

The bot reads secrets only from environment variables. Do not put real values in this repository.

Required:

- `BOT_TOKEN` — token from `@BotFather`
- `API_ID` — Telegram API ID from [my.telegram.org](https://my.telegram.org)
- `API_HASH` — Telegram API hash from [my.telegram.org](https://my.telegram.org)
- `OWNER_ID` — one Telegram user ID, comma-separated IDs, or a JSON array

Optional:

- `STRING_SESSION` — Pyrogram user session string. Public links work without it; private chats, bot chats, invite links, and restricted-content fallback need it.

For local Docker Compose use, copy `.env.example` to `.env` and fill it locally. `.env` and Telegram session files are ignored by Git.

## Render deployment

This repository is prepared as a Docker-based Render Web Service.

Dashboard settings if entering them manually:

- Runtime: `Docker`
- Dockerfile Path: `./Dockerfile`
- Docker Context: `.`
- Docker Command: leave blank so Render uses the Dockerfile command
- Instance Type: `Free`
- Health Check Path: `/health`
- Region: `Singapore` (nearby Asia-Pacific region)
- Environment variables: `BOT_TOKEN`, `API_ID`, `API_HASH`, `STRING_SESSION`, `OWNER_ID`

The Dockerfile starts `python main.py`. The process exposes `GET /health` on `0.0.0.0:$PORT` while the Pyrogram bot keeps running in the same container. `render.yaml` contains the same configuration and marks all environment variables as unsynced secrets.

Render Free web services can sleep after inactivity, so this is suitable for testing and light personal use. A sleeping service may take time to wake when Render receives a request; Telegram polling resumes when the instance is running.

## Running locally without Docker

```powershell
pip install -r requirements.txt
python main.py
```

Set the environment variables in the same shell before starting the process.
