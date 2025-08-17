import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button
from telethon.tl.types import User, Channel, Chat
from telethon.tl.functions.messages import UpdatePinnedMessageRequest
from telethon.errors import (
    ChatWriteForbiddenError,
    UserIsBlockedError,
    UserDeactivatedError,
    FloodWaitError,
    PeerIdInvalidError
)
from config import (
    OWNER_ID,
    UPDATE_CHANNEL_URL,
    COMMAND_PREFIX,
    DEVELOPER_USER_ID
)
from core import auth_admins, user_activity_collection
from utils import LOGGER

async def update_user_activity(user_id: int, chat_id: int = None, is_group: bool = False) -> None:
    try:
        now = datetime.utcnow()
        
        user_update_data = {
            "$set": {
                "user_id": user_id,
                "last_activity": now,
                "is_group": False
            },
            "$inc": {"activity_count": 1}
        }
        await user_activity_collection.update_one(
            {"user_id": user_id, "is_group": False}, 
            user_update_data, 
            upsert=True
        )
        LOGGER.debug(f"Updated user activity for user_id {user_id}")
        
        if is_group and chat_id and chat_id != user_id:
            group_update_data = {
                "$set": {
                    "user_id": chat_id,
                    "last_activity": now,
                    "is_group": True
                },
                "$inc": {"activity_count": 1}
            }
            await user_activity_collection.update_one(
                {"user_id": chat_id, "is_group": True}, 
                group_update_data, 
                upsert=True
            )
            LOGGER.debug(f"Updated group activity for chat_id {chat_id}")
            
    except Exception as e:
        LOGGER.error(f"Error updating user activity for user_id {user_id}, chat_id {chat_id}: {str(e)}")

async def is_admin(user_id: int) -> bool:
    try:
        auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        return user_id == OWNER_ID or user_id in [admin["user_id"] for admin in auth_admins_data]
    except Exception as e:
        LOGGER.error(f"Error checking admin status for user_id {user_id}: {str(e)}")
        return False

def get_command_from_text(text: str) -> tuple:
    if not text:
        return None, []
    
    parts = text.split()
    if not parts:
        return None, []
    
    command = parts[0]
    for prefix in COMMAND_PREFIX + [""]:
        if command.startswith(prefix):
            command = command[len(prefix):]
            break
    
    return command.lower(), parts[1:] if len(parts) > 1 else []

async def pin_message_safely(client: TelegramClient, chat_id: int, message_id: int):
    try:
        await client.pin_message(chat_id, message_id)
    except Exception as pin_error:
        LOGGER.warning(f"Could not pin message {message_id} in {chat_id}: {pin_error}")

async def broadcast_handler(event) -> None:
    if not event.sender or not event.chat:
        LOGGER.error("Invalid user or chat information for broadcast command")
        return

    user_id = event.sender_id
    if not await is_admin(user_id):
        LOGGER.info(f"Unauthorized broadcast attempt by user_id {user_id}")
        return

    command, args = get_command_from_text(event.raw_text)
    is_broadcast = command in ["broadcast", "b"]
    LOGGER.info(f"{'Broadcast' if is_broadcast else 'Send'} initiated by user_id {user_id}")

    if event.is_reply:
        reply_msg = await event.get_reply_message()
        if (reply_msg.text or reply_msg.photo or reply_msg.video or 
            reply_msg.audio or reply_msg.document):
            await process_broadcast(event.client, reply_msg, is_broadcast, event.chat_id)
    elif is_broadcast and args:
        await process_broadcast(event.client, " ".join(args), is_broadcast, event.chat_id)
    else:
        action = "broadcast" if is_broadcast else "send"
        await event.respond(f"**Please send a message to {action}.**", parse_mode='md')
        
        waiting_for_callback = True
        
        async def callback(callback_event):
            nonlocal waiting_for_callback
            if (callback_event.sender_id == user_id and 
                callback_event.chat_id == event.chat_id and
                waiting_for_callback):
                waiting_for_callback = False
                if not (callback_event.text or callback_event.photo or 
                       callback_event.video or callback_event.audio or 
                       callback_event.document):
                    await callback_event.respond(
                        "**Send a valid text, photo, video, audio, or document ❌**",
                        parse_mode='md'
                    )
                    waiting_for_callback = True
                    return
                await process_broadcast(event.client, callback_event, is_broadcast, callback_event.chat_id)
                event.client.remove_event_handler(callback)
        
        event.client.add_event_handler(
            callback,
            events.NewMessage(chats=event.chat_id, from_users=user_id)
        )

