# Copyright @ISmartCoder
# Updates Channel: https://t.me/TheSmartDev
import os
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeFilename
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin, progress_bar
from core import banned_users

DOWNLOAD_DIRECTORY = "./downloads/"
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

executor = ThreadPoolExecutor(max_workers=5)

async def aud_handler(event):
    user_id = event.sender_id
    if await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY, parse_mode='md')
        LOGGER.info(f"Banned user {user_id} attempted to use /aud or /convert")
        return

    reply = await event.get_reply_message()
    if not reply or not reply.video:
        await event.respond("**❌ Reply To A Video With The Command**", parse_mode='md', link_preview=False)
        LOGGER.warning("No valid video provided for /aud or /convert command")
        return

    command_parts = event.raw_text.split()
    if len(command_parts) <= 1:
        await event.respond("**❌ Provide Name For The File**", parse_mode='md', link_preview=False)
        LOGGER.warning("No audio file name provided for /aud or /convert command")
        return

    audio_file_name = command_parts[1]
    status_message = await event.respond("**Downloading Your File..✨**", parse_mode='md', link_preview=False)

    try:
        video_file_path = await reply.download_media(os.path.join(DOWNLOAD_DIRECTORY, f"input_{user_id}_{int(time.time())}.mp4"))
        LOGGER.info(f"Downloaded video file to {video_file_path}")
        await status_message.edit("**Converting To Mp3✨..**")
        audio_file_path = os.path.join(DOWNLOAD_DIRECTORY, f"{audio_file_name}_{user_id}_{int(time.time())}.mp3")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, convert_video_to_audio, video_file_path, audio_file_path)
        LOGGER.info(f"Converted video to audio at {audio_file_path}")
        start_time = time.time()
        last_update_time = [start_time]
        await event.client.send_file(
            event.chat_id,
            audio_file_path,
            caption=f"`{audio_file_name}`",
            parse_mode='md',
            attributes=[DocumentAttributeFilename(file_name=f"{audio_file_name}.mp3")],
            progress_callback=lambda current, total: progress_bar(current, total, status_message, start_time, last_update_time)
        )
        LOGGER.info("Audio file uploaded successfully")
        await status_message.delete()
    except Exception as e:
        LOGGER.error(f"An error occurred: {e}")
        await status_message.edit("**Sorry Bro Converter API Dead✨**")
        await notify_admin(event.client, "/aud or /convert", e, event)
    finally:
        if 'video_file_path' in locals() and os.path.exists(video_file_path):
            os.remove(video_file_path)
            LOGGER.info(f"Removed temporary video file {video_file_path}")
        if 'audio_file_path' in locals() and os.path.exists(audio_file_path):
            os.remove(audio_file_path)
            LOGGER.info(f"Removed temporary audio file {audio_file_path}")

def convert_video_to_audio(video_file_path, audio_file_path):
    import subprocess
    process = subprocess.run(
        ["ffmpeg", "-i", video_file_path, audio_file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if process.returncode != 0:
        raise Exception(f"ffmpeg error: {process.stderr.decode()}")

def setup_aud_handler(app: TelegramClient):
    app.add_event_handler(
        aud_handler,
        events.NewMessage(pattern=f'^{COMMAND_PREFIX}aud')
    )