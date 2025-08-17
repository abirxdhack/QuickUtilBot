import logging
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.custom import Button
from telethon.tl.types import KeyboardButtonUserProfile
from telethon.errors import UserIdInvalidError, UsernameInvalidError, PeerIdInvalidError
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
        logger.error(f"Failed to send message to {entity}: {e}")
    return None

def setup_gban_handler(app: TelegramClient):
    async def get_auth_admins():
        try:
            admins = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
            return [admin["user_id"] for admin in admins]
        except Exception as e:
            logger.error(f"Error fetching admins: {e}")
            return []

    @app.on(events.NewMessage(pattern=f'({"|".join(COMMAND_PREFIX)})ban$'))
    async def ban_command(event):
        user_id = event.sender_id
        auth_admins_data = await get_auth_admins()
        if user_id != OWNER_ID and user_id not in auth_admins_data:
            return
        if len(event.message.text.split()) < 2 and not event.message.is_reply:
            await safe_send_message(event.client, event.chat_id, "**Please Provide A Valid User To Ban ❌**")
            return
        target_user = None
        target_identifier = None
        reason = "undefined"
        if event.message.is_reply and event.message.reply_to_message.sender_id:
            target_user = await event.client.get_entity(event.message.reply_to_message.sender_id)
            target_identifier = target_user.id
            if len(event.message.text.split()) >= 2:
                reason = " ".join(event.message.text.split()[1:])
        else:
            target_identifier = event.message.text.split()[1]
            if len(event.message.text.split()) >= 3:
                reason = " ".join(event.message.text.split()[2:])
            try:
                target_user = await event.client.get_entity(int(target_identifier))
            except (ValueError, UserIdInvalidError, PeerIdInvalidError):
                try:
                    target_user = await event.client.get_entity(target_identifier.lstrip('@'))
                except (UsernameInvalidError, PeerIdInvalidError) as e:
                    sent_message = await safe_send_message(event.client, event.chat_id, "**Banning User From Smart Tools**")
                    if sent_message:
                        await sent_message.edit(
                            text="**Sorry Failed To Ban User From Bot ❌**",
                            parse_mode='markdown'
                        )
                    logger.error(f"Error resolving user {target_identifier}: {e}")
                    return
        if not target_user or not isinstance(target_user.id, int):
            sent_message = await safe_send_message(event.client, event.chat_id, "**Banning User From Smart Tools**")
            if sent_message:
                await sent_message.edit(
                    text="**Sorry Failed To Ban User From Bot ❌**",
                    parse_mode='markdown'
                )
            logger.error(f"Invalid target_user: {target_user}")
            return
        target_id = target_user.id
        if target_id == OWNER_ID or target_id in auth_admins_data:
            await safe_send_message(event.client, event.chat_id, "**Lol I Can Not Ban My Admins ❌**")
            return
        target_name = target_user.first_name or str(target_id)
        ban_date = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        sent_message = await safe_send_message(event.client, event.chat_id, "**Banning User From Smart Tools**")
        try:
            if await banned_users.find_one({"user_id": target_id}):
                if sent_message:
                    await sent_message.edit(
                        text="**Sorry Failed To Ban User From Bot ❌**",
                        parse_mode='markdown'
                    )
                return
        except Exception as e:
            if sent_message:
                await sent_message.edit(
                    text="**Sorry Failed To Ban User From Bot ❌**",
                    parse_mode='markdown'
                )
            logger.error(f"Error checking ban status for {target_id}: {e}")
            return
        try:
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
            logger.error(f"Error banning user {target_id}: {e}")
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
        reply_markup = [[KeyboardButtonUserProfile(text="Contact Owner 👨🏻‍💻", user_id=int(OWNER_ID))]]
        await safe_send_message(event.client, target_id, ban_message, buttons=reply_markup)
        if sent_message:
            await sent_message.edit(
                text=f"**{target_name} [`{target_id}`] banned.**\n"
                     f"**Reason:** {reason}\n"
                     f"**Ban Date:** {ban_date}",
                parse_mode='markdown'
            )
        for admin_id in [OWNER_ID] + auth_admins_data:
            if admin_id != user_id and isinstance(admin_id, int):
                await safe_send_message(
                    event.client, admin_id,
                    f"**{target_name} [`{target_id}`] banned.**\n"
                    f"**Reason:** {reason}\n"
                    f"**Ban Date:** {ban_date}"
                )

    @app.on(events.NewMessage(pattern=f'({"|".join(COMMAND_PREFIX)})unban$'))
    async def unban_command(event):
        user_id = event.sender_id
        auth_admins_data = await get_auth_admins()
        if user_id != OWNER_ID and user_id not in auth_admins_data:
            return
        if len(event.message.text.split()) < 2 and not event.message.is_reply:
            await safe_send_message(event.client, event.chat_id, "**Please Provide A Valid User To Unban ❌**")
            return
        target_user = None
        target_identifier = None
        if event.message.is_reply and event.message.reply_to_message.sender_id:
            target_user = await event.client.get_entity(event.message.reply_to_message.sender_id)
            target_identifier = target_user.id
        else:
            target_identifier = event.message.text.split()[1]
            try:
                target_user = await event.client.get_entity(int(target_identifier))
            except (ValueError, UserIdInvalidError, PeerIdInvalidError):
                try:
                    target_user = await event.client.get_entity(target_identifier.lstrip('@'))
                except (UsernameInvalidError, PeerIdInvalidError) as e:
                    sent_message = await safe_send_message(event.client, event.chat_id, "**Unbanning User From Smart Tools**")
                    if sent_message:
                        await sent_message.edit(
                            text="**Sorry Failed To Unban User From Bot ❌**",
                            parse_mode='markdown'
                        )
                    logger.error(f"Error resolving user {target_identifier}: {e}")
                    return
        if not target_user or not isinstance(target_user.id, int):
            sent_message = await safe_send_message(event.client, event.chat_id, "**Unbanning User From Smart Tools**")
            if sent_message:
                await sent_message.edit(
                    text="**Sorry Failed To Unban User From Bot ❌**",
                    parse_mode='markdown'
                )
            logger.error(f"Invalid target_user: {target_user}")
            return
        target_id = target_user.id
        target_name = target_user.first_name or str(target_id)
        sent_message = await safe_send_message(event.client, event.chat_id, "**Unbanning User From Smart Tools**")
        try:
            if not await banned_users.find_one({"user_id": target_id}):
                if sent_message:
                    await sent_message.edit(
                        text="**Sorry Failed To Unban User From Bot ❌**",
                        parse_mode='markdown'
                    )
                return
        except Exception as e:
            if sent_message:
                await sent_message.edit(
                    text="**Sorry Failed To Unban User From Bot ❌**",
                    parse_mode='markdown'
                )
            logger.error(f"Error checking ban status for {target_id}: {e}")
            return
        try:
            await banned_users.delete_one({"user_id": target_id})
        except Exception as e:
            if sent_message:
                sent_message.edit(
                    text="**Sorry Failed To Unban User From Bot ❌**",
                    parse_mode='markdown'
                )
            logger.error(f"Error unbanning user {target_id}: {e}")
            return
        await safe_send_message(event.client, target_id, "**Good News, You Can Now Use Me ✅**")
        if sent_message:
            await sent_message.edit(
                text=f"**Successfully Unbanned [{target_name}](tg://user?id={target_id}) From Smart Tools ✅**",
                parse_mode='markdown',
                link_preview=False
            )
        for admin_id in [OWNER_ID] + auth_admins_data:
            if admin_id != user_id and isinstance(admin_id, int):
                await safe_send_message(
                    event.client, admin_id,
                    f"**Successfully Unbanned [{target_name}](tg://user?id={target_id}) From Smart Tools ✅**",
                    buttons=None
                )

    @app.on(events.NewMessage(pattern=f'({"|".join(COMMAND_PREFIX)})banlist$'))
    async def banlist_command(event):
        user_id = event.sender_id
        auth_admins_data = await get_auth_admins()
        if user_id != OWNER_ID and user_id not in auth_admins_data:
            return
        sent_message = await safe_send_message(event.client, event.chat_id, "**Fetching Banned List From Database...**")
        try:
            banned_list = await banned_users.find({}).to_list(None)
            if not banned_list:
                await sent_message.edit(
                    text="**No Users Are Currently Banned ✅**",
                    parse_mode='markdown'
                )
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
            await sent_message.edit(
                text=response,
                parse_mode='markdown'
            )
        except Exception as e:
            await sent_message.edit(
                text="**Sorry Failed To Show Database❌**",
                parse_mode='markdown'
            )
            logger.error(f"Error fetching banned users list: {e}")
