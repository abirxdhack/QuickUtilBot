import re
from telethon import events
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

def youtube_parser(url: str):
    reg_exp = r"(?:youtube\.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)|.*[?&]v=)|youtu\.be/)([^\"&?/ ]{11})"
    try:
        match = re.search(reg_exp, url)
        return match.group(1) if match else False
    except Exception as e:
        LOGGER.error(f"Error parsing YouTube URL {url}: {e}")
        return False

async def handle_yth_command(event: events.NewMessage.Event):
    sender = await event.get_sender()
    user_id = sender.id if sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.reply(BAN_REPLY, parse_mode="html")
        return
    args = event.raw_text.split()
    if len(args) == 1:
        await event.reply("<b>❌ Provide a Valid YouTube link</b>", parse_mode="html")
        return
    youtube_url = args[1].strip()
    processing_msg = await event.reply("<b>Fetching YouTube thumbnail...✨</b>", parse_mode="html")
    try:
        video_id = youtube_parser(youtube_url)
        if not video_id:
            await processing_msg.edit("<b>Invalid YouTube link Bro ❌</b>", parse_mode="html")
            return
        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        caption = "<code>Photo Sent</code>"
        await event.client.send_file(entity=event.chat_id, file=thumbnail_url, caption=caption, parse_mode="html")
        await processing_msg.delete()
    except Exception as e:
        LOGGER.error(f"Error fetching YouTube thumbnail for URL {youtube_url}: {e}")
        error_msg = "<b>Sorry Bro YouTube Thumbnail API Dead</b>"
        await processing_msg.edit(error_msg, parse_mode="html")
        await notify_admin(event.client, "/yth", e, event)

def setup_yth_handler(app):
    @app.on(events.NewMessage(pattern=f"^{COMMAND_PREFIX}yth"))
    async def yth_command(event):
        await handle_yth_command(event)
