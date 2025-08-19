import os
import re
import asyncio
import time
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional
from telethon import TelegramClient, events
from telethon.tl.types import Message
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, progress_bar, notify_admin
from core import banned_users

logger = LOGGER

TEMP_DIR = Path("./downloads")
TEMP_DIR.mkdir(exist_ok=True)

class TikTokDownloader:
    def __init__(self):
        self.temp_dir = TEMP_DIR
    
    async def sanitize_filename(self, title: str) -> str:
        title = re.sub(r'[<>:"/\\|?*]', '', title[:50]).strip()
        return f"{title.replace(' ', '_')}_{int(time.time())}"
    
    async def download_media(self, url: str, downloading_message: Message) -> Optional[dict]:
        self.temp_dir.mkdir(exist_ok=True)
        api_url = f"https://smarttikdl.vercel.app/dl?url={url}"
        
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
                        
                        links = data.get("links", [])
                        if not links:
                            logger.error("No links found in API response")
                            await downloading_message.edit("**Unable To Extract Media**")
                            return None
                        
                        video_link = None
                        hd_video_link = None
                        audio_link = None
                        
                        for link in links:
                            filename = link.get("filename", "")
                            if filename.endswith("_hd.mp4"):
                                hd_video_link = link
                            elif filename.endswith(".mp4") and not filename.endswith("_hd.mp4"):
                                video_link = link
                            elif filename.endswith(".mp3"):
                                audio_link = link
                        
                        selected_link = hd_video_link or video_link
                        if not selected_link:
                            logger.error("No suitable video found in API response")
                            await downloading_message.edit("**Unable To Extract Media**")
                            return None
                        
                        await downloading_message.edit("**Found ☑️ Downloading...**")
                        
                        safe_title = await self.sanitize_filename("TikTok_Video")
                        video_filename = self.temp_dir / f"{safe_title}.mp4"
                        
                        await self._download_file(session, selected_link["url"], video_filename)
                        
                        result = {
                            'title': "TikTok Video",
                            'webpage_url': url,
                            'video_filename': str(video_filename)
                        }
                        
                        return result
                    
                    logger.error(f"API request failed: HTTP status {response.status}")
                    return None
                    
        except aiohttp.ClientError as e:
            logger.error(f"TikTok download error: {e}")
            await notify_admin(downloading_message._client, f"{COMMAND_PREFIX}tik", e, downloading_message)
            return None
        except asyncio.TimeoutError:
            logger.error("Request to TikTok API timed out")
            await notify_admin(downloading_message._client, f"{COMMAND_PREFIX}tik", asyncio.TimeoutError("Request to TikTok API timed out"), downloading_message)
            return None
        except Exception as e:
            logger.error(f"TikTok download error: {e}")
            await notify_admin(downloading_message._client, f"{COMMAND_PREFIX}tik", e, downloading_message)
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
            await notify_admin(None, f"{COMMAND_PREFIX}tik", e, None)
            raise

def setup_tt_handler(app: TelegramClient):
    tik_downloader = TikTokDownloader()
    command_prefix_regex = f"[{''.join(map(re.escape, COMMAND_PREFIX))}]"
    
    @app.on(events.NewMessage(pattern=rf"^{command_prefix_regex}(tik|tiktok)(\s+https?://(vm\.tiktok\.com|www\.tiktok\.com)/\S+)?$"))
    async def tik_handler(event):
        user_id = event.sender_id if event.sender_id else None
        
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        url = None
        
        if event.is_reply:
            replied_message = await event.get_reply_message()
            if replied_message and replied_message.text:
                match = re.search(r"https?://(vm\.tiktok\.com|www\.tiktok\.com)/\S+", replied_message.text)
                if match:
                    url = match.group(0)
        
        if not url:
            command_parts = event.text.split(maxsplit=1)
            if len(command_parts) > 1:
                match = re.search(r"https?://(vm\.tiktok\.com|www\.tiktok\.com)/\S+", command_parts[1])
                if match:
                    url = match.group(0)
        
        if not url:
            await event.respond("**Please provide a TikTok link**")
            logger.warning(f"No TikTok URL provided, user: {user_id or 'unknown'}, chat: {event.chat_id}")
            return
        
        logger.info(f"TikTok URL received: {url}, user: {user_id or 'unknown'}, chat: {event.chat_id}")
        
        downloading_message = await event.respond("**Searching The Media**")
        
        try:
            media_info = await tik_downloader.download_media(url, downloading_message)
            if not media_info:
                await downloading_message.edit("**Unable To Extract Media**")
                logger.error(f"Failed to download media for URL: {url}")
                return
            
            start_time = time.time()
            last_update_time = [start_time]
            
            async def progress_callback(current, total):
                await progress_bar(current, total, downloading_message, start_time, last_update_time)
            
            if 'video_filename' in media_info:
                await app.send_file(
                    event.chat_id,
                    media_info['video_filename'],
                    supports_streaming=True,
                    progress_callback=progress_callback
                )
            
            await downloading_message.delete()
            
            for key in ['video_filename', 'thumbnail_filename', 'image_filename']:
                if key in media_info and os.path.exists(media_info[key]):
                    os.remove(media_info[key])
                    logger.info(f"Deleted file: {media_info[key]}")
                    
        except Exception as e:
            logger.error(f"Error processing TikTok media: {e}")
            await notify_admin(app, f"{COMMAND_PREFIX}tik", e, downloading_message)
            await downloading_message.edit("**TikTok Downloader API Dead**")