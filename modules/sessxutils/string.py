import aiohttp
import os
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from pyrogram import Client
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid
)
from telethon.errors import (
    ApiIdInvalidError,
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PasswordHashInvalidError
)
from asyncio.exceptions import TimeoutError
import asyncio
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

logger = LOGGER
TIMEOUT_OTP = 600
TIMEOUT_2FA = 300
session_data = {}

def setup_string_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^[{"".join(COMMAND_PREFIX)}](pyro|tele)$'))
    async def session_setup(event):
        user_id = event.sender_id if event.sender_id else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        if event.is_group or event.is_channel:
            await event.respond("**❌ String Session Generator Only Works In Private Chats**")
            return
        
        await cleanup_session(event.chat_id)
        
        platform = "PyroGram" if event.pattern_match.group(1) == "pyro" else "Telethon"
        await handle_start(app, event, platform)

    @app.on(events.CallbackQuery(pattern=r"^(start_session|restart_session|close_session)"))
    async def callback_query_handler(event):
        user_id = event.sender_id if event.sender_id else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        chat_id = event.chat_id
        if chat_id not in session_data:
            await event.answer("Session expired. Please start again with /pyro or /tele", alert=True)
            return
        
        await handle_callback_query(app, event)

    @app.on(events.NewMessage(func=lambda e: e.chat_id in session_data and not e.text.startswith(tuple(COMMAND_PREFIX))))
    async def text_handler(event):
        user_id = event.sender_id if event.sender_id else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        chat_id = event.chat_id
        if chat_id not in session_data:
            return
        
        session = session_data[chat_id]
        if not session.get("stage"):
            return
        
        await handle_text(app, event)

async def handle_start(client, event, platform):
    session_type = "Telethon" if platform == "Telethon" else "Pyrogram"
    session_data[event.chat_id] = {"type": session_type, "user_id": event.sender_id}
    
    buttons = [
        [Button.inline("Start", f"start_session_{session_type.lower()}"), Button.inline("Close", "close_session")]
    ]
    
    await event.respond(
        f"**Welcome To Secure {session_type} Session Generator !**\n"
        "**━━━━━━━━━━━━━━━━━━━━━━━━**\n"
        "This is a totally safe session string generator. We don't save any info that you will provide, so this is completely safe.\n\n"
        "**📵 Note: ** Don't send OTP directly. Otherwise, you may not be able to log in.\n\n"
        "**⚠️ Warn: ** Using the session for policy-violating activities may result in your Telegram account getting banned or deleted.\n\n"
        "❌ We are not responsible for any issues that may occur due to misuse.",
        buttons=buttons
    )

async def handle_callback_query(client, event):
    data = event.data.decode()
    chat_id = event.chat_id
    
    if chat_id not in session_data:
        await event.answer("Session expired. Please start again with /pyro or /tele", alert=True)
        return
    
    session = session_data[chat_id]
    
    if event.sender_id != session.get("user_id"):
        await event.answer("This session belongs to another user!", alert=True)
        return
    
    if data == "close_session":
        platform = session.get("type", "").lower()
        if platform == "pyrogram":
            await event.edit("**❌Cancelled. You can start by sending /pyro**")
        elif platform == "telethon":
            await event.edit("**❌Cancelled. You can start by sending /tele**")
        await cleanup_session(chat_id)
        return

    if data.startswith("start_session_"):
        session_type = data.split('_')[2]
        buttons = [
            [Button.inline("Restart", f"restart_session_{session_type}"), Button.inline("Close", "close_session")]
        ]
        await event.edit("**Send Your API ID**", buttons=buttons)
        session["stage"] = "api_id"

    if data.startswith("restart_session_"):
        session_type = data.split('_')[2]
        await cleanup_session(chat_id)
        await handle_start(client, event, platform=session_type.capitalize())

