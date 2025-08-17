#Copyright @ISmartCoder
#Updates Channel https://t.me/TheSmartDev
import asyncio
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.handlers import (
    MessageHandler,
    ChatMemberUpdatedHandler
)
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    ChatMemberUpdated
)
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import (
    ChatWriteForbidden,
    UserIsBlocked,
    InputUserDeactivated,
    FloodWait,
    PeerIdInvalid
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

async def broadcast_handler(client: Client, message: Message) -> None:
    if not message.from_user or not message.chat:
        LOGGER.error("Invalid user or chat information for broadcast command")
        return

    user_id = message.from_user.id
    if not await is_admin(user_id):
        LOGGER.info(f"Unauthorized broadcast attempt by user_id {user_id}")
        return

    is_broadcast = message.command[0].lower() in ["broadcast", "b"]
    LOGGER.info(f"{'Broadcast' if is_broadcast else 'Send'} initiated by user_id {user_id}")

    if message.reply_to_message and (
        message.reply_to_message.text or message.reply_to_message.photo or
        message.reply_to_message.video or message.reply_to_message.audio or
        message.reply_to_message.document
    ):
        await process_broadcast(client, message.reply_to_message, is_broadcast, message.chat.id)
    elif is_broadcast and len(message.command) > 1:
        await process_broadcast(client, " ".join(message.command[1:]), is_broadcast, message.chat.id)
    else:
        action = "broadcast" if is_broadcast else "send"
        await client.send_message(
            message.chat.id, f"**Please send a message to {action}.**", parse_mode=ParseMode.MARKDOWN
        )
        async def callback(client: Client, msg: Message):
            if msg.from_user and msg.from_user.id == user_id and msg.chat.id == message.chat.id:
                if not (msg.text or msg.photo or msg.video or msg.audio or msg.document):
                    await client.send_message(
                        msg.chat.id, "**Send a valid text, photo, video, audio, or document ❌ **",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                await process_broadcast(client, msg, is_broadcast, msg.chat.id)
                client.remove_handler(handler, group=2)
        handler = MessageHandler(callback, filters.user(user_id) & filters.chat(message.chat.id))
        client.add_handler(handler, group=2)

async def process_broadcast(client: Client, content, is_broadcast: bool = True, chat_id: int = None) -> None:
    try:
        if isinstance(content, str):
            broadcast_text = content
            broadcast_msg = None
        elif isinstance(content, Message):
            broadcast_text = None
            broadcast_msg = content
        else:
            raise ValueError("Invalid content type")

        LOGGER.info(f"Processing {'broadcast' if is_broadcast else 'forward'}")
        processing_msg = await client.send_message(
            chat_id, f"**Broadcating Your Message To Users...**",
            parse_mode=ParseMode.MARKDOWN
        )

        bot_info = await client.get_me()
        bot_id = bot_info.id

        chats = await user_activity_collection.find({}, {"user_id": 1, "is_group": 1}).to_list(None)
        user_ids = [chat["user_id"] for chat in chats if not chat.get("is_group", False) and chat["user_id"] != bot_id]
        group_ids = [chat["user_id"] for chat in chats if chat.get("is_group", False) and chat["user_id"] != bot_id]
        LOGGER.info(f"Found {len(user_ids)} users and {len(group_ids)} groups to broadcast to")

        successful_users, blocked_users, successful_groups, failed_groups = 0, 0, 0, 0
        start_time = datetime.now()
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Updates Channel", url=UPDATE_CHANNEL_URL)]])

        all_chat_ids = user_ids + group_ids
        LOGGER.debug(f"Starting broadcast to {len(all_chat_ids)} chats")

        async def send_to_chat(target_chat_id: int) -> tuple:
            try:
                if broadcast_text:
                    sent_msg = await client.send_message(target_chat_id, broadcast_text, reply_markup=keyboard)
                    if target_chat_id in group_ids:
                        chat = await client.get_chat(target_chat_id)
                        if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                            await client.pin_chat_message(target_chat_id, sent_msg.id)
                elif broadcast_msg:
                    if is_broadcast:
                        if not (broadcast_msg.text or broadcast_msg.photo or broadcast_msg.video or
                                broadcast_msg.audio or broadcast_msg.document):
                            raise ValueError("Unsupported message type")
                        sent_msg = await client.copy_message(
                            target_chat_id, broadcast_msg.chat.id, broadcast_msg.id, reply_markup=keyboard
                        )
                        if target_chat_id in group_ids:
                            chat = await client.get_chat(target_chat_id)
                            if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                                await client.pin_chat_message(target_chat_id, sent_msg.id)
                    else:
                        await client.forward_messages(target_chat_id, broadcast_msg.chat.id, broadcast_msg.id)
                if target_chat_id in user_ids:
                    return ("user", "success")
                else:
                    return ("group", "success")
            except FloodWait as e:
                LOGGER.warning(f"FloodWait for chat_id {target_chat_id}: Waiting {e.value}s")
                await asyncio.sleep(e.value)
                return await send_to_chat(target_chat_id)
            except UserIsBlocked:
                LOGGER.error(f"User blocked the bot: chat_id {target_chat_id}")
                if target_chat_id in user_ids:
                    return ("user", "blocked")
                else:
                    return ("group", "failed")
            except (InputUserDeactivated, ChatWriteForbidden, PeerIdInvalid) as e:
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
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        chat = await client.get_chat(chat_id)
        if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await client.pin_chat_message(chat_id, summary_msg.id)

        LOGGER.info(f"{'Broadcast' if is_broadcast else 'Forward'} completed: {successful_users} users, {successful_groups} groups, "
                    f"{blocked_users} blocked users, {failed_groups} failed groups")
    except Exception as e:
        LOGGER.error(f"Error in {'broadcast' if is_broadcast else 'forward'}: {str(e)}")
        await client.send_message(chat_id, "**Sorry Broadcast Send Failed ❌**", parse_mode=ParseMode.MARKDOWN)

async def stats_handler(client: Client, message: Message) -> None:
    if not message.from_user or not message.chat:
        LOGGER.error("Invalid user or chat for stats command")
        return

    user_id = message.from_user.id
    if not await is_admin(user_id):
        LOGGER.info(f"Unauthorized stats attempt by user_id {user_id}")
        return

    LOGGER.info(f"Stats command by user_id {user_id}")
    try:
        now = datetime.utcnow()
        daily_users = await user_activity_collection.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(days=1)}})
        weekly_users = await user_activity_collection.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(weeks=1)}})
        monthly_users = await user_activity_collection.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(days=30)}})
        yearly_users = await user_activity_collection.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(days=365)}})
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
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Updates Channel", url=UPDATE_CHANNEL_URL)]])
        await client.send_message(
            message.chat.id, stats_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
        )
        LOGGER.info("Stats command completed")
    except Exception as e:
        LOGGER.error(f"Error in stats: {str(e)}")
        await client.send_message(message.chat.id, "**Sorry Database Client Unavailable ❌**", parse_mode=ParseMode.MARKDOWN)

