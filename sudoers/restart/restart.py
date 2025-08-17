#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
import os
import shutil
import asyncio
import subprocess
from telethon import TelegramClient, events
from telethon.tl.custom import Button
from config import OWNER_ID, UPDATE_CHANNEL_URL, COMMAND_PREFIX
from core import auth_admins, restart_messages
from utils import LOGGER

logger = LOGGER

async def get_auth_admins():
    try:
        admins = await auth_admins.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        return {admin["user_id"] for admin in admins}
    except Exception as e:
        logger.error(f"Failed to fetch authorized admins: {e}")
        return set()

async def is_admin(user_id):
    if user_id == OWNER_ID:
        return True
    auth_admin_ids = await get_auth_admins()
    return user_id in auth_admin_ids

def check_session_permissions(session_file: str) -> bool:
    if not os.path.exists(session_file):
        logger.warning(f"Session file {session_file} not found")
        return True
    if not os.access(session_file, os.W_OK):
        logger.error(f"Session file {session_file} is not writable")
        try:
            os.chmod(session_file, 0o600)
            logger.info(f"Set write permissions for {session_file}")
            return os.access(session_file, os.W_OK)
        except Exception as e:
            logger.error(f"Failed to set permissions for {session_file}: {e}")
            return False
    return True

async def cleanup_restart_data():
    try:
        await restart_messages.delete_many({})
        logger.info("Cleaned up any existing restart messages from database")
    except Exception as e:
        logger.error(f"Failed to cleanup restart data: {e}")

