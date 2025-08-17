#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
import aiohttp
from telethon import TelegramClient, events, Button
from config import COMMAND_PREFIX
from utils import LOGGER, notify_admin
from core import banned_users

price_storage = {}

async def get_spot_price(symbol: str) -> float | None:
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol.upper()}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                LOGGER.error("API request failed with status %s for symbol %s", response.status, symbol)
                return None
            data = await response.json()
            return float(data.get("price")) if "price" in data else None

async def get_conversion_data(base_coin: str, target_coin: str, amount: float):
    direct_symbol = base_coin + target_coin
    inverse_symbol = target_coin + base_coin
    price = await get_spot_price(direct_symbol)
    inverted = False
    if price is None:
        price = await get_spot_price(inverse_symbol)
        if price is None:
            return None
        inverted = True
    base_usdt_price = await get_spot_price(base_coin + "USDT") or 0.0
    target_usdt_price = await get_spot_price(target_coin + "USDT") or 0.0
    if inverted:
        converted_amount = amount / price
    else:
        converted_amount = amount * price
    total_in_usdt = amount * base_usdt_price
    return {
        "base_coin": base_coin,
        "target_coin": target_coin,
        "amount": amount,
        "converted_amount": converted_amount,
        "total_in_usdt": total_in_usdt,
        "base_usdt_price": base_usdt_price,
        "target_usdt_price": target_usdt_price,
    }

def format_response(data: dict) -> str:
    return (
        "**Smart Binance Convert Successful ✅**\n"
        "**━━━━━━━━━━━━━━━━**\n"
        f"**- Base Coin:**{data['base_coin']}\n"
        f"**- Target Coin: ** {data['target_coin']}\n"
        f"**- Amount:** {data['amount']:.4f} {data['base_coin']}\n"
        f"**- Total In USDT:** {data['total_in_usdt']:.4f} USDT\n"
        f"**- Converted Amount:** {data['converted_amount']:.4f} {data['target_coin']}\n"
        "**━━━━━━━━━━━━━━━━**\n"
        "**Smooth Coin Converter → Activated ✅**"
    )

def setup_coin_handler(client: TelegramClient):
    @client.on(events.NewMessage(pattern=rf"^{COMMAND_PREFIX}cx(\s|@|$)"))
    async def coin_handler(event: events.NewMessage.Event):
        user_id = event.sender_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond("**✘ Sorry You're Banned From Using Me ↯**", parse_mode="md")
            LOGGER.info(f"Banned user {user_id} attempted to use /cx")
            return
        command = event.raw_text.split()
        if len(command) < 4:
            await event.respond("**Invalid format. Use /cx 10 ton usdt**", parse_mode="md")
            LOGGER.warning("Invalid command format: %s", event.raw_text)
            return
        try:
            amount = float(command[1])
        except ValueError:
            await event.respond("**Invalid format. Use `/cx 10 ton usdt`**", parse_mode="md")
            LOGGER.warning("Invalid amount provided: %s", command[1])
            return
        base_coin = command[2].upper()
        target_coin = command[3].upper()
        loading_msg = await event.respond("**Fetching Token Price, Please Wait....**", parse_mode="md")
        try:
            data = await get_conversion_data(base_coin, target_coin, amount)
            if data is None:
                await loading_msg.edit("**❌ Failed! This token pair may not exist on Binance.**", parse_mode="md")
                return
            price_storage[event.chat_id] = data
            await loading_msg.edit(
                format_response(data),
                parse_mode="md",
                buttons=[[Button.url("Binance Convert 💸", f"https://www.binance.com/en/convert/{base_coin}/{target_coin}")]]
            )
            LOGGER.info(f"Coin conversion result sent for {base_coin} to {target_coin}: {data['converted_amount']} {target_coin}")
        except Exception as e:
            await loading_msg.edit("**❌ Failed! This token pair may not exist on Binance.**", parse_mode="md")
            LOGGER.error("Exception occurred: %s", e)
            await notify_admin(client, "/cx", e, event)