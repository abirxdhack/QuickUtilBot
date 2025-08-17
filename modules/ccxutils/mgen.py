import os
import random
from telethon import TelegramClient, events
from config import COMMAND_PREFIX, MULTI_CCGEN_LIMIT, BAN_REPLY
from utils import notify_admin, LOGGER
from core import banned_users

def is_amex_bin(bin_str):
    clean_bin = bin_str.replace('x', '').replace('X', '')
    if len(clean_bin) >= 2:
        first_two = clean_bin[:2]
        return first_two in ['34', '37']
    return False

def luhn_algorithm(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10 == 0

def calculate_luhn_check_digit(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    check_digit = (10 - (checksum % 10)) % 10
    return check_digit

def generate_credit_card(bin, amount, month=None, year=None, cvv=None):
    cards = []
    is_amex = is_amex_bin(bin)
    target_length = 14 if is_amex else 15
    cvv_length = 4 if is_amex else 3
    for _ in range(amount):
        while True:
            card_body = ''.join([str(random.randint(0, 9)) if char.lower() == 'x' else char for char in bin])
            remaining_digits = target_length - len(card_body)
            card_body += ''.join([str(random.randint(0, 9)) for _ in range(remaining_digits)])
            check_digit = calculate_luhn_check_digit(card_body)
            card_number = card_body + str(check_digit)
            if luhn_algorithm(card_number):
                card_month = month or f"{random.randint(1, 12):02}"
                card_year = year or random.randint(2024, 2029)
                card_cvv = cvv or ''.join([str(random.randint(0, 9)) for _ in range(cvv_length)])
                cards.append(f"{card_number}|{card_month}|{card_year}|{card_cvv}")
                break
    return cards

def generate_custom_cards(bin, amount, month=None, year=None, cvv=None):
    cards = []
    is_amex = is_amex_bin(bin)
    target_length = 14 if is_amex else 15
    cvv_length = 4 if is_amex else 3
    for _ in range(amount):
        while True:
            card_body = bin.replace('x', '').replace('X', '')
            remaining_digits = target_length - len(card_body)
            card_body += ''.join([str(random.randint(0, 9)) for _ in range(remaining_digits)])
            check_digit = calculate_luhn_check_digit(card_body)
            card_number = card_body + str(check_digit)
            if luhn_algorithm(card_number):
                card_month = month or f"{random.randint(1, 12):02}"
                card_year = year or random.randint(2024, 2029)
                card_cvv = cvv or ''.join([str(random.randint(0, 9)) for _ in range(cvv_length)])
                cards.append(f"{card_number}|{card_month}|{card_year}|{card_cvv}")
                break
    return cards

def setup_multi_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(?:mgn|mgen|multigen)(?:\\s+(.+))?'))
    async def multigen_handler(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
        
        user_input = event.pattern_match.group(1).strip().split() if event.pattern_match.group(1) else []
        if len(user_input) < 3:
            await event.respond("**Invalid Arguments ❌**\n**Use /mgen [BIN1] [BIN2] [BIN3]... [AMOUNT]**", parse_mode='md')
            return
        
        bins = user_input[:-1]
        try:
            amount = int(user_input[-1])
        except Exception:
            await event.respond("**Invalid amount given. Please provide a valid number.**", parse_mode='md')
            return
        
        if amount > MULTI_CCGEN_LIMIT:
            await event.respond("**You can only generate up to 2000 credit cards ❌**")
            return
        
        if any(len(bin) < 6 or len(bin) > 16 for bin in bins):
            await event.respond("**Each BIN should be between 6 and 16 digits ❌**")
            return
        
        total_cards = []
        for bin in bins:
            if 'x' in bin.lower():
                total_cards.extend(generate_credit_card(bin, amount, None, None, None))
            else:
                total_cards.extend(generate_custom_cards(bin, amount, None, None, None))
        
        valid_cards = [card for card in total_cards if luhn_algorithm(card.split('|')[0])]
        file_name = "Generated_CC_Text.txt"
        
        try:
            with open(file_name, "w") as file:
                file.write("\n".join(valid_cards))
            
            user_full_name = event.sender.first_name if event.sender else "Unknown"
            if event.sender and event.sender.last_name:
                user_full_name += f" {event.sender.last_name}"
            user_link = f"[{user_full_name}](tg://user?id={user_id})" if event.sender else "[Unknown](https://t.me/this_group)"
            
            total_bins = len(bins)
            each_bin_cc_amount = amount
            total_amount = total_bins * each_bin_cc_amount
            total_lines = len(valid_cards)
            total_size = total_lines
            
            caption = (
                "**Smart Multiple CC Generator ✅**\n"
                "**━━━━━━━━━━━━━━━━━**\n"
                f"**⊗ Total Amount:** {total_amount}\n"
                f"**⊗ Bins: ** **Multiple Bins Used **\n"
                f"**⊗ Total Size: ** {total_size}\n"
                f"**⊗ Each Bin CC Amount: ** {each_bin_cc_amount}\n"
                f"**⊗ Total Lines: ** {total_lines}\n"
                "**━━━━━━━━━━━━━━━━━**\n"
                "**Smooth Multi Gen→ Activated ✅**"
            )
            
            await event.client.send_file(
                event.chat_id,
                file_name,
                caption=caption,
                parse_mode='md'
            )
        
        except Exception as e:
            await event.respond("**Error generating cards ❌**", parse_mode='md')
            await notify_admin(event.client, "/mgen", e, event)
        
        finally:
            if os.path.exists(file_name):
                os.remove(file_name)