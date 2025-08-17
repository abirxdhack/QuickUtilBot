#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
import os
import io
from PIL import Image
import google.generativeai as genai
from telethon import TelegramClient, events
from config import COMMAND_PREFIX, IMGAI_SIZE_LIMIT, BAN_REPLY, GOOGLE_API_KEY, MODEL_NAME
from utils import notify_admin, LOGGER
from core import banned_users

def setup_gem_handler(app: TelegramClient):
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(MODEL_NAME)
    
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(?:gem|gemi|gemini)(?:\\s+(.+))?'))
    async def gemi_handler(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        try:
            loading_message = await event.respond("**🔍GeminiAI is thinking, Please Wait✨**", parse_mode='md')
            prompt = None
            reply_message = await event.get_reply_message()
            if reply_message and reply_message.text:
                prompt = reply_message.text
            elif event.pattern_match.group(1):
                prompt = event.pattern_match.group(1).strip()
            
            if not prompt:
                await event.client.edit_message(loading_message, "**Please Provide A Prompt For GeminiAI✨ Response**", parse_mode='md')
                return
            
            response = model.generate_content(prompt)
            response_text = response.text
            if len(response_text) > 4000:
                await event.client.delete_messages(event.chat_id, loading_message)
                parts = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
                for part in parts:
                    await event.respond(part, parse_mode='md')
            else:
                await event.client.edit_message(loading_message, response_text, parse_mode='md')
        
        except Exception as e:
            LOGGER.error(f"Gemini error: {str(e)}")
            await event.respond("**❌Sorry Bro Gemini API Error**", parse_mode='md')
            await notify_admin(event.client, "/gem", e, event)
        
        finally:
            if os.path.exists("temp_file"):
                os.remove("temp_file")
    
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}imgai(?:\\s+(.+))?'))
    async def imgai_handler(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        try:
            reply_message = await event.get_reply_message()
            if not reply_message or not reply_message.photo:
                await event.respond("**❌ Please Reply To An Image For Analysis**", parse_mode='md')
                return
            
            processing_msg = await event.respond("**🔍Gemini Is Analyzing The Image Please Wait✨**", parse_mode='md')
            photo_path = await event.client.download_media(reply_message, file="temp_file")
            
            try:
                if os.path.getsize(photo_path) > IMGAI_SIZE_LIMIT:
                    await event.client.edit_message(processing_msg, "**❌Sorry Bro Image Too Large**", parse_mode='md')
                    return
                
                with Image.open(photo_path) as img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                
                user_prompt = event.pattern_match.group(1).strip() if event.pattern_match.group(1) else "Describe this image in detail"
                response = model.generate_content([user_prompt, img])
                analysis = response.text
                if len(analysis) > 4000:
                    await event.client.delete_messages(event.chat_id, processing_msg)
                    parts = [analysis[i:i+4000] for i in range(0, len(analysis), 4000)]
                    for part in parts:
                        await event.respond(part, parse_mode='md')
                else:
                    await event.client.edit_message(processing_msg, analysis, parse_mode='md')
            
            except Exception as e:
                LOGGER.error(f"Image analysis error: {str(e)}")
                await event.client.edit_message(processing_msg, "**❌ Sorry Bro ImageAI Error**", parse_mode='md')
                await notify_admin(event.client, "/imgai", e, event)
            
            finally:
                if os.path.exists(photo_path):
                    os.remove(photo_path)
        
        except Exception as e:
            LOGGER.error(f"Image analysis error: {str(e)}")
            await event.respond("**❌ Sorry Bro ImageAI Error**", parse_mode='md')

            await notify_admin(event.client, "/imgai", e, event)
