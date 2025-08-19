import os
import re
import io
import math
import time
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeAudio
from concurrent.futures import ThreadPoolExecutor
from moviepy import VideoFileClip
from PIL import Image
import yt_dlp
from config import COMMAND_PREFIX, YT_COOKIES_PATH, VIDEO_RESOLUTION, MAX_VIDEO_SIZE, BAN_REPLY
from utils import LOGGER, progress_bar, notify_admin
from core import banned_users

logger = LOGGER

class Config:
    TEMP_DIR = Path("./downloads")
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }

Config.TEMP_DIR.mkdir(exist_ok=True)
executor = ThreadPoolExecutor(max_workers=6)

def sanitize_filename(title: str) -> str:
    title = re.sub(r'[<>:"/\\|?*]', '', title[:50]).replace(' ', '_')
    return f"{title}_{int(time.time())}"

def format_size(size_bytes: int) -> str:
    if not size_bytes:
        return "0B"
    units = ("B", "KB", "MB", "GB")
    i = int(math.log(size_bytes, 1024))
    return f"{round(size_bytes / (1024 ** i), 2)} {units[i]}"

def format_duration(seconds: int) -> str:
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

async def get_video_duration(video_path: str) -> float:
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration
        clip.close()
        logger.info(f"Video duration retrieved: {duration} seconds for {video_path}")
        return duration
    except Exception as e:
        logger.error(f"Failed to get duration for {video_path}: {e}")
        return 0.0

def youtube_parser(url: str) -> Optional[str]:
    youtube_patterns = [
        r"(?:youtube\.com/shorts/)([^\"&?/ ]{11})(\?.*)?",
        r"(?:youtube\.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)|.*[?&]v=)|youtu\.be/)([^\"&?/ ]{11})",
        r"(?:youtube\.com/watch\?v=)([^\"&?/ ]{11})",
        r"(?:m\.youtube\.com/watch\?v=)([^\"&?/ ]{11})",
        r"(?:youtube\.com/embed/)([^\"&?/ ]{11})",
        r"(?:youtube\.com/v/)([^\"&?/ ]{11})"
    ]
   
    for pattern in youtube_patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            if "shorts" in url.lower():
                standardized_url = f"https://www.youtube.com/shorts/{video_id}"
                logger.info(f"Parsed YouTube Shorts URL: {standardized_url}")
                return standardized_url
            else:
                standardized_url = f"https://www.youtube.com/watch?v={video_id}"
                logger.info(f"Parsed YouTube URL: {standardized_url}")
                return standardized_url
   
    logger.warning(f"Invalid YouTube URL: {url}")
    return None

def get_ydl_opts(output_path: str, is_audio: bool = False) -> dict:
    width, height = VIDEO_RESOLUTION
    base = {
        'outtmpl': output_path + '.%(ext)s',
        'cookiefile': YT_COOKIES_PATH,
        'quiet': True,
        'noprogress': True,
        'nocheckcertificate': True,
        'socket_timeout': 60,
        'retries': 3,
        'merge_output_format': 'mp4',
    }
    if is_audio:
        base.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }]
        })
    else:
        base.update({
            'format': f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={height}]+bestaudio/best[height<={height}]/best',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4'
            }],
            'prefer_ffmpeg': True,
            'postprocessor_args': {
                'FFmpegVideoConvertor': ['-c:v', 'libx264', '-c:a', 'aac', '-f', 'mp4']
            }
        })
    logger.info(f"YDL options configured for {'audio' if is_audio else 'video'} download")
    return base

