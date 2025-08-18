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
                    return "**The Stripe key is live.**"
                else:
                    return "**The Stripe key is dead.**"
    except Exception as e:
        LOGGER.error(f"Error verifying Stripe key: {e}")
        return "**Error verifying Stripe key.**"

async def get_stripe_key_info(stripe_key: str) -> str:
    url = "https://api.stripe.com/v1/account"
    headers = {
        "Authorization": f"Bearer {stripe_key}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return "**Unable to retrieve information for the provided Stripe key.**"
                data = await response.json()
        details = (
            f"**Stripe Key Information:**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"**ID:** `{data.get('id', 'N/A')}`\n"
            f"**Email:** `{data.get('email', 'N/A')}`\n"
            f"**Country:** `{data.get('country', 'N/A')}`\n"
            f"**Business Name:** `{data.get('business_name', 'N/A')}`\n"
            f"**Type:** `{data.get('type', 'N/A')}`\n"
            f"**Payouts Enabled:** `{data.get('payouts_enabled', 'N/A')}`\n"
            f"**Details Submitted:** `{data.get('details_submitted', 'N/A')}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )
        return details
    except Exception as e:
        LOGGER.error(f"Error fetching Stripe key info: {e}")
        return "**Error retrieving Stripe key information.**"

async def stripe_key_handler(event):
    client = event.client
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY)
        return
    command = event.message.text.split()
    if len(command) <= 1:
        await event.respond("**❌Please provide a Stripe key. Usage: /sk [Stripe Key]**", parse_mode="markdown", link_preview=False)
        return
    stripe_key = command[1]
    fetching_msg = await event.respond("**Processing Your Request...✨**", parse_mode="markdown", link_preview=False)
    try:
        result = await verify_stripe_key(stripe_key)
        await fetching_msg.edit(result, parse_mode="markdown", link_preview=False)
    except Exception as e:
        LOGGER.error(f"Error in stripe_key_handler: {e}")
        await fetching_msg.edit("**Error processing Stripe key verification.**", parse_mode="markdown", link_preview=False)
        await notify_admin(client, "/sk", e, event.message)

async def stripe_key_info_handler(event):
    client = event.client
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY)
        return
    command = event.message.text.split()
    if len(command) <= 1:
        await event.respond("**❌Please provide a Stripe key. Usage: /skinfo [Stripe Key]**", parse_mode="markdown", link_preview=False)
        return
    stripe_key = command[1]
    fetching_msg = await event.respond("**Processing Your Request...✨**", parse_mode="markdown", link_preview=False)
    try:
        result = await get_stripe_key_info(stripe_key)
        await fetching_msg.edit(result, parse_mode="markdown", link_preview=False)
    except Exception as e:
        LOGGER.error(f"Error in stripe_key_info_handler: {e}")
        await fetching_msg.edit("**Error processing Stripe key information.**", parse_mode="markdown", link_preview=False)
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