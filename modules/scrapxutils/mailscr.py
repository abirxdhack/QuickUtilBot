import re
import os
import asyncio
import aiofiles
from telethon import TelegramClient, events
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest
from telethon.errors import (
    UserAlreadyParticipantError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    PeerIdInvalidError,
    ChannelPrivateError,
    FloodWaitError,
    ChatAdminRequiredError
)
from urllib.parse import urlparse
from user import user
from config import (
    SUDO_MAILSCR_LIMIT,
    OWNER_ID,
    MAIL_SCR_LIMIT,
    COMMAND_PREFIX,
    BAN_REPLY
)
from utils import LOGGER
from core import banned_users

def filter_messages(message):
    if message is None:
        return []
    pattern = r'(\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b:\S+)'
    matches = re.findall(pattern, message)
    return matches

async def scrape_mail_messages(client, channel, limit):
    messages = []
    LOGGER.info(f"Starting to scrape email combos from {channel} with limit {limit}")
    
    try:
        channel_entity = channel
        if hasattr(channel, 'id'):
            channel_entity = channel.id
        elif isinstance(channel, str):
            channel_entity = channel
            
        message_count = 0
        found_combos = 0
        
        async for message in client.iter_messages(channel_entity, limit=None):
            if found_combos >= limit:
                break
                
            message_count += 1
            
            text = message.text
            if not text and hasattr(message, 'media') and message.media:
                text = getattr(message.media, 'caption', None)
            
            if text:
                matched_combos = filter_messages(text)
                if matched_combos:
                    for combo in matched_combos:
                        if found_combos >= limit:
                            break
                        messages.append(combo)
                        found_combos += 1
                    
        LOGGER.info(f"Checked {message_count} messages, found {len(messages)} email combos from {channel}")
        
    except Exception as e:
        LOGGER.error(f"Error while scraping messages: {e}")
        
    return messages

def remove_mail_duplicates(messages):
    unique_messages = list(set(messages))
    duplicates_removed = len(messages) - len(unique_messages)
    LOGGER.info(f"Removed {duplicates_removed} duplicates")
    return unique_messages, duplicates_removed

async def send_mail_results(client, chat_id, unique_messages, duplicates_removed, source_name, temporary_msg=None):
    if unique_messages:
        file_name = f"x{len(unique_messages)}_{source_name.replace(' ', '_')}_combos.txt"
        async with aiofiles.open(file_name, mode='w', encoding='utf-8') as f:
            for combo in unique_messages:
                try:
                    await f.write(f"{combo}\n")
                except UnicodeEncodeError:
                    continue
        
        caption = (
            f"**Mail Scraped Successful ✅**\n"
            f"**━━━━━━━━━━━━━━━━**\n"
            f"**Source:** `{source_name} 🌐`\n"
            f"**Amount:** `{len(unique_messages)} 📝`\n"
            f"**Duplicates Removed:** `{duplicates_removed} 🗑️`\n"
            f"**━━━━━━━━━━━━━━━━**\n"
            f"**✅ Mail-Scrapped By: Smart Tool**\n"
        )
        
        if temporary_msg:
            await temporary_msg.delete()
        
        await client.send_file(chat_id, file_name, caption=caption)
        os.remove(file_name)
        LOGGER.info(f"Mail results sent successfully for {source_name}")
    else:
        if temporary_msg:
            await temporary_msg.edit("**Sorry Bro ❌ No Mail Pass Found**")
        else:
            await client.send_message(chat_id, "**Sorry Bro ❌ No Mail Pass Found**")
        LOGGER.info("No email combos found")

async def join_private_mail_chat(invite_link, chat_id, temporary_msg=None):
    try:
        if invite_link.startswith("https://t.me/+"):
            invite_hash = invite_link.replace("https://t.me/+", "")
        elif invite_link.startswith("https://t.me/joinchat/"):
            invite_hash = invite_link.replace("https://t.me/joinchat/", "")
        else:
            invite_hash = invite_link
            
        result = await user(ImportChatInviteRequest(invite_hash))
        
        if hasattr(result, 'chats') and result.chats:
            chat_entity = result.chats[0]
            LOGGER.info(f"Successfully joined chat: {chat_entity.title}")
            return True, chat_entity
        else:
            try:
                chat_entity = await user.get_entity(invite_link)
                LOGGER.info(f"Got entity after join: {chat_entity.title}")
                return True, chat_entity
            except Exception as get_entity_error:
                LOGGER.error(f"Failed to get entity after join: {get_entity_error}")
                return False, None
                
    except UserAlreadyParticipantError:
        LOGGER.info(f"Already a participant in the chat: {invite_link}")
        try:
            if invite_link.startswith("https://t.me/+"):
                invite_hash = invite_link.replace("https://t.me/+", "")
            elif invite_link.startswith("https://t.me/joinchat/"):
                invite_hash = invite_link.replace("https://t.me/joinchat/", "")
            else:
                invite_hash = invite_link
                
            try:
                invite_info = await user(CheckChatInviteRequest(invite_hash))
                if hasattr(invite_info, 'chat'):
                    return True, invite_info.chat
                else:
                    chat = await user.get_entity(invite_link)
                    return True, chat
            except:
                chat = await user.get_entity(invite_link)
                return True, chat
        except Exception as e:
            LOGGER.error(f"Failed to get entity for {invite_link}: {e}")
            return False, None
    except (InviteHashExpiredError, InviteHashInvalidError):
        LOGGER.error(f"Failed to join chat {invite_link}: Invalid or expired invite link")
        return False, None
        
    except ChannelPrivateError:
        LOGGER.info(f"Join request sent to the chat: {invite_link}")
        return False, None
        
    except FloodWaitError as e:
        wait_time = e.seconds
        LOGGER.warning(f"FloodWait error: {wait_time} seconds")
        return False, None
        
    except ChatAdminRequiredError:
        LOGGER.error(f"Admin privileges required for {invite_link}")
        return False, None
        
    except Exception as e:
        error_msg = str(e)
        if "successfully requested to join" in error_msg.lower():
            LOGGER.info(f"Join request sent successfully to chat: {invite_link}")
            return "join_request", None
        else:
            LOGGER.error(f"Unexpected error joining chat {invite_link}: {e}")
            return False, None

