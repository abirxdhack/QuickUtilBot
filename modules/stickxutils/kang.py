#Copyright @ISmartCoder
#Updates Channel https://t.me/TheSmartDev
import asyncio
import os
import re
import shutil
import tempfile
import uuid
import random
from PIL import Image
from telethon import (
    TelegramClient, 
    events, 
    functions, 
    types, 
    Button
)
from telethon.errors import (
    BadRequestError, 
    PeerIdInvalidError, 
    StickersetInvalidError
)
from telethon.tl.functions.messages import (
    GetStickerSetRequest, 
    SendMediaRequest
)
from telethon.tl.functions.stickers import (
    AddStickerToSetRequest, 
    CreateStickerSetRequest
)
from telethon.tl.types import (
    DocumentAttributeFilename, 
    InputDocument, 
    InputMediaUploadedDocument, 
    InputStickerSetItem, 
    InputStickerSetShortName, 
    InputStickerSetID, 
    MessageMediaDocument
)
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER
from core import banned_users

EMOJI_PATTERN = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251\U0001F900-\U0001F9FF\U0001F018-\U0001F270]+')
FILE_LOCK = asyncio.Lock()

async def resize_png_for_sticker(input_file: str, output_file: str):
    async with FILE_LOCK:
        try:
            with Image.open(input_file) as im:
                width, height = im.size
                if width == 512 or height == 512:
                    im.save(output_file, "PNG", optimize=True)
                    return output_file
                if width > height:
                    new_width = 512
                    new_height = int((512 / width) * height)
                else:
                    new_height = 512
                    new_width = int((512 / height) * width)
                im = im.resize((new_width, new_height), Image.Resampling.LANCZOS)
                im.save(output_file, "PNG", optimize=True)
                return output_file
        except Exception as e:
            LOGGER.error(f"Error resizing PNG: {str(e)}")
            return None

async def process_video_sticker(input_file: str, output_file: str):
    try:
        command = [
            "ffmpeg", "-i", input_file,
            "-t", "3",
            "-vf", "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2,fps=24",
            "-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "150k",
            "-an", "-y",
            output_file
        ]
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            LOGGER.error(f"FFmpeg error: {stderr.decode()}")
            return None
        async with FILE_LOCK:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 256 * 1024:
                LOGGER.warning("File size exceeds 256KB, re-encoding with lower quality")
                command[-3] = "-b:v"
                command[-2] = "100k"
                process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await process.communicate()
                if process.returncode != 0:
                    LOGGER.error(f"FFmpeg error: {stderr.decode()}")
                    return None
        return output_file
    except Exception as e:
        LOGGER.error(f"Error processing video: {str(e)}")
        return None

async def process_gif_to_webm(input_file: str, output_file: str):
    try:
        command = [
            "ffmpeg", "-i", input_file,
            "-t", "3",
            "-vf", "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2,fps=24",
            "-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "150k",
            "-an", "-y",
            output_file
        ]
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            LOGGER.error(f"FFmpeg error: {stderr.decode()}")
            return None
        async with FILE_LOCK:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 256 * 1024:
                LOGGER.warning("File size exceeds 256KB, re-encoding with lower quality")
                command[-3] = "-b:v"
                command[-2] = "100k"
                process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await process.communicate()
                if process.returncode != 0:
                    LOGGER.error(f"FFmpeg error: {stderr.decode()}")
                    return None
        return output_file
    except Exception as e:
        LOGGER.error(f"Error processing GIF: {str(e)}")
        return None

async def cleanup_files(temp_files):
    async def remove_file(file):
        try:
            async with FILE_LOCK:
                os.remove(file)
        except:
            LOGGER.warning(f"Failed to remove temporary file: {file}")
    await asyncio.gather(*[remove_file(file) for file in temp_files])

