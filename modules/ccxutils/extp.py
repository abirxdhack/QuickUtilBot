import asyncio
import aiohttp
import random
import pycountry
from telethon import TelegramClient, events
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonRow
from telethon.tl.custom import Button
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
        LOGGER.error(f"Error fetching BIN info: {str(e)}")
        asyncio.create_task(notify_admin(client, "/extp", e, event))
        return None

def luhn_algorithm(number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(number)
    checksum = 0
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum += sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10 == 0

def generate_extrapolated_numbers(bin, amount=5):
    extrapolated_numbers = set()
    while len(extrapolated_numbers) < amount:
        number = bin + ''.join(random.choices('0123456789', k=9))
        check_sum = 0
        reverse_digits = number[::-1]
        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 0:
                n = n * 2
                if n > 9:
                    n = n - 9
            check_sum += n
        last_digit = (10 - (check_sum % 10)) % 10
        final_number = number + str(last_digit)
        if luhn_algorithm(final_number):
            extrapolated_numbers.add(final_number)
    return list(extrapolated_numbers)

def get_flag_emoji(country_code):
    return chr(0x1F1E6 + ord(country_code[0]) - ord('A')) + chr(0x1F1E6 + ord(country_code[1]) - ord('A'))

async def extrapolate_handler(event):
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY)
        return
    
    user_full_name = event.sender.first_name if event.sender else "Unknown"
    if event.sender and event.sender.last_name:
        user_full_name += f" {event.sender.last_name}"
    
    command_parts = event.pattern_match.group(1).strip().split() if event.pattern_match.group(1) else []
    if len(command_parts) != 1 or not command_parts[0].isdigit() or len(command_parts[0]) != 6:
        await event.respond("**❌Please provide a valid BIN**", parse_mode='md')
        return
    
    bin = command_parts[0]
    progress_message = await event.respond("**Extrapolation In Progress...✨**", parse_mode='md')
    bin_info = await get_bin_info(bin, event.client, event)
    
    if not bin_info or bin_info.get('Status') != 'SUCCESS':
        await event.client.edit_message(progress_message, "**BIN Not Found In Database❌**", parse_mode='md')
        return
    
    extrapolated_numbers = generate_extrapolated_numbers(bin)
    formatted_numbers = [f"`{num[:random.randint(8, 12)] + 'x' * (len(num) - random.randint(8, 12))}`" for num in extrapolated_numbers]
    country_code = bin_info.get('Country', {}).get('A2', '')
    country_name = bin_info.get('Country', {}).get('Name', 'N/A')
    flag_emoji = get_flag_emoji(country_code) if country_code else ''
    
    result_message = (
        f"**𝗘𝘅𝘁𝗿𝗮𝗽** ⇾ {bin}\n"
        f"**Amount** ⇾ {len(formatted_numbers)}\n\n"
        + "\n".join(formatted_numbers) + "\n\n"
        f"**Bank:** {bin_info.get('Issuer', 'None')}\n"
        f"**Country:** {country_name} {flag_emoji}\n"
        f"**Bin Info** {bin_info.get('CardTier', 'None')} - {bin_info.get('Type', 'None')} - {bin_info.get('Scheme', 'None')}"
    )
    
    markup = ReplyInlineMarkup([KeyboardButtonRow([Button.inline("Re-Generate", f"regenerate_{bin}_{user_id}")])])
    await event.client.delete_messages(event.chat_id, progress_message)
    await event.respond(result_message, parse_mode='md', buttons=markup)