async def process_broadcast(client: TelegramClient, content, is_broadcast: bool = True, chat_id: int = None) -> None:
    try:
        if isinstance(content, str):
            broadcast_text = content
            broadcast_msg = None
        else:
            broadcast_text = None
            broadcast_msg = content

        LOGGER.info(f"Processing {'broadcast' if is_broadcast else 'forward'}")
        processing_msg = await client.send_message(
            chat_id, "**Broadcasting Your Message To Users...**", parse_mode='md'
        )

        bot_me = await client.get_me()
        bot_id = bot_me.id

        chats = await user_activity_collection.find({}, {"user_id": 1, "is_group": 1}).to_list(None)
        user_ids = [chat["user_id"] for chat in chats if not chat.get("is_group", False) and chat["user_id"] != bot_id]
        group_ids = [chat["user_id"] for chat in chats if chat.get("is_group", False) and chat["user_id"] != bot_id]
        LOGGER.info(f"Found {len(user_ids)} users and {len(group_ids)} groups to broadcast to")

        successful_users, blocked_users, successful_groups, failed_groups = 0, 0, 0, 0
        start_time = datetime.now()
        keyboard = [Button.url("Updates Channel", UPDATE_CHANNEL_URL)]

        all_chat_ids = user_ids + group_ids
        LOGGER.debug(f"Starting broadcast to {len(all_chat_ids)} chats")

        async def send_to_chat(target_chat_id: int) -> tuple:
            try:
                sent_msg = None
                
                if broadcast_text:
                    sent_msg = await client.send_message(
                        target_chat_id, broadcast_text, buttons=keyboard
                    )
                            
                elif broadcast_msg:
                    if is_broadcast:
                        if not (broadcast_msg.text or broadcast_msg.photo or 
                               broadcast_msg.video or broadcast_msg.audio or 
                               broadcast_msg.document):
                            raise ValueError("Unsupported message type")
                        
                        if broadcast_msg.text:
                            sent_msg = await client.send_message(
                                target_chat_id, broadcast_msg.text, buttons=keyboard
                            )
                        elif broadcast_msg.photo:
                            sent_msg = await client.send_file(
                                target_chat_id, broadcast_msg.photo, 
                                caption=broadcast_msg.text or "", buttons=keyboard
                            )
                        elif broadcast_msg.video:
                            sent_msg = await client.send_file(
                                target_chat_id, broadcast_msg.video,
                                caption=broadcast_msg.text or "", buttons=keyboard
                            )
                        elif broadcast_msg.audio:
                            sent_msg = await client.send_file(
                                target_chat_id, broadcast_msg.audio,
                                caption=broadcast_msg.text or "", buttons=keyboard
                            )
                        elif broadcast_msg.document:
                            sent_msg = await client.send_file(
                                target_chat_id, broadcast_msg.document,
                                caption=broadcast_msg.text or "", buttons=keyboard
                            )
                    else:
                        sent_msg = await client.forward_messages(
                            target_chat_id, broadcast_msg
                        )
                
                if sent_msg and target_chat_id in group_ids:
                    await pin_message_safely(client, target_chat_id, sent_msg.id)
                
                if target_chat_id in user_ids:
                    return ("user", "success")
                else:
                    return ("group", "success")
                    
            except FloodWaitError as e:
                LOGGER.warning(f"FloodWait for chat_id {target_chat_id}: Waiting {e.seconds}s")
                await asyncio.sleep(e.seconds)
                return await send_to_chat(target_chat_id)
            except UserIsBlockedError:
                LOGGER.error(f"User blocked the bot: chat_id {target_chat_id}")
                if target_chat_id in user_ids:
                    return ("user", "blocked")
                else:
                    return ("group", "failed")
            except (UserDeactivatedError, ChatWriteForbiddenError, PeerIdInvalidError) as e:
                LOGGER.error(f"Failed to send to chat_id {target_chat_id}: {str(e)}")
                if target_chat_id in user_ids:
                    return ("user", "blocked")
                else:
                    return ("group", "failed")
            except Exception as e:
                LOGGER.error(f"Error sending to chat_id {target_chat_id}: {str(e)}")
                if target_chat_id in user_ids:
                    return ("user", "blocked")
                else:
                    return ("group", "failed")

        results = await asyncio.gather(*[send_to_chat(chat_id) for chat_id in all_chat_ids], return_exceptions=True)

        for result in results:
            if isinstance(result, tuple):
                chat_type, status = result
                if chat_type == "user":
                    if status == "success":
                        successful_users += 1
                    elif status == "blocked":
                        blocked_users += 1
                elif chat_type == "group":
                    if status == "success":
                        successful_groups += 1
                    elif status == "failed":
                        failed_groups += 1

        time_diff = (datetime.now() - start_time).seconds
        await processing_msg.delete()

        total_chats = successful_users + successful_groups
        summary_msg = await client.send_message(
            chat_id,
            f"**Smart Broadcast Successful✅**\n"
            f"**━━━━━━━━━━━━━━━━━**\n"
            f"**⊗ To Users: ** **{successful_users} Users**\n"
            f"**⊗ Blocked Users: ** **{blocked_users} Users**\n"
            f"**⊗ To Groups: ** **{successful_groups} Groups**\n"
            f"**⊗ Failed Groups: ** **{failed_groups} Groups**\n"
            f"**⊗ Total Chats: ** **{total_chats} Chats**\n"
            f"**━━━━━━━━━━━━━━━━━**\n"
            f" **Smooth Telecast → Activated ✅**",
            parse_mode='md',
            buttons=keyboard
        )
        
        try:
            entity = await client.get_entity(chat_id)
            if isinstance(entity, (Channel, Chat)):
                await pin_message_safely(client, chat_id, summary_msg.id)
        except Exception as e:
            LOGGER.warning(f"Could not pin summary message: {e}")

        LOGGER.info(f"{'Broadcast' if is_broadcast else 'Forward'} completed: {successful_users} users, {successful_groups} groups, "
                    f"{blocked_users} blocked users, {failed_groups} failed groups")
    except Exception as e:
        LOGGER.error(f"Error in {'broadcast' if is_broadcast else 'forward'}: {str(e)}")
        await client.send_message(chat_id, "**Sorry Broadcast Send Failed ❌**", parse_mode='md')

