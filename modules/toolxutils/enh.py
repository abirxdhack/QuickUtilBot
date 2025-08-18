import os
import aiohttp
import random
import time
from io import BytesIO
from PIL import Image
from telethon import TelegramClient, events
from config import COMMAND_PREFIX, BAN_REPLY
from core import banned_users
from utils import notify_admin, LOGGER
import threading

user_daily_limits = {}
daily_limits_lock = threading.Lock()

async def upscale(buffer: bytes, width: int, height: int) -> tuple:
    try:
        random_number = random.randint(1_000_000, 999_999_999_999)
        form_data = aiohttp.FormData()
        form_data.add_field("image_file", buffer, filename="image.png", content_type="image/png")
        form_data.add_field("name", str(random_number))
        form_data.add_field("desiredHeight", str(height * 4))
        form_data.add_field("desiredWidth", str(width * 4))
        form_data.add_field("outputFormat", "png")
        form_data.add_field("compressionLevel", "high")
        form_data.add_field("anime", "false")
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://upscalepics.com",
            "Referer": "https://upscalepics.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.upscalepics.com/upscale-to-size", data=form_data, headers=headers) as response:
                if response.status == 200:
                    json_response = await response.json()
                    return json_response.get("bgRemoved", "").strip(), None
                else:
                    return None, f"API request failed with status {response.status}"
    except Exception as e:
        return None, f"Upscale error: {str(e)}"

def setup_enh_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}enh$'))
    async def enh_handler(event):
        user_id = event.sender_id
        with daily_limits_lock:
            if user_id not in user_daily_limits:
                user_daily_limits[user_id] = 10
            if user_daily_limits[user_id] <= 0:
                await event.respond("**You have reached your daily limit of 10 enhancements.**", parse_mode='markdown')
                return
        reply = await event.get_reply_message()
        valid_photo = reply and reply.photo
        valid_doc = reply and reply.document and reply.document.mime_type and reply.document.mime_type.startswith("image/")
        if not (valid_photo or valid_doc):
            await event.respond("**Reply to a photo or image file to enhance face**", parse_mode='markdown')
            return
        loading_message = await event.respond("**Enhancing Your Face....**", parse_mode='markdown')
        temp_file = f"/tmp/enh_{user_id}_{int(time.time())}.png"
        try:
            file_bytes = BytesIO()
            if valid_photo:
                await app.download_media(reply.photo, file=file_bytes)
            else:
                await app.download_media(reply.document, file=file_bytes)
            file_bytes.seek(0)
            image_buffer = file_bytes.read()
            with Image.open(BytesIO(image_buffer)) as img:
                width, height = img.size
            image_url, error = await upscale(image_buffer, width, height)
            if image_url and image_url.startswith("http"):
                with daily_limits_lock:
                    user_daily_limits[user_id] -= 1
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as img_resp:
                        if img_resp.status == 200:
                            img_bytes = await img_resp.read()
                            if not img_bytes:
                                raise ValueError("Empty image data received from API")
                            with open(temp_file, 'wb') as f:
                                f.write(img_bytes)
                            try:
                                await loading_message.delete()
                            except Exception:
                                LOGGER.warning("Loading message deletion failed")
                            await app.send_file(
                                event.chat_id,
                                file=temp_file,
                                force_document=True,
                                caption=f"✅ Face enhanced!\n{user_daily_limits[user_id]} enhancements remaining today.",
                                parse_mode='markdown'
                            )
                        else:
                            try:
                                await loading_message.edit(text="**Sorry Enhancer API Dead**", parse_mode='markdown')
                            except Exception:
                                await event.respond("**Sorry Enhancer API Dead**", parse_mode='markdown')
            else:
                try:
                    await loading_message.edit(text="**Sorry Enhancer API Dead**", parse_mode='markdown')
                except Exception:
                    await event.respond("**Sorry Enhancer API Dead**", parse_mode='markdown')
                if error:
                    LOGGER.error(f"Enhancer error: {error}")
                    await notify_admin(app, "/enh", error, event)
        except Exception as e:
            LOGGER.error(f"Enhancer error: {str(e)}")
            try:
                await loading_message.edit(text="**Sorry Enhancer API Dead**", parse_mode='markdown')
            except Exception:
                await event.respond("**Sorry Enhancer API Dead**", parse_mode='markdown')
            await notify_admin(app, "/enh", e, event)
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    LOGGER.warning(f"Cleanup error for {temp_file}")

    return app