import aiohttp
from telethon import events
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

async def check_spelling(word):
    url = f"https://abirthetech.serv00.net/spl.php?prompt={word}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                result = await response.json()
                if 'response' not in result:
                    raise ValueError("Invalid API response: 'response' key missing")
                return result['response'].strip()
    except Exception as e:
        LOGGER.error(f"Spelling check API error for word '{word}': {e}")
        raise

async def spell_check(event):
    client = event.client
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY)
        return
    reply_message = await event.message.get_reply_message()
    if reply_message and reply_message.text:
        user_input = reply_message.text.strip()
        if len(user_input.split()) != 1:
            await event.respond("**❌ Reply to a message with a single word to check spelling.**", parse_mode="markdown")
            return
    else:
        user_input = event.message.text.split(maxsplit=1)
        if len(user_input) < 2 or len(user_input[1].split()) != 1:
            await event.respond("**❌ Provide a single word to check spelling.**", parse_mode="markdown")
            return
        user_input = user_input[1].strip()
    checking_message = await event.respond("**Checking Spelling...✨**", parse_mode="markdown")
    try:
        corrected_word = await check_spelling(user_input)
        await checking_message.edit(f"`{corrected_word}`", parse_mode="markdown")
    except Exception as e:
        LOGGER.error(f"Error processing spelling check for word '{user_input}': {e}")
        await notify_admin(client, "/spell", e, event.message)
        await checking_message.edit("**❌ Sorry, Spelling Check API Failed**", parse_mode="markdown")

def setup_spl_handler(app):
    app.add_event_handler(
        spell_check,
        events.NewMessage(pattern=f"^{COMMAND_PREFIX}spell(?:\s|$)")
    )