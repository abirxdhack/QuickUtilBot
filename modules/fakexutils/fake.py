import re
import asyncio
import pycountry
from telethon import events
from telethon.client.telegramclient import TelegramClient
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonRow, KeyboardButtonCopy
from config import COMMAND_PREFIX, BAN_REPLY
from core import banned_users
from smartfaker import Faker
from utils import LOGGER

def get_flag(country_code, address_data=None, client=None, message=None):
    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if not country and address_data and 'country_flag' in address_data:
            return address_data['country'], address_data['country_flag']
        if not country:
            return None, "🏚"
        country_name = country.name
        flag_emoji = chr(0x1F1E6 + ord(country_code[0]) - ord('A')) + chr(0x1F1E6 + ord(country_code[1]) - ord('A'))
        return country_name, flag_emoji
    except Exception as e:
        if address_data and 'country_flag' in address_data:
            return address_data['country'], address_data['country_flag']
        LOGGER.error(f"Error in get_flag: {str(e)}")
        return None, "🏚"

def resolve_country(input_str):
    input_str = input_str.strip().upper()
    country_mappings = {
        "UK": ("GB", "United Kingdom"),
        "UAE": ("AE", "United Arab Emirates"),
        "AE": ("AE", "United Arab Emirates"),
        "UNITED KINGDOM": ("GB", "United Kingdom"),
        "UNITED ARAB EMIRATES": ("AE", "United Arab Emirates")
    }
    if input_str in country_mappings:
        return country_mappings[input_str]
    if len(input_str) == 2:
        country = pycountry.countries.get(alpha_2=input_str)
        if country:
            return country.alpha_2, country.name
    try:
        country = pycountry.countries.search_fuzzy(input_str)[0]
        return country.alpha_2, country.name
    except LookupError:
        return input_str, input_str

def setup_fake_handler(app: TelegramClient):
    app.parse_mode = "md"

    prefix_pat = "|".join(re.escape(p) for p in COMMAND_PREFIX)
    cmd_pat = rf"^(?:{prefix_pat})(?:fake|rnd)(?:\s+(?P<arg>.+))?$"
    pattern = re.compile(cmd_pat, flags=re.IGNORECASE)

    @app.on(events.NewMessage(pattern=pattern))
    async def fake_handler(event: events.NewMessage.Event):
        user_id = event.sender_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await app.send_message(event.chat_id, BAN_REPLY)
            LOGGER.info(f"Banned user {user_id} attempted to use /fake")
            return

        arg = (event.pattern_match.group("arg") or "").strip()
        if not arg:
            await app.send_message(event.chat_id, "**❌ Please Provide A Country Code or Name**")
            LOGGER.warning(f"Invalid command format: {event.raw_text}")
            return

        country_code, country_name = resolve_country(arg)
        if not country_code:
            await app.send_message(event.chat_id, "**❌ Invalid Country Code or Name**")
            LOGGER.warning(f"Invalid country input: {arg}")
            return

        generating_message = await app.send_message(event.chat_id, "**Generating Fake Address...**")

        try:
            fake = Faker()
            address = await fake.address(country_code, 1)
            _, flag_emoji = get_flag(country_code, address, app, event)

            keyboard = ReplyInlineMarkup(rows=[
                KeyboardButtonRow(buttons=[
                    KeyboardButtonCopy(text="Copy Postal Code", copy_text=address['postal_code'])
                ])
            ])

            await generating_message.edit(
                text=f"**Address for {address['country']} {flag_emoji}**\n"
                     f"**━━━━━━━━━━━━━**\n"
                     f"**- Street :** `{address['building_number']} {address['street_name']}`\n"
                     f"**- Street Name :** `{address['street_name']}`\n"
                     f"**- Currency :** `{address['currency']}`\n"
                     f"**- Full Name :** `{address['person_name']}`\n"
                     f"**- City/Town/Village :** `{address['city']}`\n"
                     f"**- Gender :** `{address['gender']}`\n"
                     f"**- Postal Code :** `{address['postal_code']}`\n"
                     f"**- Phone Number :** `{address['phone_number']}`\n"
                     f"**- State :** `{address['state']}`\n"
                     f"**- Country :** `{address['country']}`\n"
                     f"**━━━━━━━━━━━━━**\n"
                     f"**Click Below Button For Code 👇**",
                buttons=keyboard
            )
            LOGGER.info(f"Sent fake address for {country_code} in chat {event.chat_id}")
        except Exception as e:
            LOGGER.error(f"Fake address generation error for country '{country_code}': {e}")
            await generating_message.edit(text="**❌ Sorry, Fake Address Generation Failed**")
