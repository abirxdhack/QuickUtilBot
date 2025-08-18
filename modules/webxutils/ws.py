import os
import re
import asyncio
import zipfile
import io
import aiohttp
import aiofiles
import shutil
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from telethon import TelegramClient, events
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

LOGGER.debug("URL Downloader initialized - logs should appear in console and botlog.txt")

class UrlDownloader:
    def __init__(self, imgFlg=True, linkFlg=True, scriptFlg=True):
        self.soup = None
        self.imgFlg = imgFlg
        self.linkFlg = linkFlg
        self.scriptFlg = scriptFlg
        self.linkType = ('css', 'png', 'ico', 'jpg', 'jpeg', 'mov', 'ogg', 'gif', 'xml', 'js')
        self.size_limit = 10 * 1024 * 1024
        self.semaphore = asyncio.Semaphore(50)

    async def savePage(self, url, pagefolder='page', session=None):
        LOGGER.debug(f"Starting download: {url}")
        try:
            async with session.get(url, timeout=10) as response:
                content = await response.read()
                if len(content) > self.size_limit:
                    LOGGER.error(f"Size limit exceeded: {url}")
                    return False, "Size limit of 10 MB exceeded."
                try:
                    self.soup = BeautifulSoup(content, features="lxml")
                    LOGGER.debug(f"Parsed HTML with lxml for: {url}")
                except Exception as e:
                    LOGGER.warning(f"lxml parser failed: {str(e)}. Falling back to html.parser")
                    self.soup = BeautifulSoup(content, features="html.parser")
                    LOGGER.debug(f"Parsed HTML with html.parser for: {url}")
            if not os.path.exists(pagefolder):
                LOGGER.debug(f"Creating folder: {pagefolder}")
                os.makedirs(pagefolder, exist_ok=True)
            tasks = []
            if self.imgFlg:
                tasks.append(self._soupfindnSave(url, pagefolder, tag2find='img', inner='src', session=session))
            if self.linkFlg:
                tasks.append(self._soupfindnSave(url, pagefolder, tag2find='link', inner='href', session=session))
            if self.scriptFlg:
                tasks.append(self._soupfindnSave(url, pagefolder, tag2find='script', inner='src', session=session))
            LOGGER.debug(f"Downloading {len(tasks)} resource types")
            await asyncio.gather(*tasks)
            html_path = os.path.join(pagefolder, 'page.html')
            LOGGER.debug(f"Saving HTML to: {html_path}")
            async with aiofiles.open(html_path, 'wb') as file:
                await file.write(self.soup.prettify('utf-8'))
            LOGGER.info(f"Download complete: {url}")
            return True, None
        except Exception as e:
            LOGGER.error(f"Download failed for {url}: {str(e)}")
            return False, f"Failed to download: {str(e)}"

    async def _soupfindnSave(self, url, pagefolder, tag2find='img', inner='src', session=None):
        pagefolder = os.path.join(pagefolder, tag2find)
        if not os.path.exists(pagefolder):
            LOGGER.debug(f"Creating folder: {pagefolder}")
            os.makedirs(pagefolder, exist_ok=True)
        tasks = []
        for res in self.soup.findAll(tag2find):
            if not res.has_attr(inner):
                continue
            filename = re.sub(r'\W+', '.', os.path.basename(res[inner]))
            if tag2find == 'link' and not any(ext in filename for ext in self.linkType):
                filename += '.html'
            fileurl = urljoin(url, res.get(inner))
            filepath = os.path.join(pagefolder, filename)
            res[inner] = os.path.join(os.path.basename(pagefolder), filename)
            tasks.append(self._download_file(fileurl, filepath, session))
        LOGGER.debug(f"Found {len(tasks)} {tag2find} resources for {url}")
        for i in range(0, len(tasks), 50):
            await asyncio.gather(*tasks[i:i+50])

    async def _download_file(self, fileurl, filepath, session):
        async with self.semaphore:
            try:
                LOGGER.debug(f"Downloading: {fileurl}")
                async with session.get(fileurl, timeout=5) as response:
                    content = await response.read()
                    if len(content) > self.size_limit or len(content) == 0:
                        LOGGER.warning(f"Skipped {fileurl}: Size {len(content)} bytes")
                        return
                    async with aiofiles.open(filepath, 'wb') as file:
                        await file.write(content)
                    LOGGER.debug(f"Saved file: {filepath}")
            except Exception as exc:
                LOGGER.error(f"Failed to download {fileurl}: {exc}")

def create_zip(folder_path):
    LOGGER.debug(f"Creating zip: {folder_path}")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                zip_file.write(file_path, os.path.relpath(file_path, folder_path))
                LOGGER.debug(f"Zipped: {file_path}")
    zip_buffer.seek(0)
    LOGGER.info(f"Zip created: {folder_path}")
    return zip_buffer

def setup_ws_handler(client: TelegramClient):
    prefix_pattern = '|'.join(re.escape(p) for p in COMMAND_PREFIX)
    pattern = rf'^({prefix_pattern})(ws|websource)(\s|$)'
    
    @client.on(events.NewMessage(pattern=pattern))
    async def websource(event):
        if not (event.is_private or event.is_group):
            return

        user_id = event.sender_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await client.send_message(event.chat_id, BAN_REPLY, parse_mode='md')
            return

        sender = await event.get_sender()
        LOGGER.info(f"Command received from user {user_id} in chat {event.chat_id}: {event.message.message}")
        
        message_text = event.message.message
        command_parts = message_text.split(None, 1)
        
        if len(command_parts) < 2:
            LOGGER.warning("No URL provided")
            await client.send_message(event.chat_id, "**❌ Please provide at least one valid URL.**", parse_mode='md')
            return

        url = command_parts[1].strip()
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        LOGGER.debug(f"Processing URL: {url}")

        loading_message = await client.send_message(event.chat_id, "**Downloading Website Source...**", parse_mode='md')
        LOGGER.debug(f"Sent loading message {loading_message.id}")

        async with aiohttp.ClientSession() as session:
            downloader = UrlDownloader()
            pagefolder = f"page_{event.chat_id}_{event.id}"
            success, error = await downloader.savePage(url, pagefolder, session)

            if not success:
                LOGGER.error(f"Download failed: {error}")
                await loading_message.edit("**❌ Failed to download source code. Please check the URL and try again.**", parse_mode='md')
                await notify_admin(client, "/ws", Exception(error), event)
                if os.path.exists(pagefolder):
                    LOGGER.debug(f"Cleaning up: {pagefolder}")
                    shutil.rmtree(pagefolder)
                return

            zip_buffer = create_zip(pagefolder)
            user_mention = f"[{sender.first_name} {getattr(sender, 'last_name', '') or ''}](tg://user?id={sender.id})".strip()
            caption = (
                f"**Source Code Downloaded ✅**\n"
                f"**━━━━━━━━━━━**\n"
                f"**Site:** `{url}`\n"
                f"**Files:** `HTML`, `CSS`, `JS`\n"
                f"**━━━━━━━━━━━**\n"
                f"**Downloaded By:** {user_mention}"
            )

            LOGGER.debug(f"Sending zip file for {url}")
            await loading_message.delete()
            
            zip_buffer.name = f"{urlparse(url).netloc}_source.zip"
            await client.send_file(
                event.chat_id,
                zip_buffer,
                caption=caption,
                parse_mode='md'
            )
            LOGGER.info(f"Sent zip file for {url}")

            if os.path.exists(pagefolder):
                LOGGER.debug(f"Cleaning up: {pagefolder}")
                shutil.rmtree(pagefolder)