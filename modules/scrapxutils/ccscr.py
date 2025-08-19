#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev 
import re
import os
import asyncio
import aiofiles
from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest
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
    SUDO_CCSCR_LIMIT,
    OWNER_ID,
    CC_SCRAPPER_LIMIT,
    COMMAND_PREFIX,
    MULTI_CCSCR_LIMIT,
    BAN_REPLY
)
from utils import LOGGER
from core import banned_users

async def scrape_messages(client, channel, limit, start_number=None, bank_name=None):
    messages = []
    pattern = r'\d{16}\D*\d{2}\D*\d{2,4}\D*\d{3,4}'
    LOGGER.info(f"Starting to scrape messages from {channel} with limit {limit}")
    
    try:
        channel_entity = channel
        if hasattr(channel, 'id'):
            channel_entity = channel.id
        elif isinstance(channel, str):
            channel_entity = channel
            
        message_count = 0
        found_cards = 0
        
        async for message in client.iter_messages(channel_entity, limit=None):
            if found_cards >= limit:
                break
                
            message_count += 1
            
            text = message.text
            if not text and hasattr(message, 'media') and message.media:
                text = getattr(message.media, 'caption', None)
            
            if text:
                if bank_name and bank_name.lower() not in text.lower():
                    continue
                    
                matched_messages = re.findall(pattern, text)
                if matched_messages:
                    for matched_message in matched_messages:
                        if found_cards >= limit:
                            break
                            
                        extracted_values = re.findall(r'\d+', matched_message)
                        if len(extracted_values) == 4:
                            card_number, mo, year, cvv = extracted_values
                            if len(year) > 2:
                                year = year[-2:]
                            
                            if start_number:
                                if card_number.startswith(start_number[:6]):
                                    messages.append(f"{card_number}|{mo}|{year}|{cvv}")
                                    found_cards += 1
                            else:
                                messages.append(f"{card_number}|{mo}|{year}|{cvv}")
                                found_cards += 1
                    
        LOGGER.info(f"Checked {message_count} messages, found {len(messages)} credit cards from {channel}")
        
    except Exception as e:
        LOGGER.error(f"Error while scraping messages: {e}")
        
    return messages

def remove_duplicates(messages):
    unique_messages = list(set(messages))
    duplicates_removed = len(messages) - len(unique_messages)
    LOGGER.info(f"Removed {duplicates_removed} duplicates")
    return unique_messages, duplicates_removed

async def send_results(client, chat_id, unique_messages, duplicates_removed, source_name, bin_filter=None, bank_filter=None, temporary_msg=None):
    if unique_messages:
        file_name = f"x{len(unique_messages)}_{source_name.replace(' ', '_')}.txt"
        async with aiofiles.open(file_name, mode='w') as f:
            await f.write("\n".join(unique_messages))
        async with aiofiles.open(file_name, mode='rb') as f:
            caption = (
                f"**CC Scrapped Successful ✅**\n"
                f"**━━━━━━━━━━━━━━━━**\n"
                f"**Source:** `{source_name} 🌐`\n"
                f"**Amount:** `{len(unique_messages)} 📝`\n"
                f"**Duplicates Removed:** `{duplicates_removed} 🗑`\n"
            )
            if bin_filter:
                caption += f"**📝 BIN Filter:** `{bin_filter}`\n"
            if bank_filter:
                caption += f"**📝 Bank Filter:** `{bank_filter}`\n"
            caption += (
                f"**━━━━━━━━━━━━━━━━**\n"
                f"**✅ Card-Scrapped By: Smart Tool**\n"
            )
            if temporary_msg:
                await temporary_msg.delete()
            await client.send_file(chat_id, file_name, caption=caption)
        os.remove(file_name)
        LOGGER.info(f"Results sent successfully for {source_name}")
    else:
        if temporary_msg:
            await temporary_msg.edit("**Sorry Bro ❌ No Credit Card Found**")
        else:
            await client.send_message(chat_id, "**Sorry Bro ❌ No Credit Card Found**")
        LOGGER.info("No credit cards found")

async def get_user_link(message):
    if not message.sender:
        return '[Smart Tool](https://t.me/TheSmartDev)'
    else:
        user_first_name = message.sender.first_name
        user_last_name = message.sender.last_name or ""
        user_full_name = f"{user_first_name} {user_last_name}".strip()
        return f'[{user_full_name}](tg://user?id={message.sender_id})'

async def join_private_chat(invite_link, chat_id, temporary_msg=None):
    try:
        if invite_link.startswith("https://t.me/+"):
            invite_hash = invite_link.replace("https://t.me/+", "")
        elif invite_link.startswith("https://t.me/joinchat/"):
            invite_hash = invite_link.replace("https://t.me/joinchat/", "")
        else:
            invite_hash = invite_link
            
        from telethon.tl.functions.messages import ImportChatInviteRequest
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
                from telethon.tl.functions.messages import CheckChatInviteRequest
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

async def send_join_request(invite_link, chat_id):
    try:
        if invite_link.startswith("https://t.me/+"):
            invite_hash = invite_link.replace("https://t.me/+", "")
        elif invite_link.startswith("https://t.me/joinchat/"):
            invite_hash = invite_link.replace("https://t.me/joinchat/", "")
        else:
            invite_hash = invite_link
            
        from telethon.tl.functions.messages import ImportChatInviteRequest
        await user(ImportChatInviteRequest(invite_hash))
        LOGGER.info(f"Sent join request to chat: {invite_link}")
        return True
    except ChannelPrivateError:
        LOGGER.info(f"Join request sent to the chat: {invite_link}")
        return False
    except PeerIdInvalidError:
        LOGGER.error(f"Failed to send join request to chat {invite_link}: Invalid peer ID")
        return False
    except Exception as e:
        LOGGER.error(f"Unexpected error sending join request to chat {invite_link}: {e}")
        return False

