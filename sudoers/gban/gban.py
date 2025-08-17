#Copyright @ISmartCoder
#Updates Channel https://t.me/TheSmartDev
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserIdInvalid, UsernameInvalid, PeerIdInvalid
from config import OWNER_ID, COMMAND_PREFIX
from core import auth_admins, banned_users
from utils import LOGGER
from datetime import datetime

def setup_gban_handler(app: Client):
    async def safe_send_message(client, chat_id, text, reply_markup=None):
        try:
            if chat_id and isinstance(chat_id, (int, str)):
                return await client.send_message(chat_id, text, reply_markup=reply_markup)
        except Exception as e:
            LOGGER.error(f"Failed to send message to {chat_id}: {e}")
        return None

    @app.on_message(filters.command(["ban"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def ban_command(client, message):
        user_id = message.from_user.id
        try:
            auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
            AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        except Exception as e:
            LOGGER.error(f"Error fetching admins: {e}")
            return

        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            return

        if len(message.command) < 2 and not message.reply_to_message:
            await safe_send_message(client, message.chat.id, "**Please Provide A Valid User To Ban ❌**")
            return

        target_user = None
        target_identifier = None
        reason = "undefined"
        if message.reply_to_message and message.reply_to_message.from_user:
            target_user = message.reply_to_message.from_user
            target_identifier = target_user.id
            if len(message.command) >= 2:
                reason = " ".join(message.command[1:])
        else:
            target_identifier = message.command[1]
            if len(message.command) >= 3:
                reason = " ".join(message.command[2:])
            try:
                target_user = await client.get_users(int(target_identifier))
            except (ValueError, UserIdInvalid, PeerIdInvalid):
                try:
                    target_identifier = target_identifier.lstrip('@')
                    target_user = await client.get_users(target_identifier)
                except (UsernameInvalid, PeerIdInvalid) as e:
                    sent_message = await safe_send_message(client, message.chat.id, "**Banning User From Smart Tools**")
                    if sent_message:
                        await sent_message.edit("**Sorry Failed To Ban User From Bot ❌**")
                    LOGGER.error(f"Error resolving user {target_identifier}: {e}")
                    return

        if not target_user or not isinstance(target_user.id, int):
            sent_message = await safe_send_message(client, message.chat.id, "**Banning User From Smart Tools**")
            if sent_message:
                await sent_message.edit("**Sorry Failed To Ban User From Bot ❌**")
            LOGGER.error(f"Invalid target_user: {target_user}")
            return

        target_id = target_user.id
        if target_id == OWNER_ID or target_id in AUTH_ADMIN_IDS:
            await safe_send_message(client, message.chat.id, "**Lol I Can Not Ban My Admins ❌**")
            return

        target_name = target_user.first_name or str(target_id)
        profile_link = f"tg://user?id={target_id}"
        ban_date = datetime.now().strftime("%Y-%m-%d %I:%M %p")

        sent_message = await safe_send_message(client, message.chat.id, "**Banning User From Smart Tools**")

        try:
            if await banned_users.find_one({"user_id": target_id}):
                if sent_message:
                    await sent_message.edit("**Sorry Failed To Ban User From Bot ❌**")
                return
        except Exception as e:
            if sent_message:
                await sent_message.edit("**Sorry Failed To Ban User From Bot ❌**")
            LOGGER.error(f"Error checking ban status for {target_id}: {e}")
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
                await sent_message.edit("**Sorry Failed To Ban User From Bot ❌**")
            LOGGER.error(f"Error banning user {target_id}: {e}")
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
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Contact Owner 👨🏻‍💻", user_id=OWNER_ID)]
        ])
        await safe_send_message(client, target_id, ban_message, reply_markup=reply_markup)

        if sent_message:
            await sent_message.edit(
                f"**{target_name} [`{target_id}`] banned.**\n"
                f"**Reason:** {reason}\n"
                f"**Ban Date:** {ban_date}"
            )
        
        for admin_id in [OWNER_ID] + AUTH_ADMIN_IDS:
            if admin_id != user_id and isinstance(admin_id, int):
                await safe_send_message(
                    client, admin_id,
                    f"**{target_name} [`{target_id}`] banned.**\n"
                    f"**Reason:** {reason}\n"
                    f"**Ban Date:** {ban_date}"
                )

    @app.on_message(filters.command(["unban"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def unban_command(client, message):
        user_id = message.from_user.id
        try:
            auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
            AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        except Exception as e:
            LOGGER.error(f"Error fetching admins: {e}")
            return

        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            return

        if len(message.command) < 2 and not message.reply_to_message:
            await safe_send_message(client, message.chat.id, "**Please Provide A Valid User To Unban ❌**")
            return

        target_user = None
        target_identifier = None
        if message.reply_to_message and message.reply_to_message.from_user:
            target_user = message.reply_to_message.from_user
            target_identifier = target_user.id
        else:
            target_identifier = message.command[1]
            try:
                target_user = await client.get_users(int(target_identifier))
            except (ValueError, UserIdInvalid, PeerIdInvalid):
                try:
                    target_identifier = target_identifier.lstrip('@')
                    target_user = await client.get_users(target_identifier)
                except (UsernameInvalid, PeerIdInvalid) as e:
                    sent_message = await safe_send_message(client, message.chat.id, "**Unbanning User From Smart Tools**")
                    if sent_message:
                        await sent_message.edit("**Sorry Failed To Unban User From Bot ❌**")
                    LOGGER.error(f"Error resolving user {target_identifier}: {e}")
                    return

        if not target_user or not isinstance(target_user.id, int):
            sent_message = await safe_send_message(client, message.chat.id, "**Unbanning User From Smart Tools**")
            if sent_message:
                await sent_message.edit("**Sorry Failed To Unban User From Bot ❌**")
            LOGGER.error(f"Invalid target_user: {target_user}")
            return

        target_id = target_user.id
        target_name = target_user.first_name or str(target_id)
        profile_link = f"tg://user?id={target_id}"

        sent_message = await safe_send_message(client, message.chat.id, "**Unbanning User From Smart Tools**")

        try:
            if not await banned_users.find_one({"user_id": target_id}):
                if sent_message:
                    await sent_message.edit("**Sorry Failed To Unban User From Bot ❌**")
                return
        except Exception as e:
            if sent_message:
                await sent_message.edit("**Sorry Failed To Unban User From Bot ❌**")
            LOGGER.error(f"Error checking ban status for {target_id}: {e}")
            return

        try:
            await banned_users.delete_one({"user_id": target_id})
        except Exception as e:
            if sent_message:
                await sent_message.edit("**Sorry Failed To Unban User From Bot ❌**")
            LOGGER.error(f"Error unbanning user {target_id}: {e}")
            return

        await safe_send_message(client, target_id, "**Good News, You Can Now Use Me ✅**")
        if sent_message:
            await sent_message.edit(f"**Successfully Unbanned [{target_name}]({profile_link}) From Smart Tools ✅**")
        
        for admin_id in [OWNER_ID] + AUTH_ADMIN_IDS:
            if admin_id != user_id and isinstance(admin_id, int):
                await safe_send_message(client, admin_id, f"**Successfully Unbanned [{target_name}]({profile_link}) From Smart Tools ✅**")

    @app.on_message(filters.command(["banlist"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def banlist_command(client, message):
        user_id = message.from_user.id
        try:
            auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
            AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        except Exception as e:
            LOGGER.error(f"Error fetching admins: {e}")
            return

        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            return

        sent_message = await safe_send_message(client, message.chat.id, "**Fetching Banned List From Database...**")
        
        try:
            banned_list = await banned_users.find({}).to_list(None)
            if not banned_list:
                await sent_message.edit("**No Users Are Currently Banned ✅**")
                return

            response = "**🚫 Banned Users List:**\n\n"
            for index, user in enumerate(banned_list, 1):
                reason = user.get("reason", "Undefined")
                ban_date = user.get("ban_date", "Undefined")
                response += (
                    f"**{index}. {user['username']} [`{user['user_id']}`]**\n"
                    f"   - **Reason:** {reason}\n"
                    f"   - **Date:** {ban_date}\n\n"
                )
            await sent_message.edit(response)
        except Exception as e:
            await sent_message.edit("**Sorry Failed To Show Database❌**")
            LOGGER.error(f"Error fetching banned users list: {e}")
