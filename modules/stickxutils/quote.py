#Copyright @ISmartCoder
#Updates Channel https://t.me/TheSmartDev
import aiohttp
import asyncio
import base64
import os
import re
from telethon import TelegramClient, events
from telethon.tl.types import (
    User, Chat, Channel, MessageEntityCustomEmoji, 
    DocumentAttributeImageSize, PhotoSize, UserProfilePhoto,
    ChatPhoto, MessageMediaPhoto, MessageMediaDocument,
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntityPre, MessageEntityTextUrl, MessageEntityMention,
    MessageEntityHashtag, MessageEntityCashtag, MessageEntityBotCommand,
    MessageEntityUrl, MessageEntityEmail, MessageEntityPhone,
    MessageEntityMentionName, MessageEntityStrike, MessageEntityUnderline,
    MessageEntitySpoiler, MessageEntityBlockquote, PeerUser, PeerChat, PeerChannel,
    DocumentAttributeSticker, DocumentAttributeAnimated, DocumentAttributeVideo,
    SendMessageChooseStickerAction
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import GetMessagesRequest, SetTypingRequest
from telethon.errors import RPCError
from telethon.utils import get_display_name
from PIL import Image
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER
from core import banned_users
import json

logger = LOGGER

MAX_CONCURRENT_TASKS = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

async def download_default_avatar(client, url, session):
    async with semaphore:
        if "t.me/" in url:
            parts = url.split("/")
            if len(parts) >= 5:
                chat_username = parts[3]
                message_id = int(parts[4])
                try:
                    entity = await client.get_entity(chat_username)
                    message = await client.get_messages(entity, ids=message_id)
                    if message and hasattr(message, 'media') and message.media:
                        return await client.download_media(message.media)
                    return None
                except Exception as e:
                    logger.error(f"Failed to get message from Telegram: {e}")
                    return None
            return None
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    temp_file = f"default_avatar_{os.urandom(4).hex()}.jpg"
                    content = await response.read()
                    with open(temp_file, 'wb') as f:
                        f.write(content)
                    return temp_file
                return None
        except Exception as e:
            logger.error(f"Error downloading default avatar: {e}")
            return None

async def upload_to_imgbb(image_path, session):
    try:
        async with semaphore:
            with open(image_path, "rb") as file:
                image_data = base64.b64encode(file.read()).decode('utf-8')
            api_key = "134919706cb1f04cb24f6069213fc1d9"
            upload_url = "https://api.imgbb.com/1/upload"
            payload = {"key": api_key, "image": image_data}
            async with session.post(upload_url, data=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("success"):
                        return result["data"]["url"]
                return None
    except Exception as e:
        logger.error(f"Failed to upload image to ImgBB: {e}")
        return None

async def convert_photo_to_sticker(photo_path):
    try:
        async with semaphore:
            with Image.open(photo_path) as img:
                img.thumbnail((512, 512), Image.Resampling.LANCZOS)
                square_size = max(img.size)
                sticker = Image.new('RGBA', (square_size, square_size), (0, 0, 0, 0))
                offset = ((square_size - img.size[0]) // 2, (square_size - img.size[1]) // 2)
                sticker.paste(img, offset)
                sticker_path = f"sticker_{os.urandom(4).hex()}.webp"
                sticker.save(sticker_path, 'WEBP', quality=85)
                return sticker_path
    except Exception as e:
        logger.error(f"Failed to convert photo to sticker: {e}")
        return None

async def convert_sticker_to_image(sticker_path):
    async with semaphore:
        try:
            with Image.open(sticker_path) as img:
                img.thumbnail((512, 512), Image.Resampling.LANCZOS)
                photo_path = f"converted_{os.urandom(4).hex()}.jpg"
                img.convert('RGB').save(photo_path, "JPEG")
            return photo_path
        except Exception as e:
            logger.error(f"Failed to convert sticker: {e}")
            return None

async def get_emoji_status(client, user_id):
    try:
        async with semaphore:
            try:
                user_entity = await client.get_entity(user_id)
                full_user = await client(GetFullUserRequest(user_entity))
                if hasattr(full_user, 'full_user') and hasattr(full_user.full_user, 'emoji_status'):
                    emoji_status = full_user.full_user.emoji_status
                    if hasattr(emoji_status, 'document_id'):
                        return str(emoji_status.document_id)
            except Exception:
                pass
            
            user = await client.get_entity(user_id)
            if hasattr(user, 'emoji_status') and user.emoji_status:
                if hasattr(user.emoji_status, 'document_id'):
                    return str(user.emoji_status.document_id)
            return None
    except Exception as e:
        logger.error(f"Failed to fetch emoji status for user {user_id}: {e}", exc_info=True)
        return None

async def extract_premium_emojis(message, offset_adjust=0):
    premium_emoji_entities = []
    if hasattr(message, 'entities') and message.entities:
        for entity in message.entities:
            if isinstance(entity, MessageEntityCustomEmoji):
                entity_data = {
                    "type": "custom_emoji",
                    "offset": entity.offset - offset_adjust,
                    "length": entity.length,
                    "document_id": str(entity.document_id)
                }
                premium_emoji_entities.append(entity_data)
    return premium_emoji_entities

async def extract_message_entities(message, skip_command_prefix=False, command_prefix_length=0):
    entities = []
    
    def process_entity(entity, is_caption=False):
        adjusted_offset = entity.offset - (command_prefix_length if skip_command_prefix else 0)
        if skip_command_prefix and entity.offset < command_prefix_length:
            return None
        
        entity_type_map = {
            MessageEntityBold: "bold",
            MessageEntityItalic: "italic", 
            MessageEntityCode: "code",
            MessageEntityPre: "pre",
            MessageEntityTextUrl: "text_link",  
            MessageEntityUrl: "url",
            MessageEntityMention: "mention",
            MessageEntityHashtag: "hashtag",
            MessageEntityCashtag: "cashtag",
            MessageEntityBotCommand: "bot_command",
            MessageEntityEmail: "email",
            MessageEntityPhone: "phone_number",
            MessageEntityMentionName: "text_mention",
            MessageEntityStrike: "strikethrough",
            MessageEntityUnderline: "underline",
            MessageEntitySpoiler: "spoiler",
            MessageEntityBlockquote: "blockquote",
            MessageEntityCustomEmoji: "custom_emoji"
        }
        
        entity_type = entity_type_map.get(type(entity), "unknown")
        entity_data = {"type": entity_type, "offset": adjusted_offset, "length": entity.length}
        
        
        if isinstance(entity, MessageEntityCustomEmoji):
            entity_data["document_id"] = str(entity.document_id)
        elif isinstance(entity, MessageEntityTextUrl):
            entity_data['url'] = entity.url
        elif isinstance(entity, MessageEntityMentionName):
            entity_data['user'] = str(entity.user_id)
        elif isinstance(entity, MessageEntityPre) and hasattr(entity, 'language') and entity.language:
            entity_data['language'] = entity.language
        
        return entity_data

    
    if hasattr(message, 'entities') and message.entities:
        for entity in message.entities:
            entity_data = process_entity(entity)
            if entity_data and entity_data["type"] != "unknown":
                entities.append(entity_data)
    
    return entities

async def is_media_supported(media):
    if isinstance(media, MessageMediaPhoto):
        return True, "photo"
    elif isinstance(media, MessageMediaDocument):
        doc = media.document
        mime_type = doc.mime_type
        
        if mime_type in ['image/webp', 'application/x-tgsticker']:
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeSticker):
                    return True, "sticker"
        
        if mime_type.startswith('video/'):
            for attr in doc.attributes:
                if isinstance(attr, (DocumentAttributeVideo, DocumentAttributeAnimated)):
                    return True, "video" if isinstance(attr, DocumentAttributeVideo) else "animation"
        
        if mime_type.startswith('image/'):
            return True, "photo"
    
    return False, None

async def generate_quote(client: TelegramClient, event, session):
    
    avatar_file_path = None
    photo_path = None
    sticker_path = None
    
    try:
        
        await client(SetTypingRequest(
            peer=event.peer_id,
            action=SendMessageChooseStickerAction()
        ))
        await asyncio.sleep(1)
        
        message = event.message
        command_parts = message.text.split()
        replied_message = await message.get_reply_message() if message.is_reply else None
        text = None
        user = None
        user_id = None
        full_name = None
        message_entities = []

        async with semaphore:
            if replied_message and len(command_parts) == 1 and (replied_message.text or replied_message.media):
                if replied_message.forward:
                    if replied_message.forward.sender_id:
                        try:
                            user = await client.get_entity(replied_message.forward.sender_id)
                        except:
                            user = await client.get_entity(replied_message.sender_id) if replied_message.sender_id else None
                    elif replied_message.forward.sender_name:
                        full_name = replied_message.forward.sender_name
                        user_id = None
                    else:
                        user = await client.get_entity(replied_message.sender_id) if replied_message.sender_id else None
                else:
                    user = await client.get_entity(replied_message.sender_id) if replied_message.sender_id else None
            elif replied_message and len(command_parts) > 1:
                if replied_message.forward:
                    if replied_message.forward.sender_id:
                        try:
                            user = await client.get_entity(replied_message.forward.sender_id)
                        except:
                            user = await client.get_entity(replied_message.sender_id) if replied_message.sender_id else None
                    elif replied_message.forward.sender_name:
                        full_name = replied_message.forward.sender_name
                        user_id = None
                    else:
                        user = await client.get_entity(replied_message.sender_id) if replied_message.sender_id else None
                else:
                    user = await client.get_entity(replied_message.sender_id) if replied_message.sender_id else None
                text = " ".join(command_parts[1:])
            elif len(command_parts) > 1:
                user = await client.get_entity(message.sender_id) if message.sender_id else None
                text = " ".join(command_parts[1:])

            if user and isinstance(user, User):
                full_name = get_display_name(user)
                user_id = user.id
                if user.photo:
                    try:
                        avatar_file_path = await client.download_profile_photo(user)
                    except Exception as e:
                        logger.error(f"Failed to download user photo: {e}")
                        avatar_file_path = None
            elif not full_name:
                if message.is_group or message.is_channel:
                    chat = await client.get_entity(message.peer_id)
                    if isinstance(chat, (Chat, Channel)):
                        full_name = chat.title
                        user_id = chat.id
                        if chat.photo:
                            try:
                                avatar_file_path = await client.download_profile_photo(chat)
                            except Exception as e:
                                logger.error(f"Failed to download chat photo: {e}")
                                avatar_file_path = None
                else:
                    user = await client.get_entity(message.sender_id) if message.sender_id else None
                    if user:
                        full_name = get_display_name(user)
                        user_id = user.id

            avatar_base64 = None
            if avatar_file_path:
                async with semaphore:
                    with open(avatar_file_path, "rb") as file:
                        avatar_data = file.read()
                    avatar_base64 = base64.b64encode(avatar_data).decode()

            font_size = "small"

            emoji_status_id = await get_emoji_status(client, user_id) if user_id and user_id > 0 else None
            from_payload = {
                "id": str(user_id) if user_id else "0",
                "name": full_name or "Anonymous",
                "fontSize": font_size
            }
            if avatar_file_path and user_id and avatar_base64:
                from_payload["photo"] = {"url": f"data:image/jpeg;base64,{avatar_base64}"}
            if emoji_status_id and user_id:
                from_payload["emoji_status"] = emoji_status_id

            if replied_message and len(command_parts) == 1 and replied_message.media:
                supported, media_type = await is_media_supported(replied_message.media)
                
                if not supported:
                    await client.send_message(event.chat_id, "**❌ Unsupported media type.**")
                    return
                
                try:
                    if media_type == "photo":
                        photo_path = await client.download_media(replied_message.media)
                        if not photo_path:
                            logger.error("Failed to download replied photo")
                            await client.send_message(event.chat_id, "**❌ Failed To Generate Sticker**")
                            return
                    elif media_type == "sticker":
                        doc = replied_message.media.document
                        is_animated = any(isinstance(attr, DocumentAttributeAnimated) for attr in doc.attributes)
                        is_video_sticker = doc.mime_type == 'video/webm'
                        
                        if is_animated or is_video_sticker:
                            if doc.thumbs:
                                sticker_path = await client.download_media(replied_message.media, thumb=-1)
                            else:
                                await client.send_message(event.chat_id, "**❌ Sticker has no thumbnail.**")
                                return
                        else:
                            sticker_path = await client.download_media(replied_message.media)
                        
                        photo_path = await convert_sticker_to_image(sticker_path)
                        if not photo_path:
                            logger.error("Failed to convert sticker to image")
                            await client.send_message(event.chat_id, "**❌ Failed To Generate Sticker**")
                            return
                    elif media_type in ["video", "animation"]:
                        doc = replied_message.media.document
                        if doc.thumbs:
                            photo_path = await client.download_media(replied_message.media, thumb=-1)
                            if not photo_path:
                                logger.error("Failed to download media thumbnail")
                                await client.send_message(event.chat_id, "**❌ Failed To Generate Sticker**")
                                return
                        else:
                            await client.send_message(event.chat_id, "**❌ Media has no thumbnail.**")
                            return

                    hosted_url = await upload_to_imgbb(photo_path, session)
                    if not hosted_url:
                        async with semaphore:
                            with open(photo_path, "rb") as file:
                                content = file.read()
                            photo_base64 = base64.b64encode(content).decode()
                            hosted_url = f"data:image/jpeg;base64,{photo_base64}"

                    text = replied_message.raw_text if replied_message.raw_text else ""

                    message_entities = await extract_message_entities(replied_message)
                    premium_emojis = await extract_premium_emojis(replied_message)
                    if premium_emojis:
                        existing_offsets = [e['offset'] for e in message_entities if e.get("type") == "custom_emoji"]
                        for emoji in premium_emojis:
                            if emoji['offset'] not in existing_offsets:
                                message_entities.append(emoji)

                    json_data = {
                        "type": "quote",
                        "format": "webp",
                        "backgroundColor": "#000000",
                        "width": 512,
                        "height": 768,
                        "scale": 2,
                        "messages": [
                            {
                                "entities": message_entities,
                                "avatar": bool(avatar_file_path and user_id),
                                "from": from_payload,
                                "media": {"type": "photo", "url": hosted_url},
                                "text": text,
                                "textFontSize": font_size
                            }
                        ]
                    }
                    
                    async with semaphore:
                        async with session.post('https://bot.lyo.su/quote/generate', json=json_data) as response:
                            if response.status != 200:
                                logger.error(f"Quotly API error: {response.status} - {await response.text()}")
                                raise Exception(f"API returned status code {response.status}")
                            response_json = await response.json()
                            if 'result' not in response_json or 'image' not in response_json['result']:
                                logger.error(f"Invalid response from API: {response_json}")
                                raise Exception("Invalid response from API")

                    async with semaphore:
                        buffer = base64.b64decode(response_json['result']['image'].encode('utf-8'))
                        file_path = 'Quotly.webp'
                        with open(file_path, 'wb') as f:
                            f.write(buffer)
                        try:
                            await client.send_file(
                                event.chat_id,
                                file_path,
                                attributes=[DocumentAttributeImageSize(512, 512)]
                            )
                            logger.info("Sticker sent successfully")
                        except Exception as e:
                            logger.error(f"Failed to send sticker: {e}", exc_info=True)
                            raise
                except Exception as e:
                    logger.error(f"Error creating sticker from media: {e}", exc_info=True)
                    await client.send_message(event.chat_id, "**❌ Failed To Generate Sticker**")
                finally:
                    async with semaphore:
                        if avatar_file_path and os.path.exists(avatar_file_path):
                            os.remove(avatar_file_path)
                        if photo_path and os.path.exists(photo_path):
                            os.remove(photo_path)
                        if sticker_path and os.path.exists(sticker_path):
                            os.remove(sticker_path)
                        if os.path.exists('Quotly.webp'):
                            os.remove('Quotly.webp')
                return

            if replied_message and len(command_parts) == 1:
                if replied_message.raw_text or (hasattr(replied_message, 'caption') and replied_message.caption):
                    # Use raw_text to get unformatted text (without markdown asterisks)
                    text = replied_message.raw_text or replied_message.caption
                    message_entities = await extract_message_entities(replied_message)
                    premium_emojis = await extract_premium_emojis(replied_message)
                    if premium_emojis:
                        existing_offsets = [e['offset'] for e in message_entities if e.get("type") == "custom_emoji"]
                        for emoji in premium_emojis:
                            if emoji['offset'] not in existing_offsets:
                                message_entities.append(emoji)
                    logger.info(f"Replied message text: '{text}' with {len(message_entities)} entities")
                else:
                    await client.send_message(event.chat_id, "**Please send text, a sticker, a photo, a video, or a GIF to create your sticker.**")
                    return
            elif len(command_parts) > 1:
                
                full_raw_text = message.raw_text
                command_with_space = command_parts[0] + " "
                if full_raw_text.startswith(command_with_space):
                    text = full_raw_text[len(command_with_space):]
                else:
                    text = " ".join(command_parts[1:])  
                
                message_entities = await extract_message_entities(message, skip_command_prefix=True, command_prefix_length=len(command_parts[0]) + 1)
                premium_emojis = await extract_premium_emojis(message, offset_adjust=len(command_parts[0]) + 1)
                if premium_emojis:
                    existing_offsets = [e['offset'] for e in message_entities if e.get("type") == "custom_emoji"]
                    for emoji in premium_emojis:
                        if emoji['offset'] not in existing_offsets:
                            message_entities.append(emoji)
                logger.info(f"Command text: '{text}' with {len(message_entities)} entities")
            else:
                await client.send_message(event.chat_id, "**Please send text, a sticker, a photo, a video, or a GIF to create your sticker.**")
                return

            if message_entities:
                logger.info(f"Extracted entities: {message_entities}")
                for i, entity in enumerate(message_entities, 1):
                    if entity.get("type") == "custom_emoji" and "document_id" not in entity:
                        logger.error(f"Premium emoji {i} is missing document_id!")
                    logger.debug(f"Entity {i}: type={entity.get('type')}, offset={entity.get('offset')}, length={entity.get('length')}")
            else:
                logger.info("No message entities found")

            json_data = {
                "type": "quote",
                "format": "webp",
                "backgroundColor": "#000000",
                "width": 512,
                "height": 768,
                "scale": 2,
                "messages": [
                    {
                        "entities": message_entities,
                        "avatar": bool(avatar_file_path and user_id),
                        "from": from_payload,
                        "text": text or "",
                        "textFontSize": font_size,
                        "replyMessage": {}
                    }
                ]
            }
            
            async with semaphore:
                async with session.post('https://bot.lyo.su/quote/generate', json=json_data) as response:
                    if response.status != 200:
                        logger.error(f"Quotly API error: {response.status} - {await response.text()}")
                        raise Exception(f"API returned status code {response.status}")
                    response_json = await response.json()
                    if 'result' not in response_json or 'image' not in response_json['result']:
                        logger.error(f"Invalid response from API: {response_json}")
                        raise Exception("Invalid response from API")

            async with semaphore:
                buffer = base64.b64decode(response_json['result']['image'].encode('utf-8'))
                file_path = 'Quotly.webp'
                with open(file_path, 'wb') as f:
                    f.write(buffer)
                try:
                    await client.send_file(
                        event.chat_id,
                        file_path,
                        attributes=[DocumentAttributeImageSize(512, 512)]
                    )
                    logger.info("Sticker sent successfully")
                except Exception as e:
                    logger.error(f"Failed to send sticker: {e}", exc_info=True)
                    raise
    except Exception as e:
        logger.error(f"Error generating quote: {e}", exc_info=True)
        await client.send_message(event.chat_id, "**❌ Failed To Generate Sticker**")
    finally:
        async with semaphore:
            if avatar_file_path and os.path.exists(avatar_file_path):
                os.remove(avatar_file_path)
            if photo_path and os.path.exists(photo_path):
                os.remove(photo_path)
            if sticker_path and os.path.exists(sticker_path):
                os.remove(sticker_path)
            if os.path.exists('Quotly.webp'):
                os.remove('Quotly.webp')

def setup_q_handler(app: TelegramClient):
    command_regex = '|'.join(re.escape(prefix) for prefix in COMMAND_PREFIX)
    pattern = rf'^[{command_regex}]q(\s|$)'
    
    @app.on(events.NewMessage(pattern=pattern))
    async def q_command(event):
        if event.is_private or event.is_group:
            user_id = event.sender_id if event.sender_id else None
            if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
                await event.reply(BAN_REPLY)
                return

            async with aiohttp.ClientSession() as session:
                try:
                    await generate_quote(app, event, session)
                except Exception as e:
                    logger.error(f"Unhandled exception in q_command: {e}", exc_info=True)
                    await event.reply("**❌ Failed To Generate Sticker**")