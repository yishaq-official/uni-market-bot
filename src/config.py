import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_GROUP_ID = os.getenv("ADMIN_GROUP_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")
# Linux uses forward slashes /, but os.path.join handles it automatically
DB_PATH = os.path.join("data", "market.db")

if not BOT_TOKEN:
    raise ValueError("Missing BOT_TOKEN in .env file")