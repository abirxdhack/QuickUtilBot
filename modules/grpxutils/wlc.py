import time
from telethon import TelegramClient, events
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonRow, InputKeyboardButtonUserProfile
from config import DEVELOPER_USER_ID
from utils import LOGGER

last_actions = {}

def setup_wlc_handler(app: TelegramClient):

    @app.on(events.ChatAction())
    async def handle_chat_actions(event):
        user = await event.get_user()
        if not user:
            return

        is_join = bool(event.user_joined or event.user_added)
        is_leave = bool(event.user_left or event.user_kicked)

        if not (is_join or is_leave):
            return

        action = "join" if is_join else "leave"
        key = f"{event.chat_id}:{user.id}:{action}"
        now = time.time()
        if key in last_actions and now - last_actions[key] < 3:
            return
        last_actions[key] = now

        if is_join:
            group_name = event.chat.title

            added_by = "self-joined"
            if event.user_added and event.action_message and event.action_message.sender_id:
                adder = await event.action_message.get_sender()
                if adder and adder.id != user.id:
                    added_by = adder.username or adder.first_name or "Unknown"

            first = user.first_name or "N/A"
            last = user.last_name or ""
            full_name = f"{first} {last}".strip()
            username = user.username or "N/A"
            user_id = user.id
            member_type = "Bot" if user.bot else "User"

            added_by_disp = f"@{added_by}" if added_by != "self-joined" else "self-joined"
            LOGGER.info(f"New {member_type} @{username} (ID: {user_id}) joined {group_name}, added by {added_by_disp}.")

            caption = f"""
Wow, there's a new member! Yo <b>{full_name}</b> 👋 welcome to <b>{group_name}</b>! Don't forget to put your username so it's easy to tag. Don't forget to read the <b>rules</b> below.

<b>Rules:</b>
1. Polite and polite
2. Respect other users
3. NO CRINGE
"""

            try:
                dev_entity = await app.get_input_entity(DEVELOPER_USER_ID)
                buttons = ReplyInlineMarkup([
                    KeyboardButtonRow([
                        InputKeyboardButtonUserProfile("My Dev 👋", dev_entity)
                    ])
                ])
                image_url = "https://telegra.ph/file/36be820a8775f0bfc773e.jpg"
                await app.send_message(event.chat_id, caption, file=image_url, parse_mode="html", buttons=buttons)
            except Exception as e:
                LOGGER.error(f"Error sending welcome message: {str(e)}")
                await app.send_message(event.chat_id, caption, parse_mode="html")

        elif is_leave and not event.user_kicked:
            username = user.username or user.first_name or "A member"
            user_id = user.id
            member_type = "Bot" if user.bot else "User"
            farewell_text = f"<b>Nice Knowing You, @{username}!</b>"
            LOGGER.info(f"{member_type} @{username} (ID: {user_id}) left {event.chat.title}.")
            await app.send_message(event.chat_id, farewell_text, parse_mode="html")
