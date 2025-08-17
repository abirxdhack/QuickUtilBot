#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
import os
import aiohttp
import asyncio
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from telethon import TelegramClient, events
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonRow
from telethon.tl.custom import Button
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

BASE_URL = "https://api.binance.com/api/v3/ticker/24hr?symbol="

async def fetch_crypto_data(token=None):
    try:
        url = f"{BASE_URL}{token}USDT"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                LOGGER.info(f"Successfully fetched data for {token}")
                return await response.json()
    except Exception as e:
        LOGGER.error(f"Error fetching data for {token}: {e}")
        raise Exception("<b>❌ Data unavailable or invalid token symbol </b>")

async def create_crypto_info_card(
    symbol: str,
    change: str,
    last_price: str,
    high: str,
    low: str,
    volume: str,
    quote_volume: str,
    output_path: str = "crypto_card.png"
):
    if not output_path.lower().endswith(".png"):
        output_path += ".png"
    outer_width, outer_height = 1200, 800
    inner_width, inner_height = 1160, 760
    background_color = (20, 20, 30)
    inner_color = (30, 30, 40)
    border_color = (0, 255, 150)
    text_white = (240, 240, 250)
    text_neon = (0, 255, 150)
    gradient_start = (0, 50, 100)
    gradient_end = (0, 20, 40)
    gap = 35
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 70)
        font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 50)
        font_credit = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    except IOError:
        raise RuntimeError("Fonts not found. Please install DejaVu Sans or update font paths.")
    img = Image.new("RGB", (outer_width, outer_height), color=background_color)
    draw = ImageDraw.Draw(img)
    for y in range(outer_height):
        r = int(gradient_start[0] + (gradient_end[0] - gradient_start[0]) * y / outer_height)
        g = int(gradient_start[1] + (gradient_end[1] - gradient_start[1]) * y / outer_height)
        b = int(gradient_start[2] + (gradient_end[2] - gradient_start[2]) * y / outer_height)
        draw.line([(0, y), (outer_width, y)], fill=(r, g, b))
    draw.rectangle([(20, 20), (20 + inner_width - 1, 20 + inner_height - 1)], fill=inner_color)
    draw.rectangle([(20, 20), (20 + inner_width - 1, 20 + inner_height - 1)], outline=border_color, width=6)
    draw.rectangle([(22, 22), (22 + inner_width - 5, 22 + inner_height - 5)], outline=(0, 200, 120), width=2)
    title_text = f"Price Info for {symbol.split('USDT')[0]}"
    bbox_title = draw.textbbox((0, 0), title_text, font=font_title)
    x_title = (inner_width - (bbox_title[2] - bbox_title[0])) // 2 + 20
    y = 40
    draw.text((x_title, y), title_text, font=font_title, fill=text_neon)
    y += (bbox_title[3] - bbox_title[1]) + gap
    info_lines = [
        f"Symbol: {symbol}",
        f"Change: {change}",
        f"Last Price: ${last_price}",
        f"24h High: ${high}",
        f"24h Low: ${low}",
        f"24h Volume: {volume}",
        f"24h Quote Volume: ${quote_volume}"
    ]
    for line in info_lines:
        bbox = draw.textbbox((0, 0), line, font=font_text)
        x = (inner_width - (bbox[2] - bbox[0])) // 2 + 20
        draw.text((x, y), line, font=font_text, fill=text_white)
        y += (bbox[3] - bbox[1]) + gap
    credit_text = "Powered By @ISmartCoder"
    bbox_credit = draw.textbbox((0, 0), credit_text, font=font_credit)
    x_credit = (inner_width - (bbox_credit[2] - bbox_credit[0])) // 2 + 20
    draw.text((x_credit + 2, outer_height - 80), credit_text, font=font_credit, fill=(0, 200, 120))
    draw.text((x_credit, outer_height - 82), credit_text, font=font_credit, fill=text_neon)
    img.save(output_path, format="PNG")
    return os.path.abspath(output_path)

def format_crypto_info(data):
    result = (
        f"📊 <b>Symbol:</b> {data['symbol']}\n"
        f"↕️ <b>Change:</b> {data['priceChangePercent']}%\n"
        f"💰 <b>Last Price:</b> {data['lastPrice']}\n"
        f"📈 <b>24h High:</b> {data['highPrice']}\n"
        f"📉 <b>24h Low:</b> {data['lowPrice']}\n"
        f"🔄 <b>24h Volume:</b> {data['volume']}\n"
        f"💵 <b>24h Quote Volume:</b> {data['quoteVolume']}\n\n"
    )
    return result

