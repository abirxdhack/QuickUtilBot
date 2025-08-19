import os
import re
import asyncio
import time
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeVideo
from moviepy import VideoFileClip
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, progress_bar, notify_admin
from core import banned_users

logger = LOGGER

class Config:
    TEMP_DIR = Path("./downloads")

def setup_temp_dir():
    Config.TEMP_DIR = Path("./downloads")
    Config.TEMP_DIR.mkdir(exist_ok=True)

class FacebookDownloader:
    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(exist_ok=True)

    async def sanitize_filename(self, title: str) -> str:
        title = re.sub(r'[<>:"/\\|?*]', '', title[:50]).strip()
        return f"{title.replace(' ', '_')}_{int(time.time())}"

    async def download_file(self, session: aiohttp.ClientSession, url: str, dest: Path) -> None:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    logger.info(f"Downloading file from {url} to {dest}")
                    async with aiofiles.open(dest, mode='wb') as f:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            await f.write(chunk)
                    logger.info(f"File downloaded successfully to {dest}")
                else:
                    logger.error(f"Failed to download file: HTTP status {response.status}")
                    raise Exception(f"Failed to download file: HTTP status {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Error downloading file from {url}: {e}")
            raise

    async def download_video(self, url: str, downloading_message) -> Optional[dict]:
        api_url = f"https://smartfbdl.vercel.app/dl?url={url}"
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit_per_host=10),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.get(api_url) as response:
                    logger.info(f"API request to {api_url} returned status {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"API response: {data}")
                        video_url = next(
                            (link["url"] for link in data.get("links", []) if link.get("quality") == "HD"),
                            None
                        )
                        if not video_url:
                            logger.error("No HD video URL found in API response")
                            await downloading_message.edit("**Unable To Extract Video URL**", parse_mode="markdown")
                            return None
                        await downloading_message.edit("**Found ☑️ Downloading...**", parse_mode="markdown")
                        title = data.get("title", "Facebook Video")
                        safe_title = await self.sanitize_filename(title)
                        video_filename = self.temp_dir / f"{safe_title}.mp4"
                        await self.download_file(session, video_url, video_filename)
                        thumbnail_url = data.get("thumbnail")
                        thumbnail_filename = None
                        if thumbnail_url:
                            thumbnail_filename = self.temp_dir / f"{safe_title}_thumb.jpg"
                            try:
                                await self.download_file(session, thumbnail_url, thumbnail_filename)
                            except Exception as e:
                                logger.warning(f"Failed to download thumbnail: {e}")
                                thumbnail_filename = None
                        return {
                            'title': title,
                            'filename': str(video_filename),
                            'thumbnail': str(thumbnail_filename) if thumbnail_filename else None,
                            'webpage_url': url
                        }
                    logger.error(f"API request failed: HTTP status {response.status}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Facebook download error: {e}")
            if hasattr(downloading_message, 'client'):
                await notify_admin(downloading_message.client, f"{COMMAND_PREFIX}fb", e, downloading_message)
            return None
        except asyncio.TimeoutError:
            logger.error("Request to Facebook API timed out")
            if hasattr(downloading_message, 'client'):
                await notify_admin(downloading_message.client, f"{COMMAND_PREFIX}fb", asyncio.TimeoutError("Request to Facebook API timed out"), downloading_message)
            return None
        except Exception as e:
            logger.error(f"Facebook download error: {e}")
            if hasattr(downloading_message, 'client'):
                await notify_admin(downloading_message.client, f"{COMMAND_PREFIX}fb", e, downloading_message)
            return None

def setup_fb_handlers(app: TelegramClient):
    fb_downloader = FacebookDownloader(Config.TEMP_DIR)
    command_prefix_regex = f"[{''.join(map(re.escape, COMMAND_PREFIX))}]"

    @app.on(events.NewMessage(pattern=rf"^{command_prefix_regex}fb(\s+https?://\S+)?$"))
    async def fb_handler(event):
        user_id = event.sender_id if event.sender_id else None
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode="markdown")
            return
        url = None
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg and reply_msg.text:
                match = re.search(r"https?://(www\.facebook\.com|fb\.watch|m\.facebook\.com)/\S+", reply_msg.text)
                if match:
                    url = match.group(0)
        if not url:
            command_parts = event.text.split(maxsplit=1)
            if len(command_parts) > 1:
                match = re.search(r"https?://(www\.facebook\.com|fb\.watch|m\.facebook\.com)/\S+", command_parts[1])
                if match:
                    url = match.group(0)
        if not url:
            await event.respond(
                "**Please provide a valid Facebook video link **",
                parse_mode="markdown"
            )
            logger.warning(f"No Facebook URL provided, user: {user_id or 'unknown'}, chat: {event.chat_id}")
            return
        logger.info(f"Facebook URL received: {url}, user: {user_id or 'unknown'}, chat: {event.chat_id}")
        downloading_message = await event.respond(
            "**Searching The Video**",
            parse_mode="markdown"
        )
        try:
            video_info = await fb_downloader.download_video(url, downloading_message)
            if not video_info:
                await downloading_message.edit("**Invalid Video URL or Video is Private**", parse_mode="markdown")
                logger.error(f"Failed to download video for URL: {url}")
                return
            title = video_info['title']
            filename = video_info['filename']
            thumbnail = video_info['thumbnail']
            webpage_url = video_info['webpage_url']
            video_clip = VideoFileClip(filename)
            duration = video_clip.duration
            duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}"
            video_clip.close()
            if event.sender and hasattr(event.sender, 'first_name'):
                user_full_name = f"{event.sender.first_name} {getattr(event.sender, 'last_name', '') or ''}".strip()
                user_info = f"[{user_full_name}](tg://user?id={user_id})"
            else:
                group_name = getattr(event.chat, 'title', None) or "this group"
                group_username = getattr(event.chat, 'username', None)
                group_url = f"https://t.me/{group_username}" if group_username else "this group"
                user_info = f"[{group_name}]({group_url})"
            caption = (
                f"**Smart Facebook Download →Successful ✅**\n"
                f"**━━━━━━━━━━━━━━━━━━━**\n"
                f"**Title:** **{title}**\n"
                f"**URL:** [Watch On Facebook]({webpage_url})\n"
                f"**Duration:** **{duration_str}** \n"
                f"**━━━━━━━━━━━━━━━━━━━**\n"
                f"**Video Downloaded By: {user_info} ✅**"
            )
            start_time = time.time()
            last_update_time = [start_time]
            thumb_data = None
            if thumbnail and os.path.exists(thumbnail):
                with open(thumbnail, 'rb') as thumb_file:
                    thumb_data = thumb_file.read()
            attributes = [DocumentAttributeVideo(
                duration=int(duration),
                w=1280,
                h=720,
                supports_streaming=True
            )]
            await app.send_file(
                event.chat_id,
                filename,
                caption=caption,
                parse_mode="markdown",
                thumb=thumb_data,
                attributes=attributes,
                progress_callback=lambda c, t: progress_bar(c, t, downloading_message, start_time, last_update_time)
            )
            try:
                await downloading_message.delete()
            except:
                pass
            if os.path.exists(filename):
                os.remove(filename)
                logger.info(f"Deleted video file: {filename}")
            if thumbnail and os.path.exists(thumbnail):
                os.remove(thumbnail)
                logger.info(f"Deleted thumbnail file: {thumbnail}")
        except Exception as e:
            logger.error(f"Error processing Facebook video: {e}")
            if hasattr(downloading_message, 'client'):
                await notify_admin(app, f"{COMMAND_PREFIX}fb", e, downloading_message)
            await downloading_message.edit("**Facebook Downloader API Dead**", parse_mode="markdown")
            if 'filename' in locals() and os.path.exists(filename):
                os.remove(filename)
                logger.info(f"Deleted video file on error: {filename}")
            if 'thumbnail' in locals() and thumbnail and os.path.exists(thumbnail):
                os.remove(thumbnail)
                logger.info(f"Deleted thumbnail file on error: {thumbnail}")