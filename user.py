#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev 
from telethon import TelegramClient
from telethon.sessions import StringSession
from utils import LOGGER
from config import SESSION_STRING, API_ID, API_HASH

LOGGER.info("Creating User Client From SESSION_STRING")

user = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH
)

LOGGER.info("User Client Successfully Created!")