def setup_crypto_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}price(?:\\s+(.+))?'))
    async def handle_price_command(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='html')
            LOGGER.info(f"Banned user {user_id} attempted to use /price")
            return
        
        user_full_name = event.sender.first_name if event.sender else "Anonymous"
        if event.sender and event.sender.last_name:
            user_full_name += f" {event.sender.last_name}"
        
        user_input = event.pattern_match.group(1).strip() if event.pattern_match.group(1) else None
        if not user_input:
            await event.respond("❌ <b>Please provide a token symbol</b>", parse_mode='html')
            LOGGER.warning(f"Invalid command format: {event.message.text}")
            return
        
        token = user_input.upper()
        fetching_message = await event.respond("<b>Fetching Token Price..✨</b>", parse_mode='html')
        
        try:
            data = await fetch_crypto_data(token)
            formatted_info = format_crypto_info(data)
            response_message = f"📈 <b>Price Info for {token}:</b>\n\n{formatted_info}"
            image_path = await create_crypto_info_card(
                symbol=data['symbol'],
                change=f"{data['priceChangePercent']}%",
                last_price=data['lastPrice'],
                high=data['highPrice'],
                low=data['lowPrice'],
                volume=data['volume'],
                quote_volume=data['quoteVolume']
            )
            keyboard = ReplyInlineMarkup([
                KeyboardButtonRow([
                    Button.url("📊 Data Insight", f"https://www.binance.com/en/trading_insight/glass?id=44&token={token}"),
                    Button.inline("🔄 Refresh", f"refresh_{token}_{user_id}")
                ])
            ])
            await event.client.send_file(
                event.chat_id,
                image_path,
                caption=response_message,
                parse_mode='html',
                buttons=keyboard
            )
            await event.client.delete_messages(event.chat_id, fetching_message)
            if os.path.exists(image_path):
                os.remove(image_path)
            LOGGER.info(f"Sent price info with image for {token} to chat {event.chat_id}")
        except Exception as e:
            LOGGER.error(f"Error processing /price for {token}: {e}")
            await notify_admin(event.client, "/price", e, event)
            await event.client.edit_message(fetching_message, "❌ <b>Nothing Detected From Binance Database</b>", parse_mode='html')
    
    @app.on(events.CallbackQuery(pattern=r"refresh_(.*?)_(\d+)$"))
    async def handle_refresh_callback(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.edit(BAN_REPLY, parse_mode='html')
            LOGGER.info(f"Banned user {user_id} attempted to use refresh for {event.data.decode()}")
            return
        
        callback_data_parts = event.data.decode().split("_")
        token = callback_data_parts[1]
        original_user_id = int(callback_data_parts[2])
        user_full_name = event.sender.first_name if event.sender else "Anonymous"
        if event.sender and event.sender.last_name:
            user_full_name += f" {event.sender.last_name}"
        
        if user_id != original_user_id:
            original_user = await event.client.get_entity(original_user_id)
            original_user_name = original_user.first_name
            if original_user.last_name:
                original_user_name += f" {original_user.last_name}"
            await event.answer(f"Action Disallowed. This Button Only For {original_user_name}", show_alert=True)
            return
        
        try:
            data = await fetch_crypto_data(token)
            old_message = await event.get_message()
            new_formatted_info = format_crypto_info(data)
            old_formatted_info = old_message.text.split("\n\n", 1)[1] if old_message.text else ""
            if new_formatted_info.strip() == old_formatted_info.strip():
                await event.answer("No changes detected from Binance Database")
                LOGGER.info(f"No changes detected for {token} in chat {event.chat_id}")
            else:
                image_path = await create_crypto_info_card(
                    symbol=data['symbol'],
                    change=f"{data['priceChangePercent']}%",
                    last_price=data['lastPrice'],
                    high=data['highPrice'],
                    low=data['lowPrice'],
                    volume=data['volume'],
                    quote_volume=data['quoteVolume']
                )
                response_message = f"📈 <b>Price Info for {token}:</b>\n\n{new_formatted_info}"
                keyboard = ReplyInlineMarkup([
                    KeyboardButtonRow([
                        Button.url("📊 Data Insight", f"https://www.binance.com/en/trading_insight/glass?id=44&token={token}"),
                        Button.inline("🔄 Refresh", f"refresh_{token}_{user_id}")
                    ])
                ])
                await event.client.delete_messages(event.chat_id, old_message)
                await event.client.send_file(
                    event.chat_id,
                    image_path,
                    caption=response_message,
                    parse_mode='html',
                    buttons=keyboard
                )
                if os.path.exists(image_path):
                    os.remove(image_path)
                await event.answer("Price Updated Successfully!")
                LOGGER.info(f"Updated price info with image for {token} in chat {event.chat_id}")
        except Exception as e:
            LOGGER.error(f"Error in refresh for {token}: {e}")
            await notify_admin(event.client, "/price refresh", e, event)
            await event.answer("❌ Nothing Detected From Binance Database", show_alert=True)