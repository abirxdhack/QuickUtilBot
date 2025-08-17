import os
import aiohttp
from telethon import TelegramClient, events
from config import GROQ_API_KEY, GROQ_API_URL, TEXT_MODEL, COMMAND_PREFIX, BAN_REPLY
from utils import notify_admin, LOGGER
from core import banned_users

def setup_dep_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}dep(?:\\s+(.+))?'))
    async def dep_command(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        user_text = None
        reply_message = await event.get_reply_message()
        if reply_message and reply_message.text:
            user_text = reply_message.text
        elif event.pattern_match.group(1):
            user_text = event.pattern_match.group(1).strip()
        
        if not user_text:
            await event.respond("**Please Provide A Prompt For DeepSeekAi✨ Response**", parse_mode='md')
            return
        
        temp_message = await event.respond("**DeepSeek AI Is Thinking Wait..✨**", parse_mode='md')
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    GROQ_API_URL,
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": TEXT_MODEL,
                        "messages": [
                            {"role": "system", "content": "Reply in the same language as the user's message But Always Try To Answer Shortly"},
                            {"role": "user", "content": user_text},
                        ],
                    },
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    bot_response = data.get("choices", [{}])[0].get("message", {}).get("content", "Sorry DeepSeek API Dead")
            
            await event.client.edit_message(temp_message, bot_response, parse_mode='md')
        
        except aiohttp.ClientError as e:
            LOGGER.error(f"HTTP error while calling Groq API: {e}")
            await event.client.edit_message(temp_message, "**Sorry Bro DeepseekAI✨ API Dead**", parse_mode='md')
            await notify_admin(event.client, "/dep", e, event)
        except Exception as e:
            LOGGER.error(f"Error generating response: {e}")
            await event.client.edit_message(temp_message, "**Sorry Bro DeepseekAI✨ API Dead**", parse_mode='md')
            await notify_admin(event.client, "/dep", e, event)