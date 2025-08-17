import os
import logging
import json
import aiohttp
from telethon import TelegramClient, events
from config import COMMAND_PREFIX, BAN_REPLY, REPLICATE_API_TOKEN
from core import banned_users
from utils import LOGGER, notify_admin

CLAUDE_API_URL = "https://api.replicate.com/v1/models/anthropic/claude-3.7-sonnet/predictions"

async def query_claude(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
        "Prefer": "wait"
    }
    payload = {
        "input": {
            "prompt": prompt,
            "max_tokens": 8192,
            "system_prompt": "",
            "extended_thinking": False,
            "max_image_resolution": 0.5,
            "thinking_budget_tokens": 1024
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(CLAUDE_API_URL, headers=headers, data=json.dumps(payload)) as response:
            if response.status == 201:
                result = await response.json()
                output = result.get("output", [])
                if isinstance(output, list):
                    return ''.join(output).strip()
                return str(output)
            else:
                raise Exception(f"Claude API error {response.status}: {await response.text()}")

def setup_cla_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}cla(?:\\s+(.+))?'))
    async def claude_handler(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        loading_message = None
        try:
            loading_message = await event.respond("**🔍 Claude AI ✨ is thinking... Please wait!**", parse_mode='md')
            prompt = None
            reply_message = await event.get_reply_message()
            if reply_message and reply_message.text:
                prompt = reply_message.text
            elif event.pattern_match.group(1):
                prompt = event.pattern_match.group(1).strip()
            
            if not prompt:
                await event.client.edit_message(loading_message, "**⚠️ Please provide a prompt for Claude AI ✨**", parse_mode='md')
                return
            
            response_text = await query_claude(prompt)
            if len(response_text) > 4000:
                parts = [response_text[i:i + 4000] for i in range(0, len(response_text), 4000)]
                await event.client.delete_messages(event.chat_id, loading_message)
                await event.client.edit_message(event.chat_id, parts[0], parse_mode='md')
                for part in parts[1:]:
                    await event.respond(part, parse_mode='md')
            else:
                await event.client.edit_message(loading_message, response_text, parse_mode='md')
        
        except Exception as e:
            LOGGER.error(f"Error during Claude generation: {e}")
            if loading_message:
                await event.client.edit_message(loading_message, "**🔍 Sorry, Claude AI ✨ failed to respond.**", parse_mode='md')
            await notify_admin(event.client, "/cla", e, event)