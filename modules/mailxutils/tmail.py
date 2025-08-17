import re
import time
import asyncio
import random
import string
import hashlib
import aiohttp
from bs4 import BeautifulSoup
from telethon import TelegramClient, events, Button, types
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

user_data = {}
token_map = {}
user_tokens = {}
MAX_MESSAGE_LENGTH = 4000
BASE_URL = "https://api.mail.tm"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def short_id_generator(email):
    unique_string = email + str(time.time())
    return hashlib.md5(unique_string.encode()).hexdigest()[:10]

def generate_random_username(length=8):
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

def generate_random_password(length=12):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(length))

async def get_domain():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/domains", headers=HEADERS, timeout=5) as response:
                LOGGER.info(f"get_domain: Status {response.status}")
                data = await response.json()
                if isinstance(data, list) and data:
                    return data[0]['domain']
                elif 'hydra:member' in data and data['hydra:member']:
                    return data['hydra:member'][0]['domain']
                LOGGER.error(f"get_domain: No valid domain found in response: {data}")
                return None
    except Exception as e:
        LOGGER.error(f"get_domain: Error fetching domain: {str(e)}")
        return None

async def create_account(email, password):
    data = {
        "address": email,
        "password": password
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BASE_URL}/accounts", headers=HEADERS, json=data, timeout=5) as response:
                LOGGER.info(f"create_account: Status {response.status} for email {email}")
                if response.status in [200, 201]:
                    return await response.json()
                text = await response.text()
                LOGGER.error(f"create_account: Error Code {response.status}, Response: {text}")
                return None
    except Exception as e:
        LOGGER.error(f"create_account: Error for email {email}: {str(e)}")
        return None

async def get_token(email, password):
    data = {
        "address": email,
        "password": password
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BASE_URL}/token", headers=HEADERS, json=data, timeout=5) as response:
                LOGGER.info(f"get_token: Status {response.status} for email {email}")
                if response.status == 200:
                    return (await response.json()).get('token')
                text = await response.text()
                LOGGER.error(f"get_token: Error Code {response.status}, Response: {text}")
                return None
    except Exception as e:
        LOGGER.error(f"get_token: Error for email {email}: {str(e)}")
        return None

def get_text_from_html(html_content_list):
    html_content = ''.join(html_content_list)
    soup = BeautifulSoup(html_content, 'html.parser')
    for a_tag in soup.find_all('a', href=True):
        url = a_tag['href']
        new_content = f"{a_tag.text} [{url}]"
        a_tag.string = new_content
    text_content = soup.get_text()
    cleaned_content = re.sub(r'\s+', ' ', text_content).strip()
    return cleaned_content

async def list_messages(token):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/messages", headers=headers, timeout=5) as response:
                LOGGER.info(f"list_messages: Status {response.status} for token {token[:10]}...")
                if response.status != 200:
                    text = await response.text()
                    LOGGER.error(f"list_messages: Error Code {response.status}, Response: {text}")
                    return []
                data = await response.json()
                if isinstance(data, list):
                    LOGGER.info(f"list_messages: Found {len(data)} messages")
                    return data
                elif 'hydra:member' in data:
                    LOGGER.info(f"list_messages: Found {len(data['hydra:member'])} messages in hydra:member")
                    return data['hydra:member']
                LOGGER.error(f"list_messages: No valid messages found in response: {data}")
                return []
    except aiohttp.ClientError as e:
        LOGGER.error(f"list_messages: Network error for token {token[:10]}...: {str(e)}")
        return []
    except Exception as e:
        LOGGER.error(f"list_messages: Unexpected error for token {token[:10]}...: {str(e)}")
        return []

