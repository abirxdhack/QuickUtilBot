import os
import re
import aiohttp
import time
import aiofiles
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import Message
from config import COMMAND_PREFIX, BAN_REPLY
from urllib.parse import quote
from utils import LOGGER, notify_admin
from core import banned_users

SCREENSHOT_API_URL = "https://api.screenshotone.com/take"
SCREENSHOT_ACCESS_KEY = "Z8LQ6Z0DsTQV_A"
MAX_FILE_SIZE = 5 * 1024 * 1024

def validate_url(url: str) -> bool:
    return '.' in url and len(url) < 2048

def normalize_url(url: str) -> str:
    return url if url.startswith(('http://', 'https://')) else f"https://{url}"

async def fetch_screenshot(url: str) -> bytes:
    params = {
        'access_key': SCREENSHOT_ACCESS_KEY,
        'url': url,
        'format': 'jpg',
        'block_ads': 'true',
        'block_cookie_banners': 'true',
        'block_banners_by_heuristics': 'false',
        'block_trackers': 'true',
        'delay': '0',
        'timeout': '60',
        'response_type': 'by_format',
        'image_quality': '100'
    }
    
    timeout = aiohttp.ClientTimeout(total=70)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(SCREENSHOT_API_URL, params=params) as response:
                response.raise_for_status()
                content_type = response.headers.get('Content-Type', '')
                if 'image' not in content_type:
                    raise ValueError(f"Unexpected content type: {content_type}")
                content_length = int(response.headers.get('Content-Length', 0))
                if content_length > MAX_FILE_SIZE:
                    raise ValueError(f"Screenshot too large ({content_length / 1024 / 1024:.1f}MB)")
                return await response.read()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        LOGGER.error(f"Failed to fetch screenshot for {url}: {e}")
        return None

async def save_screenshot(url: str, timestamp: int) -> str:
    screenshot_bytes = await fetch_screenshot(url)
    if not screenshot_bytes:
        return None
    temp_file = f"screenshot_{timestamp}_{hash(url)}.jpg"
    async with aiofiles.open(temp_file, 'wb') as file:
        await file.write(screenshot_bytes)
    file_size = os.path.getsize(temp_file)
    if file_size > MAX_FILE_SIZE:
        os.remove(temp_file)
        return None
    return temp_file

async def capture_screenshots(client: TelegramClient, event, urls: list) -> None:
    user_id = event.sender_id
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await client.send_message(event.chat_id, BAN_REPLY, parse_mode='md')
        return

    if not urls:
        await client.send_message(event.chat_id, "**❌ Please provide at least one URL after the command**", parse_mode='md')
        return

    for url in urls:
        if not validate_url(url):
            await client.send_message(event.chat_id, f"**❌ Invalid URL format: {url}**", parse_mode='md')
            return

    processing_msg = await client.send_message(event.chat_id, "**Capturing ScreenShots Please Wait**", parse_mode='md')

    timestamp = int(time.time())
    tasks = [save_screenshot(normalize_url(url), timestamp) for url in urls]
    temp_files = await asyncio.gather(*tasks, return_exceptions=True)

    try:
        for i, temp_file in enumerate(temp_files):
            if isinstance(temp_file, Exception):
                LOGGER.error(f"Error processing {urls[i]}: {temp_file}")
                continue
            if temp_file:
                await client.send_file(event.chat_id, temp_file)
                os.remove(temp_file)

        await processing_msg.delete()

    except Exception as e:
        error_msg = "**Sorry Bro SS Capture API Dead**"
        try:
            await processing_msg.edit(error_msg, parse_mode='md')
        except Exception as edit_error:
            LOGGER.warning(f"Failed to edit processing message: {edit_error}")
        LOGGER.error(f"Error in capture_screenshots: {e}")
        await notify_admin(client, "/ss", e, event)

def setup_ss_handler(client: TelegramClient):
    prefix_pattern = '|'.join(re.escape(p) for p in COMMAND_PREFIX)
    pattern = rf'^({prefix_pattern})(ss|sshot|screenshot|snap)(\s|$)'
    
    @client.on(events.NewMessage(pattern=pattern))
    async def handler(event):
        if not (event.is_private or event.is_group):
            return
        
        message_text = event.message.message
        command_part = message_text.split(None, 1)
        urls = command_part[1].split() if len(command_part) > 1 else []
        
        await capture_screenshots(client, event, urls)