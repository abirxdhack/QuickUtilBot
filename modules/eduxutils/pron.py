import os
import aiohttp
from telethon import events
from telethon.tl import types
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

async def fetch_pronunciation_info(word):
    url = f"https://abirthetech.serv00.net/pr.php?prompt={word}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                result = await response.json()
                pronunciation_info = result['response']
                return {
                    "word": pronunciation_info['Word'],
                    "breakdown": pronunciation_info['- Breakdown'],
                    "pronunciation": pronunciation_info['- Pronunciation'],
                    "stems": pronunciation_info['Word Stems'].split(", "),
                    "definition": pronunciation_info['Definition'],
                    "audio_link": pronunciation_info['Audio']
                }
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        LOGGER.error(f"Pronunciation API error for word '{word}': {e}")
        return None

async def pronunciation_check(event):
    client = event.client
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY)
        return
    reply_message = await event.message.get_reply_message()
    if reply_message and reply_message.text:
        word = reply_message.text.strip()
        if len(word.split()) != 1:
            await event.respond("**❌ Reply to a message with a single word to check pronunciation.**", parse_mode="markdown")
            return
    else:
        user_input = event.message.text.split(maxsplit=1)
        if len(user_input) < 2 or len(user_input[1].split()) != 1:
            await event.respond("**❌ Provide a single word to check pronunciation.**", parse_mode="markdown")
            return
        word = user_input[1].strip()
    checking_message = await event.respond("**Checking Pronunciation...✨**", parse_mode="markdown")
    try:
        pronunciation_info = await fetch_pronunciation_info(word)
        if pronunciation_info is None:
            await checking_message.edit("**❌ Sorry Bro Pronunciation API Dead**", parse_mode="markdown")
            await notify_admin(client, "/prn", Exception("Pronunciation API returned no data"), event.message)
            return
        audio_filename = None
        if pronunciation_info['audio_link']:
            audio_filename = f"Smart Tool ⚙️ {word}.mp3"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(pronunciation_info['audio_link']) as response:
                        response.raise_for_status()
                        with open(audio_filename, 'wb') as f:
                            f.write(await response.read())
            except aiohttp.ClientError as e:
                LOGGER.error(f"Failed to download audio for word '{word}': {e}")
                await notify_admin(client, "/prn audio", e, event.message)
                audio_filename = None
        caption = (
            f"**Word:** {pronunciation_info['word']}\n"
            f"- **Breakdown:** {pronunciation_info['breakdown']}\n"
            f"- **Pronunciation:** {pronunciation_info['pronunciation']}\n\n"
            f"**Word Stems:**\n{', '.join(pronunciation_info['stems'])}\n\n"
            f"**Definition:**\n{pronunciation_info['definition']}"
        )
        if audio_filename:
            await client.send_file(
                event.chat_id,
                audio_filename,
                caption=caption,
                parse_mode="markdown",
                attributes=[types.DocumentAttributeAudio(duration=0, title=pronunciation_info['word'], performer="Smart Tool")]
            )
            os.remove(audio_filename)
        else:
            await client.send_message(
                event.chat_id,
                caption,
                parse_mode="markdown"
            )
        await checking_message.delete()
    except Exception as e:
        LOGGER.error(f"Error processing pronunciation check for word '{word}': {e}")
        await notify_admin(client, "/prn", e, event.message)
        await checking_message.edit("**❌ Sorry Bro Pronunciation API Dead**", parse_mode="markdown")

def setup_prn_handler(app):
    app.add_event_handler(
        pronunciation_check,
        events.NewMessage(pattern=f"^{COMMAND_PREFIX}prn(?:\s|$)")
    )