# Copyright @ISmartDevs
# Channel t.me/TheSmartDev
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from config import OWNER_ID, COMMAND_PREFIX
from core import auth_admins
from utils import LOGGER
from pyrogram.errors import UserIdInvalid, UsernameInvalid, PeerIdInvalid

def setup_sudo_handler(app: Client):
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
            LOGGER.error(f"Error fetching auth admins: {e}")
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
            LOGGER.info(f"Added/Updated admin {user_id} with title {title}")
            return True
        except Exception as e:
            LOGGER.error(f"Error adding/updating admin {user_id}: {e}")
            return False

    async def remove_auth_admin(user_id: int):
        try:
            result = await auth_admins.delete_one({"user_id": user_id})
            if result.deleted_count > 0:
                LOGGER.info(f"Removed admin {user_id}")
                return True
            else:
                LOGGER.info(f"Admin {user_id} not found for removal")
                return False
        except Exception as e:
            LOGGER.error(f"Error removing admin {user_id}: {e}")
            return False

    async def resolve_user(client: Client, identifier: str):
        try:
            if identifier.startswith("@"):
                user = await client.get_users(identifier)
                full_name = f"{user.first_name} {user.last_name or ''}".strip()
                username = f"@{user.username}" if user.username else "None"
                return user.id, full_name, username
            else:
                user_id = int(identifier)
                user = await client.get_users(user_id)
                full_name = f"{user.first_name} {user.last_name or ''}".strip()
                username = f"@{user.username}" if user.username else "None"
                return user_id, full_name, username
        except (UserIdInvalid, UsernameInvalid, PeerIdInvalid, ValueError) as e:
            LOGGER.error(f"Error resolving user {identifier}: {e}")
            return None, None, None

    def format_time_duration(start_time, end_time):
        duration = end_time - start_time
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @app.on_message(filters.command(["getadmins"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def get_admins_command(client, message):
        user_id = message.from_user.id
        if user_id != OWNER_ID:
            return

        loading_message = await client.send_message(
            chat_id=message.chat.id,
            text="**Fetching Bot Admins List....**",
            parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(1)

        admin_list = ["**Smart Tools Admins List ✅**", "**━━━━━━━━━━━━━**"]
        
        try:
            owner_user = await client.get_users(OWNER_ID)
            owner_full_name = f"{owner_user.first_name} {owner_user.last_name or ''}".strip()
            owner_username = f"@{owner_user.username}" if owner_user.username else "None"
            owner_profile_link = f"tg://user?id={OWNER_ID}"
            
            admin_list.extend([
                f"**⊗ Name ➺** {owner_full_name}",
                f"**⊗ Title ➺** Owner",
                f"**⊗ Username ➺** {owner_username}",
                f"**⊗ UserID ➺** `{OWNER_ID}`",
                f"**⊗ Auth Time ➺** Infinity",
                f"**⊗ Auth Date ➺** Infinity",
                f"**⊗ Auth By ➺** [{owner_full_name}]({owner_profile_link})",
                "**━━━━━━━━━━━━━**"
            ])
        except Exception:
            admin_list.extend([
                f"**⊗ Name ➺** ID {OWNER_ID} (Not found)",
                f"**⊗ Title ➺** Owner",
                f"**⊗ Username ➺** None",
                f"**⊗ UserID ➺** `{OWNER_ID}`",
                f"**⊗ Auth Time ➺** Infinity",
                f"**�otimes Auth Date ➺** Infinity",
                f"**⊗ Auth By ➺** Unknown",
                "**━━━━━━━━━━━━━**"
            ])

        auth_admins_data = await get_auth_admins()
        total_admins = 1
        
        for admin_id, data in auth_admins_data.items():
            try:
                user = await client.get_users(admin_id)
                full_name = f"{user.first_name} {user.last_name or ''}".strip()
                username = f"@{user.username}" if user.username else "None"
                profile_link = f"tg://user?id={admin_id}"
                
                auth_time = data["auth_time"]
                time_str = auth_time.strftime("%H:%M:%S")
                auth_date = auth_time.strftime("%Y-%m-%d")
                
                try:
                    owner_user = await client.get_users(OWNER_ID)
                    owner_full_name = f"{owner_user.first_name} {owner_user.last_name or ''}".strip()
                    owner_profile_link = f"tg://user?id={OWNER_ID}"
                    auth_by_text = f"[{owner_full_name}]({owner_profile_link})"
                except:
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
            except Exception:
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

        await loading_message.edit_text(
            text="\n".join(admin_list),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✘ Close ↯", callback_data="close_admins$")]
            ])
        )

    @app.on_message(filters.command(["auth"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def auth_command(client, message):
        user_id = message.from_user.id
        if user_id != OWNER_ID:
            return

        args = message.text.split(maxsplit=2)
        if len(args) < 2:
            await client.send_message(
                chat_id=message.chat.id,
                text="**Please Provide Specify A Valid User To Promote❌**",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        identifier = args[1]
        title = args[2] if len(args) > 2 else "Admin"
        
        target_user_id, full_name, username = await resolve_user(client, identifier)
        if not target_user_id:
            await client.send_message(
                chat_id=message.chat.id,
                text="**Please Provide Specify A Valid User To Promote❌**",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        if target_user_id == OWNER_ID:
            await client.send_message(
                chat_id=message.chat.id,
                text="**Cannot Modify Owners Permission ↯**",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        loading_message = await client.send_message(
            chat_id=message.chat.id,
            text="**Promoting User To Authorized Users....**",
            parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(1)

        try:
            owner_user = await client.get_users(OWNER_ID)
            auth_by = f"{owner_user.first_name} {owner_user.last_name or ''}".strip()
        except:
            auth_by = "Unknown"

        if await add_auth_admin(target_user_id, title, username, full_name, auth_by):
            profile_link = f"tg://user?id={target_user_id}"
            await loading_message.edit_text(
                text=f"**Successfully Promoted [{full_name}]({profile_link}) ✅**",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await loading_message.edit_text(
                text="**Sorry Failed To Promote User ❌**",
                parse_mode=ParseMode.MARKDOWN
            )

    @app.on_message(filters.command(["unauth"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def unauth_command(client, message):
        user_id = message.from_user.id
        if user_id != OWNER_ID:
            return

        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await client.send_message(
                chat_id=message.chat.id,
                text="**Please Provide Specify A Valid User To Demote❌**",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        identifier = args[1]
        target_user_id, full_name, username = await resolve_user(client, identifier)
        if not target_user_id:
            await client.send_message(
                chat_id=message.chat.id,
                text="**Please Provide Specify A Valid User To Demote❌**",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        if target_user_id == OWNER_ID:
            await client.send_message(
                chat_id=message.chat.id,
                text="**Cannot Modify Owners Permission ❌**",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        loading_message = await client.send_message(
            chat_id=message.chat.id,
            text="**Demoting User From Authorized Users....**",
            parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(1)

        if await remove_auth_admin(target_user_id):
            profile_link = f"tg://user?id={target_user_id}"
            await loading_message.edit_text(
                text=f"**Successfully Demoted [{full_name}]({profile_link}) ✅**",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await loading_message.edit_text(
                text="**Sorry Failed To Demote User ❌**",
                parse_mode=ParseMode.MARKDOWN
            )

    @app.on_callback_query(filters.regex(r"^close_admins\$"))
    async def handle_close_callback(client: Client, query: CallbackQuery):
        user_id = query.from_user.id
        if user_id != OWNER_ID:
            await query.answer(
                text="🛑 Action Not Allowed For You",
                show_alert=True
            )
            return
        await query.message.delete()
        await query.answer()
