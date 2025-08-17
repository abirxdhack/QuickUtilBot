#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
import aiohttp
from telethon import TelegramClient, events
from config import COMMAND_PREFIX, BAN_REPLY
from utils import notify_admin, LOGGER
from core import banned_users

def setup_ai_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}ai(?:\\s+(.+))?'))
    async def ai_handler(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        try:
            loading_message = await event.respond("**🔍SmartAI is thinking, Please Wait✨**", parse_mode='md')
            prompt = None
            reply_message = await event.get_reply_message()
            if reply_message and reply_message.text:
                prompt = reply_message.text
            elif event.pattern_match.group(1):
                prompt = event.pattern_match.group(1).strip()
            
            if not prompt:
                await event.client.edit_message(loading_message, "**Please Provide A Prompt For SmartAI✨ Response**", parse_mode='md')
                return
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://abirthetech.serv00.net/ai.php?prompt={prompt}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        response_text = data.get("response", "No response received")
                    else:
                        response_text = "**❌Sorry Bro SmartAI API Error**"
                        LOGGER.error(f"API request failed with status {resp.status}")
            
            if len(response_text) > 4000:
                await event.client.delete_messages(event.chat_id, loading_message)
                parts = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
                for part in parts:
                    await event.respond(part, parse_mode='md')
            else:
                await event.client.edit_message(loading_message, response_text, parse_mode='md')
        
        except Exception as e:
            LOGGER.error(f"SmartAI error: {str(e)}")
            await event.respond("**❌Sorry Bro SmartAI API Error**", parse_mode='md')
            await notify_admin(event.client, "/ai", e, event)
