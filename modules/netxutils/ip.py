import aiohttp
import asyncio
from telethon import events
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

async def get_ip_info(ip: str) -> str:
    url = f"https://ipinfo.io/{ip}/json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
        ip = data.get("ip", "Unknown")
        asn = data.get("org", "Unknown")
        isp = data.get("org", "Unknown")
        country = data.get("country", "Unknown")
        city = data.get("city", "Unknown")
        timezone = data.get("timezone", "Unknown")
        fraud_score = 0
        risk_level = "low" if fraud_score < 50 else "high"
        details = (
            f"**YOUR IP INFORMATION 🌐**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"**IP:** `{ip}`\n"
            f"**ASN:** `{asn}`\n"
            f"**ISP:** `{isp}`\n"
            f"**Country City:** `{country} {city}`\n"
            f"**Timezone:** `{timezone}`\n"
            f"**IP Fraud Score:** `{fraud_score}`\n"
            f"**Risk LEVEL:** `{risk_level} Risk`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )
        return details
    except aiohttp.ClientError as e:
        LOGGER.error(f"Failed to fetch IP info for {ip}: {e}")
        await notify_admin(None, f"{COMMAND_PREFIX}ip", e, None)
        return "Invalid IP address or API error"
    except Exception as e:
        LOGGER.error(f"Unexpected error fetching IP info for {ip}: {e}")
        await notify_admin(None, f"{COMMAND_PREFIX}ip", e, None)
        return "Invalid IP address or API error"

async def ip_info_handler(event):
    client = event.client
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY)
        return
    command = event.message.text.split()
    if len(command) <= 1:
        await event.respond("**❌ Please provide a single IP address.**", parse_mode="markdown", link_preview=False)
        return
    ip = command[1]
    fetching_msg = await event.respond("**Fetching IP Info Please Wait.....✨**", parse_mode="markdown", link_preview=False)
    try:
        details = await get_ip_info(ip)
        if details.startswith("Invalid"):
            raise Exception("Failed to retrieve IP information")
        chat = await event.get_chat()
        if event.is_private:
            user_full_name = f"{event.sender.first_name} {event.sender.last_name or ''}".strip()
            user_info = f"\n**Ip-Info Grab By:** [{user_full_name}](tg://user?id={event.sender_id})"
        else:
            group_name = chat.title or "this group"
            group_url = f"https://t.me/{chat.username}" if hasattr(chat, "username") and chat.username else "this group"
            user_info = f"\n**Ip-Info Grab By:** [{group_name}]({group_url})"
        details += user_info
        await fetching_msg.edit(details, parse_mode="markdown", link_preview=False)
    except Exception as e:
        LOGGER.error(f"Error processing IP info for {ip}: {e}")
        await notify_admin(client, f"{COMMAND_PREFIX}ip", e, event.message)
        await fetching_msg.edit("**❌ Sorry Bro IP Info API Dead**", parse_mode="markdown", link_preview=False)

def setup_ip_handlers(app):
    app.add_event_handler(
        ip_info_handler,
        events.NewMessage(pattern=f"^{COMMAND_PREFIX}(ip|\.ip)(?:\s|$)")
    )