# Copyright @ISmartCoder
# Updates Channel: https://t.me/TheSmartDev
import os
import time
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeAudio
from pydub import AudioSegment
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

async def handle_voice_command(event):
    user_id = event.sender_id
    if await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY, parse_mode='md')
        LOGGER.info(f"Banned user {user_id} attempted to use /voice")
        return

    reply = await event.get_reply_message()
    if not reply:
        await event.respond("**Please reply to an audio message.**", parse_mode='md')
        LOGGER.warning("No reply to an audio message provided for /voice command")
        return

    if not (reply.audio or reply.voice or (reply.document and any(isinstance(attr, DocumentAttributeAudio) for attr in reply.document.attributes))):
        await event.respond("**⚠️ Please reply to a valid audio file.**", parse_mode='md')
        LOGGER.warning("No valid audio file provided for /voice command")
        return

    file_extension = ""
    if reply.audio and any(isinstance(attr, DocumentAttributeAudio) and getattr(attr, 'file_name', None) for attr in reply.audio.attributes):
        file_extension = next(attr.file_name for attr in reply.audio.attributes if isinstance(attr, DocumentAttributeAudio) and getattr(attr, 'file_name', None)).split('.')[-1].lower()
    elif reply.document and any(isinstance(attr, DocumentAttributeAudio) and getattr(attr, 'file_name', None) for attr in reply.document.attributes):
        file_extension = next(attr.file_name for attr in reply.document.attributes if isinstance(attr, DocumentAttributeAudio) and getattr(attr, 'file_name', None)).split('.')[-1].lower()

    valid_audio_extensions = ['mp3', 'wav', 'ogg', 'm4a']
    if file_extension and file_extension not in valid_audio_extensions:
        await event.respond("**⚠️ Please reply to a valid audio file**", parse_mode='md')
        LOGGER.warning(f"Invalid audio file extension: {file_extension}")
        return

    processing_message = await event.respond("**Converting Mp3 To Voice Message✨..**", parse_mode='md')
    input_path = f"downloads/input_{user_id}_{int(time.time())}.{file_extension if file_extension else 'ogg'}"
    output_path = f"downloads/output_{user_id}_{int(time.time())}.ogg"
    os.makedirs("downloads", exist_ok=True)

    try:
        await reply.download_media(input_path)
        LOGGER.info(f"Downloaded audio file to {input_path}")
        await convert_audio(input_path, output_path)
        LOGGER.info(f"Converted audio to {output_path}")
        await processing_message.delete()
        await event.client.send_file(
            event.chat_id,
            output_path,
            voice_note=True,
            caption=""
        )
        LOGGER.info("Voice message sent successfully")
    except Exception as e:
        await processing_message.edit("**Sorry Failed To Convert✨**", parse_mode='md')
        LOGGER.error(f"Failed to convert audio: {e}")
        await notify_admin(event.client, "/voice", e, event)
    finally:
        await cleanup_files(input_path, output_path)

async def convert_audio(input_path, output_path):
    audio = AudioSegment.from_file(input_path)
    audio.export(output_path, format="ogg", codec="libopus")

async def cleanup_files(*files):
    for file in files:
        try:
            if os.path.exists(file):
                os.remove(file)
                LOGGER.info(f"Removed temporary file {file}")
        except Exception as e:
            LOGGER.error(f"Failed to remove {file}: {e}")

def setup_voice_handler(app: TelegramClient):
    app.add_event_handler(
        handle_voice_command,
        events.NewMessage(pattern=f'^{COMMAND_PREFIX}voice')
    )