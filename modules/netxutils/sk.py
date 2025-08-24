#Copyright @ISmartCoder
#Updates Channel https://t.me/TheSmartDev
import aiohttp
from telethon import events
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

async def verify_stripe_key(stripe_key: str) -> str:
    url = "https://api.stripe.com/v1/account"
    headers = {
        "Authorization": f"Bearer {stripe_key}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return "Live ✅"
                else:
                    return "SK KEY REVOKED ❌"
    except Exception as e:
        LOGGER.error(f"Error verifying Stripe key: {e}")
        return "SK KEY REVOKED ❌"

async def get_stripe_key_info(stripe_key: str) -> str:
    url = "https://api.stripe.com/v1/account"
    balance_url = "https://api.stripe.com/v1/balance"
    headers = {
        "Authorization": f"Bearer {stripe_key}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return "SK KEY REVOKED ❌"
                data = await response.json()
            async with session.get(balance_url, headers=headers) as balance_response:
                balance_data = await balance_response.json() if balance_response.status == 200 else {}
        available_balance = balance_data.get("available", [{}])[0].get("amount", 0) / 100 if balance_data else 0
        currency = balance_data.get("available", [{}])[0].get("currency", "N/A").upper() if balance_data else "N/A"
        details = (
            f"**み SK Key Authentication ↝ Successful ✅**\n"
            f"**━━━━━━━━━━━━━━━━━━━━━━**\n"
            f"**⊗ SK Key Status** ↝ {'Live ✅' if data.get('charges_enabled') else 'Restricted ❌'}\n"
            f"**⊗ Account ID** ↝ {data.get('id', 'N/A')}\n"
            f"**⊗ Email** ↝ {data.get('email', 'N/A')}\n"
            f"**⊗ Business Name** ↝ {data.get('business_profile', {}).get('name', 'N/A')}\n"
            f"**⊗ Charges Enabled** ↝ {'Yes ✅' if data.get('charges_enabled') else 'No ❌'}\n"
            f"**⊗ Payouts Enabled** ↝ {'Yes ✅' if data.get('payouts_enabled') else 'No ❌'}\n"
            f"**⊗ Account Type** ↝ {data.get('type', 'N/A').capitalize()}\n"
            f"**⊗ Balance** ↝ {available_balance} {currency}\n"
            f"**━━━━━━━━━━━━━━━━━━━━━━**\n"
            f"**⌁ Thank You For Using Smart Tool ↯**"
        )
        return details
    except Exception as e:
        LOGGER.error(f"Error fetching Stripe key info: {e}")
        return "SK KEY REVOKED ❌"

async def stripe_key_handler(event):
    client = event.client
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY)
        return
    command = event.message.text.split()
    if len(command) <= 1:
        await event.respond("**❌ Please provide a Stripe key. Usage: /sk [Stripe Key]**", parse_mode="markdown", link_preview=False)
        return
    stripe_key = command[1]
    fetching_msg = await event.respond("**Processing Your Request...✨**", parse_mode="markdown", link_preview=False)
    try:
        result = await verify_stripe_key(stripe_key)
        if result == "SK KEY REVOKED ❌":
            user = await client.get_entity(user_id)
            user_name = f"{user.first_name} {user.last_name or ''}".strip()
            user_link = f"[{user_name}](tg://user?id={user_id})"
            await fetching_msg.edit(
                f"⊗ **SK ➺** `{stripe_key}`\n"
                f"⊗ **Response: SK KEY REVOKED ❌**\n"
                f"⊗ **Checked By ➺** {user_link}",
                parse_mode="markdown",
                link_preview=False
            )
        else:
            await fetching_msg.edit(result, parse_mode="markdown", link_preview=False)
    except Exception as e:
        LOGGER.error(f"Error in stripe_key_handler: {e}")
        user = await client.get_entity(user_id)
        user_name = f"{user.first_name} {user.last_name or ''}".strip()
        user_link = f"[{user_name}](tg://user?id={user_id})"
        await fetching_msg.edit(
            f"⊗ **SK ➺** `{stripe_key}`\n"
            f"⊗ **Response: SK KEY REVOKED ❌**\n"
            f"⊗ **Checked By ➺** {user_link}",
            parse_mode="markdown",
            link_preview=False
        )
        await notify_admin(client, "/sk", e, event.message)

async def stripe_key_info_handler(event):
    client = event.client
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY)
        return
    command = event.message.text.split()
    if len(command) <= 1:
        await event.respond("**❌ Please provide a Stripe key. Usage: /skinfo [Stripe Key]**", parse_mode="markdown", link_preview=False)
        return
    stripe_key = command[1]
    fetching_msg = await event.respond("**Processing Your Request...✨**", parse_mode="markdown", link_preview=False)
    try:
        result = await get_stripe_key_info(stripe_key)
        if result == "SK KEY REVOKED ❌":
            user = await client.get_entity(user_id)
            user_name = f"{user.first_name} {user.last_name or ''}".strip()
            user_link = f"[{user_name}](tg://user?id={user_id})"
            await fetching_msg.edit(
                f"⊗ **SK ➺** `{stripe_key}`\n"
                f"⊗ **Response: SK KEY REVOKED ❌**\n"
                f"⊗ **Checked By ➺** {user_link}",
                parse_mode="markdown",
                link_preview=False
            )
        else:
            await fetching_msg.edit(result, parse_mode="markdown", link_preview=False)
    except Exception as e:
        LOGGER.error(f"Error in stripe_key_info_handler: {e}")
        user = await client.get_entity(user_id)
        user_name = f"{user.first_name} {user.last_name or ''}".strip()
        user_link = f"[{user_name}](tg://user?id={user_id})"
        await fetching_msg.edit(
            f"⊗ **SK ➺** `{stripe_key}`\n"
            f"⊗ **Response: SK KEY REVOKED ❌**\n"
            f"⊗ **Checked By ➺** {user_link}",
            parse_mode="markdown",
            link_preview=False
        )
        await notify_admin(client, "/skinfo", e, event.message)

def setup_sk_handlers(app):
    app.add_event_handler(
        stripe_key_handler,
        events.NewMessage(pattern=f"^{COMMAND_PREFIX}(sk|\.sk)(?:\s|$)")
    )
    app.add_event_handler(
        stripe_key_info_handler,
        events.NewMessage(pattern=f"^{COMMAND_PREFIX}(skinfo|\.skinfo)(?:\s|$)")
    )
