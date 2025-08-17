#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
import aiohttp
from telethon import TelegramClient, events
from config import OPENAI_API_KEY, COMMAND_PREFIX, BAN_REPLY
from utils import notify_admin, LOGGER
from core import banned_users

async def fetch_gpt_response(prompt, model):
    if not OPENAI_API_KEY or OPENAI_API_KEY.strip() == "":
        return None
    
    async with aiohttp.ClientSession() as session:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
            "n": 1,
            "stop": None,
            "temperature": 0.5
        }
        try:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    json_response = await response.json()
                    response_text = json_response['choices'][0]['message']['content']
                    return response_text
                else:
                    return None
        except Exception as e:
            return None

def setup_gpt_handlers(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}gpt4'))
    async def gpt4_handler(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        await event.respond("**GPT-4 Gate Off 🔕**", parse_mode='md')
    
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(?:gpt|gpt3|gpt3\\.5)(?:\\s+(.+))?'))
    async def gpt_handler(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        try:
            prompt = None
            reply_message = await event.get_reply_message()
            if reply_message and reply_message.text:
                prompt = reply_message.text
            elif event.pattern_match.group(1):
                prompt = event.pattern_match.group(1).strip()
            
            if not prompt:
                await event.respond("**Please Provide A Prompt For ChatGPTAI✨ Response**", parse_mode='md')
                return
            
            loading_message = await event.respond("**ChatGPT 3.5 Is Thinking✨**", parse_mode='md')
            response_text = await fetch_gpt_response(prompt, "gpt-4o-mini")
            
            if response_text:
                await event.client.edit_message(loading_message, response_text, parse_mode='md')
            else:
                await event.client.edit_message(loading_message, "**Sorry Chat Gpt 3.5 API Dead**", parse_mode='md')
                await notify_admin(event.client, "/gpt", Exception("Failed to fetch GPT response"), event)
        
        except Exception as e:
            await event.client.edit_message(loading_message, "**Sorry Chat Gpt 3.5 API Dead**", parse_mode='md')

            await notify_admin(event.client, "/gpt", e, event)
