#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev 
import time
from .logging_setup import LOGGER as logger

async def progress_bar(current, total, status_message, start_time, last_update_time):
    elapsed_time = time.time() - start_time
    percentage = (current / total) * 100
    progress = f"**{'▓' * int(percentage // 5)}{'░' * (20 - int(percentage // 5))}**"
    speed = current / elapsed_time / 1024 / 1024
    uploaded = current / 1024 / 1024
    total_size = total / 1024 / 1024

    if time.time() - last_update_time[0] < 1:
        return
    last_update_time[0] = time.time()

    text = (
        f"**Smart Upload Progress Bar ✅**\n"
        f"**━━━━━━━━━━━━━━━━━**\n"
        f"{progress}\n"
        f"**⊗ Percentage:  ** **{percentage:.2f}%**\n"
        f"**⊗ Speed:** **{speed:.2f} MB/s**\n"
        f"**⊗ Status: ** **{uploaded:.2f} MB of {total_size:.2f} MB**\n"
        f"**━━━━━━━━━━━━━━━━━**\n"
        f"** Smooth Transfer → Activated ✅**"
    )
    try:
        await status_message.edit(text)
    except Exception as e:
        logger.error(f"Error updating progress: {e}")
