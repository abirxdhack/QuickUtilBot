import aiohttp
import secrets
import urllib.parse
from datetime import datetime
from mimetypes import guess_type
from typing import Optional, Tuple
from telethon import TelegramClient, events, Button
from telethon.tl.types import DocumentAttributeFilename, DocumentAttributeVideo, DocumentAttributeAudio
from config import COMMAND_PREFIX, BAN_REPLY, LOG_CHANNEL_ID
from utils import notify_admin, LOGGER
from core import banned_users

class Server:
    BASE_URL = "https://fdlapi-ed9a85898ea5.herokuapp.com"

async def check_channel_membership(client: TelegramClient, user_id: int) -> Tuple[bool, str, Optional[int]]:
    try:
        if not LOG_CHANNEL_ID:
            return False, "LOG_CHANNEL_ID is not configured", None
        
        channel_id = LOG_CHANNEL_ID
        if isinstance(channel_id, str):
            if channel_id.startswith("@"):
                pass
            else:
                try:
                    channel_id = int(channel_id)
                except (ValueError, TypeError):
                    return False, f"Invalid LOG_CHANNEL_ID format: {LOG_CHANNEL_ID}. Must be integer or @username.", None
        
        if isinstance(channel_id, int):
            if channel_id > 0:
                channel_id = -channel_id
            if not str(abs(channel_id)).startswith("100"):
                channel_id = int(f"-100{abs(channel_id)}")
        
        async for participant in client.iter_participants(channel_id):
            if participant.id == user_id:
                return True, "", channel_id
        
        return False, f"User {user_id} is not a member of the channel", channel_id
        
    except Exception as e:
        error_msg = str(e).lower()
        if "user not found" in error_msg:
            return False, f"User {user_id} not found in channel", None
        elif "chat not found" in error_msg or "channel_invalid" in error_msg:
            return False, f"Channel {LOG_CHANNEL_ID} not found or invalid", None
        elif "peer_id_invalid" in error_msg:
            return False, f"Invalid channel ID: {LOG_CHANNEL_ID}", None
        elif "forbidden" in error_msg:
            return False, f"Bot doesn't have permission to check membership in channel {LOG_CHANNEL_ID}", None
        else:
            return False, f"Failed to check membership: {str(e)}", None

async def get_file_properties(message):
    file_name = None
    file_size = 0
    mime_type = None
    
    if message.document:
        file_size = message.document.size
        mime_type = message.document.mime_type
        
        for attr in message.document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                file_name = attr.file_name
                break
                
    elif message.video:
        file_name = getattr(message.video, 'file_name', None)
        file_size = message.video.size
        mime_type = message.video.mime_type
                    
    elif message.audio:
        file_name = getattr(message.audio, 'file_name', None)
        file_size = message.audio.size
        mime_type = message.audio.mime_type
                    
    elif message.photo:
        file_name = None
        file_size = message.photo.sizes[-1].size if message.photo.sizes else 0
        mime_type = "image/jpeg"
        
    elif message.video_note:
        file_name = None
        file_size = message.video_note.size
        mime_type = "video/mp4"
    
    if not file_name:
        attributes = {
            "video": "mp4",
            "audio": "mp3",
            "video_note": "mp4",
            "photo": "jpg",
        }
        for attribute in attributes:
            if getattr(message, attribute, None):
                file_type, file_format = attribute, attributes[attribute]
                break
        else:
            raise ValueError("Invalid media type.")
        date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"{file_type}-{date}.{file_format}"
    
    if not mime_type:
        mime_type = guess_type(file_name)[0] or "application/octet-stream"
    
    return file_name, file_size, mime_type

async def format_file_size(file_size):
    if file_size < 1024 * 1024:
        size = file_size / 1024
        unit = "KB"
    elif file_size < 1024 * 1024 * 1024:
        size = file_size / (1024 * 1024)
        unit = "MB"
    else:
        size = file_size / (1024 * 1024 * 1024)
        unit = "GB"
    return f"{size:.2f} {unit}"

def setup_fdl_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}fdl$'))
    async def handle_file_download(event):
        user_id = event.sender_id
        
        if await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY)
            return
            
        is_member, msg, resolved_channel_id = await check_channel_membership(app, user_id)
        if not is_member:
            await event.respond(f"**❌ {msg}**", parse_mode='markdown')
            return
        
        reply = await event.get_reply_message()
        if not reply or not (reply.document or reply.video or reply.photo or reply.audio or reply.video_note):
            await event.respond("**Please Reply To A Valid File**", parse_mode='markdown')
            return
        
        processing_msg = await event.respond("**Processing Your File.....**", parse_mode='markdown')
        file_id = None
        
        try:
            bot_member = await app.get_permissions(resolved_channel_id, "me")
            if not bot_member.is_admin:
                await processing_msg.edit(text="**Error: Bot must be an admin in the log channel**", parse_mode='markdown')
                return
            
            code = secrets.token_urlsafe(6)[:6]
            file_name, file_size, mime_type = await get_file_properties(reply)
            
            if event.chat_id == resolved_channel_id:
                file_id = reply.id
                sent = await app.send_message(
                    resolved_channel_id,
                    code,
                    file=reply.media,
                    reply_to=reply.id
                )
                file_id = sent.id
            else:
                sent = await app.send_message(
                    resolved_channel_id,
                    code,
                    file=reply.media
                )
                file_id = sent.id
            
            quoted_code = urllib.parse.quote(code)
            base_url = Server.BASE_URL.rstrip('/')
            download_link = f"{base_url}/dl/{file_id}?code={quoted_code}"
            
            is_video = mime_type.startswith('video') or reply.video or reply.video_note
            stream_link = f"{base_url}/stream/{file_id}?code={quoted_code}" if is_video else None
            
            buttons = [Button.url("🚀 Download Link", download_link)]
            if stream_link:
                buttons.append(Button.url("🖥 Stream Link", stream_link))
            
            response = (
                f"**✨ Your Links are Ready! ✨**\n\n"
                f"> {file_name}\n\n"
                f"**📂 File Size: {await format_file_size(file_size)}**\n\n"
                f"**🚀 Download Link:** {download_link}\n\n"
            )
            
            if stream_link:
                response += f"**🖥 Stream Link:** {stream_link}\n\n"
            
            response += "**⌛️ Note: Links remain active while the bot is running and the file is accessible.**"
            
            await processing_msg.edit(
                text=response, 
                parse_mode='markdown', 
                buttons=buttons,
                link_preview=False
            )
            
            LOGGER.info(f"Generated links for file_id: {file_id}, download: {download_link}, stream: {stream_link}")
            
        except Exception as e:
            LOGGER.error(f"Error generating links for file_id: {file_id if file_id else 'unknown'}, error: {str(e)}")
            await processing_msg.edit(text="**Sorry Failed To Generate Link**", parse_mode='markdown')
            await notify_admin(app, "/fdl", e, event)

    return app