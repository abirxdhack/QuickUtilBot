#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
import os
import aiohttp
import asyncio
from telethon import TelegramClient, events
from config import BIN_KEY, COMMAND_PREFIX, BAN_REPLY
from utils import notify_admin, LOGGER
from core import banned_users

async def get_bin_info(bin, client, event):
    headers = {'x-api-key': BIN_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://data.handyapi.com/bin/{bin}", headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    LOGGER.error(f"API returned status code {response.status}")
                    raise Exception(f"API returned status code {response.status}")
    except Exception as e:
        LOGGER.error(f"Error retrieving info for BIN: {bin} - {e}")
        await notify_admin(client, "/mbin", e, event)
        return None

def get_flag_emoji(country_code):
    if len(country_code) == 2:
        return chr(0x1F1E6 + ord(country_code[0]) - ord('A')) + chr(0x1F1E6 + ord(country_code[1]) - ord('A'))
    return ''

def setup_mbin_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}mbin(?:\\s+(.+))?'))
    async def bin_handler(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        LOGGER.info(f"Received /mbin command from user: {user_id}")
        bins = []
        
        reply_message = await event.get_reply_message()
        if reply_message and reply_message.document:
            file_name = await event.client.download_media(reply_message, file="temp_file.txt")
            with open(file_name, 'r') as file:
                bins = [line.strip() for line in file.readlines() if line.strip()]
            os.remove(file_name)
            LOGGER.info(f"BINs extracted from the uploaded file by user: {user_id}")
        else:
            input_text = event.pattern_match.group(1).strip() if event.pattern_match.group(1) else None
            if not input_text:
                await event.respond("**Provide a valid BIN (6 digits) or reply to a text file containing BINs❌**", parse_mode='md')
                LOGGER.warning(f"Invalid BIN input by user: {user_id}")
                return
            bins = input_text.split()
        
        if len(bins) > 20:
            await event.respond("**You can check up to 20 BINs at a time❌**", parse_mode='md')
            LOGGER.warning(f"User {user_id} tried to fetch more than 20 BINs")
            return
        
        invalid_bins = [bin for bin in bins if len(bin) != 6 or not bin.isdigit()]
        if invalid_bins:
            await event.respond(f"**Invalid BINs provided ❌** {' '.join(invalid_bins)}", parse_mode='md')
            LOGGER.warning(f"Invalid BIN formats from user: {user_id} - {invalid_bins}")
            return
        
        fetching_message = await event.respond("**Fetching BINs Info...✨**", parse_mode='md')
        results = []
        
        async def fetch_bin_info(bin):
            bin_info = await get_bin_info(bin, event.client, event)
            if isinstance(bin_info, dict):
                if bin_info.get('Status') == "SUCCESS":
                    country_code = bin_info.get('Country', {}).get('A2', '')
                    country_name = bin_info.get('Country', {}).get('Name', 'N/A')
                    flag_emoji = get_flag_emoji(country_code) if country_code else ''
                    info = f"• **BIN**: `{bin}`\n"
                    info += f"• **INFO**: {bin_info.get('CardTier', 'N/A')} - {bin_info.get('Type', 'N/A')} - {bin_info.get('Scheme', 'N/A')}\n"
                    info += f"• **BANK**: {bin_info.get('Issuer', 'N/A')}\n"
                    info += f"• **COUNTRY**: {country_name} {flag_emoji}\n\n"
                    return info
                else:
                    error_message = bin_info.get('Status', 'Unknown error')
                    LOGGER.error(f"Error for BIN: {bin} - {error_message}")
                    return f"• **BIN**: `{bin}`\n• **INFO**: {error_message}\n\n"
            else:
                LOGGER.error(f"Invalid bin_info format or response for BIN: {bin} - {bin_info}")
                return f"• **BIN**: `{bin}`\n• **INFO**: Not Found\n\n"
        
        tasks = [fetch_bin_info(bin) for bin in bins]
        results = await asyncio.gather(*tasks)
        response_text = "🔍 **BIN Details 📋**\n━━━━━━━━━━━━━━━━━━\n" + "".join(results)
        
        await event.client.edit_message(fetching_message, response_text, parse_mode='md')

        LOGGER.info(f"BIN info sent to user: {user_id}")
