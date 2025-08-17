#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
import os
import time
from collections import Counter
from telethon import TelegramClient, events
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonRow, DocumentAttributeFilename
from telethon.tl.custom import Button
from config import COMMAND_PREFIX, MAX_TXT_SIZE, UPDATE_CHANNEL_URL, BAN_REPLY
from utils import notify_admin, LOGGER
from core import banned_users

async def handle_topbin_command(event):
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(
            BAN_REPLY,
            parse_mode='md',
            buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
        )
        return
    
    reply_message = await event.get_reply_message()
    if not reply_message or not reply_message.document:
        await event.respond(
            "**Reply to a text file containing credit cards to check top bins❌**",
            parse_mode='md',
            buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
        )
        return
    
    file_name = None
    for attr in reply_message.document.attributes:
        if isinstance(attr, DocumentAttributeFilename):
            file_name = attr.file_name
            break
    if not file_name or not file_name.endswith('.txt'):
        await event.respond(
            "**Reply to a text file containing credit cards to check top bins❌**",
            parse_mode='md',
            buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
        )
        return
    
    file_size_mb = reply_message.document.size / (1024 * 1024)
    if file_size_mb > MAX_TXT_SIZE:
        await event.respond(
            "**File size exceeds the 15MB limit❌**",
            parse_mode='md',
            buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
        )
        return
    
    temp_msg = await event.respond(
        "**Finding Top Bins...**",
        parse_mode='md',
        buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
    )
    
    try:
        start_time = time.time()
        file_path = await event.client.download_media(reply_message, file="temp_file.txt")
        with open(file_path, 'r') as file:
            content = file.readlines()
        
        bin_counter = Counter([line.strip()[:6] for line in content if len(line.strip()) >= 6])
        top_bins = bin_counter.most_common(20)
        end_time = time.time()
        time_taken = end_time - start_time
        
        if not top_bins:
            await event.client.delete_messages(event.chat_id, temp_msg)
            await event.respond(
                "**❌ No BIN data found in the file.**",
                parse_mode='md',
                buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
            )
            os.remove(file_path)
            return
        
        response_message = (
            f"**Smart Top Bin Find → Successful ✅**\n"
            f"**━━━━━━━━━━━━━━━━━**\n"
        )
        for bin, count in top_bins:
            response_message += f"**⊗ BIN:** `{bin}` - **Amount:** `{count}`\n"
        response_message += (
            f"**━━━━━━━━━━━━━━━━━**\n"
            f"**Smart Top Bin Finder → Activated ✅**"
        )
        
        await event.client.delete_messages(event.chat_id, temp_msg)
        await event.respond(
            response_message,
            parse_mode='md',
            buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
        )
        
        os.remove(file_path)
    
    except Exception as e:
        LOGGER.error(f"Error processing topbin command: {e}")
        await event.client.delete_messages(event.chat_id, temp_msg)
        await event.respond(
            "**❌ Error processing file**",
            parse_mode='md',
            buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
        )
        await notify_admin(event.client, "/topbin", e, event)
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

def setup_topbin_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}topbin'))
    async def topbin(event):

        await handle_topbin_command(event)
