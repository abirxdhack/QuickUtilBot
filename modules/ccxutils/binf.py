#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
import asyncio
import re
import os
from telethon import TelegramClient, events
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonRow, DocumentAttributeFilename
from telethon.tl.custom import Button
from config import COMMAND_PREFIX, MAX_TXT_SIZE, UPDATE_CHANNEL_URL, BAN_REPLY
from utils import notify_admin, LOGGER
from core import banned_users

def filter_bin(content, bin_number):
    filtered_lines = [line for line in content if line.startswith(bin_number)]
    return filtered_lines

def remove_bin(content, bin_number):
    filtered_lines = [line for line in content if not line.startswith(bin_number)]
    return filtered_lines

async def process_file(file_path, bin_number, command):
    with open(file_path, 'r') as file:
        content = file.readlines()
    if command in ['/adbin', '.adbin']:
        return filter_bin(content, bin_number)
    elif command in ['/rmbin', '.rmbin']:
        return remove_bin(content, bin_number)

async def handle_bin_commands(event):
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(
            BAN_REPLY,
            parse_mode='md',
            buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
        )
        return
    
    temp_msg = None
    try:
        args = event.pattern_match.group(1).strip().split(maxsplit=1) if event.pattern_match.group(1) else []
        if len(args) != 1:
            await event.respond(
                "**⚠️ Please provide a valid BIN number❌**",
                parse_mode='md',
                buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
            )
            return
        
        command = event.pattern_match.group(0).split()[0]
        bin_number = args[0]
        if not re.match(r'^\d{6}$', bin_number):
            await event.respond(
                "**⚠️ BIN number must be 6 digits❌**",
                parse_mode='md',
                buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
            )
            return
        
        reply_message = await event.get_reply_message()
        if not reply_message or not reply_message.document:
            await event.respond(
                "**⚠️ Please provide a valid .txt file by replying to it.❌**",
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
                "**⚠️ Please provide a valid .txt file by replying to it.❌**",
                parse_mode='md',
                buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
            )
            return
        
        file_size_mb = reply_message.document.size / (1024 * 1024)
        if file_size_mb > MAX_TXT_SIZE:
            await event.respond(
                "**⚠️ File size exceeds the 15MB limit❌**",
                parse_mode='md',
                buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
            )
            return
        
        processing_text = "**Adding Bins.....**" if command in ['/adbin', '.adbin'] else "**Removing Bins.....**"
        temp_msg = await event.respond(
            processing_text,
            parse_mode='md',
            buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
        )
        
        file_path = await event.client.download_media(reply_message, file="temp_file.txt")
        processed_cards = await process_file(file_path, bin_number, command)
        
        if not processed_cards:
            await event.respond(
                f"**❌ No credit card details found with BIN {bin_number}.**",
                parse_mode='md',
                buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
            )
            os.remove(file_path)
            if temp_msg:
                await event.client.delete_messages(event.chat_id, temp_msg)
            return
        
        action = "Add" if command in ['/adbin', '.adbin'] else "Remove"
        actioner = "Adder" if command in ['/adbin', '.adbin'] else "Remover"
        file_label = "Added" if command in ['/adbin', '.adbin'] else "Removed"
        
        if len(processed_cards) <= 10:
            formatted_cards = "\n".join(f"`{line.strip()}`" for line in processed_cards)
            response_message = (
                f"**Smart Bin {action} → Successful ✅**\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"{formatted_cards}\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"**Smart Bin {actioner} → Activated ✅**"
            )
            await event.respond(
                response_message,
                parse_mode='md',
                buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
            )
        else:
            file_name = f"Bin {file_label} Txt.txt"
            with open(file_name, "w") as file:
                file.write("".join(processed_cards))
            total_amount = len(processed_cards)
            total_size = f"{os.path.getsize(file_name) / 1024:.2f} KB"
            total_lines = len(processed_cards)
            caption = (
                f"**Smart Bin {action} → Successful ✅**\n"
                f"**━━━━━━━━━━━━━━━━━**\n"
                f"**⊗ Total Amount:** {total_amount}\n"
                f"**⊗ Total Size:** {total_size}\n"
                f"**⊗ Target Bin:** {bin_number}\n"
                f"**⊗ Total Lines:** {total_lines}\n"
                f"**━━━━━━━━━━━━━━━━━**\n"
                f"**Smart Bin {actioner} → Activated ✅**"
            )
            await event.client.send_file(
                event.chat_id,
                file_name,
                caption=caption,
                parse_mode='md',
                buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
            )
            os.remove(file_name)
        
        os.remove(file_path)
        if temp_msg:
            await event.client.delete_messages(event.chat_id, temp_msg)
    
    except Exception as e:
        LOGGER.error(f"Error processing file for {command if 'command' in locals() else '/adbin'}: {str(e)}")
        await event.respond(
            "**❌ Error processing file**",
            parse_mode='md',
            buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
        )
        await notify_admin(event.client, command if 'command' in locals() else "/adbin", e, event)
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        if temp_msg:
            await event.client.delete_messages(event.chat_id, temp_msg)

def setup_binf_handlers(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(?:adbin|rmbin)(?:\\s+(.+))?'))
    async def bin_commands(event):

        await handle_bin_commands(event)
