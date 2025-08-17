import os
import time
import subprocess
from datetime import datetime, timedelta
import psutil
from telethon.tl.custom import Button
from config import UPDATE_CHANNEL_URL
from core import user_activity_collection
from utils import (
    LOGGER,
    responses,
    main_menu_keyboard,
    second_menu_keyboard,
    third_menu_keyboard,
    timeof_fmt,
    DONATION_OPTIONS_TEXT,
    get_donation_buttons,
    generate_invoice,
    handle_donate_callback
)
async def handle_callback_query(callback_query):
    call = callback_query
    chat_id = call.chat_id
    user_id = call.sender_id
   
    if call.data == b"stats":
        now = datetime.utcnow()
        daily_users = await user_activity_collection.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(days=1)}})
        weekly_users = await user_activity_collection.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(weeks=1)}})
        monthly_users = await user_activity_collection.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(days=30)}})
        yearly_users = await user_activity_collection.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(days=365)}})
        total_users = await user_activity_collection.count_documents({"is_group": False})
        total_groups = await user_activity_collection.count_documents({"is_group": True})
        stats_text = (
            f"**Smart Bot Status ⇾ Report ✅**\n"
            f"**━━━━━━━━━━━━━━━━**\n"
            f"**Users & Groups Engagements:**\n"
            f"**1 Day:** {daily_users} users were active\n"
            f"**1 Week:** {weekly_users} users were active\n"
            f"**1 Month:** {monthly_users} users were active\n"
            f"**1 Year:** {yearly_users} users were active\n"
            f"**Total Connected Groups:** {total_groups}\n"
            f"**━━━━━━━━━━━━━━━━**\n"
            f"**Total Smart Tools Users:** {total_users} ✅"
        )
        back_button = [[Button.inline("⬅️ Back", b"fstats")]]
        await call.edit(stats_text, parse_mode='md', buttons=back_button)
        return
    if call.data == b"fstats":
        stats_dashboard_text = (
            "**🗒 Smart Tool Basic Statistics Menu 🔍**\n"
            "**━━━━━━━━━━━━━━━━━**\n"
            "Stay Updated With Real Time Insights....⚡️\n"
            "⊗ **Full Statistics:** Get Full Statistics Of Smart Tool ⚙️\n"
            "⊗ **Top Users:** Get Top User's Leaderboard 🔥\n"
            "⊗ **Growth Trends:** Get Knowledge About Growth 👁\n"
            "⊗ **Activity Times:** See Which User Is Most Active ⏰\n"
            "⊗ **Milestones:** Track Special Achievements 🏅\n"
            "**━━━━━━━━━━━━━━━━━**\n"
            "**💡 Select an option and take control:**"
        )
        stats_dashboard_buttons = [
            [Button.inline("📈 Usage Report", b"stats"), Button.inline("🏆 Top Users", b"top_users_1")],
            [Button.inline("⬅️ Back", b"about_me")]
        ]
        await call.edit(stats_dashboard_text, parse_mode='md', buttons=stats_dashboard_buttons)
        return
    if call.data.startswith(b"top_users_"):
        page = int(call.data.decode().split("_")[-1])
        users_per_page = 9
        now = datetime.utcnow()
        daily_users = await user_activity_collection.find({"is_group": False, "last_activity": {"$gte": now - timedelta(days=1)}}).to_list(None)
        total_users = len(daily_users)
        total_pages = (total_users + users_per_page - 1) // users_per_page
        start_index = (page - 1) * users_per_page
        end_index = start_index + users_per_page
        paginated_users = daily_users[start_index:end_index]
        top_users_text = (
            f"**🏆 Top Users (All-time) — page {page}/{total_pages if total_pages > 0 else 1}:**\n"
            f"**━━━━━━━━━━━━━━━**\n"
        )
        for i, user in enumerate(paginated_users, start=start_index + 1):
            user_id = user['user_id']
            try:
                telegram_user = await call.client.get_entity(user_id)
                full_name = f"{telegram_user.first_name} {telegram_user.last_name}" if telegram_user.last_name else telegram_user.first_name
            except Exception as e:
                LOGGER.error(f"Failed to fetch user {user_id}: {e}")
                full_name = f"User_{user_id}"
            rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔸"
            top_users_text += f"**{rank_emoji} {i}.** [{full_name}](tg://user?id={user_id})\n** - User Id :** `{user_id}`\n\n"
        buttons = []
        nav_buttons = []
        if page == 1 and total_pages > 1:
            nav_buttons.append(Button.inline("Next ➡️", f"top_users_{page+1}".encode()))
            nav_buttons.append(Button.inline("⬅️ Back", b"fstats"))
            buttons.append(nav_buttons)
        elif page > 1 and page < total_pages:
            nav_buttons.append(Button.inline("⬅️ Previous", f"top_users_{page-1}".encode()))
            nav_buttons.append(Button.inline("Next ➡️", f"top_users_{page+1}".encode()))
            buttons.append(nav_buttons)
        elif page == total_pages and page > 1:
            nav_buttons.append(Button.inline("⬅️ Previous", f"top_users_{page-1}".encode()))
            buttons.append(nav_buttons)
        else:
            buttons.append([Button.inline("⬅️ Back", b"fstats")])
        top_users_buttons = buttons
        await call.edit(top_users_text, parse_mode='md', buttons=top_users_buttons)
        return
    if call.data == b"server":
        ping_output = subprocess.getoutput("ping -c 1 google.com")
        ping = ping_output.split("time=")[1].split()[0] if "time=" in ping_output else "N/A"
        disk = psutil.disk_usage('/')
        total_disk = disk.total / (2**30)
        used_disk = disk.used / (2**30)
        free_disk = disk.free / (2**30)
        mem = psutil.virtual_memory()
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        uptime = timeof_fmt(uptime_seconds)
        swap = psutil.swap_memory()
        total_mem = mem.total / (2**30)
        used_mem = mem.used / (2**30)
        available_mem = mem.available / (2**30)
        server_status_text = (
            f"**Smart Bot Status ⇾ Report ✅**\n"
            f"**━━━━━━━━━━━━━**\n"
            f"**Server Connection:**\n"
            f"**- Ping:** {ping} ms\n"
            f"**- Bot Status:** Online\n"
            f"**- Server Uptime:** {uptime}\n"
            f"**━━━━━━━━━━━━━**\n"
            f"**Server Storage:**\n"
            f"**- Total:** {total_disk:.2f} GB\n"
            f"**- Used:** {used_disk:.2f} GB\n"
            f"**- Available:** {free_disk:.2f} GB\n"
            f"**━━━━━━━━━━━━━**\n"
            f"**Memory Usage:**\n"
            f"**- Total:** {total_mem:.2f} GB\n"
            f"**- Used:** {used_mem:.2f} GB\n"
            f"**- Available:** {available_mem:.2f} GB\n"
            f"**━━━━━━━━━━━━━**\n"
            f"**Server Stats Check Successful ✅**"
        )
        back_button = [[Button.inline("⬅️ Back", b"about_me")]]
        await call.edit(server_status_text, parse_mode='md', buttons=back_button)
        return
    if call.data.decode() in responses:
        if call.data == b"server":
            back_button = [[Button.inline("⬅️ Back", b"about_me")]]
        elif call.data == b"stats":
            back_button = [[Button.inline("⬅️ Back", b"fstats")]]
        elif call.data == b"about_me":
            back_button = [
                [Button.inline("📊 Statistics", b"fstats"), Button.inline("💾 Server", b"server"), Button.inline("⭐️ Donate", b"donate")],
                [Button.inline("⬅️ Back", b"start_message")]
            ]
        elif call.data in [b"ai_tools", b"credit_cards", b"crypto", b"converter", b"coupons", b"decoders", b"downloaders", b"domain_check", b"education_utils", b"rembg"]:
            back_button = [[Button.inline("Back", b"main_menu")]]
        elif call.data in [b"file_to_link", b"github", b"info", b"network_tools", b"random_address", b"string_session", b"stripe_keys", b"sticker", b"time_date", b"text_split"]:
            back_button = [[Button.inline("Back", b"second_menu")]]
        elif call.data in [b"tempmail", b"text_ocr", b"bot_users_export", b"web_capture", b"weather", b"yt_tools", b"translate"]:
            back_button = [[Button.inline("Back", b"third_menu")]]
        else:
            back_button = [[Button.inline("Back", b"main_menu")]]
        await call.edit(
            responses[call.data.decode()][0],
            parse_mode=responses[call.data.decode()][1]['parse_mode'],
            link_preview=responses[call.data.decode()][1].get('link_preview', False),
            buttons=back_button
        )
    elif call.data.startswith(b"donate_") or call.data.startswith(b"increment_donate_") or call.data.startswith(b"decrement_donate_") or call.data == b"donate":
        await handle_donate_callback(call.client, call)
    elif call.data == b"main_menu":
        await call.edit("<b>Here are the Smart-Tool Options: 👇</b>", parse_mode='html', buttons=main_menu_keyboard)
    elif call.data == b"next_1":
        await call.edit("<b>Here are the Smart-Tool Options: 👇</b>", parse_mode='html', buttons=second_menu_keyboard)
    elif call.data == b"next_2":
        await call.edit("<b>Here are the Smart-Tool Options: 👇</b>", parse_mode='html', buttons=third_menu_keyboard)
    elif call.data == b"previous_1":
        await call.edit("<b>Here are the Smart-Tool Options: 👇</b>", parse_mode='html', buttons=main_menu_keyboard)
    elif call.data == b"previous_2":
        await call.edit("<b>Here are the Smart-Tool Options: 👇</b>", parse_mode='html', buttons=second_menu_keyboard)
    elif call.data == b"close":
        await call.delete()
    elif call.data == b"start_message":
        full_name = f"{call.sender.first_name} {call.sender.last_name}" if call.sender.last_name else call.sender.first_name if call.sender else "User"
        start_message = (
            f"<b>Hi {full_name}! Welcome To This Bot</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Smart Tool</b> The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit card tool, and more. Simplify your tasks with ease!\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Don't Forget To <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> For Updates!</b>"
        )
        await call.edit(
            start_message,
            parse_mode='html',
            buttons=[
                [Button.inline("⚙️ Main Menu", b"main_menu")],
                [Button.inline("ℹ️ About Me", b"about_me"), Button.inline("📄 Policy & Terms", b"policy_terms")]
            ],
            link_preview=False
        )
    elif call.data == b"policy_terms":
        policy_terms_text = (
            f"<b>📜 Policy & Terms Menu</b>\n\n"
            f"At <b>Smart Tool ⚙️</b>, we prioritize your privacy and security. To ensure a seamless and safe experience, we encourage you to review our <b>Privacy Policy</b> and <b>Terms & Conditions</b>.\n\n"
            f"🔹 <b>Privacy Policy</b>: Learn how we collect, use, and protect your personal data.\n"
            f"🔹 <b>Terms & Conditions</b>: Understand the rules and guidelines for using our services.\n\n"
            f"<b>💡 Choose an option below to proceed:</b>"
        )
        policy_terms_button = [
            [Button.inline("Privacy Policy", b"privacy_policy"), Button.inline("Terms & Conditions", b"terms_conditions")],
            [Button.inline("⬅️ Back", b"start_message")]
        ]
        await call.edit(policy_terms_text, parse_mode='html', buttons=policy_terms_button)
    elif call.data == b"privacy_policy":
        privacy_policy_text = (
            f"<b>📜 Privacy Policy for Smart Tool ⚙️</b>\n\n"
            f"Welcome to <b>Smart Tool ⚙️</b> Bot. By using our services, you agree to this privacy policy.\n\n"
            f"1. <b>Personal Information</b>:\n"
            f" - Personal Information: User ID and username for personalization.\n"
            f" - <b>Usage Data</b>: Information on how you use the app to improve our services.\n\n"
            f"2. Usage of Information:\n"
            f" - <b>Service Enhancement</b>: To provide and improve <b>Smart Tool ⚙️</b>\n"
            f" - <b>Communication</b>: Updates and new features.\n"
            f" - <b>Security</b>: To prevent unauthorized access.\n"
            f" - <b>Advertisements</b>: Display of promotions.\n\n"
            f"3. Data Security:\n"
            f" - These tools do not store any data, ensuring your privacy.\n"
            f" - We use strong security measures, although no system is 100% secure.\n\n"
            f"Thank you for using <b>Smart Tool ⚙️</b>. We prioritize your privacy and security."
        )
        back_button = [[Button.inline("⬅️ Back", b"policy_terms")]]
        await call.edit(privacy_policy_text, parse_mode='html', buttons=back_button)
    elif call.data == b"terms_conditions":
        terms_conditions_text = (
            f"<b>📜 Terms & Conditions for Smart Tool ⚙️</b>\n\n"
            f"Welcome to <b>Smart Tool ⚙️</b>. By using our services, you accept these <b>Terms & Conditions</b>.\n\n"
            f"<b>1. Usage Guidelines</b>\n"
            f" - Eligibility: Must be 13 years of age or older.\n\n"
            f"<b>2. Prohibited</b>\n"
            f" - Illegal and unauthorized uses are strictly forbidden.\n"
            f" - Spamming and abusing are not allowed in this Bot\n\n"
            f"<b>3. Tools and Usage</b>\n"
            f" - For testing/development purposes only, not for illegal use.\n"
            f" - We <b>do not support</b> misuse for fraud or policy violations.\n"
            f" - Automated requests may lead to service limitations or suspension.\n"
            f" - We are not responsible for any account-related issues.\n\n"
            f"<b>4. User Responsibility</b>\n"
            f" - You are responsible for all activities performed using the bot.\n"
            f" - Ensure that your activities comply with platform policies.\n\n"
            f"<b>5. Disclaimer of Warranties</b>\n"
            f" - We do not guarantee uninterrupted service, accuracy, or reliability.\n"
            f" - We are not responsible for any consequences arising from your use of the bot.\n\n"
            f"<b>6. Termination</b>\n"
            f" - Access may be terminated for any violations without prior notice.\n\n"
            f"<b>7. Contact Information</b>\n"
            f" - Contact My Dev for any inquiries or concerns. <a href='tg://user?id=7303810912'>Abir Arafat Chawdhury👨‍💻</a> \n\n"
            f"Thank you for using <b>Smart Tool ⚙️</b>. We prioritize your safety, security, and best user experience. 🚀"
        )
        back_button = [[Button.inline("⬅️ Back", b"policy_terms")]]
        await call.edit(terms_conditions_text, parse_mode='html', buttons=back_button)
    elif call.data == b"second_menu":
        await call.edit("<b>Here are the Smart-Tool Options: 👇</b>", parse_mode='html', buttons=second_menu_keyboard)
    elif call.data == b"third_menu":
        await call.edit("<b>Here are the Smart-Tool Options: 👇</b>", parse_mode='html', buttons=third_menu_keyboard)