def setup_kang_handler(app: TelegramClient):
    if not COMMAND_PREFIX:
        prefixes = ["/"]
    else:
        prefixes = COMMAND_PREFIX if isinstance(COMMAND_PREFIX, list) else [COMMAND_PREFIX]
    
    prefix_pattern = "|".join(re.escape(p) for p in prefixes)
    pattern = f"^({prefix_pattern})kang(?:\\s+(.*))?$"
    
    @app.on(events.NewMessage(pattern=pattern))
    async def kang(event):
        user_id = event.sender_id
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='markdown')
            return

        user = await event.get_sender()
        bot_me = await app.get_me()
        packnum = 1
        packname = f"a{user.id}_by_{bot_me.username}"
        max_stickers = 120
        temp_files = []

        temp_message = await event.respond("<b>Kanging this Sticker...✨</b>", parse_mode='html')

        async def check_sticker_set():
            nonlocal packnum, packname
            while packnum <= 100:
                try:
                    stickerset = await app(GetStickerSetRequest(
                        stickerset=InputStickerSetShortName(short_name=packname),
                        hash=0
                    ))
                    if stickerset.set.count < max_stickers:
                        return True
                    packnum += 1
                    packname = f"a{packnum}_{user.id}_by_{bot_me.username}"
                except StickersetInvalidError:
                    return False
            return False

        packname_found = await check_sticker_set()
        if not packname_found and packnum > 100:
            await temp_message.edit("<b>❌ Maximum sticker packs reached!</b>", parse_mode='html')
            return

        reply = await event.get_reply_message()
        if not reply:
            await temp_message.edit("<b>Please reply to a sticker, image, or document to kang it!</b>", parse_mode='html')
            return

        file_id = None
        if reply.sticker:
            file_id = reply.sticker
        elif reply.photo:
            file_id = reply.photo
        elif reply.document:
            file_id = reply.document
        elif reply.gif:
            file_id = reply.gif
        else:
            await temp_message.edit("<b>Please reply to a valid sticker, image, GIF, or document!</b>", parse_mode='html')
            return

        sticker_format = "png"
        if reply.sticker:
            if hasattr(reply.sticker, 'mime_type'):
                if reply.sticker.mime_type == "application/x-tgsticker":
                    sticker_format = "tgs"
                elif reply.sticker.mime_type == "video/webm":
                    sticker_format = "webm"
        elif reply.gif or (reply.document and reply.document.mime_type == "image/gif"):
            sticker_format = "gif"

        try:
            file_name = f"kangsticker_{uuid.uuid4().hex}"
            if sticker_format == "tgs":
                kang_file = await app.download_media(file_id, file=f"{file_name}.tgs")
            elif sticker_format == "webm":
                kang_file = await app.download_media(file_id, file=f"{file_name}.webm")
            elif sticker_format == "gif":
                kang_file = await app.download_media(file_id, file=f"{file_name}.gif")
            else:
                kang_file = await app.download_media(file_id, file=f"{file_name}.png")
            
            if not kang_file:
                await temp_message.edit("<b>❌ Failed To Kang The Sticker</b>", parse_mode='html')
                await cleanup_files(temp_files)
                return
            
            temp_files.append(kang_file)

        except Exception as e:
            LOGGER.error(f"Download error: {str(e)}")
            await temp_message.edit("<b>❌ Failed To Kang The Sticker</b>", parse_mode='html')
            await cleanup_files(temp_files)
            return

        sticker_emoji = "🌟"
        if event.pattern_match.group(2):
            emoji_matches = "".join(set(EMOJI_PATTERN.findall(event.pattern_match.group(2))))
            sticker_emoji = emoji_matches or sticker_emoji
        elif reply.sticker and hasattr(reply.sticker, 'emoticon') and reply.sticker.emoticon:
            sticker_emoji = reply.sticker.emoticon

        full_name = user.first_name or ""
        if user.last_name:
            full_name += f" {user.last_name}"
        pack_title = f"{full_name}'s Pack"

        try:
            if sticker_format == "png":
                output_file = f"resized_{uuid.uuid4().hex}.png"
                processed_file = await resize_png_for_sticker(kang_file, output_file)
                if not processed_file:
                    await temp_message.edit("<b>❌ Failed To Kang The Sticker</b>", parse_mode='html')
                    await cleanup_files(temp_files)
                    return
                kang_file = processed_file
                temp_files.append(kang_file)
            
            elif sticker_format == "gif":
                output_file = f"compressed_{uuid.uuid4().hex}.webm"
                processed_file = await process_gif_to_webm(kang_file, output_file)
                if not processed_file:
                    await temp_message.edit("<b>❌ Failed To Kang The Sticker</b>", parse_mode='html')
                    await cleanup_files(temp_files)
                    return
                kang_file = output_file
                sticker_format = "webm"
                temp_files.append(kang_file)
            
            elif sticker_format == "webm":
                output_file = f"compressed_{uuid.uuid4().hex}.webm"
                processed_file = await process_video_sticker(kang_file, output_file)
                if not processed_file:
                    await temp_message.edit("<b>❌ Failed To Kang The Sticker</b>", parse_mode='html')
                    await cleanup_files(temp_files)
                    return
                kang_file = output_file
                temp_files.append(kang_file)

            async def upload_and_add_sticker():
                file = await app.upload_file(kang_file)
                
                mime_type = "image/png"
                if sticker_format == "tgs":
                    mime_type = "application/x-tgsticker"
                elif sticker_format == "webm":
                    mime_type = "video/webm"
                
                media = await app(SendMediaRequest(
                    peer=await app.get_input_entity(event.chat_id),
                    media=InputMediaUploadedDocument(
                        file=file,
                        mime_type=mime_type,
                        attributes=[DocumentAttributeFilename(file_name=os.path.basename(kang_file))],
                    ),
                    message=f"#Sticker kang by UserID -> {user.id}",
                    random_id=random.randint(1, 2**63),
                ))
                return media.updates[-1].message

            async def add_to_sticker_set(stkr_file):
                try:
                    await app(AddStickerToSetRequest(
                        stickerset=InputStickerSetShortName(short_name=packname),
                        sticker=InputStickerSetItem(
                            document=InputDocument(
                                id=stkr_file.id,
                                access_hash=stkr_file.access_hash,
                                file_reference=stkr_file.file_reference,
                            ),
                            emoji=sticker_emoji,
                        ),
                    ))
                    return True
                except StickersetInvalidError:
                    await app(CreateStickerSetRequest(
                        user_id=await app.get_input_entity(user.id),
                        title=pack_title,
                        short_name=packname,
                        stickers=[
                            InputStickerSetItem(
                                document=InputDocument(
                                    id=stkr_file.id,
                                    access_hash=stkr_file.access_hash,
                                    file_reference=stkr_file.file_reference,
                                ),
                                emoji=sticker_emoji,
                            )
                        ],
                    ))
                    return True
                except Exception as e:
                    LOGGER.error(f"Error adding sticker: {str(e)}")
                    return False

            msg_ = await upload_and_add_sticker()
            stkr_file = msg_.media.document
            success = await add_to_sticker_set(stkr_file)

            if success:
                keyboard = [Button.url("View Sticker Pack", f"t.me/addstickers/{packname}")]
                await temp_message.edit(
                    f"**Sticker Kanged! **\n**Emoji: {sticker_emoji}**\n**Pack: {pack_title}**",
                    buttons=keyboard,
                    parse_mode='markdown'
                )
                await app.delete_messages(event.chat_id, msg_.id)
            else:
                await temp_message.edit("<b>❌ Failed To Kang The Sticker</b>", parse_mode='html')

        except Exception as e:
            LOGGER.error(f"Processing error: {str(e)}")
            await temp_message.edit("<b>❌ Failed To Kang The Sticker</b>", parse_mode='html')
        
        finally:
            await cleanup_files(temp_files)
