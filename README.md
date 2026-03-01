# Uni Market Bot

A Telegram bot for university communities that combines:
- a moderated marketplace,
- lost-and-found reporting,
- and user feedback collection.

The bot is built with `python-telegram-bot`, stores data in SQLite, and uses a small Flask keep-alive server for hosting environments that expect an HTTP process.

## Features

- Seller registration with phone/contact verification.
- ID capture for verification (`University ID` or `National ID`).
- Marketplace listing flow with:
  - photo upload,
  - price/category/condition capture,
  - admin approval or rejection,
  - publish to Telegram channel after approval.
- Lost & Found flow:
  - `I Lost` (guest flow),
  - `I Found` (requires verification).
- Post rate limit: max 3 posts per user per 24 hours.
- Feedback flow with rate limit: max 1 message per user per 24 hours.
- Admin moderation actions:
  - approve/reject pending posts,
  - mark cases as sold/closed,
  - list users, delete user data, and permanently ban users.
- Blacklist support for permanently banned users.

## Tech Stack

- Python 3.11
- `python-telegram-bot` (async bot framework)
- SQLite
- Flask (keep-alive endpoint)
- Docker

## Project Structure

```text
.
├── src/
│   ├── main.py               # Bot entry point + menu + admin commands
│   ├── config.py             # Env config and DB path
│   ├── database.py           # SQLite schema + queries
│   ├── keep_alive.py         # Flask keep-alive server
│   └── handlers/
│       ├── auth.py           # Seller registration flow
│       ├── selling.py        # Marketplace posting flow
│       ├── lost_found.py     # Lost & found flow
│       ├── feedback.py       # Feedback flow
│       └── admin.py          # Approve/reject/publish/close logic
├── requirements.txt
├── Dockerfile
└── fly.toml
```

## Prerequisites

- Python 3.11+
- A Telegram bot token from BotFather
- Telegram IDs for:
  - admin group (`ADMIN_GROUP_ID`)
  - publish channel (`CHANNEL_ID`)

## Environment Variables

Create a `.env` file in the project root:

```env
BOT_TOKEN=your_bot_token_here
ADMIN_GROUP_ID=-1001234567890
CHANNEL_ID=-1009876543210
```

Notes:
- `BOT_TOKEN` is required; the app exits if missing.
- `ADMIN_GROUP_ID` and `CHANNEL_ID` must be valid chat IDs where the bot has permission to post.

## Local Setup

1. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the bot:

```bash
python -m src.main
```

On first run, SQLite schema is created automatically at `data/market.db`.

## Docker

Build and run:

```bash
docker build -t uni-market-bot .
docker run --env-file .env -v "$(pwd)/data:/app/data" uni-market-bot
```

## Admin Controls

Hardcoded admin IDs are currently defined in `src/main.py` (`ADMIN_IDS`).

Supported admin commands:
- `/users` -> list registered users
- `/delete <user_id>` -> remove user + posts (can re-register)
- `/ban <user_id>` -> remove user + posts and add to permanent blacklist

Admin approval buttons in the admin group:
- `Approve` / `Reject` for pending posts
- Post owner receives a button to mark the post/case as closed (`sold_*` callback flow)

## Deployment Notes (Fly.io)

- `fly.toml` mounts persistent storage to `/app/data`.
- This matches the SQLite path used by the app (`data/market.db`).

## Important Operational Notes

- The bot must be an admin in the publish channel to post approved items.
- The bot must be in the admin group to receive/moderate approvals.
- User verification details are stored in SQLite; use secure hosting and access controls.
