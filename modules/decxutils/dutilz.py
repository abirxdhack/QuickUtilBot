# Copyright @ISmartCoder
# Updates Channel: https://t.me/TheSmartDev
import os
import base64
import binascii
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaDocument
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

def setup_decoders_handler(client: TelegramClient):
    commands = {
        "b64en": lambda text: base64.b64encode(text.encode()).decode(),
        "b64de": lambda text: base64.b64decode(text).decode(),
        "b32en": lambda text: base64.b32encode(text.encode()).decode(),
        "b32de": lambda text: base64.b32decode(text).decode(),
        "binen": lambda text: ' '.join(format(ord(char), '08b') for char in text),
        "binde": lambda text: ''.join(chr(int(b, 2)) for b in text.split()),
        "hexen": lambda text: binascii.hexlify(text.encode()).decode(),
        "hexde": lambda text: binascii.unhexlify(text).decode(),
        "octen": lambda text: ' '.join(format(ord(char), '03o') for char in text),
        "octde": lambda text: ''.join(chr(int(o, 8)) for o in text.split()),
        "trev": lambda text: text[::-1],
        "tcap": lambda text: text.upper(),
        "tsm": lambda text: text.lower(),
        "wc": lambda text: (
            "<b>📊 Text Counter</b>\n\n"
            "<b>✅ Words:</b> <code>{}</code>\n"
            "<b>✅ Characters:</b> <code>{}</code>\n"
            "<b>✅ Sentences:</b> <code>{}</code>\n"
            "<b>✅ Paragraphs:</b> <code>{}</code>".format(
                len(text.split()),
                len(text),
                text.count('.') + text.count('!') + text.count('?'),
                text.count('\n') + 1
            )
        )
    }

    for command, func in commands.items():
        @client.on(events.NewMessage(pattern=f"^{COMMAND_PREFIX}{command}(\\s|$)"))
        async def handle_command(event, func=func, command=command):
            user_id = event.sender_id
            if user_id and await banned_users.find_one({"user_id": user_id}):
                await event.respond(BAN_REPLY, parse_mode="md")
                LOGGER.info(f"Banned user {user_id} attempted to use /{command}")
                return

            processing_msg = await event.respond("<b>Processing Your Input...✨</b>", parse_mode="html")

            try:
                text = None

                # Handle reply to message
                if event.is_reply:
                    reply = await event.get_reply_message()
                    if reply.media and isinstance(reply.media, MessageMediaDocument):
                        file_path = await client.download_media(reply.media)
                        with open(file_path, "r", encoding="utf-8") as file:
                            text = file.read()
                        os.remove(file_path)
                    else:
                        text = reply.message
                else:
                    parts = event.raw_text.split(maxsplit=1)
                    text = parts[1] if len(parts) > 1 else None

                if not text:
                    await event.respond("<b>⚠️ Please provide text or reply to a message/file❌</b>", parse_mode="html")
                    await processing_msg.delete()
                    LOGGER.warning(f"No text provided for /{command} by user {user_id} in chat {event.chat_id}")
                    return

                result = func(text)

                if event.sender:
                    user_full_name = event.sender.first_name + (" " + event.sender.last_name if event.sender.last_name else "")
                    user_mention = f"<a href='tg://user?id={event.sender_id}'>{user_full_name}</a>"
                else:
                    user_mention = "<a href='https://t.me/ItsSmartToolBot'>ItsSmartToolBot</a>"

                LOGGER.info(f"Processed /{command} for user {user_id} in chat {event.chat_id}")

                if len(result) > 4096:
                    file_name = f"{command}_result.txt"
                    with open(file_name, "w", encoding="utf-8") as file:
                        file.write(result)

                    await client.send_file(
                        event.chat_id,
                        file_name,
                        caption=f"✨ <b>Here is your processed file!</b> ✨\n\n"
                                f"📂 <b>Command Used:</b> <code>{command}</code>\n"
                                f"📝 <b>Requested By:</b> {user_mention}\n"
                                f"📜 <b>Processed Successfully!</b> ✅",
                        parse_mode="html"
                    )
                    os.remove(file_name)
                else:
                    await event.respond(f"<b>✅ {command} Result:</b>\n<code>{result}</code>" if command != "wc" else result, parse_mode="html")

            except Exception as e:
                LOGGER.error(f"Error processing /{command} for user {user_id} in chat {event.chat_id}: {str(e)}")
                await notify_admin(client, f"/{command}", e, event)
                await event.respond("<b>❌ Sorry Bro, Invalid Text Provided!</b>", parse_mode="html")

            await processing_msg.delete()
