import pytz
import pycountry
from datetime import datetime
import calendar
from PIL import Image, ImageDraw, ImageFont
from telethon import TelegramClient, events, Button
from utils import LOGGER
from config import COMMAND_PREFIX, BAN_REPLY
from core import banned_users
import threading
import os
import time

def get_flag(country_code):
    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if not country:
            return None, "🏳️"
        country_name = country.name
        flag_emoji = ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in country_code.upper())
        return country_name, flag_emoji
    except Exception as e:
        LOGGER.error(f"Error in get_flag: {str(e)}")
        return None, "🏳️"

async def create_clock_image(country_name, time_str, date_str, day_str, output_path):
    width, height = 1240, 740
    bg_color = (8, 12, 18)
    card_color = (19, 26, 34)
    accent_color = (0, 230, 255)
    white = (255, 255, 255)
    gray = (168, 177, 186)

    font_time = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 110)
    font_date = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
    font_day = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
    font_country = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    margin = 60
    card_rect = [margin, margin, width - margin, height - margin]
    draw.rounded_rectangle(card_rect, radius=30, fill=card_color, outline=accent_color, width=4)

    time_x = (width - draw.textlength(time_str, font=font_time)) // 2
    time_y = 220
    draw.text((time_x, time_y), time_str, font=font_time, fill=white)

    date_x = (width - draw.textlength(date_str, font=font_date)) // 2
    date_y = time_y + 120
    draw.text((date_x, date_y), date_str, font=font_date, fill=gray)

    day_x = (width - draw.textlength(day_str, font=font_day)) // 2
    day_y = date_y + 85
    draw.text((day_x, day_y), day_str, font=font_day, fill=white)

    country_x = (width - draw.textlength(country_name, font=font_country)) // 2
    country_y = day_y + 80
    draw.text((country_x, country_y), country_name, font=font_country, fill=accent_color)

    img.save(output_path)
    return output_path

async def create_calendar_image(country_code):
    try:
        country = pycountry.countries.get(alpha_2=country_code)
        country_name = country.name if country else "Unknown"

        time_zones = {"gb": ["Europe/London"], "ae": ["Asia/Dubai"]}.get(country_code, pytz.country_timezones.get(country_code))

        if time_zones:
            tz = pytz.timezone(time_zones[0])
            now = datetime.now(tz)
            time_str = now.strftime("%I:%M:%S %p")
            date_str = now.strftime("%d %b, %Y")
            day_str = now.strftime("%A")
        else:
            time_str, date_str, day_str = "00:00:00 AM", "Unknown Date", "Unknown Day"

        await create_clock_image(country_name, time_str, date_str, day_str, f"calendar_{country_code}.png")

        def delete_image():
            time.sleep(20)
            if os.path.exists(f"calendar_{country_code}.png"):
                os.remove(f"calendar_{country_code}.png")

        threading.Thread(target=delete_image, daemon=True).start()
    except Exception as e:
        LOGGER.error(f"Error creating calendar image: {str(e)}")

async def get_calendar_markup(client, year, month, country_code):
    cal = calendar.Calendar()
    month_days = cal.monthdayscalendar(year, month)

    prev_month = month - 1 if month > 1 else 12
    next_month = month + 1 if month < 12 else 1
    prev_year = year - 1 if month == 1 else year
    next_year = year + 1 if month == 12 else year

    navigation_buttons = [
        [Button.inline("<", data=f"nav_{country_code}_{prev_year}_{prev_month}".encode()),
         Button.inline(">", data=f"nav_{country_code}_{next_year}_{next_month}".encode())]
    ]

    days_buttons = [ [Button.inline(day, data=f"alert_{country_code}_{year}_{month}".encode()) for day in ["Mo","Tu","We","Th","Fr","Sa","Su"]] ]

    day_buttons = []
    for week in month_days:
        row = []
        for day in week:
            if day == 0:
                row.append(Button.inline(" ", data=f"alert_{country_code}_{year}_{month}".encode()))
            else:
                row.append(Button.inline(str(day), data=f"day_{country_code}_{month:02d}_{day:02d}".encode()))
        day_buttons.append(row)

    country = pycountry.countries.get(alpha_2=country_code)
    country_name = country.name if country else "Unknown"
    flag_emoji = get_flag(country_code)[1]

    time_zones = {"gb": ["Europe/London"], "ae": ["Asia/Dubai"]}.get(country_code, pytz.country_timezones.get(country_code))
    tz = pytz.timezone(time_zones[0]) if time_zones else datetime.now().tzinfo
    now_tz = datetime.now(tz)
    current_time = now_tz.strftime("%I:%M:%S %p")

    header_row = []
    if month == now_tz.month and year == now_tz.year:
        header_row.append(Button.inline(f"{calendar.month_name[month]} {year} 📅", data=f"alert_{country_code}_{year}_{month}".encode()))
        header_row.append(Button.inline(now_tz.strftime('%d %b, %Y'), data=f"alert_{country_code}_{year}_{month}".encode()))
    else:
        header_row.append(Button.inline(f"{calendar.month_name[month]} {year}", data=f"alert_{country_code}_{year}_{month}".encode()))

    keyboard = [header_row, [Button.inline(f"{flag_emoji} {country_name} | {current_time}", data=f"alert_{country_code}_{year}_{month}".encode())]]
    keyboard += days_buttons + day_buttons + navigation_buttons
    return keyboard

