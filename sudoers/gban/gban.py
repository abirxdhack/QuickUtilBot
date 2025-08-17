import logging
import traceback
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.custom import Button
from telethon.tl.types import KeyboardButtonUserProfile
from telethon.types import ReplyInlineMarkup, KeyboardButtonRow, InputKeyboardButtonUserProfile
from telethon.utils import get_display_name
from telethon.errors import UserIdInvalidError, UsernameInvalidError, PeerIdInvalidError, FloodWaitError
from config import OWNER_ID, COMMAND_PREFIX
from core import auth_admins, banned_users
from utils import LOGGER

logger = LOGGER

async def safe_send_message(client, entity, text, buttons=None):
    try:
        if entity and isinstance(entity, (int, str)):
            return await client.send_message(
                entity=entity,
                message=text,
                parse_mode='markdown',
                buttons=buttons,
                link_preview=False
            )
    except Exception as e:
        logger.error(f"Failed to send message to {entity}: {e}\n{traceback.format_exc()}")
    return None

def setup_gban_handler(app: TelegramClient):
    async def get_auth_admins():
        try:
            admins = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
            return [admin["user_id"] for admin in admins]
        except Exception as e:
            logger.error(f"Error fetching admins: {e}\n{traceback.format_exc()}")
            return []

    async def resolve_user(client: TelegramClient, identifier: str, event):
        logger.info(f"Attempting to resolve user: {identifier}")
        if not identifier:
            await event.respond(
                message="**Invalid user identifier provided ❌**",
                parse_mode='markdown'
            )
            logger.error("No identifier provided for user resolution")
            return None, None, None
        try:
            if identifier.startswith("@"):
                user = await client.get_entity(identifier)
            else:
                user = await client.get_entity(int(identifier))
            full_name = user.first_name or str(user.id)
            username = f"@{user.username}" if user.username else "None"
            logger.info(f"Resolved user {identifier} to ID {user.id}")
            return user.id, full_name, username
        except (UserIdInvalidError, UsernameInvalidError, PeerIdInvalidError, FloodWaitError, ValueError, Exception) as e:
            logger.error(f"Error resolving user {identifier}: {e}\n{traceback.format_exc()}")
            await event.respond(
                message=f"**Failed to resolve user {identifier}: {str(e)} ❌**",
                parse_mode='markdown'
            )
            return None, None, None

    @app.on(events.NewMessage(pattern=f'({"|".join(COMMAND_PREFIX)})ban(?!list)'))
    async def ban_command(event):
        user_id = event.sender_id
        logger.info(f"/ban command triggered by user {user_id} with input: {event.raw_text}")
        auth_admins_data = await get_auth_admins()
        if user_id != OWNER_ID and user_id not in auth_admins_data:
            logger.info(f"Unauthorized /ban attempt by user {user_id}")
            return
        if len(event.raw_text.split()) < 2 and not event.message.is_reply:
            await safe_send_message(event.client, event.chat_id, "**Please Provide A Valid User To Ban ❌**")
            logger.info("No user identifier or reply provided for /ban")
            return
        target_user = None
        target_identifier = None
        reason = "undefined"
        if event.message.is_reply and event.message.reply_to_message.sender_id:
            try:
                target_user = await event.client.get_entity(event.message.reply_to_message.sender_id)
                target_identifier = target_user.id
                if len(event.raw_text.split()) >= 2:
                    reason = " ".join(event.raw_text.split()[1:])
            except Exception as e:
                logger.error(f"Error resolving reply-to user: {e}\n{traceback.format_exc()}")
                await safe_send_message(event.client, event.chat_id, f"**Failed to resolve reply-to user: {str(e)} ❌**")
                return
        else:
            target_identifier = event.raw_text.split()[1].strip()
            if len(event.raw_text.split()) >= 3:
                reason = " ".join(event.raw_text.split()[2:])
            logger.info(f"Resolving user {target_identifier} for /ban")
            target_id, target_name, username = await resolve_user(event.client, target_identifier, event)
            if not target_id:
                logger.info(f"Failed to resolve user {target_identifier} for /ban")
                return
            target_user = await event.client.get_entity(target_id)
        if not target_user or not isinstance(target_user.id, int):
            await safe_send_message(event.client, event.chat_id, "**Sorry Failed To Ban User From Bot ❌**")
            logger.error(f"Invalid target_user: {target_user}")
            return
        target_id = target_user.id
        target_name = target_user.first_name or str(target_id)
        if target_id == OWNER_ID or target_id in auth_admins_data:
            await safe_send_message(event.client, event.chat_id, "**Lol I Can Not Ban My Admins ❌**")
            logger.info(f"Attempted to ban admin or owner {target_id}")
            return
        sent_message = await safe_send_message(event.client, event.chat_id, "**Banning User From Smart Tools**")
        try:
            if await banned_users.find_one({"user_id": target_id}):
                if sent_message:
                    await sent_message.edit(
                        text="**Sorry Failed To Ban User From Bot: Already Banned ❌**",
                        parse_mode='markdown'
                    )
                logger.info(f"User {target_id} already banned")
                return
        except Exception as e:
            if sent_message:
                await sent_message.edit(
                    text="**Sorry Failed To Ban User From Bot ❌**",
                    parse_mode='markdown'
                )
            logger.error(f"Error checking ban status for {target_id}: {e}\n{traceback.format_exc()}")
            return
        try:
            ban_date = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            await banned_users.insert_one({
                "user_id": target_id,
                "username": target_name,
                "ban_date": ban_date,
                "reason": reason
            })
        except Exception as e:
            if sent_message:
                await sent_message.edit(
                    text="**Sorry Failed To Ban User From Bot ❌**",
                    parse_mode='markdown'
                )
            logger.error(f"Error banning user {target_id}: {e}\n{traceback.format_exc()}")
            return
        ban_message = (
            "**❌ Sorry Bro You're Banned From Using Me**\n"
            "**━━━━━━━━━━━━━━━━━━━━━━**\n"
            "**You're Currently Banned From Using Me Or My Services.\n"
            "If you believe this was a mistake or want to appeal, \n"
            "please contact the admin. 🚨**\n"
            "**━━━━━━━━━━━━━━━━━━━━━━**\n"
            "**Note: NSFW Work Can Cause Forever Ban ✅**"
        )
        try:
            owner_entity = await event.client.get_entity(OWNER_ID)
            owner_name = get_display_name(owner_entity)
            reply_markup = ReplyInlineMarkup([
                KeyboardButtonRow([
                    InputKeyboardButtonUserProfile("Contact Owner 👨🏻‍💻", await event.client.get_input_entity(OWNER_ID))
                ])
            ])
        except Exception as e:
            logger.error(f"Error creating user profile button: {e}")
            reply_markup = [[Button.url("Contact Owner 👨🏻‍💻", f"tg://user?id={OWNER_ID}")]]
        await safe_send_message(event.client, target_id, ban_message, buttons=reply_markup)
        if sent_message:
            await sent_message.edit(
                text=f"**{target_name} [`{target_id}`] banned.**\n"
                     f"**Reason:** {reason}\n"
                     f"**Ban Date:** {ban_date}",
                parse_mode='markdown'
            )
            logger.info(f"Successfully banned user {target_id} with reason: {reason}")
        for admin_id in [OWNER_ID] + auth_admins_data:
            if admin_id != user_id and isinstance(admin_id, int):
                await safe_send_message(
                    event.client, admin_id,
                    f"**{target_name} [`{target_id}`] banned.**\n"
                    f"**Reason:** {reason}\n"
                    f"**Ban Date:** {ban_date}"
                )

    @app.on(events.NewMessage(pattern=f'({"|".join(COMMAND_PREFIX)})unban(?!list)'))
    async def unban_command(event):
        user_id = event.sender_id
        logger.info(f"/unban command triggered by user {user_id} with input: {event.raw_text}")
        auth_admins_data = await get_auth_admins()
        if user_id != OWNER_ID and user_id not in auth_admins_data:
            logger.info(f"Unauthorized /unban attempt by user {user_id}")
            return
        if len(event.raw_text.split()) < 2 and not event.message.is_reply:
            await safe_send_message(event.client, event.chat_id, "**Please Provide A Valid User To Unban ❌**")
            logger.info("No user identifier or reply provided for /unban")
            return
        target_user = None
        target_identifier = None
        if event.message.is_reply and event.message.reply_to_message.sender_id:
            try:
                target_user = await event.client.get_entity(event.message.reply_to_message.sender_id)
                target_identifier = target_user.id
            except Exception as e:
                logger.error(f"Error resolving reply-to user: {e}\n{traceback.format_exc()}")
                await safe_send_message(event.client, event.chat_id, f"**Failed to resolve reply-to user: {str(e)} ❌**")
                return
        else:
            target_identifier = event.raw_text.split()[1].strip()
            logger.info(f"Resolving user {target_identifier} for /unban")
            target_id, target_name, username = await resolve_user(event.client, target_identifier, event)
            if not target_id:
                logger.info(f"Failed to resolve user {target_identifier} for /unban")
                return
            target_user = await event.client.get_entity(target_id)
        if not target_user or not isinstance(target_user.id, int):
            await safe_send_message(event.client, event.chat_id, "**Sorry Failed To Unban User From Bot ❌**")
            logger.error(f"Invalid target_user: {target_user}")
            return
        target_id = target_user.id
        target_name = target_user.first_name or str(target_id)
        sent_message = await safe_send_message(event.client, event.chat_id, "**Unbanning User From Smart Tools**")
        try:
            if not await banned_users.find_one({"user_id": target_id}):
                if sent_message:
                    await sent_message.edit(
                        text="**Sorry Failed To Unban User From Bot: Not Banned ❌**",
                        parse_mode='markdown'
                    )
                logger.info(f"User {target_id} not banned")
                return
        except Exception as e:
            if sent_message:
                await sent_message.edit(
                    text="**Sorry Failed To Unban User From Bot ❌**",
                    parse_mode='markdown'
                )
            logger.error(f"Error checking ban status for {target_id}: {e}\n{traceback.format_exc()}")
            return
        try:
            await banned_users.delete_one({"user_id": target_id})
        except Exception as e:
            if sent_message:
                await sent_message.edit(
                    text="**Sorry Failed To Unban User From Bot ❌**",
                    parse_mode='markdown'
                )
            logger.error(f"Error unbanning user {target_id}: {e}\n{traceback.format_exc()}")
            return
        await safe_send_message(event.client, target_id, "**Good News, You Can Now Use Me ✅**")
        if sent_message:
            await sent_message.edit(
                text=f"**Successfully Unbanned [{target_name}](tg://user?id={target_id}) From Smart Tools ✅**",
                parse_mode='markdown',
                link_preview=False
            )
            logger.info(f"Successfully unbanned user {target_id}")
        for admin_id in [OWNER_ID] + auth_admins_data:
            if admin_id != user_id and isinstance(admin_id, int):
                await safe_send_message(
                    event.client, admin_id,
                    f"**Successfully Unbanned [{target_name}](tg://user?id={target_id}) From Smart Tools ✅**",
                    buttons=None
                )

    @app.on(events.NewMessage(pattern=f'({"|".join(COMMAND_PREFIX)})banlist'))
    async def banlist_command(event):
        user_id = event.sender_id
        logger.info(f"/banlist command triggered by user {user_id}")
        auth_admins_data = await get_auth_admins()
        if user_id != OWNER_ID and user_id not in auth_admins_data:
            logger.info(f"Unauthorized /banlist attempt by user {user_id}")
            return
        sent_message = await safe_send_message(event.client, event.chat_id, "**Fetching Banned List From Database...**")
        try:
            banned_list = await banned_users.find({}).to_list(None)
            if not banned_list:
                if sent_message:
                    await sent_message.edit(
                        text="**No Users Are Currently Banned ✅**",
                        parse_mode='markdown'
                    )
                logger.info("No banned users found")
                return
            response = "**🚫 Banned Users List:**\n\n"
            for index, user in enumerate(banned_list, 1):
                reason = user.get("reason", "Undefined")
                ban_date = user.get("ban_date", "Undefined")
                response += (
                    f"**{index}. {user['username']} [`{user['user_id']}`]**\n"
                    f" - **Reason:** {reason}\n"
                    f" - **Date:** {ban_date}\n\n"
                )
            if sent_message:
                await sent_message.edit(
                    text=response,
                    parse_mode='markdown'
                )
            logger.info("Successfully sent banned users list")
        except Exception as e:
            if sent_message:
                await sent_message.edit(
                    text="**Sorry Failed To Show Database❌**",
                    parse_mode='markdown'
                )
            logger.error(f"Error fetching banned users list: {e}\n{traceback.format_exc()}")
