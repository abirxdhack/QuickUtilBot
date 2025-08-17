#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.custom import Button
from config import COMMAND_PREFIX, OWNER_ID
from core import auth_admins
from utils import LOGGER

logger = LOGGER
load_dotenv()
user_session = {}
settings_lock = asyncio.Lock()

def validate_message(func):
    async def wrapper(event):
        if not event.message or not event.sender_id:
            logger.error("Invalid message received")
            return
        return await func(event)
    return wrapper

def admin_only(func):
    async def wrapper(event):
        user_id = event.sender_id
        auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            logger.info(f"Unauthorized settings access attempt by user_id {user_id}")
            return
        return await func(event)
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
                logger.warning(f"Duplicate keys found in .env: {', '.join(duplicates)}")
    except Exception as e:
        logger.error(f"Error detecting duplicate keys in .env: {e}")

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
        logger.error(f"Error loading environment variables: {e}")
        return {}

async def update_env_var(key, value):
    async with settings_lock:
        try:
            env_vars = await load_env_vars()
            env_vars[key] = value
            os.environ[key] = value
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, sync_write_env_vars, env_vars)
            logger.info(f"Updated environment variable: {key}")
        except Exception as e:
            logger.error(f"Error updating environment variable {key}: {e}")

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
            Button.inline(current_keys[i], f"settings_edit_{current_keys[i]}")
        ]
        if i + 1 < len(current_keys):
            buttons.append(Button.inline(current_keys[i + 1], f"settings_edit_{current_keys[i + 1]}"))
        rows.append(buttons)
    nav_buttons = []
    if page > 0:
        nav_buttons.append(Button.inline("⬅️ Previous", f"settings_page_{page - 1}"))
    if end < len(keys):
        nav_buttons.append(Button.inline("Next ➡️", f"settings_page_{page + 1}"))
    if nav_buttons:
        if page == 0:
            nav_buttons.append(Button.inline("Close ❌", "settings_closesettings"))
            rows.append(nav_buttons)
        else:
            rows.append(nav_buttons)
    if page > 0:
        rows.append([Button.inline("Close ❌", "settings_closesettings")])
    return rows

def setup_settings_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'({"|".join(COMMAND_PREFIX)})settings$'))
    @validate_message
    @admin_only
    async def show_settings(event):
        logger.info(f"Settings command initiated by user_id {event.sender_id}")
        await event.client.send_message(
            entity=event.chat_id,
            message="**Select a change or edit 👇**",
            parse_mode='markdown',
            buttons=build_menu()
        )

    @app.on(events.CallbackQuery(pattern=r"^settings_page_(\d+)$"))
    async def paginate_menu(event):
        user_id = event.sender_id
        auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            logger.info(f"Unauthorized pagination attempt by user_id {user_id}")
            await event.answer()
            return
        page = int(event.data.decode().split("_")[2])
        await event.edit(
            text="**Select a change or edit 👇**",
            parse_mode='markdown',
            buttons=build_menu(page)
        )
        await event.answer()
        logger.debug(f"Paginated to page {page} by user_id {user_id}")

    @app.on(events.CallbackQuery(pattern=r"^settings_edit_(.+)"))
    async def edit_var(event):
        user_id = event.sender_id
        auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            logger.info(f"Unauthorized edit attempt by user_id {user_id}")
            await event.answer()
            return
        var_name = event.data.decode().split("_", 2)[2]
        if var_name not in config_keys:
            await event.answer("Invalid variable selected.", show_alert=True)
            logger.warning(f"Invalid variable {var_name} selected by user_id {user_id}")
            return
        user_session[user_id] = {
            "var": var_name,
            "chat_id": event.chat_id
        }
        await event.edit(
            text=f"**Editing `{var_name}`. Please send the new value below.**",
            parse_mode='markdown',
            buttons=[[Button.inline("Cancel ❌", "settings_cancel_edit")]]
        )
        await event.answer()
        logger.info(f"User_id {user_id} started editing variable {var_name}")

    @app.on(events.CallbackQuery(pattern=r"^settings_cancel_edit$"))
    async def cancel_edit(event):
        user_id = event.sender_id
        auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            logger.info(f"Unauthorized cancel edit attempt by user_id {user_id}")
            await event.answer()
            return
        user_session.pop(user_id, None)
        await event.edit(
            text="**Variable Editing Cancelled ❌**",
            parse_mode='markdown'
        )
        await event.answer()
        logger.info(f"User_id {user_id} cancelled variable editing")

    @app.on(events.NewMessage())
    @validate_message
    async def update_value(event):
        user_id = event.sender_id
        session = user_session.get(user_id)
        if not session or session["chat_id"] != event.chat_id:
            return
        message_text = event.message.text
        if not message_text:
            await event.client.send_message(
                entity=event.chat_id,
                message="**Please provide a text value to update ❌**",
                parse_mode='markdown'
            )
            return
        var, val = session["var"], message_text.strip()
        await update_env_var(var, val)
        config_keys[var] = val
        await event.client.send_message(
            entity=event.chat_id,
            message=f"**`{var}` Has Been Successfully Updated To `{val}`. ✅**",
            parse_mode='markdown'
        )
        user_session.pop(user_id, None)
        logger.info(f"User_id {user_id} updated variable {var} to {val}")

    @app.on(events.CallbackQuery(pattern=r"^settings_closesettings$"))
    async def close_menu(event):
        user_id = event.sender_id
        auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            logger.info(f"Unauthorized close menu attempt by user_id {user_id}")
            await event.answer()
            return
        await event.edit(
            text="**Closed Settings Menu✅**",
            parse_mode='markdown'
        )
        await event.answer()
        logger.info(f"User_id {user_id} closed settings menu")