async def get_time_and_calendar(client, country_input, year=None, month=None):
    country_code = None
    try:
        country_input = country_input.lower().strip()
        if country_input in ["uk", "united kingdom"]:
            country_code = "gb"
        elif country_input in ["uae", "united arab emirates"]:
            country_code = "ae"
        else:
            try:
                country = pycountry.countries.search_fuzzy(country_input)[0]
                country_code = country.alpha_2.lower()
            except LookupError:
                country_code = country_input.lower()
                if len(country_code) != 2 or not pycountry.countries.get(alpha_2=country_code.upper()):
                    raise ValueError("Invalid country code or name")

        country = pycountry.countries.get(alpha_2=country_code.upper())
        country_name, flag_emoji = get_flag(country_code.upper())
        if not country_name:
            country_name = "Unknown"

        time_zones = {"gb": ["Europe/London"], "ae": ["Asia/Dubai"]}.get(country_code, pytz.country_timezones.get(country_code))
        tz = pytz.timezone(time_zones[0]) if time_zones else datetime.now().tzinfo
        now = datetime.now(tz)
        time_str = now.strftime("%I:%M:%S %p")

        if year is None or month is None:
            year, month = now.year, now.month

        message = f"📅 {flag_emoji} <b>{country_name} Calendar | ⏰ {time_str} 👇</b>"
        calendar_markup = await get_calendar_markup(client, year, month, country_code)
        await create_calendar_image(country_code)
        return (message, calendar_markup, country_code, year, month)
    except ValueError as e:
        raise ValueError(str(e))

def setup_time_handler(app: TelegramClient):

    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(time|calendar)( .*)?$'))
    async def handle_time_command(event):
        user_id = event.sender_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='html')
            return

        command_text = event.pattern_match.group(2)
        if not command_text or not command_text.strip():
            await event.respond("<b>❌ Ensure you provide a valid country code or name.</b>", parse_mode='html')
            return

        country_input = command_text.strip()
        try:
            header_text, calendar_markup, country_code, year, month = await get_time_and_calendar(event.client, country_input)
            await event.respond(
                header_text,
                file=f"calendar_{country_code}.png",
                parse_mode='html',
                buttons=calendar_markup
            )
        except ValueError as e:
            LOGGER.error(f"ValueError in handle_time_command: {str(e)}")
            await event.respond("<b>❌ Ensure you provide a valid country code or name.</b>", parse_mode='html')
        except Exception as e:
            LOGGER.error(f"Exception in handle_time_command: {str(e)}")
            await event.respond("<b>The Country Is Not In My Database</b>", parse_mode='html')

    @app.on(events.CallbackQuery(pattern=r'^nav_'))
    async def handle_calendar_nav(event):
        try:
            _, country_code, year, month = event.data.decode().split('_')
            year, month = int(year), int(month)
            header_text, calendar_markup, _, _, _ = await get_time_and_calendar(event.client, country_code, year, month)
            await create_calendar_image(country_code)
            await event.edit(
                header_text,
                file=f"calendar_{country_code}.png",
                parse_mode='html',
                buttons=calendar_markup
            )
        except Exception as e:
            LOGGER.error(f"Exception in handle_calendar_nav: {str(e)}")
            await event.answer("Sorry Invalid Button Query", alert=True)

    @app.on(events.CallbackQuery(pattern=r'^alert_'))
    async def handle_alert(event):
        await event.answer("This Is The Button For Calendar", alert=True)

    @app.on(events.CallbackQuery(pattern=r'^day_'))
    async def handle_day_click(event):
        try:
            _, country_code, month, day = event.data.decode().split('_')
            month, day = int(month), int(day)
            await event.answer(f"Selected {day} {calendar.month_name[month]}", alert=True)
        except Exception as e:
            LOGGER.error(f"Exception in handle_day_click: {str(e)}")
            await event.answer("Sorry Invalid Button Query", alert=True)