def setup_tmail_handler(client: TelegramClient):
    @client.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}tmail'))
    async def generate_mail(event):
        user_id = event.sender_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='markdown')
            return
        chat = await event.get_chat()
        if not isinstance(chat, types.User):
            await event.respond("**❌ Bro Tempmail Feature Only Works In Private**", parse_mode='markdown')
            return
        loading_msg = await event.respond("**Generating Temporary Mail...**", parse_mode='markdown')
        
        message_parts = event.message.text.strip().split(maxsplit=1)
        args_text = message_parts[1] if len(message_parts) > 1 else ""
        
        username = None
        password = None
        
        if args_text:
            if ':' in args_text:
                try:
                    username, password = args_text.split(':', 1)
                    username = username.strip()
                    password = password.strip()
                except ValueError:
                    pass
        
        if not username:
            username = generate_random_username()
        if not password:
            password = generate_random_password()
        
        domain = await get_domain()
        if not domain:
            await event.respond("**❌ TempMail API Dead Bro**", parse_mode='markdown')
            await loading_msg.delete()
            return
        email = f"{username}@{domain}"
        LOGGER.info(f"generate_mail: Creating account for {email}")
        account = await create_account(email, password)
        if not account:
            await event.respond("**❌ Username already taken. Choose another one.**", parse_mode='markdown')
            await loading_msg.delete()
            return
        await asyncio.sleep(2)
        token = await get_token(email, password)
        if not token:
            await event.respond("**❌ Failed to retrieve token**", parse_mode='markdown')
            await loading_msg.delete()
            return
        short_id = short_id_generator(email)
        token_map[short_id] = token
        user_tokens[event.sender_id] = token
        output_message = (
            "**📧 SmartTools-Email Details 📧**\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"**📧 Email:** `{email}`\n"
            f"**🔑 Password:** `{password}`\n"
            f"**🔒 Token:** `{token}`\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "**Note: Keep the token to Access Mail**"
        )
        keyboard = [[Button.inline("Check Incoming Emails", f"check_{short_id}")]]
        await event.respond(output_message, parse_mode='markdown', buttons=keyboard)
        await loading_msg.delete()

    @client.on(events.CallbackQuery(pattern=r'^check_'))
    async def check_mail(event):
        user_id = event.sender_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.answer("✘ Sorry You're Banned From Using Me ↯", alert=True)
            return
        short_id = event.data.decode().split('_')[1]
        token = token_map.get(short_id) or user_tokens.get(event.sender_id)
        if not token:
            await event.respond("**❌ Session expired or no token found. Please use .cmail or /cmail with your token.**", parse_mode='markdown')
            return
        user_tokens[event.sender_id] = token
        LOGGER.info(f"check_mail: Fetching messages for user {user_id}, token {token[:10]}...")
        messages = await list_messages(token)
        if not messages:
            await event.answer("No messages received ❌", alert=True)
            return
        loading_msg = await event.respond("**Checking Mails... Please wait...**", parse_mode='markdown')
        output = "**📧 Your SmartTools-Mail Messages 📧**\n"
        output += "**━━━━━━━━━━━━━━━━━━**\n"
        buttons = []
        for idx, msg in enumerate(messages[:10], 1):
            output += f"{idx}. From: `{msg['from']['address']}` - Subject: {msg['subject']}\n"
            button = Button.inline(f"{idx}", f"read_{msg['id']}")
            buttons.append(button)
        keyboard = []
        for i in range(0, len(buttons), 5):
            keyboard.append(buttons[i:i+5])
        await event.respond(output, parse_mode='markdown', buttons=keyboard)
        await loading_msg.delete()

    @client.on(events.CallbackQuery(pattern=r'^close_message'))
    async def close_message(event):
        try:
            await event.delete()
        except Exception as e:
            LOGGER.error(f"close_message: Error deleting message: {str(e)}")
            try:
                await event.answer("Message deleted", alert=False)
            except:
                pass

    @client.on(events.CallbackQuery(pattern=r'^read_'))
    async def read_message(event):
        user_id = event.sender_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.answer("✘ Sorry You're Banned From Using Me ↯", alert=True)
            return
        message_id = event.data.decode().split('_')[1]
        token = user_tokens.get(event.sender_id)
        if not token:
            await event.respond("**❌ Token not found. Please use .cmail or /cmail with your token again**", parse_mode='markdown')
            return
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        LOGGER.info(f"read_message: Fetching message {message_id} for user {user_id}, token {token[:10]}...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{BASE_URL}/messages/{message_id}", headers=headers, timeout=5) as response:
                    LOGGER.info(f"read_message: Status {response.status} for message {message_id}")
                    if response.status == 200:
                        details = await response.json()
                        if 'html' in details:
                            message_text = get_text_from_html(details['html'])
                        elif 'text' in details:
                            message_text = details['text']
                        else:
                            message_text = "Content not available."
                        if len(message_text) > MAX_MESSAGE_LENGTH:
                            message_text = message_text[:MAX_MESSAGE_LENGTH - 100] + "... [message truncated]"
                        output = f"**From:** `{details['from']['address']}`\n**Subject:** `{details['subject']}`\n━━━━━━━━━━━━━━━━━━\n{message_text}"
                        keyboard = [[Button.inline("Close", "close_message")]]
                        await event.respond(output, parse_mode='markdown', buttons=keyboard, link_preview=False)
                    else:
                        text = await response.text()
                        LOGGER.error(f"read_message: Error Code {response.status}, Response: {text}")
                        await event.respond("**❌ Error retrieving message details**", parse_mode='markdown')
        except aiohttp.ClientError as e:
            LOGGER.error(f"read_message: Network error for message {message_id}: {str(e)}")
            await notify_admin(client, "/cmail read", e, event.query.message)
            await event.respond("**❌ Error retrieving message details: Network issue**", parse_mode='markdown')
        except Exception as e:
            LOGGER.error(f"read_message: Unexpected error for message {message_id}: {str(e)}")
            await notify_admin(client, "/cmail read", e, event.query.message)
            await event.respond("**❌ Error retrieving message details**", parse_mode='markdown')

    @client.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}cmail'))
    async def manual_check_mail(event):
        user_id = event.sender_id
        LOGGER.info(f"manual_check_mail: Command received from user {user_id}")
        if user_id and await banned_users.find_one({"user_id": user_id}):
            LOGGER.info(f"manual_check_mail: User {user_id} is banned")
            await event.respond(BAN_REPLY, parse_mode='markdown')
            return
        chat = await event.get_chat()
        if not isinstance(chat, types.User):
            LOGGER.info(f"manual_check_mail: Command used in non-private chat by user {user_id}")
            await event.respond("**❌ Bro Tempmail Feature Only Works In Private**", parse_mode='markdown')
            return
        
        message_parts = event.message.text.strip().split(maxsplit=1)
        token = message_parts[1] if len(message_parts) > 1 else ""
        
        if not token:
            LOGGER.info(f"manual_check_mail: No token provided by user {user_id}")
            await event.respond("**❌ Please provide a token after the .cmail or /cmail command.**", parse_mode='markdown')
            return
        loading_msg = await event.respond("**Checking Mails... Please wait**", parse_mode='markdown')
        LOGGER.info(f"manual_check_mail: Processing token {token[:10]}... for user {user_id}")
        try:
            user_tokens[event.sender_id] = token
            messages = await list_messages(token)
            if not messages:
                LOGGER.info(f"manual_check_mail: No messages found for user {user_id}, token {token[:10]}...")
                await event.respond("**❌ No messages found or maybe wrong token**", parse_mode='markdown')
                await loading_msg.delete()
                return
            LOGGER.info(f"manual_check_mail: Found {len(messages)} messages for user {user_id}")
            output = "**📧 Your SmartTools-Mail Messages 📧**\n"
            output += "**━━━━━━━━━━━━━━━━━━**\n"
            buttons = []
            for idx, msg in enumerate(messages[:10], 1):
                output += f"{idx}. From: `{msg['from']['address']}` - Subject: {msg['subject']}\n"
                button = Button.inline(f"{idx}", f"read_{msg['id']}")
                buttons.append(button)
            keyboard = []
            for i in range(0, len(buttons), 5):
                keyboard.append(buttons[i:i+5])
            await event.respond(output, parse_mode='markdown', buttons=keyboard)
            await loading_msg.delete()
        except Exception as e:
            LOGGER.error(f"manual_check_mail: Unexpected error for user {user_id}, token {token[:10]}...: {str(e)}")
            await notify_admin(client, "/cmail", e, event.message)
            await event.respond("**❌ Error processing your request. Please try again later.**", parse_mode='markdown')
            await loading_msg.delete()