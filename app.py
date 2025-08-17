#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
from telethon import TelegramClient
from utils import LOGGER
from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN
)
LOGGER.info("Creating Bot Client From BOT_TOKEN")
app = TelegramClient(
    "SmartTools",
    api_id=API_ID,
    api_hash=API_HASH
).start(bot_token=BOT_TOKEN)
LOGGER.info("Bot Client Created Successfully!")
