#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
import os
import aiohttp
import asyncio
import json
from telethon import TelegramClient, events
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonRow
from telethon.tl.custom import Button
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

url = "https://smartbinancep2p-production-af69.up.railway.app/api/v1/p2p"

async def fetch_sellers(asset, fiat, trade_type, pay_type, client=None, event=None):
    params = {
        "asset": asset,
        "pay_type": pay_type,
        "trade_type": trade_type,
        "limit": 100
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    LOGGER.error(f"Error fetching data: {response.status}")
                    raise Exception(f"API request failed with status {response.status}")
                data = await response.json()
                if not data.get("success", False):
                    LOGGER.error(f"API returned success: false")
                    raise Exception("API returned success: false")
                LOGGER.info(f"Successfully fetched {len(data['data'])} sellers for {asset} in {fiat}")
                return data['data']
    except Exception as e:
        LOGGER.error(f"Exception occurred while fetching data: {e}")
        if client and event:
            await notify_admin(client, "/p2p", e, event)
        return []

def process_sellers_to_json(sellers, fiat):
    processed = []
    for seller in sellers:
        processed.append({
            "seller": seller.get("seller_name", "Unknown"),
            "price": f"{seller['price']} {fiat}",
            "available_usdt": f"{seller['available_amount']} USDT",
            "min_amount": f"{seller['min_order_amount']} {fiat}",
            "max_amount": f"{seller['max_order_amount']} {fiat}",
            "completion_rate": f"{seller['completion_rate']}%",
            "trade_method": ", ".join(seller['payment_methods']) if seller['payment_methods'] else "Unknown"
        })
    return processed

async def save_to_json_file(data, filename, client=None, event=None):
    try:
        os.makedirs('data', exist_ok=True)
        path = os.path.join('data', filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        LOGGER.info(f"Data saved to {path}")
        asyncio.create_task(delete_file_after_delay(path, 10*60))
    except Exception as e:
        LOGGER.error(f"Error saving to {filename}: {e}")
        if client and event:
            await notify_admin(client, "/p2p", e, event)
        raise

async def load_from_json_file(filename, client=None, event=None):
    try:
        path = os.path.join('data', filename)
        if not os.path.exists(path):
            LOGGER.error(f"File not found: {path}")
            raise Exception("File not found")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        LOGGER.error(f"Error loading from {filename}: {e}")
        if client and event:
            await notify_admin(client, "/p2p", e, event)
        raise

async def delete_file_after_delay(file_path, delay):
    await asyncio.sleep(delay)
    if os.path.exists(file_path):
        os.remove(file_path)
        LOGGER.info(f"Deleted file {file_path} after delay")

def generate_message(sellers, page, fiat):
    start = (page - 1) * 10
    end = start + 10
    selected_sellers = sellers[start:end]
    message = f"💱 **Latest P2P USDT Trades for {fiat}** 👇\n\n"
    for i, seller in enumerate(selected_sellers, start=start + 1):
        message += (f"**{i}. Name:** {seller['seller']}\n"
                    f"**Price:** {seller['price']}\n"
                    f"**Payment Method:** {seller['trade_method']}\n"
                    f"**Crypto Amount:** {seller['available_usdt']}\n"
                    f"**Limit:** {seller['min_amount']} - {seller['max_amount']}\n\n")
    return message

def setup_p2p_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}p2p(?:\\s+(.+))?'))
    async def p2p_handler(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='md')
            LOGGER.info(f"Banned user {user_id} attempted to use /p2p")
            return
        
        try:
            user_input = event.pattern_match.group(1).strip() if event.pattern_match.group(1) else None
            if not user_input:
                await event.respond("**Please provide a currency. e.g. /p2p BDT or /p2p SAR**", parse_mode='md')
                LOGGER.warning(f"Invalid command format: {event.message.text}")
                return
            
            fiat = user_input.upper()
            asset = "USDT"
            trade_type = "SELL"
            pay_type = fiat
            filename = f"p2p_{asset}_{fiat}.json"
            LOGGER.info(f"Fetching P2P trades for {asset} in {fiat} using {pay_type}")
            loading_message = await event.respond("**🔄 Fetching All P2P Trades**", parse_mode='md')
            
            sellers = await fetch_sellers(asset, fiat, trade_type, pay_type, client=event.client, event=event)
            if not sellers:
                await event.client.edit_message(loading_message, "**❌ No sellers found or API error occurred**", parse_mode='md')
                LOGGER.warning(f"No sellers found for {asset} in {fiat}")
                return
            
            processed_sellers = process_sellers_to_json(sellers, fiat)
            await save_to_json_file(processed_sellers, filename, client=event.client, event=event)
            message_text = generate_message(processed_sellers, 1, fiat)
            keyboard = ReplyInlineMarkup([KeyboardButtonRow([Button.inline("▶️ Next", f"nextone_1_{filename}")])])
            await event.client.edit_message(loading_message, message_text, parse_mode='md', buttons=keyboard)
            LOGGER.info(f"Sent P2P trades for {asset} in {fiat} to chat {event.chat_id}")
        
        except Exception as e:
            LOGGER.error(f"Exception in p2p_handler: {e}")
            await event.client.edit_message(loading_message, "**Sorry, an error occurred while fetching P2P data ❌**", parse_mode='md')
            await notify_admin(event.client, "/p2p", e, event)
    
    @app.on(events.CallbackQuery(pattern=r"nextone_\d+_(.+\.json)"))
    async def next_page(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.edit(BAN_REPLY, parse_mode='md')
            LOGGER.info(f"Banned user {user_id} attempted to use next page for {event.data.decode()}")
            return
        
        try:
            current_page = int(event.data.decode().split('_', 2)[1])
            filename = event.data.decode().split('_', 2)[2]
            sellers = await load_from_json_file(filename, client=event.client, event=event)
            fiat = filename.split('_')[2].split('.')[0]
            next_page = current_page + 1
            if (next_page - 1) * 10 >= len(sellers):
                await event.answer("❌ Data Expired Please Request Again To Get Latest Database")
                LOGGER.info(f"Data expired for next page {next_page} in chat {event.chat_id}")
                return
            message_text = generate_message(sellers, next_page, fiat)
            prev_button = Button.inline("◀️ Previous", f"prevone_{next_page}_{filename}")
            next_button = Button.inline("▶️ Next", f"nextone_{next_page}_{filename}")
            keyboard = ReplyInlineMarkup([KeyboardButtonRow([prev_button, next_button])])
            await event.edit(message_text, parse_mode='md', buttons=keyboard)
            await event.answer()
            LOGGER.info(f"Updated to next page {next_page} for {filename} in chat {event.chat_id}")
        except Exception as e:
            LOGGER.error(f"Exception in next_page: {e}")
            await event.edit("**Sorry, an error occurred while fetching data ❌**", parse_mode='md')
            await notify_admin(event.client, "/p2p next", e, event)
    
    @app.on(events.CallbackQuery(pattern=r"prevone_\d+_(.+\.json)"))
    async def prev_page(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.edit(BAN_REPLY, parse_mode='md')
            LOGGER.info(f"Banned user {user_id} attempted to use previous page for {event.data.decode()}")
            return
        
        try:
            current_page = int(event.data.decode().split('_', 2)[1])
            filename = event.data.decode().split('_', 2)[2]
            sellers = await load_from_json_file(filename, client=event.client, event=event)
            fiat = filename.split('_')[2].split('.')[0]
            prev_page = current_page - 1
            if prev_page < 1:
                await event.answer("❌ Data Expired Please Request Again To Get Latest Database")
                LOGGER.info(f"Data expired for previous page {prev_page} in chat {event.chat_id}")
                return
            message_text = generate_message(sellers, prev_page, fiat)
            prev_button = Button.inline("◀️ Previous", f"prevone_{prev_page}_{filename}")
            next_button = Button.inline("▶️ Next", f"nextone_{prev_page}_{filename}")
            keyboard = ReplyInlineMarkup([KeyboardButtonRow([prev_button, next_button])])
            await event.edit(message_text, parse_mode='md', buttons=keyboard)
            await event.answer()
            LOGGER.info(f"Updated to previous page {prev_page} for {filename} in chat {event.chat_id}")
        except Exception as e:
            LOGGER.error(f"Exception in prev_page: {e}")
            await event.edit("**Sorry, an error occurred while fetching data ❌**", parse_mode='md')
            await notify_admin(event.client, "/p2p prev", e, event)