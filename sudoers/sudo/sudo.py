#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
import asyncio
import traceback
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.custom import Button
from telethon.tl.types import KeyboardButtonUserProfile
from telethon.types import ReplyInlineMarkup, KeyboardButtonRow, InputKeyboardButtonUserProfile
from telethon.utils import get_display_name
from telethon.errors import UserIdInvalidError, UsernameInvalidError, PeerIdInvalidError, FloodWaitError
from config import OWNER_ID, COMMAND_PREFIX
from core import auth_admins
from utils import LOGGER

logger = LOGGER

def setup_sudo_handler(app: TelegramClient):
    async def get_auth_admins():
        try:
            admins = await auth_admins.find({}, {
                "user_id": 1, "title": 1, "auth_date": 1, "username": 1,
                "full_name": 1, "auth_time": 1, "auth_by": 1, "_id": 0
            }).to_list(None)
            return {admin["user_id"]: {
                "title": admin["title"],
                "auth_date": admin["auth_date"],
                "username": admin.get("username", "None"),
                "full_name": admin.get("full_name", "Unknown"),
                "auth_time": admin.get("auth_time", datetime.utcnow()),
                "auth_by": admin.get("auth_by", "Unknown")
            } for admin in admins}
        except Exception as e:
            logger.error(f"Error fetching auth admins: {e}\n{traceback.format_exc()}")
            return {}

    async def add_auth_admin(user_id: int, title: str, username: str, full_name: str, auth_by: str):
        try:
            auth_time = datetime.utcnow()
            await auth_admins.update_one(
                {"user_id": user_id},
                {"$set": {
                    "user_id": user_id,
                    "title": title,
                    "auth_date": auth_time,
                    "auth_time": auth_time,
                    "username": username,
                    "full_name": full_name,
                    "auth_by": auth_by
                }},
                upsert=True
            )
            logger.info(f"Added/Updated admin {user_id} with title {title}")
            return True
        except Exception as e:
            logger.error(f"Error adding/updating admin {user_id}: {e}\n{traceback.format_exc()}")
            return False

    async def remove_auth_admin(user_id: int):
        try:
            result = await auth_admins.delete_one({"user_id": user_id})
            if result.deleted_count > 0:
                logger.info(f"Removed admin {user_id}")
                return True
            else:
                logger.info(f"Admin {user_id} not found for removal")
                return False
        except Exception as e:
            logger.error(f"Error removing admin {user_id}: {e}\n{traceback.format_exc()}")
            return False

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
            full_name = f"{user.first_name} {getattr(user, 'last_name', '')}".strip()
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

    def format_time_duration(start_time, end_time):
        duration = end_time - start_time
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @app.on(events.NewMessage(pattern=f'({"|".join(COMMAND_PREFIX)})getadmins'))
    async def get_admins_command(event):
        user_id = event.sender_id
        logger.info(f"/getadmins command triggered by user {user_id}")
        if user_id != OWNER_ID:
            logger.info(f"Unauthorized /getadmins attempt by user {user_id}")
            return
        loading_message = await event.client.send_message(
            entity=event.chat_id,
            message="**Fetching Bot Admins List....**",
            parse_mode='markdown'
        )
        await asyncio.sleep(1)
        admin_list = ["**Smart Tools Admins List ✅**", "**━━━━━━━━━━━━━**"]
        try:
            owner_user = await event.client.get_entity(OWNER_ID)
            owner_full_name = f"{owner_user.first_name} {getattr(owner_user, 'last_name', '')}".strip()
            owner_username = f"@{owner_user.username}" if owner_user.username else "None"
            admin_list.extend([
                f"**⊗ Name ➺** {owner_full_name}",
                f"**⊗ Title ➺** Owner",
                f"**⊗ Username ➺** {owner_username}",
                f"**⊗ UserID ➺** `{OWNER_ID}`",
                f"**⊗ Auth Time ➺** Infinity",
                f"**⊗ Auth Date ➺** Infinity",
                f"**⊗ Auth By ➺** [{owner_full_name}](tg://user?id={OWNER_ID})",
                "**━━━━━━━━━━━━━**"
            ])
        except Exception as e:
            logger.error(f"Error fetching owner {OWNER_ID}: {e}\n{traceback.format_exc()}")
            admin_list.extend([
                f"**⊗ Name ➺** ID {OWNER_ID} (Not found)",
                f"**⊗ Title ➺** Owner",
                f"**⊗ Username ➺** None",
                f"**⊗ UserID ➺** `{OWNER_ID}`",
                f"**⊗ Auth Time ➺** Infinity",
                f"**⊗ Auth Date ➺** Infinity",
                f"**⊗ Auth By ➺** Unknown",
                "**━━━━━━━━━━━━━**"
            ])
        auth_admins_data = await get_auth_admins()
        total_admins = 1
        for admin_id, data in auth_admins_data.items():
            try:
                user = await event.client.get_entity(admin_id)
                full_name = f"{user.first_name} {getattr(user, 'last_name', '')}".strip()
                username = f"@{user.username}" if user.username else "None"
                auth_time = data["auth_time"]
                time_str = auth_time.strftime("%H:%M:%S")
                auth_date = auth_time.strftime("%Y-%m-%d")
                try:
                    owner_user = await event.client.get_entity(OWNER_ID)
                    owner_full_name = f"{owner_user.first_name} {getattr(owner_user, 'last_name', '')}".strip()
                    auth_by_text = owner_full_name
                except Exception:
                    auth_by_text = "Unknown"
                admin_list.extend([
                    f"**⊗ Name ➺** {full_name}",
                    f"**⊗ Title ➺** {data['title']}",
                    f"**⊗ Username ➺** {username}",
                    f"**⊗ UserID ➺** `{admin_id}`",
                    f"**⊗ Auth Time ➺** {time_str}",
                    f"**⊗ Auth Date ➺** {auth_date}",
                    f"**⊗ Auth By ➺** {auth_by_text}",
                    "**━━━━━━━━━━━━━**"
                ])
                total_admins += 1
            except Exception as e:
                logger.error(f"Error fetching admin {admin_id}: {e}\n{traceback.format_exc()}")
                auth_time = data["auth_time"]
                time_str = auth_time.strftime("%H:%M:%S")
                auth_date = auth_time.strftime("%Y-%m-%d")
                admin_list.extend([
                    f"**⊗ Name ➺** ID {admin_id} (Not found)",
                    f"**⊗ Title ➺** {data['title']}",
                    f"**⊗ Username ➺** {data.get('username', 'None')}",
                    f"**⊗ UserID ➺** `{admin_id}`",
                    f"**⊗ Auth Time ➺** {time_str}",
                    f"**⊗ Auth Date ➺** {auth_date}",
                    f"**⊗ Auth By ➺** Unknown",
                    "**━━━━━━━━━━━━━**"
                ])
                total_admins += 1
        admin_list.append(f"**Total Smart Tools Admins Are {total_admins} ✅**")
        await loading_message.edit(
            text="\n".join(admin_list),
            parse_mode='markdown',
            buttons=[[Button.inline("✘ Close ↯", "close_admins$")]]
        )

    @app.on(events.NewMessage(pattern=f'({"|".join(COMMAND_PREFIX)})auth'))
    async def auth_command(event):
        user_id = event.sender_id
        logger.info(f"/auth command triggered by user {user_id} with input: {event.raw_text}")
        if user_id != OWNER_ID:
            logger.info(f"Unauthorized /auth attempt by user {user_id}")
            return
        args = event.raw_text.split(maxsplit=2)
        if len(args) < 2:
            await event.respond(
                message="**Please Provide A Valid User To Promote ❌**",
                parse_mode='markdown'
            )
            logger.info("No user identifier provided for /auth")
            return
        identifier = args[1].strip()
        title = args[2].strip() if len(args) > 2 else "Admin"
        logger.info(f"Resolving user {identifier} for /auth")
        target_user_id, full_name, username = await resolve_user(event.client, identifier, event)
        if not target_user_id:
            logger.info(f"Failed to resolve user {identifier} for /auth")
            return
        if target_user_id == OWNER_ID:
            await event.respond(
                message="**Cannot Modify Owners Permission ↯**",
                parse_mode='markdown'
            )
            logger.info("Attempted to modify owner permissions")
            return
        loading_message = await event.client.send_message(
            entity=event.chat_id,
            message="**Promoting User To Authorized Users....**",
            parse_mode='markdown'
        )
        await asyncio.sleep(1)
        try:
            owner_user = await event.client.get_entity(OWNER_ID)
            auth_by = f"{owner_user.first_name} {getattr(owner_user, 'last_name', '')}".strip()
        except Exception as e:
            logger.error(f"Error fetching owner for auth_by: {e}\n{traceback.format_exc()}")
            auth_by = "Unknown"
        if await add_auth_admin(target_user_id, title, username, full_name, auth_by):
            try:
                reply_markup = ReplyInlineMarkup([
                    KeyboardButtonRow([
                        InputKeyboardButtonUserProfile("View Profile", await event.client.get_input_entity(target_user_id))
                    ])
                ])
            except Exception as e:
                logger.error(f"Error creating user profile button: {e}")
                reply_markup = [[Button.url("View Profile", f"tg://user?id={target_user_id}")]]
            await loading_message.edit(
                text=f"**Successfully Promoted [{full_name}](tg://user?id={target_user_id}) ✅**",
                parse_mode='markdown',
                buttons=reply_markup,
                link_preview=False
            )
            logger.info(f"Successfully promoted user {target_user_id} with title {title}")
        else:
            await loading_message.edit(
                text="**Sorry Failed To Promote User ❌**",
                parse_mode='markdown'
            )
            logger.error(f"Failed to promote user {target_user_id}")

    @app.on(events.NewMessage(pattern=f'({"|".join(COMMAND_PREFIX)})unauth'))
    async def unauth_command(event):
        user_id = event.sender_id
        logger.info(f"/unauth command triggered by user {user_id} with input: {event.raw_text}")
        if user_id != OWNER_ID:
            logger.info(f"Unauthorized /unauth attempt by user {user_id}")
            return
        args = event.raw_text.split(maxsplit=1)
        if len(args) < 2:
            await event.respond(
                message="**Please Provide A Valid User To Demote ❌**",
                parse_mode='markdown'
            )
            logger.info("No user identifier provided for /unauth")
            return
        identifier = args[1].strip()
        logger.info(f"Resolving user {identifier} for /unauth")
        target_user_id, full_name, username = await resolve_user(event.client, identifier, event)
        if not target_user_id:
            logger.info(f"Failed to resolve user {identifier} for /unauth")
            return
        if target_user_id == OWNER_ID:
            await event.respond(
                message="**Cannot Modify Owners Permission ❌**",
                parse_mode='markdown'
            )
            logger.info("Attempted to modify owner permissions")
            return
        loading_message = await event.client.send_message(
            entity=event.chat_id,
            message="**Demoting User From Authorized Users....**",
            parse_mode='markdown'
        )
        await asyncio.sleep(1)
        if await remove_auth_admin(target_user_id):
            try:
                reply_markup = ReplyInlineMarkup([
                    KeyboardButtonRow([
                        InputKeyboardButtonUserProfile("View Profile", await event.client.get_input_entity(target_user_id))
                    ])
                ])
            except Exception as e:
                logger.error(f"Error creating user profile button: {e}")
                reply_markup = [[Button.url("View Profile", f"tg://user?id={target_user_id}")]]
            await loading_message.edit(
                text=f"**Successfully Demoted [{full_name}](tg://user?id={target_user_id}) ✅**",
                parse_mode='markdown',
                buttons=reply_markup,
                link_preview=False
            )
            logger.info(f"Successfully demoted user {target_user_id}")
        else:
            await loading_message.edit(
                text="**Sorry Failed To Demote User ❌**",
                parse_mode='markdown'
            )
            logger.error(f"Failed to demote user {target_user_id}")

    @app.on(events.CallbackQuery(pattern=r"^close_admins\$"))
    async def handle_close_callback(event):
        user_id = event.sender_id
        logger.info(f"Close admins callback triggered by user {user_id}")
        if user_id != OWNER_ID:
            await event.answer(
                text="🛑 Action Not Allowed For You",
                show_alert=True
            )
            logger.info(f"Unauthorized close admins attempt by user {user_id}")
            return
        await event.delete()
        await event.answer()
        logger.info("Admins list closed")

