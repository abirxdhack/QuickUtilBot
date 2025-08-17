import os
from concurrent.futures import ThreadPoolExecutor
from telethon import TelegramClient, events
from config import COMMAND_PREFIX, MAX_TXT_SIZE, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

def process_file(file_path, line_limit):
    with open(file_path, "r", encoding='utf-8', errors='ignore') as file:
        lines = file.readlines()
    
    total_lines = len(lines)
    split_files = []
    file_index = 1
    
    for start in range(0, total_lines, line_limit):
        end = start + line_limit
        split_file_path = f"{file_path}_part_{file_index}.txt"
        with open(split_file_path, "w", encoding='utf-8') as split_file:
            split_file.writelines(lines[start:end])
        split_files.append(split_file_path)
        file_index += 1
    
    return split_files

def setup_txt_handler(app: TelegramClient):
    executor = ThreadPoolExecutor(max_workers=4)
    
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}sptxt( .*)?$'))
    async def split_text(event):
        if not event.is_private:
            return
        user_id = event.sender_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='html')
            return
        reply_msg = await event.message.get_reply_message()
        if not reply_msg or not reply_msg.media or not hasattr(reply_msg, 'document') or reply_msg.document.mime_type != 'text/plain':
            await event.respond("<b>⚠️ Please Reply To A Txt File And Give Amount To Split</b>", parse_mode='html')
            return
        file_size_mb = reply_msg.document.size / (1024 * 1024)
        if file_size_mb > MAX_TXT_SIZE:
            await event.respond("<b>⚠️ File size exceeds the 10MB limit❌</b>", parse_mode='html')
            return
        command_text = event.pattern_match.group(1)
        try:
            line_limit = int(command_text.strip())
        except (IndexError, ValueError):
            await event.respond("<b>⚠️ Please Provide A Valid Line Limit</b>", parse_mode='html')
            return
        processing_msg = await event.respond("<b>Processing Text Split..✨</b>", parse_mode='html')
        try:
            file_path = await event.client.download_media(reply_msg)
            split_files = await app.loop.run_in_executor(executor, process_file, file_path, line_limit)
            await processing_msg.delete()
            for split_file in split_files:
                await event.respond(file=split_file)
                os.remove(split_file)
            os.remove(file_path)
        except Exception as e:
            LOGGER.error(f"Error processing text split: {e}")
            await notify_admin(event.client, "/sptxt", e, event.message)
            await processing_msg.edit("<b>❌ Error processing text split</b>", parse_mode='html')

    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}sptxt( .*)?$'))
    async def notify_private_chat(event):
        if event.is_private:
            return
        await event.respond("<b>You only can Split text in private chat⚠️</b>", parse_mode='html')