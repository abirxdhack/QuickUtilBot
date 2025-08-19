import aiohttp
from telethon import events
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

async def ytag_handler(event: events.NewMessage.Event):
    sender = await event.get_sender()
    user_id = sender.id if sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.client.send_message(event.chat_id, BAN_REPLY, parse_mode="markdown")
        return

    args = event.raw_text.split()
    if len(args) <= 1:
        await event.client.send_message(event.chat_id, "**❌ Please provide a YouTube URL. Usage: /ytag [URL]**", parse_mode="markdown", link_preview=False)
        return

    url = args[1].strip()
    fetching_msg = await event.client.send_message(event.chat_id, "**Processing Your Request...**", parse_mode="markdown", link_preview=False)

    try:
        api_url = f"https://smartytdl.vercel.app/dl?url={url}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    raise Exception(f"API returned status {resp.status}")
                data = await resp.json()

        tags = data.get("tags", [])
        if not tags:
            response = "**Sorry, no tags available for this video.**"
        else:
            tags_str = "\n".join([f"`{tag}`" for tag in tags])
            response = f"**Your Requested Video Tags ✅**\n━━━━━━━━━━━━━━━━\n{tags_str}"

        await fetching_msg.edit(response, parse_mode="markdown", link_preview=False)

    except Exception as e:
        LOGGER.error(f"Error extracting YouTube tags for URL {url}: {e}")
        error_msg = "**Sorry Bro YouTube Tags API Dead**"
        await fetching_msg.edit(error_msg, parse_mode="markdown", link_preview=False)
        await notify_admin(event.client, "/ytag", e, event)

def setup_ytag_handlers(app):
    @app.on(events.NewMessage(pattern=f"^{COMMAND_PREFIX}(ytag|\\.ytag)"))
    async def ytag_info(event):
        await ytag_handler(event)
