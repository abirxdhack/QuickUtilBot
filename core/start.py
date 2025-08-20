#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from telethon.tl.custom import Button
from config import UPDATE_CHANNEL_URL, COMMAND_PREFIX, BAN_REPLY
from core import banned_users
import asyncio

def setup_start_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}start$', incoming=True))
    async def start_message(event):
        user_id = event.sender_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='md')
            return
        
        chat_id = event.chat_id
        animation_message = await event.respond("<b>Starting Quick Util ⚙️...</b>", parse_mode='html')
        await asyncio.sleep(0.3)
        await app.edit_message(chat_id, animation_message, "<b>Generating Session Keys Please Wait...</b>", parse_mode='html')
        await asyncio.sleep(0.3)
        await app.delete_messages(chat_id, animation_message)
        
        full_name = "User"
        
        if event.sender:
            first_name = getattr(event.sender, 'first_name', '') or ""
            last_name = getattr(event.sender, 'last_name', '') or ""
            full_name = f"{first_name} {last_name}".strip() or "User"
        
        if event.is_private:
            response_text = (
                f"<b>Hi {full_name}! Welcome To This Bot</b>\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Quick Util</b> The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit cards, and more. Simplify your tasks with ease!\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Don't forget to <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> for updates!</b>"
            )
        elif event.is_group or event.is_channel:
            chat_entity = await event.get_chat()
            group_name = getattr(chat_entity, 'title', 'this group')
            
            if event.sender:
                response_text = (
                    f"<b>Hi {full_name}! Welcome To This Bot</b>\n"
                    "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>Quick Util</b> The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit cards, and more. Simplify your tasks with ease!\n"
                    "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>Don't forget to <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> for updates!</b>"
                )
            else:
                response_text = (
                    f"<b>Hi! Welcome {group_name} To This Bot</b>\n"
                    "<b>━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>Quick Util</b> The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit cards, and more. Simplify your tasks with ease!\n"
                    "<b>━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>Don't forget to <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> for updates!</b>"
                )
        else:
            response_text = (
                f"<b>Hi {full_name}! Welcome To This Bot</b>\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                "<b>Quick Util</b> The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit cards, and more. Simplify your tasks with ease!\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Don't forget to <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> for updates!</b>"
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

