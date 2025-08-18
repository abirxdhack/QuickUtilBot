import aiohttp
import time
from telethon import TelegramClient, events, Button
from config import COMMAND_PREFIX, BAN_REPLY
from core import banned_users
from utils import notify_admin, LOGGER

pagination_sessions = {}

def setup_cpn_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(cpn|promo)( .*)?$'))
    async def cpn_handler(event):
        user_id = event.sender_id
        chat_id = event.chat_id
        if await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='markdown')
            return
        args = event.raw_text.strip().split()
        if len(args) < 2 or not args[1].strip():
            await event.respond("**❌ Missing store name! Try like this: /cpn amazon**", parse_mode='markdown')
            return
        sitename = args[1].strip().lower()
        sitename_with_com = f"{sitename}.com"
        loading = await event.respond(f"**🔍 Searching Coupon For {sitename}**", parse_mode='markdown')
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://smartcoupon.vercel.app/cpn?site={sitename_with_com}") as resp:
                    if resp.status != 200:
                        raise Exception(f"API Error: Status {resp.status}")
                    data = await resp.json()
        except Exception as e:
            LOGGER.error(f"[CPN] API error: {e}")
            await notify_admin(app, "/cpn", e, event)
            await loading.edit(text="**❌ Site unreachable or error occurred. Try again later.**", parse_mode='markdown')
            return
        if "results" not in data or not data["results"]:
            await loading.edit(text="**❌ No promo code found. Store name is incorrect?**", parse_mode='markdown')
            return
        coupons = data["results"]
        pages = [coupons[i:i + 5] for i in range(0, len(coupons), 5)]
        session_id = f"{chat_id}_{event.id}"
        pagination_sessions[session_id] = {
            "coupons": coupons,
            "current_page": 0,
            "timestamp": time.time(),
            "sitename": sitename
        }
        async def format_page(page_idx):
            start_index = page_idx * 5
            text = f"**Successfully Found {len(coupons)} Coupons For {sitename.upper()} ✅**\n\n"
            for i, item in enumerate(pages[page_idx], start=start_index + 1):
                title = item.get("title", "No title available")
                code = item.get("code", "No code available")
                text += f"**{i}.**\n**⊗ Title:** {title}\n**⊗ Coupon Code:** `{code}`\n\n"
            return text.strip()
        buttons = []
        if len(pages) > 1:
            buttons.append([Button.inline("➡️ Next", f"cpn_next_{session_id}")])
        try:
            await loading.edit(text=await format_page(0), parse_mode='markdown', buttons=buttons)
        except Exception as e:
            LOGGER.error(f"[CPN] Button edit error: {e}")
            await loading.edit(text=await format_page(0), parse_mode='markdown')
    @app.on(events.CallbackQuery(pattern=b'^cpn_(next|prev)_(.+)$'))
    async def handle_pagination(event):
        action, session_id = event.data.decode().split("_", 2)[1:]
        user_id = event.sender_id
        session = pagination_sessions.get(session_id)
        if not session or time.time() - session["timestamp"] > 20:
            await event.answer("❌ Session Expired. Try Again.", alert=True)
            if session_id in pagination_sessions:
                del pagination_sessions[session_id]
            return
        try:
            coupons = session["coupons"]
            sitename = session["sitename"]
            pages = [coupons[i:i + 5] for i in range(0, len(coupons), 5)]
            page = session["current_page"]
            if action == "next" and page < len(pages) - 1:
                session["current_page"] += 1
            elif action == "prev" and page > 0:
                session["current_page"] -= 1
            page = session["current_page"]
            session["timestamp"] = time.time()
            async def format_page(page_idx):
                start_index = page_idx * 5
                text = f"**Successfully Found {len(coupons)} Coupons For {sitename.upper()} ✅**\n\n"
                for i, item in enumerate(pages[page_idx], start=start_index + 1):
                    title = item.get("title", "No title available")
                    code = item.get("code", "No code available")
                    text += f"**{i}.**\n**⊗ Title:** {title}\n**⊗ Coupon Code:** `{code}`\n\n"
                return text.strip()
            buttons = []
            if page > 0:
                buttons.append(Button.inline("⬅️ Previous", f"cpn_prev_{session_id}"))
            if page < len(pages) - 1:
                buttons.append(Button.inline("➡️ Next", f"cpn_next_{session_id}"))
            await event.edit(text=await format_page(page), parse_mode='markdown', buttons=buttons if buttons else None)
            await event.answer()
        except Exception as e:
            LOGGER.error(f"[CPN] Pagination error for user {user_id}: {e}")
            await notify_admin(app, "/cpn-pagination", e, event)
            await event.answer("❌ Something went wrong!", alert=True)

    return app