async def handle_text(client, event):
    chat_id = event.chat_id
    session = session_data[chat_id]
    stage = session.get("stage")

    if stage == "api_id":
        try:
            api_id = int(event.text)
            session["api_id"] = api_id
            buttons = [
                [Button.inline("Restart", f"restart_session_{session['type'].lower()}"), Button.inline("Close", "close_session")]
            ]
            await event.respond("**Send Your API Hash**", buttons=buttons)
            session["stage"] = "api_hash"
        except ValueError:
            await event.respond("**❌Invalid API ID. Please enter a valid integer.**")
            logger.error(f"Invalid API ID provided by user {event.sender_id}")

    elif stage == "api_hash":
        session["api_hash"] = event.text
        buttons = [
            [Button.inline("Restart", f"restart_session_{session['type'].lower()}"), Button.inline("Close", "close_session")]
        ]
        await event.respond("** Send Your Phone Number\n[Example: +880xxxxxxxxxx] **", buttons=buttons)
        session["stage"] = "phone_number"

    elif stage == "phone_number":
        session["phone_number"] = event.text
        otp_message = await event.respond("**Sending OTP Check PM.....**")
        await send_otp(client, event, otp_message)

    elif stage == "otp":
        otp = ''.join([char for char in event.text if char.isdigit()])
        session["otp"] = otp
        otp_message = await event.respond("**Checking & Processing Your OTP**")
        await validate_otp(client, event, otp_message)

    elif stage == "2fa":
        session["password"] = event.text
        await validate_2fa(client, event)

async def cleanup_session(chat_id):
    if chat_id in session_data:
        session = session_data[chat_id]
        client_obj = session.get("client_obj")
        if client_obj:
            asyncio.create_task(disconnect_client(client_obj, session.get("type")))
        del session_data[chat_id]
        logger.info(f"Session data cleared for user {chat_id}")

async def disconnect_client(client_obj, session_type):
    try:
        if hasattr(client_obj, 'disconnect'):
            await client_obj.disconnect()
        elif hasattr(client_obj, 'stop'):
            await client_obj.stop()
        if session_type == "Pyrogram":
            session_file = ":memory:.session"
            if os.path.exists(session_file):
                os.remove(session_file)
    except Exception as e:
        logger.error(f"Error during client disconnect: {str(e)}")

async def send_otp(client, event, otp_message):
    session = session_data[event.chat_id]
    api_id = session["api_id"]
    api_hash = session["api_hash"]
    phone_number = session["phone_number"]
    telethon = session["type"] == "Telethon"

    client_obj = TelegramClient(StringSession(), api_id, api_hash) if telethon else Client(":memory:", api_id, api_hash)

    try:
        await client_obj.connect()
        code = await client_obj.send_code_request(phone_number) if telethon else await client_obj.send_code(phone_number)

        session["client_obj"] = client_obj
        session["code"] = code
        session["stage"] = "otp"
        
        asyncio.create_task(handle_otp_timeout(client, event))

        buttons = [[Button.inline("Restart", f"restart_session_{session['type'].lower()}"), Button.inline("Close", "close_session")]]
        await event.respond("**✅Send The OTP as text. Please send a text message embedding the OTP like: 'AB5 CD0 EF3 GH7 IJ6'**", buttons=buttons)
        await otp_message.delete()

    except (ApiIdInvalidError, ApiIdInvalid):
        buttons = [[Button.inline("Restart", f"restart_session_{session['type'].lower()}"), Button.inline("Close", "close_session")]]
        await event.respond('**❌ `API_ID` and `API_HASH` combination is invalid**', buttons=buttons)
        await otp_message.delete()
        logger.error(f"Invalid API_ID/API_HASH for user {event.sender_id}")
        await cleanup_session(event.chat_id)

    except (PhoneNumberInvalidError, PhoneNumberInvalid):
        buttons = [[Button.inline("Restart", f"restart_session_{session['type'].lower()}"), Button.inline("Close", "close_session")]]
        await event.respond('**❌`PHONE_NUMBER` is invalid.**', buttons=buttons)
        await otp_message.delete()
        logger.error(f"Invalid phone number for user {event.sender_id}")
        await cleanup_session(event.chat_id)

async def handle_otp_timeout(client, event):
    await asyncio.sleep(TIMEOUT_OTP)
    if event.chat_id in session_data and session_data[event.chat_id].get("stage") == "otp":
        await client.send_message(
            entity=event.chat_id,
            message="**❌ Bro Your OTP Has Expired**"
        )
        await cleanup_session(event.chat_id)
        logger.info(f"OTP timed out for user {event.sender_id}")

