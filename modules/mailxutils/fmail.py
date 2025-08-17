import re
import os
import time
from telethon import TelegramClient, events, Button
from config import COMMAND_PREFIX, MAX_TXT_SIZE, UPDATE_CHANNEL_URL, BAN_REPLY
from core import banned_users
from utils import LOGGER, notify_admin

async def filter_emails(content):
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    emails = [line.split(':')[0].strip() for line in content if email_pattern.match(line.split(':')[0])]
    return emails

async def filter_email_pass(content):
    email_pass_pattern = re.compile(r'^([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}):(.+)$')
    email_passes = []
    for line in content:
        match = email_pass_pattern.match(line)
        if match:
            email = match.group(1)
            password = match.group(2).split()[0]
            email_passes.append(f"{email}:{password}")
    return email_passes

async def handle_fmail_command(event):
    start_time = time.time()
    user_id = event.sender_id
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY, parse_mode='markdown')
        return
    reply_msg = await event.get_reply_message()
    if not reply_msg or not reply_msg.document or not reply_msg.document.mime_type.startswith('text/'):
        await event.respond("**⚠️ Reply to a message with a text file❌**", parse_mode='markdown')
        return
    temp_msg = await event.respond("**Fetching And Filtering Mails...✨**", parse_mode='markdown')
    file_path = await event.client.download_media(reply_msg)
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > MAX_TXT_SIZE:
        await temp_msg.delete()
        await event.respond("**⚠️ File size exceeds the 15MB limit❌**", parse_mode='markdown')
        os.remove(file_path)
        return
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
        content = file.readlines()
    emails = await filter_emails(content)
    if not emails:
        await temp_msg.delete()
        await event.respond("**❌ No valid emails found in the file.**", parse_mode='markdown')
        os.remove(file_path)
        return
    sender = await event.get_sender()
    if hasattr(sender, 'first_name'):
        user_full_name = f"{sender.first_name} {sender.last_name or ''}".strip()
        user_profile_url = f"https://t.me/{sender.username}" if sender.username else None
        user_link = f'[{user_full_name}]({user_profile_url})' if user_profile_url else user_full_name
    else:
        chat = await event.get_chat()
        group_name = chat.title or "this group"
        group_url = f"https://t.me/{chat.username}" if chat.username else "this group"
        user_link = f'[{group_name}]({group_url})'
    time_taken = round(time.time() - start_time, 2)
    total_lines = len(content)
    total_mails = len(emails)
    caption = (
        f"**Smart Mail Extraction Complete ✅**\n"
        f"**━━━━━━━━━━━━━━━━━**\n"
        f"**⊗ Total Size:** `{file_size_mb:.2f} MB`\n"
        f"**⊗ Total Mails:** `{total_mails}`\n"
        f"**⊗ Total Lines:** `{total_lines}`\n"
        f"**⊗ Time Taken:** `{time_taken} seconds`\n"
        f"**━━━━━━━━━━━━━━━━━**\n"
        f"**Requested By {user_link}**"
    )
    button = [[Button.url("Join For Updates", UPDATE_CHANNEL_URL)]]
    if len(emails) > 10:
        file_name = "ProcessedFile.txt"
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write("\n".join(emails))
        await temp_msg.delete()
        await event.respond(caption, file=file_name, parse_mode='markdown', buttons=button)
        os.remove(file_name)
    else:
        formatted_emails = '\n'.join(f'`{email}`' for email in emails)
        await temp_msg.delete()
        await event.respond(f"{caption}\n\n{formatted_emails}", parse_mode='markdown', buttons=button)
    os.remove(file_path)

async def handle_fpass_command(event):
    start_time = time.time()
    user_id = event.sender_id
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY, parse_mode='markdown')
        return
    reply_msg = await event.get_reply_message()
    if not reply_msg or not reply_msg.document or not reply_msg.document.mime_type.startswith('text/'):
        await event.respond("**⚠️ Reply to a message with a text file.**", parse_mode='markdown')
        return
    temp_msg = await event.respond("**Filtering And Extracting Mail Pass...✨**", parse_mode='markdown')
    file_path = await event.client.download_media(reply_msg)
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > MAX_TXT_SIZE:
        await temp_msg.delete()
        await event.respond("**⚠️ File size exceeds the 15MB limit❌**", parse_mode='markdown')
        os.remove(file_path)
        return
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
        content = file.readlines()
    email_passes = await filter_email_pass(content)
    if not email_passes:
        await temp_msg.delete()
        await event.respond("**❌ No Mail Pass Combo Found**", parse_mode='markdown')
        os.remove(file_path)
        return
    sender = await event.get_sender()
    if hasattr(sender, 'first_name'):
        user_full_name = f"{sender.first_name} {sender.last_name or ''}".strip()
        user_profile_url = f"https://t.me/{sender.username}" if sender.username else None
        user_link = f'[{user_full_name}]({user_profile_url})' if user_profile_url else user_full_name
    else:
        chat = await event.get_chat()
        group_name = chat.title or "this group"
        group_url = f"https://t.me/{chat.username}" if chat.username else "this group"
        user_link = f'[{group_name}]({group_url})'
    time_taken = round(time.time() - start_time, 2)
    total_lines = len(content)
    total_mails = len(email_passes)
    total_pass = len(email_passes)
    caption = (
        f"**Smart Mail-Pass Combo Process Complete ✅**\n"
        f"**━━━━━━━━━━━━━━━━━**\n"
        f"**⊗ Total Size:** `{file_size_mb:.2f} MB`\n"
        f"**⊗ Total Mails:** `{total_mails}`\n"
        f"**⊗ Total Pass:** `{total_pass}`\n"
        f"**⊗ Total Lines:** `{total_lines}`\n"
        f"**⊗ Time Taken:** `{time_taken} seconds`\n"
        f"**━━━━━━━━━━━━━━━━━**\n"
        f"**Requested By {user_link}**"
    )
    button = [[Button.url("Join For Updates", UPDATE_CHANNEL_URL)]]
    if len(email_passes) > 10:
        file_name = "ProcessedFile.txt"
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write("\n".join(email_passes))
        await temp_msg.delete()
        await event.respond(caption, file=file_name, parse_mode='markdown', buttons=button)
        os.remove(file_name)
    else:
        formatted_email_passes = '\n'.join(f'`{email_pass}`' for email_pass in email_passes)
        await temp_msg.delete()
        await event.respond(f"{caption}\n\n{formatted_email_passes}", parse_mode='markdown', buttons=button)
    os.remove(file_path)

def setup_fmail_handlers(client: TelegramClient):
    client.add_event_handler(handle_fmail_command, events.NewMessage(pattern=f'^{COMMAND_PREFIX}fmail$'))
    client.add_event_handler(handle_fpass_command, events.NewMessage(pattern=f'^{COMMAND_PREFIX}fpass$'))