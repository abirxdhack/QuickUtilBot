#Copyright @ISmartCoder
#Updates Channel: https://t.me/TheSmartDev
import os
import asyncio
import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from telegraph import Telegraph
from config import OWNER_ID, COMMAND_PREFIX, UPDATE_CHANNEL_URL
from core import auth_admins
from utils import LOGGER

logging.basicConfig(level=logging.INFO)
logger = LOGGER

telegraph = Telegraph()
try:
    telegraph.create_account(
        short_name="SmartUtilBot",
        author_name="SmartUtilBot",
        author_url="https://t.me/TheSmartDevs"
    )
except Exception as e:
    logger.error(f"Failed to create or access Telegraph account: {e}")

async def get_auth_admins():
    try:
        admins = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        return {admin["user_id"] for admin in admins}
    except Exception as e:
        logger.error(f"Error fetching auth admins: {e}")
        return set()

async def is_admin(user_id):
    if user_id == OWNER_ID:
        return True
    auth_admin_ids = await get_auth_admins()
    return user_id in auth_admin_ids

def setup_logs_handler(app: Client):
    async def create_telegraph_page(content: str) -> list:
        try:
            truncated_content = content[:40000]
            max_size_bytes = 20 * 1024
            pages = []
            page_content = ""
            current_size = 0
            lines = truncated_content.splitlines(keepends=True)
            for line in lines:
                line_bytes = line.encode('utf-8', errors='ignore')
                if current_size + len(line_bytes) > max_size_bytes and page_content:
                    safe_content = page_content.replace('<', '&lt;').replace('>', '&gt;')
                    html_content = f'<pre>{safe_content}</pre>'
                    page = telegraph.create_page(
                        title="SmartLogs",
                        html_content=html_content,
                        author_name="SmartUtilBot",
                        author_url="https://t.me/TheSmartDevs"
                    )
                    # Replace telegra.ph with graph.org in the URL
                    graph_url = page['url'].replace('telegra.ph', 'graph.org')
                    pages.append(graph_url)
                    page_content = ""
                    current_size = 0
                    await asyncio.sleep(0.5)
                page_content += line
                current_size += len(line_bytes)
            if page_content:
                safe_content = page_content.replace('<', '&lt;').replace('>', '&gt;')
                html_content = f'<pre>{safe_content}</pre>'
                page = telegraph.create_page(
                    title="SmartLogs",
                    html_content=html_content,
                    author_name="SmartUtilBot",
                    author_url="https://t.me/TheSmartDevs"
                )
                # Replace telegra.ph with graph.org in the URL
                graph_url = page['url'].replace('telegra.ph', 'graph.org')
                pages.append(graph_url)
                await asyncio.sleep(0.5)
            return pages
        except Exception as e:
            logger.error(f"Failed to create Telegraph page: {e}")
            return []

    @app.on_message(filters.command(["logs"], prefixes=COMMAND_PREFIX) & (filters.private | filters.group))
    async def logs_command(client: Client, message):
        user_id = message.from_user.id
        logger.info(f"Logs command from user {user_id}")
        if not await is_admin(user_id):
            logger.info("User not admin, ignoring command")
            return
        loading_message = await client.send_message(
            chat_id=message.chat.id,
            text="**Checking The Logs...💥**",
            parse_mode=ParseMode.MARKDOWN
        )
        await asyncio.sleep(2)
        if not os.path.exists("botlog.txt"):
            await loading_message.edit_text(
                text="**Sorry, No Logs Found ❌**",
                parse_mode=ParseMode.MARKDOWN
            )
            return await loading_message.delete()
        logger.info("User is admin, sending log document")
        try:
            file_size_bytes = os.path.getsize("botlog.txt")
            file_size_kb = file_size_bytes / 1024
            with open("botlog.txt", "r", encoding="utf-8", errors="ignore") as f:
                line_count = sum(1 for _ in f)
            now = datetime.now()
            time_str = now.strftime("%H-%M-%S")
            date_str = now.strftime("%Y-%m-%d")
            response = await client.send_document(
                chat_id=message.chat.id,
                document="botlog.txt",
                caption=(
                    "**Smart Logs Check → Successful ✅**\n"
                    "**━━━━━━━━━━━━━━━━━**\n"
                    f"**⊗ File Size: ** {file_size_kb:.2f} KB\n"
                    f"**⊗ Logs Lines: ** {line_count} Lines\n"
                    f"**⊗ Time: ** {time_str}\n"
                    f"**⊗ Date: ** {date_str}\n"
                    "**━━━━━━━━━━━━━━━━━**\n"
                    "**Smart LogsChecker → Activated ✅**"
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("Display Logs", callback_data="display_logs"),
                        InlineKeyboardButton("Web Paste", callback_data="web_paste$")
                    ],
                    [InlineKeyboardButton("❌ Close", callback_data="close_doc$")]
                ])
            )
            await loading_message.delete()
            return response
        except Exception as e:
            logger.error(f"Error sending log document: {e}")
            await loading_message.edit_text(
                text="**Sorry, Unable to Send Log Document ❌**",
                parse_mode=ParseMode.MARKDOWN
            )
            return await loading_message.delete()

    @app.on_callback_query(filters.regex(r"^(close_doc\$|close_logs\$|web_paste\$|display_logs)$"))
    async def handle_callback(client: Client, query: CallbackQuery):
        user_id = query.from_user.id
        data = query.data
        logger.info(f"Callback query from user {user_id}, data: {data}")
        if not await is_admin(user_id):
            logger.info("User not admin, ignoring callback")
            return
        logger.info("User is admin, processing callback")
        if data == "close_doc$":
            await query.message.delete()
            return await query.answer()
        elif data == "close_logs$":
            await query.message.delete()
            return await query.answer()
        elif data == "web_paste$":
            await query.answer("Uploading logs to Telegraph...")
            await query.message.edit_caption(
                caption="** Uploading SmartLogs To Telegraph✅**",
                parse_mode=ParseMode.MARKDOWN
            )
            if not os.path.exists("botlog.txt"):
                await query.message.edit_caption(
                    caption="** Sorry, No Logs Found ❌**",
                    parse_mode=ParseMode.MARKDOWN
                )
                return await query.answer()
            try:
                with open("botlog.txt", "r", encoding="utf-8", errors="ignore") as f:
                    logs_content = f.read()
                telegraph_urls = await create_telegraph_page(logs_content)
                if telegraph_urls:
                    buttons = []
                    for i in range(0, len(telegraph_urls), 2):
                        row = [
                            InlineKeyboardButton(f"View Web Part {i+1}", url=telegraph_urls[i])
                        ]
                        if i + 1 < len(telegraph_urls):
                            row.append(InlineKeyboardButton(f"View Web Part {i+2}", url=telegraph_urls[i+1]))
                        buttons.append(row)
                    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_doc$")])
                    file_size_bytes = os.path.getsize("botlog.txt")
                    file_size_kb = file_size_bytes / 1024
                    with open("botlog.txt", "r", encoding="utf-8", errors="ignore") as f:
                        line_count = sum(1 for _ in f)
                    now = datetime.now()
                    time_str = now.strftime("%H-%M-%S")
                    date_str = now.strftime("%Y-%m-%d")
                    return await query.message.edit_caption(
                        caption=(
                            "**Smart Logs Check → Successful ✅**\n"
                            "**━━━━━━━━━━━━━━━━━**\n"
                            f"**⊗ File Size: ** {file_size_kb:.2f} KB\n"
                            f"**⊗ Logs Lines: ** {line_count} Lines\n"
                            f"**⊗ Time: ** {time_str}\n"
                            f"**⊗ Date: ** {date_str}\n"
                            "**━━━━━━━━━━━━━━━━━**\n"
                            "**Smart LogsChecker → Activated ✅**"
                        ),
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                else:
                    return await query.message.edit_caption(
                        caption="** Sorry, Unable to Upload to Telegraph ❌**",
                        parse_mode=ParseMode.MARKDOWN
                    )
            except Exception as e:
                logger.error(f"Error uploading to Telegraph: {e}")
                return await query.message.edit_caption(
                    caption="** Sorry, Unable to Upload to Telegraph ❌**",
                    parse_mode=ParseMode.MARKDOWN
                )
        elif data == "display_logs":
            return await send_logs_page(client, query.message.chat.id, query)

    async def send_logs_page(client: Client, chat_id: int, query: CallbackQuery):
        logger.info(f"Sending latest logs to chat {chat_id}")
        if not os.path.exists("botlog.txt"):
            return await client.send_message(
                chat_id=chat_id,
                text="** Sorry, No Logs Found ❌**",
                parse_mode=ParseMode.MARKDOWN
            )
        try:
            with open("botlog.txt", "r", encoding="utf-8", errors="ignore") as f:
                logs = f.readlines()
            latest_logs = logs[-20:] if len(logs) > 20 else logs
            text = "".join(latest_logs)
            if len(text) > 4096:
                text = text[-4096:]
            return await client.send_message(
                chat_id=chat_id,
                text=text if text else "No logs available.❌",
                parse_mode=ParseMode.DISABLED,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="close_logs$")]
                ])
            )
        except Exception as e:
            logger.error(f"Error sending logs: {e}")
            return await client.send_message(
                chat_id=chat_id,
                text="** Sorry, There Was an Issue on the Server ❌**",
                parse_mode=ParseMode.MARKDOWN
            )
