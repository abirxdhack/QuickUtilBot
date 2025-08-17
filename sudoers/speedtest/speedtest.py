import asyncio
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor
from telethon import TelegramClient, events
from telethon.tl.custom import Button
from config import OWNER_ID, COMMAND_PREFIX, UPDATE_CHANNEL_URL
from core import auth_admins
from utils import LOGGER

logger = LOGGER

def speed_convert(size: float, is_mbps: bool = False) -> str:
    if is_mbps:
        return f"{size:.2f} Mbps"
    power = 2**10
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}bps"

def get_readable_file_size(size_in_bytes: int) -> str:
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    power = 1024
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size_in_bytes >= power:
        size_in_bytes /= power
        n += 1
    return f"{size_in_bytes:.2f} {power_labels[n]}"

def run_speedtest():
    try:
        result = subprocess.run(["speedtest-cli", "--secure", "--json"], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception("Speedtest failed.")
        data = json.loads(result.stdout)
        return data
    except Exception as e:
        logger.error(f"Speedtest error: {e}")
        return {"error": str(e)}

async def run_speedtest_task(client: TelegramClient, chat_id: int, status_message):
    with ThreadPoolExecutor() as pool:
        try:
            result = await asyncio.get_running_loop().run_in_executor(pool, run_speedtest)
        except Exception as e:
            logger.error(f"Error running speedtest task: {e}")
            await status_message.edit(
                text="<b>Speed Test API Dead ❌ </b>",
                parse_mode='html'
            )
            return
    if "error" in result:
        await status_message.edit(
            text="<b>Speed Test Failed ❌ </b>",
            parse_mode='html'
        )
        return
    response_text = (
        "<b>Smart Speedtest Check → Successful ✅</b>\n"
        "<b>━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>⊗ Download:</b> <b>{speed_convert(result['download'])}</b>\n"
        f"<b>⊗ Upload:</b> <b>{speed_convert(result['upload'])}</b>\n"
        f"<b>⊗ Ping:</b> <b>{result['ping']:.2f} ms</b>\n"
        f"<b>⊗ Internet Provider:</b> <b>{result['client']['isp']}</b>\n"
        "<b>━━━━━━━━━━━━━━━━━</b>\n"
        "<b>Smart SpeedTester → Activated ✅</b>"
    )
    await status_message.edit(
        text=response_text,
        parse_mode='html',
        buttons=[[Button.url("Join For Updates", UPDATE_CHANNEL_URL)]],
        link_preview=False
    )

def setup_speed_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'({"|".join(COMMAND_PREFIX)})speedtest$'))
    async def speedtest_handler(event):
        user_id = event.sender_id
        auth_admins_data = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            return
        status_message = await event.client.send_message(
            entity=event.chat_id,
            message="<b>Processing SpeedTest Please Wait....</b>",
            parse_mode='html'
        )
        asyncio.create_task(run_speedtest_task(event.client, event.chat_id, status_message))
