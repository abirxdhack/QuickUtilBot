import os
import re
import asyncio
import time
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeImageSize
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, progress_bar, notify_admin
from core import banned_users

logger = LOGGER

class Config:
    TEMP_DIR = Path("./downloads")

Config.TEMP_DIR.mkdir(exist_ok=True)

class PinterestDownloader:
    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir

    async def sanitize_filename(self, title: str) -> str:
        title = re.sub(r'[<>:"/\\|?*]', '', title[:50]).strip()
        return f"{title.replace(' ', '_')}_{int(time.time())}"

    async def download_media(self, url: str, downloading_message) -> Optional[dict]:
        self.temp_dir.mkdir(exist_ok=True)
        api_url = f"https://pin-teal.vercel.app/dl?url={url}"
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=100),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.get(api_url) as response:
                    logger.info(f"API request to {api_url} returned status {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"API response: {data}")
                        if data.get("status") != "success":
                            logger.error("API response status is not success")
                            await downloading_message.edit("**Unable To Extract Media**", parse_mode="markdown")
                            return None
                        media = data.get("media", [])
                        title = data.get("title", "Pinterest Media")
                        high_quality_video = None
                        thumbnail = None
                        for item in media:
                            if item.get("type") == "video/mp4" and (not high_quality_video or "720p" in item.get("quality")):
                                high_quality_video = item.get("url")
                            if item.get("type") == "image/jpeg" and item.get("quality") == "Thumbnail":
                                thumbnail = item.get("url")
                        if not high_quality_video and not thumbnail:
                            logger.error("No suitable media found in API response")
                            await downloading_message.edit("**Unable To Extract Media**", parse_mode="markdown")
                            return None
                        await downloading_message.edit("**Found ☑️ Downloading...**", parse_mode="markdown")
                        safe_title = await self.sanitize_filename(title)
                        result = {'title': title, 'webpage_url': url}
                        if high_quality_video:
                            video_filename = self.temp_dir / f"{safe_title}.mp4"
                            await self._download_file(session, high_quality_video, video_filename)
                            result['video_filename'] = str(video_filename)
                            if thumbnail:
                                thumbnail_filename = self.temp_dir / f"{safe_title}_thumb.jpg"
                                await self._download_file(session, thumbnail, thumbnail_filename)
                                result['thumbnail_filename'] = str(thumbnail_filename)
                        else:
                            image_filename = self.temp_dir / f"{safe_title}.jpg"
                            await self._download_file(session, thumbnail, image_filename)
                            result['image_filename'] = str(image_filename)
                        return result
                    logger.error(f"API request failed: HTTP status {response.status}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Pinterest download error: {e}")
            if hasattr(downloading_message, 'client'):
                await notify_admin(downloading_message.client, f"{COMMAND_PREFIX}pnt", e, downloading_message)
            return None
        except asyncio.TimeoutError:
            logger.error("Request to Pinterest API timed out")
            if hasattr(downloading_message, 'client'):
                await notify_admin(downloading_message.client, f"{COMMAND_PREFIX}pnt", asyncio.TimeoutError("Request to Pinterest API timed out"), downloading_message)
            return None
        except Exception as e:
            logger.error(f"Pinterest download error: {e}")
            if hasattr(downloading_message, 'client'):
                await notify_admin(downloading_message.client, f"{COMMAND_PREFIX}pnt", e, downloading_message)
            return None

    async def _download_file(self, session: aiohttp.ClientSession, url: str, dest: Path):
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    logger.info(f"Downloading media from {url} to {dest}")
                    async with aiofiles.open(dest, mode='wb') as f:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            await f.write(chunk)
                    logger.info(f"Media downloaded successfully to {dest}")
                else:
                    logger.error(f"Failed to download file: HTTP status {response.status}")
                    raise Exception(f"Failed to download file: {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Error downloading file from {url}: {e}")
            await notify_admin(None, f"{COMMAND_PREFIX}pnt", e, None)
            raise

def setup_pinterest_handler(app: TelegramClient):
    pin_downloader = PinterestDownloader(Config.TEMP_DIR)
    command_prefix_regex = f"[{''.join(map(re.escape, COMMAND_PREFIX))}]"

    @app.on(events.NewMessage(pattern=rf"^{command_prefix_regex}(pnt|pint)(\s+https?://(pin\.it|in\.pinterest\.com|www\.pinterest\.com)/\S+)?$"))
    async def pin_handler(event):
        user_id = event.sender_id if event.sender_id else None
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode="markdown")
            return
        url = None
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg and reply_msg.text:
                match = re.search(r"https?://(pin\.it|in\.pinterest\.com|www\.pinterest\.com)/\S+", reply_msg.text)
                if match:
                    url = match.group(0)
        if not url:
            command_parts = event.text.split(maxsplit=1)
            if len(command_parts) > 1:
                match = re.search(r"https?://(pin\.it|in\.pinterest\.com|www\.pinterest\.com)/\S+", command_parts[1])
                if match:
                    url = match.group(0)
        if not url:
            await event.respond(
                "**Please provide a Pinterest link**",
                parse_mode="markdown"
            )
            logger.warning(f"No Pinterest URL provided, user: {user_id or 'unknown'}, chat: {event.chat_id}")
            return
        logger.info(f"Pinterest URL received: {url}, user: {user_id or 'unknown'}, chat: {event.chat_id}")
        downloading_message = await event.respond(
            "**Searching The Media**",
            parse_mode="markdown"
        )
        try:
            media_info = await pin_downloader.download_media(url, downloading_message)
            if not media_info:
                await downloading_message.edit("**Unable To Extract Media**", parse_mode="markdown")
                logger.error(f"Failed to download media for URL: {url}")
                return
            start_time = time.time()
            last_update_time = [start_time]
            title = media_info['title']
            webpage_url = media_info['webpage_url']
            if event.sender and hasattr(event.sender, 'first_name'):
                user_full_name = f"{event.sender.first_name} {getattr(event.sender, 'last_name', '') or ''}".strip()
                user_info = f"[{user_full_name}](tg://user?id={user_id})"
            else:
                group_name = getattr(event.chat, 'title', None) or "this group"
                group_username = getattr(event.chat, 'username', None)
                group_url = f"https://t.me/{group_username}" if group_username else "this group"
                user_info = f"[{group_name}]({group_url})"
            caption = (
                f"**Smart Pinterest Download →Successful ✅**\n"
                f"**━━━━━━━━━━━━━━━━━━━**\n"
                f"**Title:** **{title}**\n"
                f"**URL:** [Watch On Pinterest]({webpage_url})\n"
                f"**━━━━━━━━━━━━━━━━━━━**\n"
                f"**Media Downloaded By: {user_info} ✅**"
            )
            if 'video_filename' in media_info:
                thumbnail = media_info.get('thumbnail_filename')
                thumb_data = None
                if thumbnail and os.path.exists(thumbnail):
                    with open(thumbnail, 'rb') as thumb_file:
                        thumb_data = thumb_file.read()
                attributes = [DocumentAttributeVideo(
                    duration=0,
                    w=1280,
                    h=720,
                    supports_streaming=True
                )]
                await app.send_file(
                    event.chat_id,
                    media_info['video_filename'],
                    caption=caption,
                    parse_mode="markdown",
                    thumb=thumb_data,
                    attributes=attributes,
                    progress_callback=lambda c, t: progress_bar(c, t, downloading_message, start_time, last_update_time)
                )
            elif 'image_filename' in media_info:
                attributes = [DocumentAttributeImageSize(w=1280, h=720)]
                await app.send_file(
                    event.chat_id,
                    media_info['image_filename'],
                    caption=caption,
                    parse_mode="markdown",
                    attributes=attributes,
                    progress_callback=lambda c, t: progress_bar(c, t, downloading_message, start_time, last_update_time)
                )
            try:
                await downloading_message.delete()
            except:
                pass
            for key in ['video_filename', 'thumbnail_filename', 'image_filename']:
                if key in media_info and os.path.exists(media_info[key]):
                    os.remove(media_info[key])
                    logger.info(f"Deleted file: {media_info[key]}")
        except Exception as e:
            logger.error(f"Error processing Pinterest media: {e}")
            if hasattr(downloading_message, 'client'):
                await notify_admin(app, f"{COMMAND_PREFIX}pnt", e, downloading_message)
            await downloading_message.edit("**Pinterest Downloader API Dead**", parse_mode="markdown")
            for key in ['video_filename', 'thumbnail_filename', 'image_filename']:
                if key in locals() and key in media_info and os.path.exists(media_info[key]):
                    os.remove(media_info[key])
                    logger.info(f"Deleted file on error: {media_info[key]}")