import os
import time
import subprocess
import asyncio
from concurrent.futures import ThreadPoolExecutor
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeVideo
from config import COMMAND_PREFIX, BAN_REPLY
from core import banned_users
from utils import LOGGER, notify_admin

executor = ThreadPoolExecutor(max_workers=8)

def run_ffmpeg(ffmpeg_cmd):
    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        try:
            err = e.stderr.decode()
        except Exception:
            err = str(e)
        LOGGER.error(f"[VNOTE] FFmpeg failed: {err}")
        raise

def _is_video_message(msg):
    if getattr(msg, "video", None):
        return True
    doc = getattr(msg, "document", None)
    if doc and getattr(doc, "mime_type", None) and doc.mime_type.startswith("video/"):
        return True
    return False

def _get_video_duration(msg):
    d = getattr(msg, "duration", None)
    if d:
        try:
            return int(d)
        except Exception:
            pass
    doc = getattr(msg, "document", None)
    if doc and getattr(doc, "attributes", None):
        for a in doc.attributes:
            if isinstance(a, DocumentAttributeVideo) and getattr(a, "duration", None):
                try:
                    return int(a.duration)
                except Exception:
                    return None
    return None

def setup_vnote_handler(client: TelegramClient):
    @client.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}vnote$'))
    async def vnote_handler(event):
        user_id = event.sender_id
        chat_id = event.chat_id
        if await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='markdown')
            return
        reply = await event.get_reply_message()
        if not reply or not _is_video_message(reply):
            await event.respond("**❗ Reply to a video with this command**", parse_mode='markdown')
            return
        duration = _get_video_duration(reply)
        if duration and duration > 60:
            await event.respond("**❗ Video too long (max 60s)**", parse_mode='markdown')
            return
        status = await event.respond("**Converting video to video note...**", parse_mode='markdown')
        os.makedirs("downloads", exist_ok=True)
        input_path = f"downloads/input_{user_id}_{int(time.time())}.mp4"
        output_path = f"downloads/output_{user_id}_{int(time.time())}.mp4"
        try:
            input_path = await client.download_media(reply, file=input_path)
            if not input_path or not os.path.exists(input_path):
                raise FileNotFoundError("Download failed")
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-vf", "crop='min(iw,ih):min(iw,ih)',scale=640:640",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
                "-c:a", "aac", "-b:a", "96k", "-ar", "32000",
                "-t", "60", "-movflags", "+faststart", output_path
            ]
            await asyncio.get_event_loop().run_in_executor(executor, run_ffmpeg, ffmpeg_cmd)
            send_duration = min(duration or 0, 60)
            attrs = [DocumentAttributeVideo(duration=send_duration, w=640, h=640, round_message=True, supports_streaming=True)]
            await client.send_file(event.chat_id, file=output_path, video_note=True, attributes=attrs)
            await status.delete()
        except Exception as e:
            LOGGER.error(f"[VNOTE] {str(e)}")
            await notify_admin(client, "/vnote", e, event)
            await status.edit(text="**❌ Could not process video**", parse_mode='markdown')
        finally:
            for f in [input_path, output_path]:
                if f and os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        LOGGER.warning(f"[VNOTE] Cleanup error for {f}")
            LOGGER.info(f"[VNOTE] Cleaned up: {[input_path, output_path]}")

    return client