def setup_extp_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}extp(?:\\s+(.+))?'))
    async def extrapolate(event):
        await extrapolate_handler(event)
    
    @app.on(events.CallbackQuery(pattern=r"^regenerate_\d{6}_\d+$"))
    async def regenerate(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        callback_data_parts = event.data.decode().split("_")
        bin = callback_data_parts[1]
        original_user_id = int(callback_data_parts[2])
        user_full_name = event.sender.first_name if event.sender else "Unknown"
        if event.sender and event.sender.last_name:
            user_full_name += f" {event.sender.last_name}"
        
        if user_id != original_user_id:
            original_user = await event.client.get_entity(original_user_id)
            original_user_name = original_user.first_name
            if original_user.last_name:
                original_user_name += f" {original_user.last_name}"
            await event.answer(f"Action Disallowed. This Button Only For {original_user_name}", show_alert=True)
            return
        
        bin_info = await get_bin_info(bin, event.client, event)
        if not bin_info or bin_info.get('Status') != 'SUCCESS':
            await event.edit("**❌Invalid BIN provided**", parse_mode='md')
            return
        
        extrapolated_numbers = generate_extrapolated_numbers(bin)
        formatted_numbers = [f"`{num[:random.randint(8, 12)] + 'x' * (len(num) - random.randint(8, 12))}`" for num in extrapolated_numbers]
        country_code = bin_info.get('Country', {}).get('A2', '')
        country_name = bin_info.get('Country', {}).get('Name', 'N/A')
        flag_emoji = get_flag_emoji(country_code) if country_code else ''
        
        regenerated_message = (
            f"**�_E𝘅𝘁𝗿𝗮𝗽** ⇾ {bin}\n"
            f"**Amount** ⇾ {len(formatted_numbers)}\n\n"
            + "\n".join(formatted_numbers) + "\n\n"
            f"**Bank :** {bin_info.get('Issuer', 'None')}\n"
            f"**Country:** {country_name} {flag_emoji}\n"
            f"**Bin Info:** {bin_info.get('CardTier', 'None')} - {bin_info.get('Type', 'None')} - {bin_info.get('Scheme', 'None')}"
        )
        
        markup = ReplyInlineMarkup([KeyboardButtonRow([Button.inline("Re-Generate", f"regenerate_{bin}_{user_id}")])])
        msg = await event.get_message()
        if msg and msg.text != regenerated_message:
            await event.edit(regenerated_message, parse_mode='md', buttons=markup)

def setup_extp_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}extp(?:\\s+(.+))?'))
    async def extrapolate(event):
        await extrapolate_handler(event)
    
    @app.on(events.CallbackQuery(pattern=r"^regenerate_\d{6}_\d+$"))
    async def regenerate(event):
        await regenerate_callback(event)
    
    async def regenerate_callback(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        callback_data_parts = event.data.decode().split("_")
        bin = callback_data_parts[1]
        original_user_id = int(callback_data_parts[2])
        user_full_name = event.sender.first_name if event.sender else "Unknown"
        if event.sender and event.sender.last_name:
            user_full_name += f" {event.sender.last_name}"
        
        if user_id != original_user_id:
            original_user = await event.client.get_entity(original_user_id)
            original_user_name = original_user.first_name
            if original_user.last_name:
                original_user_name += f" {original_user.last_name}"
            await event.answer(f"Action Disallowed. This Button Only For {original_user_name}", show_alert=True)
            return
        
        bin_info = await get_bin_info(bin, event.client, event)
        if not bin_info or bin_info.get('Status') != 'SUCCESS':
            await event.edit("**❌Invalid BIN provided**", parse_mode='md')
            return
        
        extrapolated_numbers = generate_extrapolated_numbers(bin)
        formatted_numbers = [f"`{num[:random.randint(8, 12)] + 'x' * (len(num) - random.randint(8, 12))}`" for num in extrapolated_numbers]
        country_code = bin_info.get('Country', {}).get('A2', '')
        country_name = bin_info.get('Country', {}).get('Name', 'N/A')
        flag_emoji = get_flag_emoji(country_code) if country_code else ''
        
        regenerated_message = (
            f"**𝗘𝘅𝘁𝗿𝗮𝗽** ⇾ {bin}\n"
            f"**Amount** ⇾ {len(formatted_numbers)}\n\n"
            + "\n".join(formatted_numbers) + "\n\n"
            f"**Bank :** {bin_info.get('Issuer', 'None')}\n"
            f"**Country:** {country_name} {flag_emoji}\n"
            f"**Bin Info:** {bin_info.get('CardTier', 'None')} - {bin_info.get('Type', 'None')} - {bin_info.get('Scheme', 'None')}"
        )
        
        markup = ReplyInlineMarkup([KeyboardButtonRow([Button.inline("Re-Generate", f"regenerate_{bin}_{user_id}")])])
        msg = await event.get_message()
        if msg and msg.text != regenerated_message:
            await event.edit(regenerated_message, parse_mode='md', buttons=markup)