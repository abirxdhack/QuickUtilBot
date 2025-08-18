import aiohttp
import asyncio
from telethon import events
from config import COMMAND_PREFIX, DOMAIN_API_KEY, DOMAIN_API_URL, DOMAIN_CHK_LIMIT, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

async def format_date(date_str):
    return date_str

async def get_domain_info(domain: str) -> str:
    params = {
        "apiKey": DOMAIN_API_KEY,
        "domainName": domain,
        "outputFormat": "JSON"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(DOMAIN_API_URL, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                LOGGER.info(f"Response for domain {domain}: {data}")
                if data.get("WhoisRecord"):
                    whois_record = data["WhoisRecord"]
                    status = whois_record.get("status", "Unknown").lower()
                    data_error = whois_record.get("dataError", "")
                    registrar = whois_record.get("registrarName", "Unknown")
                    registration_date = await format_date(whois_record.get("createdDate", "Unknown"))
                    expiration_date = await format_date(whois_record.get("expiresDate", "Unknown"))
                    if status == "available" or data_error == "MISSING_WHOIS_DATA" or not whois_record.get("registryData"):
                        return f"**✅ {domain}**: Available for registration!"
                    else:
                        return (
                            f"**🔒 {domain}**: Already registered.\n"
                            f"**Registrar:** `{registrar}`\n"
                            f"**Registration Date:** `{registration_date}`\n"
                            f"**Expiration Date:** `{expiration_date}`"
                        )
                else:
                    return f"**✅ {domain}**: Available for registration!"
    except aiohttp.ClientError as e:
        LOGGER.error(f"Failed to fetch info for domain {domain}: {e}")
        await notify_admin(None, f"{COMMAND_PREFIX}dmn", e, None)
        return f"**❌ Sorry Bro Domain API Dead**"
    except Exception as e:
        LOGGER.error(f"Exception occurred while fetching info for domain {domain}: {e}")
        await notify_admin(None, f"{COMMAND_PREFIX}dmn", e, None)
        return f"**❌ Sorry Bro Domain Check API Dead**"

async def domain_info_handler(event):
    client = event.client
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY)
        return
    command = event.message.text.split()
    if len(command) < 2:
        await event.respond("**❌ Please provide at least one valid domain name.**", parse_mode="markdown")
        return
    domains = command[1:]
    if len(domains) > DOMAIN_CHK_LIMIT:
        await event.respond(f"**❌ You can check up to {DOMAIN_CHK_LIMIT} domains at a time.**", parse_mode="markdown")
        return
    progress_message = await event.respond("**Fetching domain information...✨**", parse_mode="markdown")
    try:
        results = await asyncio.gather(*[get_domain_info(domain) for domain in domains], return_exceptions=True)
        result_message = []
        for domain, result in zip(domains, results):
            if isinstance(result, Exception):
                LOGGER.error(f"Error processing domain {domain}: {result}")
                await notify_admin(client, f"{COMMAND_PREFIX}dmn", result, event.message)
                result_message.append(f"**❌ {domain}**: Failed to check domain")
            else:
                result_message.append(result)
        result_message = "\n\n".join(result_message)
        if all("✅" in result for result in result_message.split("\n\n")):
            await progress_message.edit(result_message, parse_mode="markdown")
            return
        chat = await event.get_chat()
        if event.is_private:
            user_full_name = f"{event.sender.first_name} {event.sender.last_name or ''}".strip()
            user_info = f"\n**Domain Info Grab By:** [{user_full_name}](tg://user?id={event.sender_id})"
        else:
            group_name = chat.title or "this group"
            group_url = f"https://t.me/{chat.username}" if hasattr(chat, "username") and chat.username else "this group"
            user_info = f"\n**Domain Info Grab By:** [{group_name}]({group_url})"
        result_message += user_info
        await progress_message.edit(f"**Domain Check Results:**\n\n{result_message}", parse_mode="markdown")
    except Exception as e:
        LOGGER.error(f"Error processing domain check: {e}")
        await notify_admin(client, f"{COMMAND_PREFIX}dmn", e, event.message)
        await progress_message.edit("**❌ Sorry Bro Domain Check API Dead**", parse_mode="markdown")

def setup_dmn_handlers(app):
    app.add_event_handler(
        domain_info_handler,
        events.NewMessage(pattern=f"^{COMMAND_PREFIX}(dmn|\.dmn)(?:\s|$)")
    )