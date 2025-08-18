import aiohttp
import aiofiles
import json
import os
import time
from telethon import TelegramClient, events
from config import COMMAND_PREFIX, BAN_REPLY
from core import banned_users
from utils import LOGGER, notify_admin

def setup_getusr_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}getusers( .+)?$'))
    async def get_users(event):
        user_id = event.sender_id
        chat_id = event.chat_id
        if await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='markdown')
            return
        if event.is_group or event.is_channel:
            await event.respond("**❌ This command is only available in private chats.**", parse_mode='markdown')
            return
        args = event.raw_text.strip().split()
        if len(args) < 2 or not args[1].strip():
            await event.respond("**❌ Please provide a valid bot token after the command.**", parse_mode='markdown')
            return
        bot_token = args[1].strip()
        if ':' not in bot_token:
            await event.respond("**❌ Invalid bot token format.**", parse_mode='markdown')
            return
        loading_message = await event.respond("**Fetching user data...**", parse_mode='markdown')
        bot_info = await validate_bot_token(bot_token)
        if not bot_info:
            await loading_message.edit(text="**❌ Invalid Bot Token Provided**", parse_mode='markdown')
            return
        data = await fetch_bot_data(bot_token)
        if not data:
            await loading_message.edit(text="**❌ Failed to fetch user data**", parse_mode='markdown')
            return
        file_path = f"/tmp/users_{user_id}_{int(time.time())}.json"
        try:
            await save_and_send_data(app, chat_id, data, file_path)
            await loading_message.delete()
        except Exception as e:
            LOGGER.error(f"Error processing data for user {user_id}: {str(e)}")
            await notify_admin(app, "/getusers", e, event)
            await loading_message.edit(text="**❌ Error processing data**", parse_mode='markdown')
        finally:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    LOGGER.warning(f"Cleanup error for {file_path}")

async def validate_bot_token(bot_token: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/bot{bot_token}/getMe") as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if not data.get("ok", False) or "result" not in data:
                    return None
                return data["result"]
    except aiohttp.ClientError:
        return None

async def fetch_bot_data(bot_token: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://gtuser-production.up.railway.app/tgusers?token={bot_token}") as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if not isinstance(data, dict) or "bot_info" not in data or "users" not in data or "chats" not in data:
                    return None
                return data
    except aiohttp.ClientError:
        return None

async def save_and_send_data(app: TelegramClient, chat_id: int, data: dict, file_path: str):
    async with aiofiles.open(file_path, mode='w') as f:
        await f.write(json.dumps(data, indent=4))
    bot_info = data.get("bot_info", {})
    total_users = data.get("total_users", 0)
    total_chats = data.get("total_chats", 0)
    caption = (
        "**📌 Requested Users**\n"
        "**━━━━━━━━**\n"
        f"**👤 Username:** `{bot_info.get('username', 'N/A')}`\n"
        f"**👥 Total Users:** `{total_users}`\n"
        f"**👥 Total Chats:** `{total_chats}`\n"
        "**━━━━━━━━**\n"
        "**📂 File contains user & chat IDs.**"
    )
    await app.send_file(
        chat_id,
        file=file_path,
        caption=caption,
        parse_mode='markdown'
    )