async def stats_handler(event) -> None:
    if not event.sender or not event.chat:
        LOGGER.error("Invalid user or chat for stats command")
        return

    user_id = event.sender_id
    if not await is_admin(user_id):
        LOGGER.info(f"Unauthorized stats attempt by user_id {user_id}")
        return

    LOGGER.info(f"Stats command by user_id {user_id}")
    try:
        now = datetime.utcnow()
        daily_users = await user_activity_collection.count_documents({
            "is_group": False, 
            "last_activity": {"$gte": now - timedelta(days=1)}
        })
        weekly_users = await user_activity_collection.count_documents({
            "is_group": False, 
            "last_activity": {"$gte": now - timedelta(weeks=1)}
        })
        monthly_users = await user_activity_collection.count_documents({
            "is_group": False, 
            "last_activity": {"$gte": now - timedelta(days=30)}
        })
        yearly_users = await user_activity_collection.count_documents({
            "is_group": False, 
            "last_activity": {"$gte": now - timedelta(days=365)}
        })
        total_users = await user_activity_collection.count_documents({"is_group": False})
        total_groups = await user_activity_collection.count_documents({"is_group": True})

        stats_text = (
            f"**Smart Bot Status ⇾ Report ✅**\n"
            f"**━━━━━━━━━━━━━━━━**\n"
            f"**Users & Groups Engagements:**\n"
            f"**1 Day:** {daily_users} users were active\n"
            f"**1 Week:** {weekly_users} users were active\n"
            f"**1 Month:** {monthly_users} users were active\n"
            f"**1 Year:** {yearly_users} users were active\n"
            f"**Total Connected Groups:** {total_groups}\n"
            f"**━━━━━━━━━━━━━━━━**\n"
            f"**Total Smart Tools Users:** {total_users} ✅"
        )
        keyboard = [Button.url("Updates Channel", UPDATE_CHANNEL_URL)]
        await event.respond(stats_text, parse_mode='md', buttons=keyboard)
        LOGGER.info("Stats command completed")
    except Exception as e:
        LOGGER.error(f"Error in stats: {str(e)}")
        await event.respond("**Sorry Database Client Unavailable ❌**", parse_mode='md')