def setup_restart_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'({"|".join(COMMAND_PREFIX)})(restart|reboot|reload)$'))
    async def restart(event):
        user_id = event.sender_id
        if not await is_admin(user_id):
            return
        logger.info(f"Restart command received from user {user_id}")
        response = await event.client.send_message(
            entity=event.chat_id,
            message="**Restarting Bot... Please Wait.**",
            parse_mode='markdown'
        )
        session_file = "SmartTools.session"
        if not check_session_permissions(session_file):
            await response.edit(
                text="**Failed To Restart Due To ReadOnly Environment**",
                parse_mode='markdown'
            )
            return
        directories = ["downloads", "temp", "temp_media", "data", "repos", "temp_dir"]
        for directory in directories:
            try:
                if os.path.exists(directory):
                    shutil.rmtree(directory)
                    logger.info(f"Cleared directory: {directory}")
            except Exception as e:
                logger.error(f"Failed to clear directory {directory}: {e}")
        log_file = "botlog.txt"
        if os.path.exists(log_file):
            try:
                os.remove(log_file)
                logger.info(f"Cleared log file: {log_file}")
            except Exception as e:
                logger.error(f"Failed to clear log file {log_file}: {e}")
        start_script = "start.sh"
        main_script = "main.py"
        if not os.path.exists(start_script):
            if os.path.exists(main_script):
                logger.warning("start.sh not found, will try direct python execution")
                start_script = None
            else:
                logger.error("Neither start.sh nor main.py found")
                await response.edit(
                    text="**Failed To Restart Due To Unix Issue❌**",
                    parse_mode='markdown'
                )
                return
        try:
            await cleanup_restart_data()
            restart_data = {
                "chat_id": event.chat_id,
                "msg_id": response.id
            }
            await restart_messages.insert_one(restart_data)
            logger.info(f"Stored restart message details for chat {event.chat_id}")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Failed to store restart message data: {e}")
            await response.edit(
                text="**Failed To Restart Due To Database Issue❌**",
                parse_mode='markdown'
            )
            return
        try:
            if start_script:
                if not os.access(start_script, os.X_OK):
                    try:
                        os.chmod(start_script, 0o755)
                        logger.info(f"Set execute permissions for {start_script}")
                    except Exception as e:
                        logger.error(f"Failed to set execute permissions: {e}")
                        raise
                process = subprocess.Popen(
                    ["bash", start_script],
                    stdin=subprocess.DEVNULL,
                    stdout=None,
                    stderr=None,
                    start_new_session=True
                )
                logger.info("Started bot using bash script")
            else:
                import sys
                python_executable = sys.executable
                process = subprocess.Popen(
                    [python_executable, main_script],
                    stdin=subprocess.DEVNULL,
                    stdout=None,
                    stderr=None,
                    start_new_session=True,
                    cwd=os.getcwd()
                )
                logger.info("Started bot using direct python execution")
            await asyncio.sleep(3)
            if process.poll() is not None:
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, start_script or main_script)
                else:
                    logger.info("Start process completed immediately, checking if this is expected")
            else:
                logger.info("Start process is running in background")
            logger.info("Restart executed successfully, shutting down current instance")
            await asyncio.sleep(2)
            os._exit(0)
        except subprocess.CalledProcessError as e:
            logger.error(f"Start process failed with return code {e.returncode}")
            try:
                await restart_messages.delete_one({"chat_id": event.chat_id, "msg_id": response.id})
            except Exception as db_e:
                logger.error(f"Failed to cleanup restart data after script failure: {db_e}")
            error_msg = "**Failed To Restart Invalid LF Format❌**" if start_script else "**Failed To Restart Python Script Error❌**"
            await response.edit(
                text=error_msg,
                parse_mode='markdown'
            )
            return
        except FileNotFoundError:
            logger.error("Bash shell not found")
            try:
                await restart_messages.delete_one({"chat_id": event.chat_id, "msg_id": response.id})
            except Exception as db_e:
                logger.error(f"Failed to cleanup restart data after bash error: {db_e}")
            await response.edit(
                text="**Failed To Restart Due To Unix Issue❌**",
                parse_mode='markdown'
            )
            return
        except Exception as e:
            logger.error(f"Restart command execution failed: {e}")
            try:
                await restart_messages.delete_one({"chat_id": event.chat_id, "msg_id": response.id})
            except Exception as db_e:
                logger.error(f"Failed to cleanup restart data after general error: {db_e}")
            try:
                await response.edit(
                    text="**Failed To Restart Due To System Error❌**",
                    parse_mode='markdown'
                )
            except Exception as msg_e:
                logger.error(f"Failed to update error message: {msg_e}")
            return

    @app.on(events.NewMessage(pattern=f'({"|".join(COMMAND_PREFIX)})(stop|kill|off)$'))
    async def stop(event):
        user_id = event.sender_id
        if not await is_admin(user_id):
            return
        logger.info(f"Stop command received from user {user_id}")
        response = await event.client.send_message(
            entity=event.chat_id,
            message="**Stopping bot and clearing data...**",
            parse_mode='markdown'
        )
        directories = ["downloads", "temp", "temp_media", "data", "repos"]
        for directory in directories:
            try:
                if os.path.exists(directory):
                    shutil.rmtree(directory)
                    logger.info(f"Cleared directory: {directory}")
            except Exception as e:
                logger.error(f"Failed to clear directory {directory}: {e}")
        log_file = "botlog.txt"
        if os.path.exists(log_file):
            try:
                os.remove(log_file)
                logger.info(f"Cleared log file: {log_file}")
            except Exception as e:
                logger.error(f"Failed to clear log file {log_file}: {e}")
        try:
            await cleanup_restart_data()
            logger.info("Cleaned up restart data before stopping")
        except Exception as e:
            logger.error(f"Failed to cleanup restart data during stop: {e}")
        try:
            await response.edit(
                text="**Bot stopped successfully, data cleared**",
                parse_mode='markdown',
                buttons=[[Button.url("Join For Updates", UPDATE_CHANNEL_URL)]],
                link_preview=False
            )
            await asyncio.sleep(2)
            try:
                subprocess.run(["pkill", "-f", "main.py"], check=False, timeout=5)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.warning("pkill command failed or timed out, using direct exit")
            os._exit(0)
        except Exception as e:
            logger.error(f"Failed to update stop message: {e}")
            try:
                await response.edit(
                    text="**Failed To Stop Bot Due To Telegram Limit ❌**",
                    parse_mode='markdown'
                )
            except Exception as msg_e:
                logger.error(f"Failed to update error stop message: {msg_e}")
            await asyncio.sleep(2)
            os._exit(0)