async def get_mail_channel_entity(channel_identifier, chat_id, temporary_msg=None):
    chat = None
    channel_name = ""
    
    try:
        if channel_identifier.lstrip("-").isdigit():
            chat_id_int = int(channel_identifier)
            chat = await user.get_entity(chat_id_int)
            channel_name = chat.title
            LOGGER.info(f"Got entity for private channel: {channel_name} (ID: {chat_id_int})")
            
        elif channel_identifier.startswith("https://t.me/+"):
            invite_link = channel_identifier
            
            joined, chat = await join_private_mail_chat(invite_link, chat_id, temporary_msg)
            if joined == "join_request":
                if temporary_msg:
                    await temporary_msg.edit("**Hey Bro I Have Sent Join Request ✅**")
                else:
                    await client.send_message(chat_id, "**Hey Bro I Have Sent Join Request ✅**")
                return None, None, temporary_msg
            elif not joined or not chat:
                return None, None, temporary_msg
            channel_name = chat.title
            LOGGER.info(f"Joined private channel via link: {channel_name}")
            
        else:
            if channel_identifier.startswith("https://t.me/"):
                channel_username = channel_identifier[13:]
            elif channel_identifier.startswith("t.me/"):
                channel_username = channel_identifier[5:]
            else:
                channel_username = channel_identifier
                
            if not channel_username.startswith("@"):
                channel_username = f"@{channel_username}"
                
            chat = await user.get_entity(channel_username)
            channel_name = chat.title
            LOGGER.info(f"Got entity for public channel: {channel_name} (Username: {channel_username})")
            
    except Exception as e:
        LOGGER.error(f"Failed to get channel entity for {channel_identifier}: {e}")
        if temporary_msg:
            await temporary_msg.edit("**Hey Bro! 🥲 Failed to access channel ❌**")
        return None, None, temporary_msg
        
    return chat, channel_name, temporary_msg

def setup_mailscr_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(mailscr|emailscr)'))
    async def mailscr_cmd(event):
        user_id = event.sender_id
        chat_id = event.chat_id
        
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await app.send_message(chat_id, BAN_REPLY)
            return

        args = event.message.text.split()[1:]
        if len(args) < 2:
            await app.send_message(chat_id, "** Please provide a channel with amount ❌**")
            LOGGER.warning("Invalid command: Missing arguments")
            return

        channel_identifier = args[0]
        temporary_msg = None

        try:
            limit = int(args[1])
            LOGGER.info(f"Mail scraping limit set to: {limit}")
        except ValueError:
            await app.send_message(chat_id, "**Sorry Please Provide A Valid Amount❌**")
            LOGGER.warning("Invalid limit value provided")
            return

        max_lim = SUDO_MAILSCR_LIMIT if user_id in (OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]) else MAIL_SCR_LIMIT
        if limit > max_lim:
            await app.send_message(chat_id, f"**❌ Amount exceeds limit of {max_lim} ❌**")
            LOGGER.warning(f"Limit exceeded: {limit} > {max_lim}")
            return

        temporary_msg = await app.send_message(chat_id, "**Checking Username...**")
        
        chat, channel_name, temporary_msg = await get_mail_channel_entity(channel_identifier, chat_id, temporary_msg)
        if not chat and not channel_name:
            return

        try:
            await asyncio.sleep(1.5)
            if temporary_msg:
                await temporary_msg.edit("**Scraping In Progress**")

            scrapped_results = await scrape_mail_messages(user, chat, limit)
            if not scrapped_results:
                if temporary_msg:
                    await temporary_msg.edit("**❌ No Email and Password Combinations were found**")
                return
                
            unique_messages, duplicates_removed = remove_mail_duplicates(scrapped_results)
            unique_messages = unique_messages[:limit]
            await send_mail_results(app, chat_id, unique_messages, duplicates_removed, channel_name, temporary_msg=temporary_msg)
            
        except Exception as e:
            if temporary_msg:
                await temporary_msg.edit(f"**Hey Bro! 🥲 Error during scraping ❌**")
            else:
                await app.send_message(chat_id, f"**Hey Bro! 🥲 Error during scraping ❌**")
            LOGGER.error(f"Failed to scrape channel: {e}")
            return