async def group_added_handler(client: Client, message: Message) -> None:
    try:
        if not message.new_chat_members or not message.chat:
            return
        for member in message.new_chat_members:
            if member.is_self:
                chat_id = message.chat.id
                await update_user_activity(member.id, chat_id, is_group=True)
                await client.send_message(
                    chat_id,
                    "**Thank you for adding me to this group!**",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_to_message_id=message.id
                )
                LOGGER.info(f"Bot added to group {chat_id}")
    except Exception as e:
        LOGGER.error(f"Error in group_added_handler for chat_id {message.chat.id}: {str(e)}")

async def group_removed_handler(client: Client, member_update: ChatMemberUpdated) -> None:
    try:
        if (member_update.old_chat_member and member_update.old_chat_member.status in ["member", "administrator"] and
            member_update.new_chat_member and member_update.new_chat_member.status in ["banned", "left"] and
            member_update.new_chat_member.user.is_self):
            chat_id = member_update.chat.id
            await user_activity_collection.delete_one({"user_id": chat_id, "is_group": True})
            LOGGER.info(f"Bot removed/banned from group {chat_id}, removed from database")
    except Exception as e:
        LOGGER.error(f"Error in group_removed_handler for chat_id {member_update.chat.id}: {str(e)}")

async def update_user_activity_handler(client: Client, message: Message) -> None:
    try:
        if (message.from_user and message.chat and 
            message.chat.type in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]):
            
            user_id = message.from_user.id
            chat_id = message.chat.id
            is_group = message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
            
            await update_user_activity(user_id, chat_id, is_group)
            
            LOGGER.debug(f"Activity updated for user {user_id} in chat {chat_id} (is_group: {is_group})")
            
    except Exception as e:
        LOGGER.error(f"Error in update_user_activity_handler for message_id {getattr(message, 'id', 'unknown')}: {str(e)}")

def setup_admin_handler(app: Client) -> None:
    prefixes = COMMAND_PREFIX + [""]
    
    app.add_handler(
        MessageHandler(
            broadcast_handler,
            (filters.command(["broadcast", "b", "send", "s"], prefixes=prefixes) & 
             (filters.private | filters.group))
        ),
        group=2
    )
    
    app.add_handler(
        MessageHandler(
            stats_handler,
            (filters.command(["stats", "report", "status"], prefixes=prefixes) & 
             (filters.private | filters.group))
        ),
        group=2
    )
    
    app.add_handler(
        MessageHandler(
            update_user_activity_handler,
            (filters.all & 
             (filters.private | filters.group) & 
             ~filters.bot)
        ),
        group=1
    )
    
    app.add_handler(
        MessageHandler(
            group_added_handler,
            filters.group & filters.new_chat_members
        ),
        group=2
    )
    
    app.add_handler(
        ChatMemberUpdatedHandler(
            group_removed_handler,
            filters.group
        ),
        group=2
    )
