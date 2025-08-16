from misc import handle_callback_query
from telethon import events
from telethon.tl.types import UpdateShortMessage, UpdateNewMessage
from utils import LOGGER
from core import setup_start_handler, restart_messages
from app import app
import asyncio
async def main():
    await app.start()
    LOGGER.info("Bot Successfully Started! 💥")
    try:
        restart_data = await restart_messages.find_one()
        if restart_data:
            try:
                await app.edit_message(
                    restart_data["chat_id"],
                    restart_data["msg_id"],
                    "**Restarted Successfully 💥**",
                    parse_mode='md'
                )
                await restart_messages.delete_one({"_id": restart_data["_id"]})
                LOGGER.info(f"Restart message updated and cleared from database for chat {restart_data['chat_id']}")
            except Exception as e:
                LOGGER.error(f"Failed to update restart message: {e}")
    except Exception as e:
        LOGGER.error(f"Failed to fetch restart message from database: {e}")
    setup_start_handler(app)
    app.add_event_handler(handle_callback_query, events.CallbackQuery())
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
        app.run_until_disconnected()
    except KeyboardInterrupt:
        LOGGER.info("Bot Stopped Successfully!")
        try:
            loop.run_until_complete(asyncio.gather(app.disconnect(), user.disconnect()))
        except Exception as e:
            LOGGER.error(f"Failed to stop clients: {e}")
        finally:
            if not loop.is_closed():
                loop.close()