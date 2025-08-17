# Copyright @ISmartCoder
# Updates Channel https://t.me/TheSmartDev
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ParseMode, ChatType
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
import os
from dotenv import load_dotenv
from config import COMMAND_PREFIX, OWNER_ID
from core import auth_admins
from utils import LOGGER

load_dotenv()

user_session = {}

settings_lock = asyncio.Lock()

def validate_message(func):
    async def wrapper(client: Client, message: Message):
        if not message or not message.from_user:
            LOGGER.error("Invalid message received")
            return
        return await func(client, message)
    return wrapper

def admin_only(func):
    async def wrapper(client: Client, message: Message):
        user_id = message.from_user.id
        auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            LOGGER.info(f"Unauthorized settings access attempt by user_id {user_id}")
            return
        return await func(client, message)
    return wrapper

def detect_duplicate_keys():
    try:
        with open(".env") as f:
            lines = f.readlines()
            seen_keys = set()
            duplicates = set()
            for line in lines:
                if '=' in line:
                    key = line.split("=", 1)[0].strip()
                    if key in seen_keys:
                        duplicates.add(key)
                    seen_keys.add(key)
            if duplicates:
                LOGGER.warning(f"Duplicate keys found in .env: {', '.join(duplicates)}")
    except Exception as e:
        LOGGER.error(f"Error detecting duplicate keys in .env: {e}")

async def load_env_vars():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sync_load_env_vars)

def sync_load_env_vars():
    try:
        with open(".env") as f:
            lines = f.readlines()
            variables = {}
            seen_keys = set()
            for line in lines:
                if '=' in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key not in seen_keys:
                        variables[key] = value
                        seen_keys.add(key)
            return variables
    except Exception as e:
        LOGGER.error(f"Error loading environment variables: {e}")
        return {}

async def update_env_var(key, value):
    async with settings_lock:
        try:
            env_vars = await load_env_vars()
            env_vars[key] = value
            os.environ[key] = value
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, sync_write_env_vars, env_vars)
            LOGGER.info(f"Updated environment variable: {key}")
        except Exception as e:
            LOGGER.error(f"Error updating environment variable {key}: {e}")

def sync_write_env_vars(env_vars):
    with open(".env", "w") as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")

detect_duplicate_keys()
config_keys = asyncio.get_event_loop().run_until_complete(load_env_vars())
ITEMS_PER_PAGE = 10

def build_menu(page=0):
    keys = list(config_keys.keys())
    start, end = page * ITEMS_PER_PAGE, (page + 1) * ITEMS_PER_PAGE
    current_keys = keys[start:end]

    rows = []
    for i in range(0, len(current_keys), 2):
        buttons = [
            InlineKeyboardButton(current_keys[i], callback_data=f"settings_edit_{current_keys[i]}")
        ]
        if i + 1 < len(current_keys):  
            buttons.append(InlineKeyboardButton(current_keys[i + 1], callback_data=f"settings_edit_{current_keys[i + 1]}"))
        rows.append(buttons)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"settings_page_{page - 1}"))
    if end < len(keys):
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"settings_page_{page + 1}"))
    if nav_buttons:
        if page == 0:
            nav_buttons.append(InlineKeyboardButton("Close ❌", callback_data="settings_closesettings"))
            rows.append(nav_buttons)
        else:
            rows.append(nav_buttons)

    if page > 0:
        rows.append([InlineKeyboardButton("Close ❌", callback_data="settings_closesettings")])

    return InlineKeyboardMarkup(rows)

