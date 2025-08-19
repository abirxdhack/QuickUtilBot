import os
import re
import time
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional, List
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeImageSize
from moviepy import VideoFileClip
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, progress_bar, notify_admin
from core import banned_users

logger = LOGGER

class Config:
    TEMP_DIR = Path("./downloads")
    MAX_MEDIA_PER_GROUP = 10
    DOWNLOAD_RETRIES = 3
    RETRY_DELAY = 2

Config.TEMP_DIR.mkdir(exist_ok=True)

class InstagramDownloader:
    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir

    async def sanitize_filename(self, shortcode: str, index: int, media_type: str) -> str:
        safe_shortcode = re.sub(r'[<>:"/\\|?*]', '', shortcode[:30]).strip()
        return f"{safe_shortcode}_{index}_{int(time.time())}.{ 'mp4' if media_type == 'video' else 'jpg' }"

    async def sanitize_caption(self, caption: str) -> str:
        if not caption or caption.lower() == "unknown":
            return "Instagram Content"
        sanitized = re.sub(r'@\w+', '', caption).strip()
        return sanitized if sanitized else "Instagram Content"

    async def download_file(self, session: aiohttp.ClientSession, url: str, dest: Path, retries: int = Config.DOWNLOAD_RETRIES) -> Path:
        for attempt in range(1, retries + 1):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        logger.info(f"Downloading file from {url} to {dest} (attempt {attempt}/{retries})")
                        async with aiofiles.open(dest, mode='wb') as f:
                            async for chunk in response.content.iter_chunked(1024 * 1024):
                                await f.write(chunk)
                        logger.info(f"File downloaded successfully to {dest}")
                        return dest
                    else:
                        error_msg = f"Failed to download {url}: Status {response.status}"
                        logger.error(error_msg)
                        if attempt == retries:
                            raise Exception(error_msg)
            except aiohttp.ClientError as e:
                error_msg = f"Error downloading file from {url}: {e}"
                logger.error(error_msg)
                if attempt == retries:
                    raise Exception(error_msg)
            except Exception as e:
                error_msg = f"Unexpected error downloading file from {url}: {e}"
                logger.error(error_msg)
                if attempt == retries:
                    raise Exception(error_msg)
            logger.info(f"Retrying download for {url} in {Config.RETRY_DELAY} seconds...")
            await asyncio.sleep(Config.RETRY_DELAY)
        raise Exception(f"Failed to download {url} after {retries} attempts")

    async def download_content(self, url: str, downloading_message) -> Optional[dict]:
        self.temp_dir.mkdir(exist_ok=True)
        api_url = f"https://insta.bdbots.xyz/dl?url={url}"
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=100),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.get(api_url) as response:
                    logger.info(f"API request to {api_url} returned status {response.status}")
                    if response.status != 200:
                        logger.error(f"API request failed: HTTP status {response.status}")
                        return None
                    data = await response.json()
                    logger.info(f"API response: {data}")
                    if data.get("status") != "success":
                        logger.error("API response indicates failure")
                        return None
                    media_files = []
                    tasks = []
                    thumbnail_tasks = []
                    thumbnail_paths = []
                    for index, media in enumerate(data["data"]["media"]):
                        media_type = media["type"]
                        filename = self.temp_dir / await self.sanitize_filename(data["data"]["metadata"]["shortcode"], index, media_type)
                        tasks.append(self.download_file(session, media["url"], filename))
                        thumbnail_url = media.get("thumbnail")
                        thumbnail_filename = None
                        if thumbnail_url:
                            thumbnail_filename = self.temp_dir / f"{filename.stem}_thumb.jpg"
                            thumbnail_tasks.append(self.download_file(session, thumbnail_url, thumbnail_filename))
                            thumbnail_paths.append(thumbnail_filename)
                        else:
                            thumbnail_tasks.append(None)
                            thumbnail_paths.append(None)
                    downloaded_files = await asyncio.gather(*tasks, return_exceptions=True)
                    downloaded_thumbnails = await asyncio.gather(*[t for t in thumbnail_tasks if t], return_exceptions=True) if any(t for t in thumbnail_tasks) else [None] * len(tasks)
                    thumbnail_index = 0
                    for index, (result, thumbnail_result, thumbnail_path) in enumerate(zip(downloaded_files, thumbnail_tasks, thumbnail_paths)):
                        if isinstance(result, Exception):
                            logger.error(f"Failed to download media {index} for URL {data['data']['media'][index]['url']}: {result}")
                            if thumbnail_path and os.path.exists(thumbnail_path):
                                os.remove(thumbnail_path)
                                logger.info(f"Deleted orphaned thumbnail: {thumbnail_path}")
                            continue
                        thumbnail_filename = None
                        if thumbnail_result and not isinstance(thumbnail_result, Exception):
                            thumbnail_filename = str(thumbnail_path)
                            thumbnail_index += 1
                        media_files.append({
                            "filename": str(result),
                            "type": data["data"]["media"][index]["type"],
                            "thumbnail": thumbnail_filename
                        })
                    if not media_files:
                        logger.error("No media files downloaded successfully")
                        return None
                    return {
                        "title": await self.sanitize_caption(data["data"]["caption"]),
                        "media_files": media_files,
                        "webpage_url": data["data"]["metadata"]["url"],
                        "type": data["data"]["type"]
                    }
        except Exception as e:
            logger.error(f"Instagram download error: {e}")
            if hasattr(downloading_message, 'client'):
                await notify_admin(downloading_message.client, f"{COMMAND_PREFIX}in", e, downloading_message)
            return None