async def download_media(url: str, is_audio: bool, status_message) -> Tuple[Optional[dict], Optional[str]]:
    parsed_url = youtube_parser(url)
    if not parsed_url:
        await status_message.edit("**Invalid YouTube ID Or URL**", parse_mode="markdown")
        logger.error(f"Invalid YouTube URL provided: {url}")
        if hasattr(status_message, 'client'):
            await notify_admin(status_message.client, f"{COMMAND_PREFIX}yt", Exception("Invalid YouTube URL"), status_message)
        return None, "Invalid YouTube URL"
   
    try:
        ydl_opts_info = {
            'cookiefile': YT_COOKIES_PATH,
            'quiet': True,
            'socket_timeout': 30,
            'retries': 2
        }
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(executor, ydl.extract_info, parsed_url, False),
                timeout=45
            )
       
        if not info:
            await status_message.edit(f"**Sorry Bro {'Audio' if is_audio else 'Video'} Not Found**", parse_mode="markdown")
            logger.error(f"No media info found for URL: {parsed_url}")
            if hasattr(status_message, 'client'):
                await notify_admin(status_message.client, f"{COMMAND_PREFIX}yt", Exception("No media info found"), status_message)
            return None, "No media info found"
       
        duration = info.get('duration', 0)
        if duration > 7200:
            await status_message.edit(f"**Sorry Bro {'Audio' if is_audio else 'Video'} Is Over 2hrs**", parse_mode="markdown")
            logger.error(f"Media duration exceeds 2 hours: {duration} seconds")
            if hasattr(status_message, 'client'):
                await notify_admin(status_message.client, f"{COMMAND_PREFIX}yt", Exception("Media duration exceeds 2 hours"), status_message)
            return None, "Media duration exceeds 2 hours"
       
        await status_message.edit("**Found ☑️ Downloading...**", parse_mode="markdown")
        logger.info(f"Download started: {info.get('title', 'Unknown')} ({'audio' if is_audio else 'video'})")
       
        title = info.get('title', 'Unknown')
        safe_title = sanitize_filename(title)
        output_path = f"{Config.TEMP_DIR}/{safe_title}"
       
        opts = get_ydl_opts(output_path, is_audio)
        with yt_dlp.YoutubeDL(opts) as ydl:
            await asyncio.get_event_loop().run_in_executor(executor, ydl.download, [parsed_url])
       
        file_path = f"{output_path}.mp3" if is_audio else f"{output_path}.mp4"
        if not os.path.exists(file_path) and not is_audio:
            for ext in ['.webm', '.mkv']:
                alt_path = f"{output_path}{ext}"
                if os.path.exists(alt_path):
                    logger.info(f"Found alternative format: {alt_path}. Attempting conversion to mp4.")
                    try:
                        clip = VideoFileClip(alt_path)
                        clip.write_videofile(file_path, codec='libx264', audio_codec='aac')
                        clip.close()
                        os.remove(alt_path)
                        break
                    except Exception as e:
                        logger.error(f"Conversion failed for {alt_path}: {e}")
                        os.remove(alt_path)
                        continue
                else:
                    continue
       
        if not os.path.exists(file_path):
            await status_message.edit(f"**Sorry Bro {'Audio' if is_audio else 'Video'} Not Found**", parse_mode="markdown")
            logger.error(f"Download failed, file not found: {file_path}")
            await notify_admin(status_message.client, f"{COMMAND_PREFIX}yt", Exception(f"Download failed, file not found: {file_path}"), status_message)
            return None, "Download failed"
       
        file_size = os.path.getsize(file_path)
        if file_size > MAX_VIDEO_SIZE:
            os.remove(file_path)
            await status_message.edit(f"**Sorry Bro {'Audio' if is_audio else 'Video'} Is Over 2GB**", parse_mode="markdown")
            logger.error(f"File size exceeds 2GB: {file_size} bytes")
            await notify_admin(status_message.client, f"{COMMAND_PREFIX}yt", Exception("File size exceeds 2GB"), status_message)
            return None, "File exceeds 2GB"
       
        thumbnail_path = await prepare_thumbnail(info.get('thumbnail'), output_path)
        duration = await get_video_duration(file_path) if not is_audio else info.get('duration', 0)
       
        metadata = {
            'file_path': file_path,
            'title': title,
            'views': info.get('view_count', 0),
            'duration': format_duration(int(duration)),
            'file_size': format_size(file_size),
            'thumbnail_path': thumbnail_path
        }
        logger.info(f"{'Audio' if is_audio else 'Video'} metadata prepared: {metadata}")
       
        return metadata, None
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching metadata for URL: {url}")
        await status_message.edit("**Sorry Bro YouTubeDL API Dead**", parse_mode="markdown")
        await notify_admin(status_message.client, f"{COMMAND_PREFIX}yt", asyncio.TimeoutError("Metadata fetch timed out"), status_message)
        return None, "Metadata fetch timed out"
    except Exception as e:
        logger.error(f"Download error for URL {url}: {e}")
        await status_message.edit("**Sorry Bro YouTubeDL API Dead**", parse_mode="markdown")
        await notify_admin(status_message.client, f"{COMMAND_PREFIX}yt", e, status_message)
        return None, f"Download failed: {str(e)}"

