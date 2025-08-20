# Copyright @ISmartCoder
# Updates Channel: https://t.me/TheSmartDev
from telethon import TelegramClient, events
from telethon.tl.custom import Button
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER
from core import banned_users

PRIVACY_POLICY = """
<b>📜 Privacy Policy for Quick Util </b>
━━━━━━━━━━━━━━━━━
Welcome to Quick Util 💥. By using our services, you agree to this privacy policy.
<b>1. Information We Collect:</b>
   - <b>Personal Information:</b> User ID and username for personalization.
   - <b>Usage Data:</b> Information on how you use the app to improve our services.
<b>2. Usage of Information:</b>
   - <b>Service Enhancement:</b> To provide and improve SmartToolsBot.
   - <b>Communication:</b> Updates and new features.
   - <b>Security:</b> To prevent unauthorized access.
   - <b>Advertisements:</b> Display of promotions.
<b>3. Data Security:</b>
   - These tools do not store any data, ensuring your privacy.
   - We use strong security measures, although no system is 100% secure.
Thank you for using Quick Util. We prioritize your privacy and security.
"""

def setup_privacy_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}privacy$', incoming=True))
    async def show_privacy_policy(event):
        user_id = event.sender_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='md')
            return

        await event.respond(
            PRIVACY_POLICY,
            parse_mode='html',
            buttons=[
                [Button.inline("Close", b"close_privacy_policy")]
            ],
            link_preview=False
        )

    @app.on(events.CallbackQuery(pattern=r'^close_privacy_policy$'))
    async def close_privacy_policy(event):

        await event.delete()
