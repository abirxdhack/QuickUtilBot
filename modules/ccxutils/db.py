import aiohttp
import asyncio
import json
import os
import pycountry
from telethon import TelegramClient, events
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonRow
from telethon.tl.custom import Button
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users
from telegraph import Telegraph
from datetime import datetime

country_url = "https://smartdb-production-9dbf.up.railway.app/api/bin"
bank_url = "https://smartdb-production-9dbf.up.railway.app/api/bin"
telegraph = Telegraph()

try:
    telegraph.create_account(
        short_name="SmartToolBot",
        author_name="SmartToolBot",
        author_url="https://t.me/TheSmartDev"
    )
except Exception as e:
    LOGGER.error(f"Failed to create or access Telegraph account: {e}")

async def fetch_bins(params, client=None, event=None, endpoint="country"):
    try:
        async with aiohttp.ClientSession() as session:
            url = country_url if endpoint == "country" else bank_url
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    LOGGER.error(f"Error fetching data: {response.status}")
                    raise Exception(f"API request failed with status {response.status}")
                data = await response.json()
                if data.get("status") != "SUCCESS" or not data.get("data"):
                    LOGGER.error(f"API returned no data")
                    raise Exception("API returned no data")
                LOGGER.info(f"Successfully fetched {len(data['data'])} bins for params {params}")
                return data['data']
    except Exception as e:
        LOGGER.error(f"Exception occurred while fetching data: {e}")
        if client and event:
            await notify_admin(client, "/bindb or /binbank", e, event)
        return []

def process_bins_to_json(bins):
    processed = []
    for bin_data in bins:
        processed.append({
            "bin": bin_data.get("bin", "Unknown"),
            "bank": bin_data.get("issuer", "Unknown"),
            "country_code": bin_data.get("country_code", "Unknown"),
            "brand": bin_data.get("brand", "Unknown"),
            "category": bin_data.get("category", "Unknown"),
            "type": bin_data.get("type", "Unknown"),
            "website": bin_data.get("website", "")
        })
    return processed

async def create_telegraph_page(content: str, part_number: int) -> list:
    try:
        current_date = datetime.now().strftime("%m-%d")
        title = f"Smart-Tool-Bin-DB---Part-{part_number}-{current_date}"
        truncated_content = content[:40000]
        max_size_bytes = 20 * 1024
        pages = []
        page_content = ""
        current_size = 0
        lines = truncated_content.splitlines(keepends=True)
        part_count = part_number
        
        for line in lines:
            line_bytes = line.encode('utf-8', errors='ignore')
            if current_size + len(line_bytes) > max_size_bytes and page_content:
                safe_content = page_content.replace('<', '&lt;').replace('>', '&gt;')
                html_content = f'<pre>{safe_content}</pre>'
                page = telegraph.create_page(
                    title=f"Smart-Tool-Bin-DB---Part-{part_count}-{current_date}",
                    html_content=html_content,
                    author_name="ISmartCoder",
                    author_url="https://t.me/TheSmartDev"
                )
                graph_url = page['url'].replace('telegra.ph', 'graph.org')
                pages.append(graph_url)
                page_content = ""
                current_size = 0
                part_count += 1
                await asyncio.sleep(0.5)
            page_content += line
            current_size += len(line_bytes)
        
        if page_content:
            safe_content = page_content.replace('<', '&lt;').replace('>', '&gt;')
            html_content = f'<pre>{safe_content}</pre>'
            page = telegraph.create_page(
                title=f"Smart-Tool-Bin-DB---Part-{part_count}-{current_date}",
                html_content=html_content,
                author_name="TheSmartDev",
                author_url="https://t.me/TheSmartDevs"
            )
            graph_url = page['url'].replace('telegra.ph', 'graph.org')
            pages.append(graph_url)
            await asyncio.sleep(0.5)
        return pages
    except Exception as e:
        LOGGER.error(f"Failed to create Telegraph page: {e}")
        return []

def generate_message(bins, identifier):
    message = f"**Smart Tool - Bin database 📋**\n**━━━━━━━━━━━━━━━━━━**\n\n"
    for bin_data in bins[:10]:
        message += (f"**BIN:** `{bin_data['bin']}`\n"
                    f"**Bank:** {bin_data['bank']}\n"
                    f"**Country:** {bin_data['country_code']}\n\n")
    return message

def generate_telegraph_content(bins):
    content = f"Smart Tool - Bin database 📋\n━━━━━━━━━━━━━━━━━━\n\n"
    for bin_data in bins:
        content += (f"BIN: {bin_data['bin']}\n"
                    f"Bank: {bin_data['bank']}\n"
                    f"Country: {bin_data['country_code']}\n\n")
    return content