async def group_added_handler(event) -> None:
    try:
        if not hasattr(event, 'user_added') or not event.user_added:
            return
            
        bot_me = await event.client.get_me()
        if event.user_id == bot_me.id:
            chat_id = event.chat_id
            await update_user_activity(bot_me.id, chat_id, is_group=True)
            await event.respond(
                "**Thank you for adding me to this group!**",
                parse_mode='md'
            )
            LOGGER.info(f"Bot added to group {chat_id}")
    except Exception as e:
        LOGGER.error(f"Error in group_added_handler for chat_id {event.chat_id}: {str(e)}")

async def group_removed_handler(event) -> None:
    try:
        bot_me = await event.client.get_me()
        if (hasattr(event, 'user_id') and event.user_id == bot_me.id and
            (hasattr(event, 'kicked') and event.kicked or 
             hasattr(event, 'left') and event.left)):
            chat_id = event.chat_id
            await user_activity_collection.delete_one({"user_id": chat_id, "is_group": True})
            LOGGER.info(f"Bot removed/banned from group {chat_id}, removed from database")
    except Exception as e:
        LOGGER.error(f"Error in group_removed_handler for chat_id {getattr(event, 'chat_id', 'unknown')}: {str(e)}")

async def update_user_activity_handler(event) -> None:
    try:
        if event.sender and event.chat:
            user_id = event.sender_id
            chat_id = event.chat_id
            is_group = event.is_group or event.is_channel
            
            await update_user_activity(user_id, chat_id, is_group)
            
            LOGGER.debug(f"Activity updated for user {user_id} in chat {chat_id} (is_group: {is_group})")
            
    except Exception as e:
        LOGGER.error(f"Error in update_user_activity_handler for message_id {getattr(event, 'id', 'unknown')}: {str(e)}")

def create_command_pattern(commands: list) -> str:
    escaped_prefixes = [prefix.replace("|", r"\|").replace(".", r"\.").replace("(", r"\(").replace(")", r"\)").replace("[", r"\[").replace("]", r"\]").replace("*", r"\*").replace("+", r"\+").replace("?", r"\?").replace("^", r"\^").replace("$", r"\$").replace("{", r"\{").replace("}", r"\}") for prefix in COMMAND_PREFIX]
    prefix_pattern = "[" + "".join(escaped_prefixes) + "]"
    command_pattern = "|".join(commands)
    return f"^{prefix_pattern}?({command_pattern})(\\s|$)"

def setup_admin_handler(app: TelegramClient) -> None:
    broadcast_pattern = create_command_pattern(["broadcast", "b", "send", "s"])
    stats_pattern = create_command_pattern(["stats", "report", "status"])
    
    @app.on(events.NewMessage(pattern=broadcast_pattern, func=lambda e: e.is_private or e.is_group))
    async def broadcast_command(event):
        await broadcast_handler(event)
    
    @app.on(events.NewMessage(pattern=stats_pattern, func=lambda e: e.is_private or e.is_group))
    async def stats_command(event):
        await stats_handler(event)
    
    @app.on(events.NewMessage(func=lambda e: (e.is_private or e.is_group) and not e.via_bot_id))
    async def activity_tracker(event):
        await update_user_activity_handler(event)
    
    @app.on(events.ChatAction)
    async def chat_action_handler(event):
        if event.user_added or event.user_joined:
            await group_added_handler(event)
        elif event.user_kicked or event.user_left:
            await group_removed_handler(event)
    
    LOGGER.info("Admin handlers setup completed for Telethon client")
