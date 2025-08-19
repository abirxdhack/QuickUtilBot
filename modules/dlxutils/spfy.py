import os
import time
import requests
import aiohttp
import re
import asyncio
import aiofiles
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeAudio, InputWebDocument
from telethon.tl.custom import Button
from typing import Optional
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, progress_bar, notify_admin
from core import banned_users
import urllib.parse

logger = LOGGER

class Config:
    TEMP_DIR = Path("./downloads")

Config.TEMP_DIR.mkdir(exist_ok=True)
executor = ThreadPoolExecutor(max_workers=10)

async def sanitize_filename(title: str) -> str:
    title = re.sub(r'[<>:"/\\|?*]', '', title[:50]).strip()
    return f"{title.replace(' ', '_')}_{int(time.time())}"

async def download_image(url: str, output_path: str) -> Optional[str]:
    logger.info(f"Starting download of image from {url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    async with aiofiles.open(output_path, 'wb') as file:
                        await file.write(await response.read())
                    logger.info(f"Image downloaded successfully to {output_path}")
                    return output_path
                else:
                    logger.error(f"Failed to download image: HTTP status {response.status}")
                    await notify_admin(None, f"{COMMAND_PREFIX}sp", Exception(f"Failed to download image: HTTP status {response.status}"), None)
    except Exception as e:
        logger.error(f"Failed to download image: {e}")
        await notify_admin(None, f"{COMMAND_PREFIX}sp", e, None)
    return None

async def handle_spotify_request(client: TelegramClient, event, input_text: Optional[str]):
    if not input_text and event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg and reply_msg.text:
            input_text = reply_msg.text.strip()
    if not input_text:
        await event.respond(
            "**Please provide a track Spotify URL**",
            parse_mode="markdown"
        )
        logger.warning(f"No input provided, user: {event.sender_id or 'unknown'}, chat: {event.chat_id}")
        return
    is_url = input_text.lower().startswith('http')
    status_message = await event.respond(
        "**Searching The Music**",
        parse_mode="markdown"
    )
    try:
        async with aiohttp.ClientSession() as session:
            if is_url:
                logger.info(f"Processing Spotify URL: {input_text}")
                api_url = f"https://spotify-gold-one.vercel.app/sp/dl?url={urllib.parse.quote(input_text)}"
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Track API response: {data}")
                        if data["status"]:
                            await status_message.edit("**Found ☑️ Downloading...**", parse_mode="markdown")
                        else:
                            await status_message.edit("**Please Provide A Valid Spotify URL ❌**", parse_mode="markdown")
                            logger.error(f"Invalid Spotify URL: {input_text}")
                            return
                    else:
                        await status_message.edit("**❌ Song Not Available On Spotify**", parse_mode="markdown")
                        logger.error(f"API request failed: HTTP status {response.status}")
                        await notify_admin(client, f"{COMMAND_PREFIX}sp", Exception(f"API request failed: HTTP status {response.status}"), status_message)
                        return
            else:
                logger.info(f"Processing Spotify search query: {input_text}")
                encoded_query = urllib.parse.quote(input_text)
                api_url = f"https://spotify-gold-one.vercel.app/sp/search?q={encoded_query}"
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Search API response: {data}")
                        if data["status"] and data["results"]:
                            await status_message.edit("**Found ☑️ Downloading...**", parse_mode="markdown")
                            track = data["results"][0]
                            track_url = track["track_url"]
                            logger.info(f"Selected track: {track['title']} (URL: {track_url})")
                            track_api_url = f"https://spotify-gold-one.vercel.app/sp/dl?url={urllib.parse.quote(track_url)}"
                            async with session.get(track_api_url) as track_response:
                                if track_response.status == 200:
                                    data = await track_response.json()
                                    logger.info(f"Track API response: {data}")
                                    if not data["status"]:
                                        await status_message.edit("**Song Metadata Unavailable**", parse_mode="markdown")
                                        logger.error("Song metadata unavailable")
                                        await notify_admin(client, f"{COMMAND_PREFIX}sp", Exception("Song metadata unavailable"), status_message)
                                        return
                                else:
                                    await status_message.edit("**❌ Song Unavailable Bro Try Later**", parse_mode="markdown")
                                    logger.error(f"Track API request failed: HTTP status {track_response.status}")
                                    await notify_admin(client, f"{COMMAND_PREFIX}sp", Exception(f"Track API request failed: HTTP status {track_response.status}"), status_message)
                                    return
                        else:
                            await status_message.edit("**Sorry No Songs Matched To Your Search!**", parse_mode="markdown")
                            logger.error(f"No songs matched search query: {input_text}")
                            return
                    else:
                        await status_message.edit("**❌ Sorry Bro Spotify Search API Dead**", parse_mode="markdown")
                        logger.error(f"Search API request failed: HTTP status {response.status}")
                        await notify_admin(client, f"{COMMAND_PREFIX}sp", Exception(f"Search API request failed: HTTP status {response.status}"), status_message)
                        return
            title = data["title"]
            artists = data["artist"]
            duration = data["duration"]
            album = data["album"]
            release_date = data["release_date"]
            spotify_url = data["track_url"]
            download_url = data["download_url"]
            cover_url = data.get("cover_art")
            cover_path = None
            if cover_url:
                Config.TEMP_DIR.mkdir(exist_ok=True)
                cover_path = Config.TEMP_DIR / f"{await sanitize_filename(title)}.jpg"
                downloaded_path = await download_image(cover_url, str(cover_path))
                if downloaded_path:
                    logger.info(f"Cover image downloaded to {downloaded_path}")
                else:
                    logger.warning("Failed to download cover image")
                    cover_path = None
            safe_title = await sanitize_filename(title)
            output_filename = Config.TEMP_DIR / f"{safe_title}.mp3"
            logger.info(f"Starting download of audio file from {download_url}")
            async with session.get(download_url) as response:
                if response.status == 200:
                    async with aiofiles.open(output_filename, 'wb') as file:
                        await file.write(await response.read())
                    logger.info(f"Audio file downloaded successfully to {output_filename}")
                else:
                    await status_message.edit("**❌ Sorry Bro Spotify DL API Dead**", parse_mode="markdown")
                    logger.error(f"Audio download failed: HTTP status {response.status}")
                    await notify_admin(client, f"{COMMAND_PREFIX}sp", Exception(f"Audio download failed: HTTP status {response.status}"), status_message)
                    return
            if event.sender and hasattr(event.sender, 'first_name'):
                user_full_name = f"{event.sender.first_name} {getattr(event.sender, 'last_name', '') or ''}".strip()
                user_info = f"[{user_full_name}](tg://user?id={event.sender_id})"
            else:
                group_name = getattr(event.chat, 'title', None) or "this group"
                group_username = getattr(event.chat, 'username', None)
                group_url = f"https://t.me/{group_username}" if group_username else "this group"
                user_info = f"[{group_name}]({group_url})"
            audio_caption = (
                f"🌟 **Title**: `{title}`\n"
                f"💥 **Artist**: `{artists}`\n"
                f"✨ **Duration**: `{duration}`\n"
                f"👀 **Album**: `{album}`\n"
                f"🎵 **Release Date**: `{release_date}`\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"**Downloaded By**: {user_info}"
            )
            buttons = [[Button.url("🎸 Listen On Spotify", spotify_url)]]
            last_update_time = [0]
            start_time = time.time()
            logger.info("Starting upload of audio file to Telegram")
            attributes = [DocumentAttributeAudio(
                duration=int(float(duration.split(':')[0]) * 60 + float(duration.split(':')[1])),
                title=title,
                performer=artists
            )]
            await client.send_file(
                event.chat_id,
                file=str(output_filename),
                caption=audio_caption,
                parse_mode="markdown",
                attributes=attributes,
                thumb=str(cover_path) if cover_path else None,
                buttons=buttons,
                progress_callback=lambda c, t: progress_bar(c, t, status_message, start_time, last_update_time)
            )
            logger.info("Upload of audio successfully completed")
            if os.path.exists(output_filename):
                os.remove(output_filename)
                logger.info(f"Deleted audio file: {output_filename}")
            if cover_path and os.path.exists(cover_path):
                os.remove(cover_path)
                logger.info(f"Deleted cover image: {cover_path}")
            await status_message.delete()
            logger.info("Status message deleted")
    except Exception as e:
        await status_message.edit("**❌ Sorry Bro Spotify DL API Dead**", parse_mode="markdown")
        logger.error(f"Error processing Spotify request: {str(e)}")
        await notify_admin(client, f"{COMMAND_PREFIX}sp", Exception(str(e)), status_message)

def setup_spotify_handler(app: TelegramClient):
    command_prefix_regex = f"[{''.join(map(re.escape, COMMAND_PREFIX))}]"
    @app.on(events.NewMessage(pattern=rf"^{command_prefix_regex}sp(\s+.*)?$"))
    async def spotify_command(event):
        user_id = event.sender_id if event.sender_id else None
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode="markdown")
            return
        command_parts = event.text.split(maxsplit=1)
        input_text = command_parts[1].strip() if len(command_parts) > 1 else None
        logger.info(f"Spotify command received: input_text='{input_text or 'None'}', user: {user_id or 'unknown'}, chat: {event.chat_id}")
        await handle_spotify_request(app, event, input_text)