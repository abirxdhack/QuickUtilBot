import os
import asyncio
from io import BytesIO
from PIL import Image
from telethon import events
from telethon.tl.types import MessageMediaPhoto
from googletrans import Translator, LANGUAGES
import google.generativeai as genai
from config import COMMAND_PREFIX, IMGAI_SIZE_LIMIT, BAN_REPLY, TRANS_API_KEY, MODEL_NAME
from utils import LOGGER, notify_admin
from core import banned_users

translator = Translator()

def setup_tr_handler(app):
    genai.configure(api_key=TRANS_API_KEY)
    model = genai.GenerativeModel(MODEL_NAME)
    async def ocr_extract_text(event):
        photo_path = None
        try:
            LOGGER.info("Downloading image for OCR...")
            reply_message = await event.message.get_reply_message()
            photo_path = await event.client.download_media(reply_message, file=f"ocr_temp_{event.message.id}.jpg")
            if os.path.getsize(photo_path) > IMGAI_SIZE_LIMIT:
                raise ValueError(f"Image too large. Max {IMGAI_SIZE_LIMIT/1000000}MB allowed")
            LOGGER.info("Processing image for OCR with GeminiAI...")
            with Image.open(photo_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                response = model.generate_content(["Extract only the main text from this image, ignoring any labels or additional comments, and return it as plain text", img])
                text = response.text
                if not text:
                    LOGGER.warning("No text extracted from image")
                else:
                    LOGGER.info("Successfully extracted text from image")
                return text
        except Exception as e:
            LOGGER.error(f"OCR Error: {e}")
            await notify_admin(event.client, "/tr ocr", e, event.message)
            raise
        finally:
            if photo_path and os.path.exists(photo_path):
                os.remove(photo_path)
                LOGGER.info(f"Deleted temporary image file: {photo_path}")
    async def translate_text(text: str, target_lang: str) -> str:
        try:
            translation = translator.translate(text, dest=target_lang)
            return translation.text
        except Exception as e:
            LOGGER.error(f"Translation error: {e}")
            raise
    async def format_text(text: str) -> str:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)
    async def translate_handler(event):
        client = event.client
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        cmd = event.message.text.split()[0].lower()
        combined_format = len(cmd) > len(COMMAND_PREFIX) + 2 and cmd[len(COMMAND_PREFIX) + 2:] in LANGUAGES
        reply_message = await event.message.get_reply_message()
        photo_mode = reply_message and isinstance(reply_message.media, MessageMediaPhoto)
        text_mode = (reply_message and reply_message.text) or (len(event.message.text.split()) > (1 if combined_format else 2))
        if combined_format:
            target_lang = cmd[len(COMMAND_PREFIX) + 2:]
            text_to_translate = " ".join(event.message.text.split()[1:]) if not (photo_mode or (reply_message and reply_message.text)) else None
        else:
            command = event.message.text.split(maxsplit=1)
            if len(command) < 2:
                await event.respond("**❌ Invalid language code!**", parse_mode="markdown")
                return
            target_lang = command[1].split()[0].lower()
            text_to_translate = " ".join(command[1].split()[1:]) if not (photo_mode or (reply_message and reply_message.text)) else None
        if target_lang not in LANGUAGES:
            await event.respond("**❌ Invalid language code!**", parse_mode="markdown")
            return
        if text_mode and not photo_mode:
            text_to_translate = reply_message.text if reply_message and reply_message.text else text_to_translate
            if not text_to_translate:
                await event.respond("**❌ No text provided to translate!**", parse_mode="markdown")
                return
        elif photo_mode:
            if not isinstance(reply_message.media, MessageMediaPhoto):
                await event.respond("**❌ Reply to a valid photo for Translation!**", parse_mode="markdown")
                return
        else:
            await event.respond("**❌ Provide text or reply to a photo!**", parse_mode="markdown")
            return
        loading_message = await event.respond(f"**Translating Your {'Image' if photo_mode else 'Text'} Into {LANGUAGES[target_lang].capitalize()}...**", parse_mode="markdown")
        try:
            if photo_mode:
                extracted_text = await ocr_extract_text(event)
                if not extracted_text:
                    await loading_message.edit("**No Readable Text Found In The Image**", parse_mode="markdown")
                    await notify_admin(client, "/tr ocr", Exception("No valid text extracted from image"), event.message)
                    return
                text_to_translate = extracted_text
            initial_translation = await translate_text(text_to_translate, 'en')
            translated_text = await translate_text(initial_translation, target_lang)
            formatted_text = await format_text(translated_text)
            if len(formatted_text) > 4000:
                await loading_message.delete()
                parts = [formatted_text[i:i+4000] for i in range(0, len(formatted_text), 4000)]
                for part in parts:
                    await client.send_message(event.chat_id, part, parse_mode="markdown")
            else:
                await loading_message.edit(formatted_text, parse_mode="markdown")
        except Exception as e:
            LOGGER.error(f"Translation handler error: {e}")
            await notify_admin(client, "/tr", e, event.message)
            await loading_message.edit("**Sorry Bro Translation API Dead❌**", parse_mode="markdown")
    app.add_event_handler(
        translate_handler,
        events.NewMessage(pattern=f"^{COMMAND_PREFIX}(tr|tr({'|'.join(LANGUAGES.keys())}))(?:\s|$)")
    )