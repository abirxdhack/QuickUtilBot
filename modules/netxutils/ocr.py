import os
from io import BytesIO
from PIL import Image
from telethon import events
from telethon.tl.types import MessageMediaPhoto
import google.generativeai as genai
from config import COMMAND_PREFIX, IMGAI_SIZE_LIMIT, BAN_REPLY, OCR_API_KEY, MODEL_NAME
from utils import LOGGER, notify_admin
from core import banned_users

def setup_ocr_handler(app):
    genai.configure(api_key=OCR_API_KEY)
    model = genai.GenerativeModel(MODEL_NAME)
    async def ocr_handler(event):
        client = event.client
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        reply_message = await event.message.get_reply_message()
        if not reply_message or not isinstance(reply_message.media, MessageMediaPhoto):
            await event.respond("<b>❌ Please reply to a photo to extract text.</b>", parse_mode="html")
            return
        processing_msg = await event.respond("<b>Processing Your Request...✨</b>", parse_mode="html")
        photo_path = None
        try:
            LOGGER.info("Downloading image...")
            photo_file = await client.download_media(reply_message, file=f"ocr_temp_{event.message.id}.jpg")
            photo_path = photo_file
            if os.path.getsize(photo_path) > IMGAI_SIZE_LIMIT:
                raise ValueError(f"Image too large. Max {IMGAI_SIZE_LIMIT/1000000}MB allowed")
            LOGGER.info("Processing image for OCR with GeminiAI...")
            with Image.open(photo_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                response = model.generate_content(["Extract text from this image of all lang", img])
                text = response.text
                LOGGER.info(f"OCR Response: {text}")
                await processing_msg.edit(text if text else "<b>❌ No readable text found in image.</b>", parse_mode="html", link_preview=False)
        except Exception as e:
            LOGGER.error(f"OCR Error: {str(e)}")
            await processing_msg.edit("<b>❌ Sorry Bro OCR API Dead</b>", parse_mode="html")
            await notify_admin(client, "/ocr", e, event.message)
        finally:
            if photo_path and os.path.exists(photo_path):
                os.remove(photo_path)
                LOGGER.info(f"Deleted temporary image file: {photo_path}")
    app.add_event_handler(
        ocr_handler,
        events.NewMessage(pattern=f"^{COMMAND_PREFIX}ocr(?:\s|$)")
    )