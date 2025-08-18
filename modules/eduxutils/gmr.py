import aiohttp
from telethon import events
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

async def check_grammar(text):
    url = f"http://abirthetech.serv00.net/gmr.php?prompt={text}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                result = await response.json()
                if 'response' not in result:
                    raise ValueError("Invalid API response: 'response' key missing")
                LOGGER.info("Successfully fetched grammar correction")
                return result['response'].strip()
    except Exception as e:
        LOGGER.error(f"Grammar check API error: {e}")
        raise

async def grammar_check(event):
    client = event.client
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY)
        return
    reply_message = await event.message.get_reply_message()
    if reply_message and reply_message.text:
        user_input = reply_message.text.strip()
    else:
        user_input = event.message.text.split(maxsplit=1)
        if len(user_input) < 2:
            await event.respond("**❌ Provide some text or reply to a message to fix grammar.**", parse_mode="markdown")
            return
        user_input = user_input[1].strip()
    checking_message = await event.respond("**Checking And Fixing Grammar Please Wait...✨**", parse_mode="markdown")
    try:
        corrected_text = await check_grammar(user_input)
        await checking_message.edit(f"{corrected_text}", parse_mode="markdown")
    except Exception as e:
        LOGGER.error(f"Error processing grammar check: {e}")
        await notify_admin(client, "/gra", e, event.message)
        await checking_message.edit("**❌ Sorry, Grammar Check API Failed**", parse_mode="markdown")

def setup_gmr_handler(app):
    app.add_event_handler(
        grammar_check,
        events.NewMessage(pattern=f"^{COMMAND_PREFIX}gra(?:\s|$)")
    )