async def prepare_thumbnail(thumbnail_url: str, output_path: str) -> Optional[str]:
    if not thumbnail_url:
        logger.warning("No thumbnail URL provided")
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail_url) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch thumbnail, status: {resp.status}")
                    await notify_admin(None, f"{COMMAND_PREFIX}yt", Exception(f"Failed to fetch thumbnail, status: {resp.status}"), None)
                    return None
                data = await resp.read()
       
        thumbnail_path = f"{output_path}_thumb.jpg"
        with Image.open(io.BytesIO(data)) as img:
            img.convert('RGB').save(thumbnail_path, "JPEG", quality=85)
        logger.info(f"Thumbnail saved: {thumbnail_path}")
        return thumbnail_path
    except Exception as e:
        logger.error(f"Thumbnail error: {e}")
        await notify_admin(None, f"{COMMAND_PREFIX}yt", e, None)
        return None

async def search_youtube(query: str, retries: int = 2) -> Optional[str]:
    opts = {
        'default_search': 'ytsearch1',
        'cookiefile': YT_COOKIES_PATH,
        'quiet': True,
        'simulate': True,
    }
   
    for attempt in range(retries):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(executor, ydl.extract_info, query, False)
                if info.get('entries'):
                    url = info['entries'][0]['webpage_url']
                    logger.info(f"YouTube search successful, found URL: {url} for query: {query}")
                    return url
               
                simplified_query = re.sub(r'[^\w\s]', '', query).strip()
                if simplified_query != query:
                    info = await asyncio.get_event_loop().run_in_executor(executor, ydl.extract_info, simplified_query, False)
                    if info.get('entries'):
                        url = info['entries'][0]['webpage_url']
                        logger.info(f"YouTube search successful with simplified query, found URL: {url} for query: {simplified_query}")
                        return url
        except Exception as e:
            logger.error(f"Search error (attempt {attempt + 1}) for query {query}: {e}")
            if attempt == retries - 1:
                await notify_admin(None, f"{COMMAND_PREFIX}yt", e, None)
            if attempt < retries - 1:
                await asyncio.sleep(1)
    logger.error(f"YouTube search failed after {retries} attempts for query: {query}")
    return None

