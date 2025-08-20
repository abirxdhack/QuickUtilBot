# Copyright @ISmartCoder
# Updates Channel: https://t.me/TheSmartDev
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from telethon.tl.custom import Button
from config import UPDATE_CHANNEL_URL, COMMAND_PREFIX, BAN_REPLY
from core import banned_users

def setup_help_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(help|cmds)$', incoming=True))
    async def help_message(event):
        user_id = event.sender_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='md')
            return

        chat_id = event.chat_id
        full_name = "User"

        if event.sender:
            first_name = getattr(event.sender, 'first_name', '') or ""
            last_name = getattr(event.sender, 'last_name', '') or ""
            full_name = f"{first_name} {last_name}".strip() or "User"

        if event.is_private:
            response_text = (
                f"<b>Hi {full_name}! Welcome To This Bot</b>\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                "<b>Quick Util</b> The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit card tool, and more. Simplify your tasks with ease!\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Don't Forget To <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> For Updates!</b>"
            )
        elif event.is_group or event.is_channel:
            chat_entity = await event.get_chat()
            group_name = getattr(chat_entity, 'title', 'this group')
            
            if event.sender:
                response_text = (
                    f"<b>Hi {full_name}! Welcome To This Bot</b>\n"
                    "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    "<b>Quick Util</b> The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit card tool, and more. Simplify your tasks with ease!\n"
                    "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>Don't Forget To <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> For Updates!</b>"
                )
            else:
                response_text = (
                    f"<b>Hi! Welcome {group_name} To This Bot</b>\n"
                    "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    "<b>Quick Util</b> The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit card tool, and more. Simplify your tasks with ease!\n"
                    "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>Don't Forget To <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> For Updates!</b>"
                )

        await event.respond(
            response_text,
            parse_mode='html',
            buttons=[
                [Button.inline("⚙️ Main Menu", b"main_menu")],
                [Button.inline("ℹ️ About Me", b"about_me"), Button.inline("📄 Policy & Terms", b"policy_terms")]
            ],
            link_preview=False

        )
