#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
import os
import aiohttp
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonRow
from telethon.tl.custom import Button
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

BASE_URL = "https://api.binance.com/api/v3/ticker/24hr"

async def fetch_crypto_data():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(BASE_URL) as response:
                response.raise_for_status()
                LOGGER.info("Successfully fetched crypto data from Binance API")
                return await response.json()
    except Exception as e:
        LOGGER.error(f"Failed to fetch crypto data: {e}")
        raise

def get_top_gainers(data, top_n=5):
    return sorted(data, key=lambda x: float(x['priceChangePercent']), reverse=True)[:top_n]

def get_top_losers(data, top_n=5):
    return sorted(data, key=lambda x: float(x['priceChangePercent']))[:top_n]

def format_crypto_info(data, start_index=0):
    result = ""
    for idx, item in enumerate(data, start=start_index + 1):
        result += (
            f"{idx}. Symbol: {item['symbol']}\n"
            f" Change: {item['priceChangePercent']}%\n"
            f" Last Price: {item['lastPrice']}\n"
            f" 24h High: {item['highPrice']}\n"
            f" 24h Low: {item['lowPrice']}\n"
            f" 24h Volume: {item['volume']}\n"
            f" 24h Quote Volume: {item['quoteVolume']}\n\n"
        )
    return result

def setup_binance_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(?:gainers|losers)'))
    async def handle_command(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='html')
            LOGGER.info(f"Banned user {user_id} attempted to use /{event.pattern_match.group(0).split()[0]}")
            return
        
        command = event.pattern_match.group(0).split()[0].lstrip('/')
        fetching_message = await event.respond(f"Fetching {command}...", parse_mode='html')
        
        try:
            data = await fetch_crypto_data()
            top_n = 5
            if command == "gainers":
                top_cryptos = get_top_gainers(data, top_n)
                title = "Gainers"
            else:
                top_cryptos = get_top_losers(data, top_n)
                title = "Losers"
            formatted_info = format_crypto_info(top_cryptos)
            await event.client.delete_messages(event.chat_id, fetching_message)
            response_message = f"List Of Top {title}:\n\n{formatted_info}"
            
            keyboard = ReplyInlineMarkup([KeyboardButtonRow([Button.inline("Next", f"{command}_1")])])
            await event.respond(response_message, parse_mode='html', buttons=keyboard)
            LOGGER.info(f"Sent top {title.lower()} to chat {event.chat_id}")
        except Exception as e:
            await event.client.delete_messages(event.chat_id, fetching_message)
            await event.respond("Error: Unable to fetch data from Binance API", parse_mode='html')
            LOGGER.error(f"Error processing /{command}: {e}")
            await notify_admin(event.client, f"/{command}", e, event)
    
    @app.on(events.CallbackQuery(pattern=r"^(gainers|losers)_\d+$"))
    async def handle_pagination(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.edit(BAN_REPLY, parse_mode='html')
            LOGGER.info(f"Banned user {user_id} attempted to use pagination for {event.data.decode()}")
            return
        
        command, page = event.data.decode().split('_')
        page = int(page)
        next_page = page + 1
        prev_page = page - 1
        
        try:
            data = await fetch_crypto_data()
            top_n = 5
            if command == "gainers":
                top_cryptos = get_top_gainers(data, top_n * next_page)[(page-1)*top_n:page*top_n]
                title = "Gainers"
            else:
                top_cryptos = get_top_losers(data, top_n * next_page)[(page-1)*top_n:page*top_n]
                title = "Losers"
            formatted_info = format_crypto_info(top_cryptos, start_index=(page-1)*top_n)
            response_message = f"List Of Top {title}:\n\n{formatted_info}"
            
            keyboard_buttons = []
            if prev_page > 0:
                keyboard_buttons.append(Button.inline("Previous", f"{command}_{prev_page}"))
            if len(top_cryptos) == top_n:
                keyboard_buttons.append(Button.inline("Next", f"{command}_{next_page}"))
            keyboard = ReplyInlineMarkup([KeyboardButtonRow(keyboard_buttons)])
            
            await event.edit(response_message, parse_mode='html', buttons=keyboard)
            LOGGER.info(f"Updated pagination for {command} (page {page}) in chat {event.chat_id}")
        except Exception as e:
            await event.edit("Error: Unable to fetch data from Binance API", parse_mode='html')
            LOGGER.error(f"Error in pagination for {command} (page {page}): {e}")
            await notify_admin(event.client, f"/{command} pagination", e, event)