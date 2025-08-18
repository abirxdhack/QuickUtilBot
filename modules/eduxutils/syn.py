import aiohttp
from telethon import events
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

async def fetch_synonyms_antonyms(word: str):
    synonyms_url = f"https://api.datamuse.com/words?rel_syn={word}"
    antonyms_url = f"https://api.datamuse.com/words?rel_ant={word}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(synonyms_url) as syn_response, session.get(antonyms_url) as ant_response:
                syn_response.raise_for_status()
                ant_response.raise_for_status()
                synonyms = [syn['word'] for syn in await syn_response.json()]
                antonyms = [ant['word'] for ant in await ant_response.json()]
        return synonyms, antonyms
    except (aiohttp.ClientError, ValueError) as e:
        LOGGER.error(f"Datamuse API error for word '{word}': {e}")
        raise

async def synonyms_handler(event):
    client = event.client
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY)
        return
    reply_message = await event.message.get_reply_message()
    if reply_message and reply_message.text:
        word = reply_message.text.strip()
        if len(word.split()) != 1:
            await event.respond("**❌ Reply to a message with a single word to get synonyms and antonyms.**", parse_mode="markdown")
            return
    else:
        command = event.message.text.split(maxsplit=1)
        if len(command) <= 1 or len(command[1].split()) != 1:
            await event.respond("**❌ Provide a single word to get synonyms and antonyms.**", parse_mode="markdown")
            return
        word = command[1].strip()
    loading_message = await event.respond("**Fetching Synonyms and Antonyms...✨**", parse_mode="markdown")
    try:
        synonyms, antonyms = await fetch_synonyms_antonyms(word)
        synonyms_text = ", ".join(synonyms) if synonyms else "No synonyms found"
        antonyms_text = ", ".join(antonyms) if antonyms else "No antonyms found"
        response_text = (
            f"**Synonyms:**\n{synonyms_text}\n\n"
            f"**Antonyms:**\n{antonyms_text}"
        )
        await loading_message.edit(response_text, parse_mode="markdown")
    except Exception as e:
        LOGGER.error(f"Error processing synonyms/antonyms for word '{word}': {e}")
        await notify_admin(client, "/syn", e, event.message)
        await loading_message.edit("**❌ Sorry, Synonym/Antonym API Failed**", parse_mode="markdown")

def setup_syn_handler(app):
    app.add_event_handler(
        synonyms_handler,
        events.NewMessage(pattern=f"^{COMMAND_PREFIX}(syn|synonym)(?:\s|$)")
    )