async def get_channel_entity(channel_identifier, chat_id, temporary_msg=None):
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
            
            joined, chat = await join_private_chat(invite_link, chat_id, temporary_msg)
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
                
            chat = await user.get_entity(channel_username)
            channel_name = chat.title
            LOGGER.info(f"Got entity for public channel: {channel_name} (Username: {channel_username})")
            
    except Exception as e:
        LOGGER.error(f"Failed to get channel entity for {channel_identifier}: {e}")
        if temporary_msg:
            await temporary_msg.edit("**Hey Bro! 🥲 Failed to access channel ❌**")
        return None, None, temporary_msg
        
    return chat, channel_name, temporary_msg

def setup_ccscr_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(scr|ccscr|scrcc)'))
    async def scr_cmd(event):
        user_id = event.sender_id
        chat_id = event.chat_id
        
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await app.send_message(chat_id, BAN_REPLY)
            return

        args = event.message.text.split()[1:]
        if len(args) < 2:
            await app.send_message(chat_id, "**⚠️ Provide channel username and amount to scrape ❌**")
            LOGGER.warning("Invalid command: Missing arguments")
            return

        channel_identifier = args[0]
        temporary_msg = None

        try:
            limit = int(args[1])
            LOGGER.info(f"Scraping limit set to: {limit}")
        except ValueError:
            await app.send_message(chat_id, "**⚠️ Invalid limit value. Please provide a valid number ❌**")
            LOGGER.warning("Invalid limit value provided")
            return

        start_number = None
        bank_name = None
        bin_filter = None
        
        if len(args) > 2:
            if args[2].isdigit():
                start_number = args[2]
                bin_filter = args[2][:6]
                LOGGER.info(f"BIN filter applied: {bin_filter}")
            else:
                bank_name = " ".join(args[2:])
                LOGGER.info(f"Bank filter applied: {bank_name}")

        max_lim = SUDO_CCSCR_LIMIT if user_id in (OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]) else CC_SCRAPPER_LIMIT
        if limit > max_lim:
            await app.send_message(chat_id, f"**Sorry Bro! Amount over Max limit is {max_lim} ❌**")
            LOGGER.warning(f"Limit exceeded: {limit} > {max_lim}")
            return

        temporary_msg = await app.send_message(chat_id, "**Checking The Username...✨**")
        
        chat, channel_name, temporary_msg = await get_channel_entity(channel_identifier, chat_id, temporary_msg)
        if not chat and not channel_name:
            return

        try:
            await asyncio.sleep(1.5)
            if temporary_msg:
                await temporary_msg.edit("**Scraping In Progress✨**")

            scrapped_results = await scrape_messages(user, chat, limit, start_number=start_number, bank_name=bank_name)
            unique_messages, duplicates_removed = remove_duplicates(scrapped_results)
            await send_results(app, chat_id, unique_messages, duplicates_removed, channel_name, bin_filter=bin_filter, bank_filter=bank_name, temporary_msg=temporary_msg)
            
        except Exception as e:
            if temporary_msg:
                await temporary_msg.edit(f"**Hey Bro! 🥲 Error during scraping ❌**")
            else:
                await app.send_message(chat_id, f"**Hey Bro! 🥲 Error during scraping ❌**")
            LOGGER.error(f"Failed to scrape channel: {e}")
            return

    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(mc|multiscr|mscr)'))
    async def mc_cmd(event):
        user_id = event.sender_id
        chat_id = event.chat_id
        
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await app.send_message(chat_id, BAN_REPLY)
            return

        args = event.message.text.split()[1:]
        if len(args) < 2:
            await app.send_message(chat_id, "**⚠️ Provide at least one channel username**")
            LOGGER.warning("Invalid command: Missing arguments")
            return

        channel_identifiers = args[:-1]
        try:
            limit = int(args[-1])
        except ValueError:
            await app.send_message(chat_id, "**⚠️ Invalid limit value. Please provide a valid number ❌**")
            LOGGER.warning("Invalid limit value provided")
            return

        max_lim = SUDO_CCSCR_LIMIT if user_id in (OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]) else MULTI_CCSCR_LIMIT
        if limit > max_lim:
            await app.send_message(chat_id, f"**Sorry Bro! Amount over Max limit is {max_lim} ❌**")
            LOGGER.warning(f"Limit exceeded: {limit} > {max_lim}")
            return

        temporary_msg = await app.send_message(chat_id, "**Scraping In Progress✨**")
        all_messages = []
        tasks = []
        
        for channel_identifier in channel_identifiers:
            tasks.append(scrape_messages_task(channel_identifier, limit, app, chat_id))

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_messages.extend(result)
                else:
                    LOGGER.error(f"Task returned exception: {result}")

            unique_messages, duplicates_removed = remove_duplicates(all_messages)
            unique_messages = unique_messages[:limit]
            await send_results(app, chat_id, unique_messages, duplicates_removed, "Multiple Chats", temporary_msg=temporary_msg)
            
        except Exception as e:
            await temporary_msg.edit("**Hey Bro! 🥲 Error occurred during scraping ❌**")
            LOGGER.error(f"Failed to scrape multiple channels: {e}")
            return

async def scrape_messages_task(channel_identifier, limit, bot_client, chat_id):
    try:
        chat, channel_name, _ = await get_channel_entity(channel_identifier, chat_id)
        if not chat:
            LOGGER.error(f"Failed to get entity for {channel_identifier}")
            return []
            
        return await scrape_messages(user, chat, limit)
        
    except Exception as e:
        LOGGER.error(f"Failed to scrape from {channel_identifier}: {e}")
        return []