def setup_insta_handlers(app: TelegramClient):
    ig_downloader = InstagramDownloader(Config.TEMP_DIR)
    command_prefix_regex = f"[{''.join(map(re.escape, COMMAND_PREFIX))}]"

    @app.on(events.NewMessage(pattern=rf"^{command_prefix_regex}(in|insta|ig)(\s+https?://\S+)?$"))
    async def ig_handler(event):
        user_id = event.sender_id if event.sender_id else None
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode="markdown")
            return
        url = None
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg and reply_msg.text:
                match = re.search(r"https?://(www\.)?instagram\.com/\S+", reply_msg.text)
                if match:
                    url = match.group(0)
        if not url:
            command_parts = event.text.split(maxsplit=1)
            if len(command_parts) > 1:
                match = re.search(r"https?://(www\.)?instagram\.com/\S+", command_parts[1])
                if match:
                    url = match.group(0)
        if not url:
            await event.respond(
                "**Please provide a valid Instagram URL or reply to a message with one ❌**",
                parse_mode="markdown"
            )
            logger.warning(f"No Instagram URL provided, user: {user_id or 'unknown'}, chat: {event.chat_id}")
            return
        logger.info(f"Instagram URL received: {url}, user: {user_id or 'unknown'}, chat: {event.chat_id}")
        content_type = "reel" if "/reel/" in url else "igtv" if "/tv/" in url else "story" if "/stories/" in url else "post"
        downloading_message = await event.respond(
            "**Searching The Video**" if content_type in ["reel", "igtv"] else "`🔍 Fetching media from Instagram...`",
            parse_mode="markdown"
        )
        try:
            content_info = await ig_downloader.download_content(url, downloading_message)
            if not content_info:
                await downloading_message.edit("**Unable To Extract The URL 😕**", parse_mode="markdown")
                logger.error(f"Failed to download content for URL: {url}")
                return
            media_files = content_info["media_files"]
            content_type = content_info["type"]
            title = content_info["title"]
            webpage_url = content_info["webpage_url"]
            if event.sender and hasattr(event.sender, 'first_name'):
                user_full_name = f"{event.sender.first_name} {getattr(event.sender, 'last_name', '') or ''}".strip()
                user_info = f"[{user_full_name}](tg://user?id={user_id})"
            else:
                group_name = getattr(event.chat, 'title', None) or "this group"
                group_username = getattr(event.chat, 'username', None)
                group_url = f"https://t.me/{group_username}" if group_username else "this group"
                user_info = f"[{group_name}]({group_url})"
            caption = (
                f"**Smart Instagram Download →Successful ✅**\n"
                f"**━━━━━━━━━━━━━━━━━━━**\n"
                f"**Title:** **{title}**\n"
                f"**URL:** [Watch On Instagram]({webpage_url})\n"
                f"**━━━━━━━━━━━━━━━━━━━**\n"
                f"**Media Downloaded By: {user_info} ✅**"
            )
            start_time = time.time()
            last_update_time = [start_time]
            if content_type == "carousel" or media_files[0]["type"] == "image":
                await downloading_message.edit("`📤 Uploading...`", parse_mode="markdown")
            if content_type == "carousel" and len(media_files) > 1:
                media_list = []
                has_video = any(media["type"] == "video" for media in media_files[:Config.MAX_MEDIA_PER_GROUP])
                captions = [caption if has_video else ""] + [""] * (len(media_files[:Config.MAX_MEDIA_PER_GROUP]) - 1)
                for index, media in enumerate(media_files[:Config.MAX_MEDIA_PER_GROUP]):
                    thumb_data = None
                    if media["thumbnail"] and os.path.exists(media["thumbnail"]):
                        with open(media["thumbnail"], 'rb') as thumb_file:
                            thumb_data = thumb_file.read()
                    if media["type"] == "video":
                        video_clip = VideoFileClip(media["filename"])
                        duration = video_clip.duration
                        video_clip.close()
                        attributes = [DocumentAttributeVideo(
                            duration=int(duration),
                            w=0,
                            h=0,
                            supports_streaming=True
                        )]
                        media_list.append({
                            "file": media["filename"],
                            "thumb": thumb_data,
                            "attributes": attributes
                        })
                    else:
                        attributes = [DocumentAttributeImageSize(w=0, h=0)]
                        media_list.append({
                            "file": media["filename"],
                            "thumb": thumb_data,
                            "attributes": attributes
                        })
                await app.send_file(
                    event.chat_id,
                    file=[m["file"] for m in media_list],
                    caption=captions,
                    parse_mode="markdown",
                    attributes=[m["attributes"] for m in media_list],
                    thumb=[m["thumb"] for m in media_list],
                    progress_callback=lambda c, t: progress_bar(c, t, downloading_message, start_time, last_update_time)
                )
            else:
                media = media_files[0]
                thumb_data = None
                if media["thumbnail"] and os.path.exists(media["thumbnail"]):
                    with open(media["thumbnail"], 'rb') as thumb_file:
                        thumb_data = thumb_file.read()
                if media["type"] == "video":
                    video_clip = VideoFileClip(media["filename"])
                    duration = video_clip.duration
                    video_clip.close()
                    attributes = [DocumentAttributeVideo(
                        duration=int(duration),
                        w=0,
                        h=0,
                        supports_streaming=True
                    )]
                    await app.send_file(
                        event.chat_id,
                        file=media["filename"],
                        thumb=thumb_data,
                        attributes=attributes,
                        caption=caption,
                        parse_mode="markdown",
                        progress_callback=lambda c, t: progress_bar(c, t, downloading_message, start_time, last_update_time)
                    )
                else:
                    attributes = [DocumentAttributeImageSize(w=0, h=0)]
                    await app.send_file(
                        event.chat_id,
                        file=media["filename"],
                        thumb=thumb_data,
                        attributes=attributes,
                        caption="",
                        parse_mode="markdown",
                        progress_callback=lambda c, t: progress_bar(c, t, downloading_message, start_time, last_update_time)
                    )
            try:
                await downloading_message.delete()
            except:
                pass
            for media in media_files:
                if os.path.exists(media["filename"]):
                    os.remove(media["filename"])
                    logger.info(f"Deleted media file: {media['filename']}")
                if media["thumbnail"] and os.path.exists(media["thumbnail"]):
                    os.remove(media["thumbnail"])
                    logger.info(f"Deleted thumbnail file: {media['thumbnail']}")
        except Exception as e:
            logger.error(f"Error processing Instagram content: {e}")
            if hasattr(downloading_message, 'client'):
                await notify_admin(app, f"{COMMAND_PREFIX}in", e, downloading_message)
            await downloading_message.edit("**Sorry The Media Not Found**", parse_mode="markdown")
            if 'media_files' in locals():
                for media in media_files:
                    if os.path.exists(media["filename"]):
                        os.remove(media["filename"])
                        logger.info(f"Deleted media file on error: {media['filename']}")
                    if media["thumbnail"] and os.path.exists(media["thumbnail"]):
                        os.remove(media["thumbnail"])
                        logger.info(f"Deleted thumbnail file on error: {media['thumbnail']}")