async def validate_otp(client, event, otp_message):
    session = session_data[event.chat_id]
    client_obj = session["client_obj"]
    phone_number = session["phone_number"]
    otp = session["otp"]
    code = session["code"]
    telethon = session["type"] == "Telethon"

    try:
        if telethon:
            await client_obj.sign_in(phone_number, otp)
        else:
            await client_obj.sign_in(phone_number, code.phone_code_hash, otp)

        await otp_message.delete()
        await generate_session(client, event)

    except (PhoneCodeInvalidError, PhoneCodeInvalid):
        buttons = [
            [Button.inline("Restart", f"restart_session_{session['type'].lower()}"), Button.inline("Close", "close_session")]
        ]
        await otp_message.edit('**❌Bro Your OTP Is Wrong**', buttons=buttons)
        logger.error(f"Invalid OTP provided by user {event.sender_id}")
        await cleanup_session(event.chat_id)
        return

    except (PhoneCodeExpiredError, PhoneCodeExpired):
        buttons = [
            [Button.inline("Restart", f"restart_session_{session['type'].lower()}"), Button.inline("Close", "close_session")]
        ]
        await otp_message.edit('**❌Bro OTP Has expired**', buttons=buttons)
        logger.error(f"Expired OTP for user {event.sender_id}")
        await cleanup_session(event.chat_id)
        return

    except (SessionPasswordNeededError, SessionPasswordNeeded):
        session["stage"] = "2fa"
        
        asyncio.create_task(handle_2fa_timeout(client, event))
        
        buttons = [
            [Button.inline("Restart", f"restart_session_{session['type'].lower()}"), Button.inline("Close", "close_session")]
        ]
        await otp_message.edit("**❌ 2FA Is Required To Login. Please Enter 2FA**", buttons=buttons)
        logger.info(f"2FA required for user {event.sender_id}")

    except Exception as e:
        buttons = [
            [Button.inline("Restart", f"restart_session_{session['type'].lower()}"), Button.inline("Close", "close_session")]
        ]
        await otp_message.edit('**❌ Something went wrong. Please try again.**', buttons=buttons)
        logger.error(f"Unexpected error during OTP validation for user {event.sender_id}: {str(e)}")
        await cleanup_session(event.chat_id)
        return

async def handle_2fa_timeout(client, event):
    await asyncio.sleep(TIMEOUT_2FA)
    if event.chat_id in session_data and session_data[event.chat_id].get("stage") == "2fa":
        await client.send_message(
            entity=event.chat_id,
            message="**❌ Bro Your 2FA Input Has Expired**"
        )
        await cleanup_session(event.chat_id)
        logger.info(f"2FA timed out for user {event.sender_id}")

async def validate_2fa(client, event):
    session = session_data[event.chat_id]
    client_obj = session["client_obj"]
    password = session["password"]
    telethon = session["type"] == "Telethon"

    try:
        if telethon:
            await client_obj.sign_in(password=password)
        else:
            await client_obj.check_password(password=password)

        await generate_session(client, event)

    except (PasswordHashInvalidError, PasswordHashInvalid):
        buttons = [
            [Button.inline("Restart", f"restart_session_{session['type'].lower()}"), Button.inline("Close", "close_session")]
        ]
        await event.respond('**❌Invalid Password Provided**', buttons=buttons)
        logger.error(f"Invalid 2FA password provided by user {event.sender_id}")
        await cleanup_session(event.chat_id)
        return

async def generate_session(client, event):
    session = session_data[event.chat_id]
    client_obj = session["client_obj"]
    telethon = session["type"] == "Telethon"

    if telethon:
        string_session = client_obj.session.save()
    else:
        string_session = await client_obj.export_session_string()

    text = (
        f"**{session['type']} Session String From Smart Tool **\n"
        "**━━━━━━━━━━━━━━━━━━━━━━━━**\n"
        f"`{string_session}`\n"
        "**━━━━━━━━━━━━━━━━━━━━━━━━**\n"
        "**⚠️ Warn: ** Using the session for policy-violating activities may result in your Telegram account getting banned or deleted."
    )

    try:
        await client_obj.send_message("me", text)
    except:
        pass

    await cleanup_session(event.chat_id)
    await event.respond("**This string has been saved ✅ in your Saved Messages**")
    logger.info(f"Session string generated successfully for user {event.sender_id}")