def setup_settings_handler(app: Client):
    @validate_message
    async def debug_all(client: Client, message: Message):
        thread_id = getattr(message, "message_thread_id", None)
        is_reply = message.reply_to_message_id is not None
        message_text = message.text or message.caption or "[no text]"
        
        LOGGER.debug(
            f"Catch-all: user {message.from_user.id}, chat {message.chat.id}, "
            f"text='{message_text[:50]}', chat_type={message.chat.type}, "
            f"is_reply={is_reply}, reply_to={message.reply_to_message_id}, "
            f"thread={thread_id}"
        )

    @validate_message
    @admin_only
    async def show_settings(client: Client, message: Message):
        LOGGER.info(f"Settings command initiated by user_id {message.from_user.id}")
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            try:
                chat = await client.get_chat(message.chat.id)
                if not chat.permissions.can_send_messages:
                    await client.send_message(
                        chat_id=message.chat.id,
                        text="**Sorry Bro This Group Is Restricted ❌**",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
            except Exception as e:
                LOGGER.error(f"Failed to check permissions: {e}")
                return

        await client.send_message(
            chat_id=message.chat.id,
            text="**Select a change or edit 👇**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_menu()
        )

    async def paginate_menu(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            LOGGER.info(f"Unauthorized pagination attempt by user_id {user_id}")
            await callback_query.answer()
            return

        page = int(callback_query.data.split("_")[2])
        await callback_query.edit_message_reply_markup(reply_markup=build_menu(page))
        await callback_query.answer()
        LOGGER.debug(f"Paginated to page {page} by user_id {user_id}")

    async def edit_var(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            LOGGER.info(f"Unauthorized edit attempt by user_id {user_id}")
            await callback_query.answer()
            return

        var_name = callback_query.data.split("_", 2)[2]
        if var_name not in config_keys:
            await callback_query.answer("Invalid variable selected.", show_alert=True)
            LOGGER.warning(f"Invalid variable {var_name} selected by user_id {user_id}")
            return

        user_session[user_id] = {
            "var": var_name,
            "chat_id": callback_query.message.chat.id
        }
        
        await callback_query.edit_message_text(
            text=f"**Editing `{var_name}`. Please send the new value below.**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel ❌", callback_data="settings_cancel_edit")]])
        )
        LOGGER.info(f"User_id {user_id} started editing variable {var_name}")

    async def cancel_edit(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            LOGGER.info(f"Unauthorized cancel edit attempt by user_id {user_id}")
            await callback_query.answer()
            return

        user_session.pop(user_id, None)
        await callback_query.edit_message_text("**Variable Editing Cancelled ❌**", parse_mode=ParseMode.MARKDOWN)
        await callback_query.answer()
        LOGGER.info(f"User_id {user_id} cancelled variable editing")

    @validate_message
    async def update_value(client: Client, message: Message):
        user_id = message.from_user.id
        session = user_session.get(user_id)
        if not session or session["chat_id"] != message.chat.id:
            return

        message_text = message.text or message.caption
        if not message_text:
            await client.send_message(
                chat_id=message.chat.id,
                text="**Please provide a text value to update ❌**",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        var, val = session["var"], message_text.strip()
        await update_env_var(var, val)
        config_keys[var] = val
        
        await client.send_message(
            chat_id=message.chat.id,
            text=f"**`{var}` Has Been Successfully Updated To `{val}`. ✅**",
            parse_mode=ParseMode.MARKDOWN
        )
        
        user_session.pop(user_id, None)
        LOGGER.info(f"User_id {user_id} updated variable {var} to {val}")

    async def close_menu(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            LOGGER.info(f"Unauthorized close menu attempt by user_id {user_id}")
            await callback_query.answer()
            return

        await callback_query.edit_message_text("**Closed Settings Menu✅**", parse_mode=ParseMode.MARKDOWN)
        await callback_query.answer()
        LOGGER.info(f"User_id {user_id} closed settings menu")

    app.add_handler(MessageHandler(debug_all, filters.chat([ChatType.GROUP, ChatType.SUPERGROUP])), group=10)
    app.add_handler(MessageHandler(show_settings, filters.command(["settings"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group)), group=2)
    app.add_handler(MessageHandler(update_value, filters.text), group=2)
    app.add_handler(CallbackQueryHandler(paginate_menu, filters.regex(r"^settings_page_(\d+)$")), group=2)
    app.add_handler(CallbackQueryHandler(edit_var, filters.regex(r"^settings_edit_(.+)")), group=2)
    app.add_handler(CallbackQueryHandler(cancel_edit, filters.regex(r"^settings_cancel_edit$")), group=2)
    app.add_handler(CallbackQueryHandler(close_menu, filters.regex(r"^settings_closesettings$")), group=2)