async def bindb_handler(event):
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY, parse_mode='md')
        LOGGER.info(f"Banned user {user_id} attempted to use /bindb")
        return
    
    try:
        user_input = event.pattern_match.group(1).strip() if event.pattern_match.group(1) else None
        if not user_input:
            await event.respond("**Please provide a country name or code. e.g. /bindb BD or /bindb Bangladesh**", parse_mode='md')
            LOGGER.warning(f"Invalid command format: {event.message.text}")
            return
        
        country_input = user_input.upper()
        if country_input in ["UK", "UNITED KINGDOM"]:
            country_code = "GB"
            country_name = "United Kingdom"
        else:
            country = pycountry.countries.search_fuzzy(country_input)[0] if len(country_input) > 2 else pycountry.countries.get(alpha_2=country_input)
            if not country:
                await event.respond("**Invalid country name or code**", parse_mode='md')
                LOGGER.warning(f"Invalid country input: {country_input}")
                return
            country_code = country.alpha_2.upper()
            country_name = country.name
        
        LOGGER.info(f"Fetching BINs for country {country_name} ({country_code})")
        loading_message = await event.respond(f"**Finding Bins With Country {country_name}...**", parse_mode='md')
        params = {"country": country_code, "limit": 8000}
        bins = await fetch_bins(params, client=event.client, event=event, endpoint="country")
        
        if not bins:
            await event.client.edit_message(loading_message, "**Sorry No Bins Found**", parse_mode='md')
            LOGGER.warning(f"No bins found for country {country_code}")
            return
        
        processed_bins = process_bins_to_json(bins)
        message_text = generate_message(processed_bins, country_code)
        keyboard = None
        if len(processed_bins) > 10:
            bins_content = generate_telegraph_content(processed_bins[10:])
            content_size = len(bins_content.encode('utf-8'))
            telegraph_urls = await create_telegraph_page(bins_content, part_number=1)
            if telegraph_urls:
                buttons = []
                if content_size <= 20 * 1024:
                    buttons.append(KeyboardButtonRow([Button.url("Full Output", telegraph_urls[0])]))
                else:
                    for i in range(0, len(telegraph_urls), 2):
                        row = [Button.url(f"Output {i+1}", telegraph_urls[i])]
                        if i + 1 < len(telegraph_urls):
                            row.append(Button.url(f"Output {i+2}", telegraph_urls[i+1]))
                        buttons.append(KeyboardButtonRow(row))
                keyboard = ReplyInlineMarkup(buttons)
        
        await event.client.edit_message(loading_message, message_text, parse_mode='md', buttons=keyboard)
        LOGGER.info(f"Sent BINs for country {country_code} to chat {event.chat_id}")
    
    except Exception as e:
        LOGGER.error(f"Exception in bindb_handler: {e}")
        await event.client.edit_message(loading_message, "**Sorry, an error occurred while fetching BIN data ❌**", parse_mode='md')
        await notify_admin(event.client, "/bindb", e, event)

async def binbank_handler(event):
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY, parse_mode='md')
        LOGGER.info(f"Banned user {user_id} attempted to use /binbank")
        return
    
    try:
        user_input = event.pattern_match.group(1).strip() if event.pattern_match.group(1) else None
        if not user_input:
            await event.respond("**Please provide a bank name. e.g. /binbank Pubali**", parse_mode='md')
            LOGGER.warning(f"Invalid command format: {event.message.text}")
            return
        
        bank_name = user_input.title()
        LOGGER.info(f"Fetching BINs for bank {bank_name}")
        loading_message = await event.respond(f"**Finding Bins With Bank {bank_name}...**", parse_mode='md')
        params = {"bank": bank_name, "limit": 8000}
        bins = await fetch_bins(params, client=event.client, event=event, endpoint="bank")
        
        if not bins:
            await event.client.edit_message(loading_message, "**Sorry No Bins Found**", parse_mode='md')
            LOGGER.warning(f"No bins found for bank {bank_name}")
            return
        
        processed_bins = process_bins_to_json(bins)
        message_text = generate_message(processed_bins, bank_name)
        keyboard = None
        if len(processed_bins) > 10:
            bins_content = generate_telegraph_content(processed_bins[10:])
            content_size = len(bins_content.encode('utf-8'))
            telegraph_urls = await create_telegraph_page(bins_content, part_number=1)
            if telegraph_urls:
                buttons = []
                if content_size <= 20 * 1024:
                    buttons.append(KeyboardButtonRow([Button.url("Full Output", telegraph_urls[0])]))
                else:
                    for i in range(0, len(telegraph_urls), 2):
                        row = [Button.url(f"Output {i+1}", telegraph_urls[i])]
                        if i + 1 < len(telegraph_urls):
                            row.append(Button.url(f"Output {i+2}", telegraph_urls[i+1]))
                        buttons.append(KeyboardButtonRow(row))
                keyboard = ReplyInlineMarkup(buttons)
        
        await event.client.edit_message(loading_message, message_text, parse_mode='md', buttons=keyboard)
        LOGGER.info(f"Sent BINs for bank {bank_name} to chat {event.chat_id}")
    
    except Exception as e:
        LOGGER.error(f"Exception in binbank_handler: {e}")
        await event.client.edit_message(loading_message, "**Sorry, an error occurred while fetching BIN data ❌**", parse_mode='md')
        await notify_admin(event.client, "/binbank", e, event)

def setup_db_handlers(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}bindb(?:\\s+(.+))?'))
    async def bindb(event):
        await bindb_handler(event)
    
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}binbank(?:\\s+(.+))?'))
    async def binbank(event):
        await binbank_handler(event)