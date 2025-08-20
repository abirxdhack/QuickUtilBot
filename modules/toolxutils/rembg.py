import os
import aiohttp
import aiofiles
import time
from io import BytesIO
from telethon import TelegramClient, events
from config import COMMAND_PREFIX
from utils import notify_admin, LOGGER
import threading

API_KEY = "23nfCEipDijgVv6SH14oktJe"
user_daily_limits = {}
daily_limits_lock = threading.Lock()

def generate_unique_filename(base_name: str) -> str:
    if os.path.exists(base_name):
        count = 1
        name, ext = os.path.splitext(base_name)
        while True:
            new_name = f"{name}_{count}{ext}"
            if not os.path.exists(new_name):
                return new_name
            count += 1
    return base_name

async def remove_bg(buffer: bytes) -> tuple:
    headers = {"X-API-Key": API_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            form_data = aiohttp.FormData()
            form_data.add_field("image_file", buffer, filename="image.png", content_type="image/png")
            async with session.post("https://api.remove.bg/v1.0/removebg", headers=headers, data=form_data) as resp:
                if "image" not in resp.headers.get("content-type", ""):
                    return False, await resp.json()
                output_filename = generate_unique_filename("no_bg.png")
                async with aiofiles.open(output_filename, "wb") as out_file:
                    await out_file.write(await resp.read())
                return True, output_filename
    except Exception as e:
        return False, {"title": "Unknown Error", "errors": [{"detail": str(e)}]}

def setup_bg_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}rmbg$'))
    async def rmbg_handler(event):
        user_id = event.sender_id
        with daily_limits_lock:
            if user_id not in user_daily_limits:
                user_daily_limits[user_id] = 10
            if user_daily_limits[user_id] <= 0:
                await event.respond("**You have reached your daily limit of 10 background removals.**", parse_mode='markdown')
                return
        reply = await event.get_reply_message()
        valid_photo = reply and reply.photo
        valid_doc = reply and reply.document and reply.document.mime_type and reply.document.mime_type.startswith("image/")
        if not (valid_photo or valid_doc):
            await event.respond("**Reply to a photo or image file to remove background**", parse_mode='markdown')
            return
        loading_message = await event.respond("**Removing background...**", parse_mode='markdown')
        try:
            file_bytes = BytesIO()
            if valid_photo:
                await app.download_media(reply.photo, file=file_bytes)
            else:
                await app.download_media(reply.document, file=file_bytes)
            file_bytes.seek(0)
            buffer = file_bytes.read()
            success, result = await remove_bg(buffer)
            if not success:
                await loading_message.edit("**Sorry Bro Removal Failed**", parse_mode='markdown')
                await notify_admin(app, "/rmbg", result, event)
                return
            with daily_limits_lock:
                user_daily_limits[user_id] -= 1
            await app.send_file(event.chat_id, file=result, force_document=True, caption=f"✅ Background removed!\n{user_daily_limits[user_id]} removals remaining today.", parse_mode='markdown')
            try:
                await loading_message.delete()
            except Exception:
                pass
        except Exception as e:
            LOGGER.error(f"rmbg error: {str(e)}")
            try:
                await loading_message.edit("**Sorry Bro Removal Failed**", parse_mode='markdown')
            except Exception:
                await event.respond("**Sorry Bro Removal Failed**", parse_mode='markdown')
            await notify_admin(app, "/rmbg", e, event)
        finally:
            if os.path.exists(result):
                try:
                    os.remove(result)
                except Exception:
                    LOGGER.warning(f"Cleanup error for {result}")
    return app
