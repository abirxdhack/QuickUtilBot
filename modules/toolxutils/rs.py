import os
import aiofiles
import time
from PIL import Image
from telethon import TelegramClient, events, Button
from tempfile import mkstemp
from config import COMMAND_PREFIX, BAN_REPLY
from core import banned_users
from utils import LOGGER, notify_admin
import asyncio

image_store = {}
image_store_lock = asyncio.Lock()

RESOLUTIONS = {
    "dp_square": (1080, 1080),
    "widescreen": (1920, 1080),
    "story": (1080, 1920),
    "portrait": (1080, 1620),
    "vertical": (1080, 2160),
    "horizontal": (2160, 1080),
    "standard": (1620, 1080),
    "ig_post": (1080, 1080),
    "tiktok_dp": (200, 200),
    "fb_cover": (820, 312),
    "yt_banner": (2560, 1440),
    "yt_thumb": (1280, 720),
    "x_header": (1500, 500),
    "x_post": (1600, 900),
    "linkedin_banner": (1584, 396),
    "whatsapp_dp": (500, 500),
    "small_thumb": (320, 180),
    "medium_thumb": (480, 270),
    "wide_banner": (1920, 480),
    "bot_father": (640, 360)
}

async def resize_image(input_path, width, height):
    fd, output_path = mkstemp(suffix=".jpg")
    os.close(fd)
    try:
        img = Image.open(input_path)
        resized = img.resize((width, height), Image.Resampling.LANCZOS)
        resized.save(output_path, format="JPEG", quality=95, optimize=True)
        img.close()
    except Exception as e:
        LOGGER.error(f"Error in resize_image: {e}")
        raise
    return output_path

def setup_rs_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(rs|res)$'))
    async def resize_menu_handler(event):
        user_id = event.sender_id
        chat_id = event.chat_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='markdown')
            return
        reply = await event.get_reply_message()
        if not reply or (not reply.photo and not reply.document):
            await event.respond("**❌ Reply to a photo or an image file**", parse_mode='markdown')
            return
        if reply.document:
            mime_type = reply.document.mime_type
            file_name = reply.document.file_name
            if not (mime_type in ["image/jpeg", "image/png"] or
                    (file_name and file_name.lower().endswith((".jpg", ".jpeg", ".png")))):
                await event.respond("**❌ Invalid Image Provided**", parse_mode='markdown')
                return
        status_msg = await event.respond("**Resizing Your Image...**", parse_mode='markdown')
        try:
            media = reply.photo or reply.document
            original_file = await app.download_media(media, file=f"res_{user_id}_{int(time.time())}.jpg")
            async with image_store_lock:
                image_store[user_id] = original_file
            LOGGER.info(f"[{user_id}] Image saved to {original_file}")
            buttons = [
                [Button.inline("1:1 DP Square", "resize_dp_square"), Button.inline("16:9 Widescreen", "resize_widescreen")],
                [Button.inline("9:16 Story", "resize_story"), Button.inline("2:3 Portrait", "resize_portrait")],
                [Button.inline("1:2 Vertical", "resize_vertical"), Button.inline("2:1 Horizontal", "resize_horizontal")],
                [Button.inline("3:2 Standard", "resize_standard"), Button.inline("IG Post", "resize_ig_post")],
                [Button.inline("TikTok DP", "resize_tiktok_dp"), Button.inline("FB Cover", "resize_fb_cover")],
                [Button.inline("YT Banner", "resize_yt_banner"), Button.inline("YT Thumb", "resize_yt_thumb")],
                [Button.inline("X Header", "resize_x_header"), Button.inline("X Post", "resize_x_post")],
                [Button.inline("LinkedIn Banner", "resize_linkedin_banner"), Button.inline("WhatsApp DP", "resize_whatsapp_dp")],
                [Button.inline("Small Thumb", "resize_small_thumb"), Button.inline("Medium Thumb", "resize_medium_thumb")],
                [Button.inline("Wide Banner", "resize_wide_banner"), Button.inline("Bot Father", "resize_bot_father")],
                [Button.inline("❌ Close", "resize_close")]
            ]
            await app.send_message(
                chat_id,
                "**🔧 Choose a format to resize the image:**",
                buttons=buttons
            )
        except Exception as e:
            LOGGER.error(f"[{user_id}] Error downloading image: {e}")
            await notify_admin(app, "/rs", e, event)
            await event.respond("**This Image Can Not Be Resized**", parse_mode='markdown')
        finally:
            await status_msg.delete()
    @app.on(events.CallbackQuery(pattern=b'^resize_'))
    async def resize_button_handler(event):
        user_id = event.sender_id
        chat_id = event.chat_id
        data = event.data.decode().replace("resize_", "")
        if data == "close":
            await event.delete()
            await event.answer("Menu closed.")
            return
        async with image_store_lock:
            if user_id not in image_store:
                await event.answer("⚠️ Image not found. Please use /rs again.", alert=True)
                return
            input_path = image_store[user_id]
        width, height = RESOLUTIONS.get(data, (1080, 1080))
        try:
            output_file = await resize_image(input_path, width, height)
            await app.send_file(
                chat_id,
                file=output_file,
                caption=f"✔️ Resized to {width}x{height}",
                parse_mode='markdown'
            )
            await event.answer(f"Image successfully resized to {width}x{height}!")
        except Exception as e:
            LOGGER.error(f"[{user_id}] Resizing error: {e}")
            await notify_admin(app, "/rs", e, event)
            await event.answer("Failed to resize image.", alert=True)
        finally:
            async with image_store_lock:
                image_store.pop(user_id, None)
            try:
                if os.path.exists(input_path):
                    os.remove(input_path)
                if 'output_file' in locals() and os.path.exists(output_file):
                    os.remove(output_file)
            except Exception as e:
                LOGGER.warning(f"[{user_id}] Cleanup error: {e}")

    return app