# Copyright @ISmartCoder
# Updates Channel: https://t.me/TheSmartDev
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.types import User
from telethon.tl.custom import Button
from config import COMMAND_PREFIX, BAN_REPLY
from utils import notify_admin, LOGGER
from core import banned_users, user_activity_collection

def setup_tp_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(topusers|top)$', incoming=True))
    async def topusers_handler(event):
        user_id = event.sender_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='md')
            return

        loading_msg = await event.respond("**Fetching Top Users Of SmartTool ⚙️...**", parse_mode='md')

        try:
            page = 1
            users_per_page = 9
            now = datetime.utcnow()
            daily_users = await user_activity_collection.find({"is_group": False, "last_activity": {"$gte": now - timedelta(days=1)}}).to_list(None)
            total_users = len(daily_users)
            total_pages = (total_users + users_per_page - 1) // users_per_page
            start_index = (page - 1) * users_per_page
            end_index = start_index + users_per_page
            paginated_users = daily_users[start_index:end_index]

            top_users_text = (
                f"**🏆 Top Users (All-time) — page {page}/{total_pages if total_pages > 0 else 1}:**\n"
                f"**━━━━━━━━━━━━━━━**\n"
            )
            for i, user in enumerate(paginated_users, start=start_index + 1):
                user_id_data = user['user_id']
                try:
                    telegram_user = await app.get_entity(user_id_data)
                    full_name = f"{telegram_user.first_name} {telegram_user.last_name}" if getattr(telegram_user, 'last_name', None) else telegram_user.first_name
                except Exception as e:
                    LOGGER.error(f"Failed to fetch user {user_id_data}: {e}")
                    full_name = f"User_{user_id_data}"
                rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔸"
                top_users_text += f"**{rank_emoji} {i}.** [{full_name}](tg://user?id={user_id_data})\n** - User Id :** `{user_id_data}`\n\n"

            buttons = []
            if page == 1 and total_pages > 1:
                buttons.append([Button.inline("Next ➡️", f"nxttpusers_{page+1}")])
            elif page > 1 and page < total_pages:
                buttons.append([
                    Button.inline("⬅️ Previous", f"prvtpusers_{page-1}"),
                    Button.inline("Next ➡️", f"nxttpusers_{page+1}")
                ])
            elif page == total_pages and page > 1:
                buttons.append([Button.inline("⬅️ Previous", f"prvtpusers_{page-1}")])

            await loading_msg.edit(
                top_users_text,
                parse_mode='md',
                buttons=buttons if buttons else None,
                link_preview=False
            )

        except Exception as e:
            LOGGER.error(f"Failed to fetch top users: {e}")
            await loading_msg.edit("**Sorry Failed To Load Database**", parse_mode='md')

    @app.on(events.CallbackQuery(pattern=r'^(nxttpusers|prvtpusers)_'))
    async def topusers_callback(event):
        user_id = event.sender_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.answer(BAN_REPLY, show_alert=True)
            return

        try:
            data = event.data.decode('utf-8')
            page = int(data.split('_')[1])

            users_per_page = 9
            now = datetime.utcnow()
            daily_users = await user_activity_collection.find({"is_group": False, "last_activity": {"$gte": now - timedelta(days=1)}}).to_list(None)
            total_users = len(daily_users)
            total_pages = (total_users + users_per_page - 1) // users_per_page
            start_index = (page - 1) * users_per_page
            end_index = start_index + users_per_page
            paginated_users = daily_users[start_index:end_index]

            top_users_text = (
                f"**🏆 Top Users (All-time) — page {page}/{total_pages if total_pages > 0 else 1}:**\n"
                f"**━━━━━━━━━━━━━━━**\n"
            )
            for i, user in enumerate(paginated_users, start=start_index + 1):
                user_id_data = user['user_id']
                try:
                    telegram_user = await app.get_entity(user_id_data)
                    full_name = f"{telegram_user.first_name} {telegram_user.last_name}" if getattr(telegram_user, 'last_name', None) else telegram_user.first_name
                except Exception as e:
                    LOGGER.error(f"Failed to fetch user {user_id_data}: {e}")
                    full_name = f"User_{user_id_data}"
                rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔸"
                top_users_text += f"**{rank_emoji} {i}.** [{full_name}](tg://user?id={user_id_data})\n** - User Id :** `{user_id_data}`\n\n"

            buttons = []
            if page == 1 and total_pages > 1:
                buttons.append([Button.inline("Next ➡️", f"nxttpusers_{page+1}")])
            elif page > 1 and page < total_pages:
                buttons.append([
                    Button.inline("⬅️ Previous", f"prvtpusers_{page-1}"),
                    Button.inline("Next ➡️", f"nxttpusers_{page+1}")
                ])
            elif page == total_pages and page > 1:
                buttons.append([Button.inline("⬅️ Previous", f"prvtpusers_{page-1}")])

            await event.edit_message(
                top_users_text,
                parse_mode='md',
                buttons=buttons if buttons else None,
                link_preview=False
            )

        except Exception as e:
            LOGGER.error(f"Failed to handle top users callback: {e}")
            await event.answer("Failed to load data", show_alert=True)