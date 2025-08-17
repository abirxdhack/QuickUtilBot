#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
import asyncio
import aiohttp
from telethon import TelegramClient, events
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonRow
from telethon.tl.custom import Button
from config import BIN_KEY, COMMAND_PREFIX, UPDATE_CHANNEL_URL, BAN_REPLY
from utils import notify_admin, LOGGER
from core import banned_users
import pycountry
import re

async def get_single_bin_info(bin, client, event):
    headers = {'x-api-key': BIN_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://data.handyapi.com/bin/{bin}", headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_msg = f"API returned status code {response.status}"
                    LOGGER.error(error_msg)
                    return None
    except Exception as e:
        error_msg = f"Error fetching BIN info: {str(e)}"
        LOGGER.error(error_msg)
        await notify_admin(client, "/bin", e, event)
        return None

def get_flag(country_code, client=None, event=None):
    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if not country:
            raise ValueError("Invalid country code")
        country_name = country.name
        flag_emoji = chr(0x1F1E6 + ord(country_code[0]) - ord('A')) + chr(0x1F1E6 + ord(country_code[1]) - ord('A'))
        return country_name, flag_emoji
    except Exception as e:
        error_msg = f"Error in get_flag: {str(e)}"
        LOGGER.error(error_msg)
        if client and event:
            asyncio.create_task(notify_admin(client, "/bin", e, event))
        return "Unknown", "🚨"

def setup_bin_handler(app: TelegramClient):
    
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}bin(?:\\s+(.+))?$'))
    async def bin_handler(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(
                BAN_REPLY,
                parse_mode='md',
                buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
            )
            return
        
        LOGGER.info(f"Received /bin command from user: {user_id}")
        
  
        args = event.pattern_match.group(1)
        if not args:
            await event.respond(
                "**Please Provide A Valid Bin ❌**",
                parse_mode='md',
                buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
            )
            return
        
      
        bin_digits = re.sub(r'[^0-9]', '', args.strip())
        if not bin_digits or len(bin_digits) < 6:
            await event.respond(
                "**Sorry Bin Must Be 6-15 Digits❌**",
                parse_mode='md',
                buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
            )
            return
        
        
        clean_bin_for_api = bin_digits[:6]
        
        
        progress_message = await event.respond(
            "**Fetching Bin Details...**",
            parse_mode='md',
            buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
        )
        
       
        bin_info = await get_single_bin_info(clean_bin_for_api, event.client, event)
        
        
        await event.client.delete_messages(event.chat_id, progress_message)
        
        if not bin_info or bin_info.get("Status") != "SUCCESS":
            await event.respond(
                "**Invalid Bin Provided ❌**",
                parse_mode='md',
                buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
            )
            return
        
        # Check if country info is available
        if not isinstance(bin_info.get("Country"), dict):
            await event.respond(
                "**Invalid Bin Provided ❌**",
                parse_mode='md',
                buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
            )
            return
        
       
        bank = bin_info.get("Issuer", "Unknown")
        country_name = bin_info["Country"].get("Name", "Unknown")
        card_type = bin_info.get("Type", "Unknown")
        card_scheme = bin_info.get("Scheme", "Unknown")
        country_code = bin_info["Country"].get("A2", "")
        
        
        if country_code:
            country_name, flag_emoji = get_flag(country_code, event.client, event)
        else:
            country_name, flag_emoji = "Unknown", "🚨"
        
        
        bank_text = bank.upper() if bank != "Unknown" else "Unknown"
        bin_info_text = f"{card_scheme.upper()} - {card_type.upper()}"
        
        response_text = (
            f"**🔍 BIN Details From Smart Database 📋**\n"
            f"**━━━━━━━━━━━━━━━━━━**\n"
            f"**• BIN:** `{clean_bin_for_api}`\n"
            f"**• INFO:** {bin_info_text}\n"
            f"**• BANK:** {bank_text}\n"
            f"**• COUNTRY:** {country_name.upper()} {flag_emoji}\n"
            f"**━━━━━━━━━━━━━━━━━━**\n"
            f"**🔍 Smart BIN Checker → Activated ✅**"
        )
        
       
        await event.respond(
            response_text,
            parse_mode='md',
            buttons=ReplyInlineMarkup([KeyboardButtonRow([Button.url("Join For Updates", UPDATE_CHANNEL_URL)])])
        )
        

        LOGGER.info(f"BIN check completed for {clean_bin_for_api} by user {user_id}")