async def handle_media_request(client: TelegramClient, event, query: str, is_audio: bool = False):
    logger.info(f"Handling media request: {'audio' if is_audio else 'video'}, query: {query}, user: {event.sender_id}, chat: {event.chat_id}")
    
    status_message = await event.respond(
        f"**Searching The {'Audio' if is_audio else 'Video'}**",
        parse_mode="markdown"
    )
   
    video_url = youtube_parser(query) if youtube_parser(query) else await search_youtube(query)
    if not video_url:
        await status_message.edit(f"**Sorry Bro {'Audio' if is_audio else 'Video'} Not Found**", parse_mode="markdown")
        logger.error(f"No video URL found for query: {query}")
        await notify_admin(client, f"{COMMAND_PREFIX}yt", Exception("No video URL found"), event)
        return
   
    result, error = await download_media(video_url, is_audio, status_message)
    if error:
        logger.error(f"Media download failed: {error}")
        return
   
    user_info = (
        f"[{event.sender.first_name}{' ' + event.sender.last_name if event.sender.last_name else ''}](tg://user?id={event.sender_id})" if event.sender and hasattr(event.sender, 'first_name') else
        f"[{event.chat.title}](https://t.me/{getattr(event.chat, 'username', 'this_group') or 'this_group'})"
    )
    caption = (
        f"🎵 **Title:** `{result['title']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👁️‍🗨️ **Views:** {result['views']}\n"
        f"**🔗 Url:** [Watch On YouTube]({video_url})\n"
        f"⏱️ **Duration:** {result['duration']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"**Downloaded By** {user_info}"
    )
   
    last_update_time = [0]
    start_time = time.time()
    
    thumb_data = None
    if result['thumbnail_path'] and os.path.exists(result['thumbnail_path']):
        with open(result['thumbnail_path'], 'rb') as thumb_file:
            thumb_data = thumb_file.read()
    
    try:
        if is_audio:
            attributes = [DocumentAttributeAudio(
                duration=int(await get_video_duration(result['file_path'])) if not is_audio else int(result.get('duration_seconds', 0)),
                title=result['title'],
                performer="YouTube"
            )]
            
            await client.send_file(
                event.chat_id,
                result['file_path'],
                caption=caption,
                parse_mode="markdown",
                thumb=thumb_data,
                attributes=attributes,
                progress_callback=lambda c, t: progress_bar(c, t, status_message, start_time, last_update_time)
            )
        else:
            duration_seconds = int(await get_video_duration(result['file_path']))
            attributes = [DocumentAttributeVideo(
                duration=duration_seconds,
                w=1280,
                h=720,
                supports_streaming=True
            )]
            
            await client.send_file(
                event.chat_id,
                result['file_path'],
                caption=caption,
                parse_mode="markdown",
                thumb=thumb_data,
                attributes=attributes,
                progress_callback=lambda c, t: progress_bar(c, t, status_message, start_time, last_update_time)
            )
        
        logger.info(f"Media uploaded successfully: {'audio' if is_audio else 'video'}, file: {result['file_path']}")
    except Exception as e:
        logger.error(f"Upload error: {e}")
        await status_message.edit("**Sorry Bro YouTubeDL API Dead**", parse_mode="markdown")
        await notify_admin(client, f"{COMMAND_PREFIX}yt", e, event)
        return
   
    for path in (result['file_path'], result['thumbnail_path']):
        if path and os.path.exists(path):
            os.remove(path)
            logger.info(f"Cleaned up file: {path}")
    
    try:
        await status_message.delete()
        logger.info("Status message deleted")
    except:
        pass

def setup_yt_handler(app: TelegramClient):
    prefix_pattern = f"[{''.join(map(re.escape, COMMAND_PREFIX))}]"
   
    @app.on(events.NewMessage(pattern=rf"^{prefix_pattern}(yt|video)(\s+.+)?$"))
    async def video_handler(event):
        user_id = event.sender_id if event.sender_id else None
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode="markdown")
            return
        
        user_id = event.sender_id if event.sender_id else "unknown"
        chat_id = event.chat_id
        logger.info(f"Video command received from user: {user_id}, chat: {chat_id}, text: {event.text}")
       
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg and reply_msg.text:
                query = reply_msg.text.strip()
                logger.info(f"Using replied message as query: {query}")
            else:
                query = None
        else:
            text_parts = event.text.split(maxsplit=1)
            query = text_parts[1] if len(text_parts) > 1 else None
            logger.info(f"Using direct query: {query if query else 'none'}")
       
        if not query:
            await event.respond(
                "**Please provide a video name or link ❌**",
                parse_mode="markdown"
            )
            logger.warning(f"No query provided for video command, user: {user_id}, chat: {chat_id}")
            return
       
        await handle_media_request(app, event, query)
   
    @app.on(events.NewMessage(pattern=rf"^{prefix_pattern}song(\s+.+)?$"))
    async def song_handler(event):
        user_id = event.sender_id if event.sender_id else None
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode="markdown")
            return
        
        user_id = event.sender_id if event.sender_id else "unknown"
        chat_id = event.chat_id
        logger.info(f"Song command received from user: {user_id}, chat: {chat_id}, text: {event.text}")
       
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg and reply_msg.text:
                query = reply_msg.text.strip()
                logger.info(f"Using replied message as query: {query}")
            else:
                query = None
        else:
            text_parts = event.text.split(maxsplit=1)
            query = text_parts[1] if len(text_parts) > 1 else None
            logger.info(f"Using direct query: {query if query else 'none'}")
       
        if not query:
            await event.respond(
                "**Please provide a music name or link ❌**",
                parse_mode="markdown"
            )
            logger.warning(f"No query provided for song command, user: {user_id}, chat: {chat_id}")
            return
       
        await handle_media_request(app, event, query, is_audio=True)