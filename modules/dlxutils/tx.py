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
from bs4 import BeautifulSoup
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, progress_bar, notify_admin
from core import banned_users

logger = LOGGER

class Config:
    TEMP_DIR = Path("./downloads")

Config.TEMP_DIR.mkdir(exist_ok=True)

class TwitterDownloader:
    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir

    async def sanitize_filename(self, title: str) -> str:
        title = re.sub(r'[<>:"/\\|?*]', '', title[:50]).strip()
        return f"{title.replace(' ', '_')}_{int(time.time())}"

    async def download_video(self, url: str, downloading_message) -> Optional[dict]:
        self.temp_dir.mkdir(exist_ok=True)
        api_url = f"https://twitsave.com/info?url={url}"
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit_per_host=10),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.get(api_url) as response:
                    logger.info(f"API request to {api_url} returned status {response.status}")
                    if response.status == 200:
                        soup = BeautifulSoup(await response.text(), "html.parser")
                        video_section = soup.find_all("div", class_="origin-top-right")
                        if not video_section:
                            logger.error("No video section found in API response")
                            await downloading_message.edit("**Unable To Extract Video URL**", parse_mode="markdown")
                            return None
                        video_links = video_section[0].find_all("a")
                        if not video_links:
                            logger.error("No video links found in API response")
                            await downloading_message.edit("**Unable To Extract Video URL**", parse_mode="markdown")
                            return None
                        video_url = video_links[0].get("href")
                        name_section = soup.find_all("div", class_="leading-tight")
                        if not name_section:
                            logger.error("No title section found in API response")
                            await downloading_message.edit("**Unable To Extract Video Title**", parse_mode="markdown")
                            return None
                        raw_name = name_section[0].find_all("p", class_="m-2")[0].text
                        title = re.sub(r"[^a-zA-Z0-9]+", " ", raw_name).strip()
                        await downloading_message.edit("**Found ☑️ Downloading...**", parse_mode="markdown")
                        safe_title = await self.sanitize_filename(title)
                        filename = self.temp_dir / f"{safe_title}.mp4"
                        await self._download_file(session, video_url, filename)
                        return {
                            'title': title,
                            'filename': str(filename),
                            'webpage_url': url
                        }
                    logger.error(f"API request failed: HTTP status {response.status}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Twitter download error: {e}")
            if hasattr(downloading_message, 'client'):
                await notify_admin(downloading_message.client, f"{COMMAND_PREFIX}tx", e, downloading_message)
            return None
        except asyncio.TimeoutError:
            logger.error("Request to Twitter API timed out")
            if hasattr(downloading_message, 'client'):
                await notify_admin(downloading_message.client, f"{COMMAND_PREFIX}tx", asyncio.TimeoutError("Request to Twitter API timed out"), downloading_message)
            return None
        except Exception as e:
            logger.error(f"Twitter download error: {e}")
            if hasattr(downloading_message, 'client'):
                await notify_admin(downloading_message.client, f"{COMMAND_PREFIX}tx", e, downloading_message)
            return None

    async def _download_file(self, session: aiohttp.ClientSession, url: str, dest: Path):
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    logger.info(f"Downloading video from {url} to {dest}")
                    async with aiofiles.open(dest, mode='wb') as f:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            await f.write(chunk)
                    logger.info(f"Video downloaded successfully to {dest}")
                else:
                    logger.error(f"Failed to download file: HTTP status {response.status}")
                    raise Exception(f"Failed to download file: HTTP status {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Error downloading file from {url}: {e}")
            await notify_admin(None, f"{COMMAND_PREFIX}tx", e, None)
            raise

def setup_tx_handler(app: TelegramClient):
    twitter_downloader = TwitterDownloader(Config.TEMP_DIR)
    command_prefix_regex = f"[{''.join(map(re.escape, COMMAND_PREFIX))}]"

    @app.on(events.NewMessage(pattern=rf"^{command_prefix_regex}tx(\s+https?://\S+)?$"))
    async def tx_handler(event):
        user_id = event.sender_id if event.sender_id else None
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode="markdown")
            return
        url = None
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg and reply_msg.text:
                match = re.search(r"https?://(x\.com|twitter\.com)/\S+", reply_msg.text)
                if match:
                    url = match.group(0)
        if not url:
            command_parts = event.text.split(maxsplit=1)
            if len(command_parts) > 1:
                match = re.search(r"https?://(x\.com|twitter\.com)/\S+", command_parts[1])
                if match:
                    url = match.group(0)
        if not url:
            await event.respond(
                "**Bro Please Provide A Twitter URL**",
                parse_mode="markdown"
            )
            logger.warning(f"No Twitter URL provided, user: {user_id or 'unknown'}, chat: {event.chat_id}")
            return
        logger.info(f"Twitter URL received: {url}, user: {user_id or 'unknown'}, chat: {event.chat_id}")
        downloading_message = await event.respond(
            "**Searching The Media**",
            parse_mode="markdown"
        )
        try:
            video_info = await twitter_downloader.download_video(url, downloading_message)
            if not video_info:
                await downloading_message.edit("**Invalid Video URL or Video is Private**", parse_mode="markdown")
                logger.error(f"Failed to download video for URL: {url}")
                return
            title = video_info['title']
            filename = video_info['filename']
            webpage_url = video_info['webpage_url']
            video_clip = VideoFileClip(filename)
            duration = video_clip.duration
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
                f"🎥 **Title**: `{title}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔗 **Link**: [Watch on Twitter]({webpage_url})\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"**Downloaded By**: {user_info}"
            )
            start_time = time.time()
            last_update_time = [start_time]
            attributes = [DocumentAttributeVideo(
                duration=int(duration),
                w=0,
                h=0,
                supports_streaming=True
            )]
            await app.send_file(
                event.chat_id,
                file=filename,
                caption=caption,
                parse_mode="markdown",
                attributes=attributes,
                progress_callback=lambda c, t: progress_bar(c, t, downloading_message, start_time, last_update_time)
            )
            await downloading_message.delete()
            if os.path.exists(filename):
                os.remove(filename)
                logger.info(f"Deleted video file: {filename}")
        except Exception as e:
            logger.error(f"Error processing Twitter video: {e}")
            if hasattr(downloading_message, 'client'):
                await notify_admin(app, f"{COMMAND_PREFIX}tx", e, downloading_message)
            await downloading_message.edit("**Twitter Downloader API Dead**", parse_mode="markdown")
            if 'filename' in locals() and os.path.exists(filename):
                os.remove(filename)
                logger.info(f"Deleted video file on error: {filename}")