# Copyright @ISmartCoder
# Updates Channel: https://t.me/TheSmartDev
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel, KeyboardButtonCopy
from telethon.tl.functions.users import GetFullUserRequest
from telethon.errors import PeerIdInvalidError, UsernameNotOccupiedError, ChannelInvalidError
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, get_dc_locations
from core import banned_users

logger = LOGGER

def calculate_account_age(creation_date):
    today = datetime.utcnow()
    delta = relativedelta(today, creation_date)
    years = delta.years
    months = delta.months
    days = delta.days
    return f"{years} years, {months} months, {days} days"

def estimate_account_creation_date(user_id):
    reference_points = [
        (100000000, datetime(2013, 8, 1)),
        (1273841502, datetime(2020, 8, 13)),
        (1500000000, datetime(2021, 5, 1)),
        (2000000000, datetime(2022, 12, 1)),
    ]
    
    closest_point = min(reference_points, key=lambda x: abs(x[0] - user_id))
    closest_user_id, closest_date = closest_point
    
    id_difference = user_id - closest_user_id
    days_difference = id_difference / 20000000
    creation_date = closest_date + timedelta(days=days_difference)
    
    return creation_date

def setup_info_handler(app: TelegramClient):
    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(info|id)(?:\s|$)', incoming=True))
    async def handle_info_command(event):
        user_id = event.sender_id
        if user_id and await banned_users.find_one({"user_id": user_id}):
            await event.respond(BAN_REPLY, parse_mode='md')
            return

        logger.info("Received /info or /id command")
        try:
            DC_LOCATIONS = get_dc_locations()
            
            progress_message = await event.respond("`Processing User Info`", parse_mode='md')
            try:
                
                if not event.message.text.split() or (len(event.message.text.split()) == 1 and not event.message.reply_to_msg_id):
                    logger.info("Fetching current user info")
                    user = await app.get_entity(event.sender_id)  
                    chat = await event.get_chat()
                    premium_status = "Yes" if getattr(user, 'premium', False) else "No"
                    
                   
                    dc_id = None
                    try:
                        
                        dc_id = getattr(user, 'dc_id', None)
                        
                       
                        if not dc_id:
                            full_user = await app(GetFullUserRequest(user.id))
                            if hasattr(full_user, 'user') and hasattr(full_user.user, 'dc_id'):
                                dc_id = full_user.user.dc_id
                                
                        
                        if not dc_id and hasattr(user, 'photo') and user.photo:
                            if hasattr(user.photo, 'dc_id'):
                                dc_id = user.photo.dc_id
                                
                    except Exception as e:
                        logger.error(f"Error getting DC ID: {str(e)}")
                        dc_id = None
                    
                    dc_location = DC_LOCATIONS.get(dc_id, "Unknown") if dc_id else "Unknown"
                    account_created = estimate_account_creation_date(user.id)
                    account_created_str = account_created.strftime("%B %d, %Y")
                    account_age = calculate_account_age(account_created)
                    
                    verified_status = "Verified" if getattr(user, 'verified', False) else "Not Verified"
                    
                    chat_id_display = chat.id if isinstance(chat, (Chat, Channel)) else user.id
                    full_name = f"{user.first_name} {getattr(user, 'last_name', '') or ''}".strip()
                    response = (
                        "**🔍 Showing User's Profile Info 📋**\n"
                        "**━━━━━━━━━━━━━━━━**\n"
                        f"**• Full Name:** **{full_name}**\n"
                    )
                    if user.username:
                        response += f"**• Username:** @{user.username}\n"
                    response += (
                        f"**• User ID:** `{user.id}`\n"
                        f"**• Chat ID:** `{chat_id_display}`\n"
                        f"**• Premium User:** **{premium_status}**\n"
                        f"**• Data Center:** **{dc_location}**\n"
                        f"**• Created On:** **{account_created_str}**\n"
                        f"**• Account Age:** **{account_age}**\n"
                        "**━━━━━━━━━━━━━━━━**\n"
                        "**👁 Thank You for Using Our Tool ✅**"
                    )
                    buttons = [[KeyboardButtonCopy(text=full_name, copy_text=str(user.id))]]
                    await progress_message.edit(
                        text=response,
                        parse_mode='md',
                        buttons=buttons
                    )
                    logger.info("User info fetched successfully with copy button")

               
                elif event.message.reply_to_msg_id:
                    logger.info("Fetching info of the replied user or bot")
                    reply_message = await event.message.get_reply_message()
                    if not reply_message:
                        await progress_message.edit(
                            text="**Please Provide Reply To A Valid Message ❌**",
                            parse_mode='md'
                        )
                        return

                    user = await app.get_entity(reply_message.sender_id)  
                    if not user:
                        await progress_message.edit(
                            text="**Looks Like I Don't Have Control Over The User**",
                            parse_mode='md'
                        )
                        return

                    chat = await event.get_chat()
                    premium_status = "Yes" if getattr(user, 'premium', False) else "No"
                    
                    
                    dc_id = None
                    try:
                       
                        dc_id = getattr(user, 'dc_id', None)
                        
                        
                        if not dc_id:
                            full_user = await app(GetFullUserRequest(user.id))
                            if hasattr(full_user, 'user') and hasattr(full_user.user, 'dc_id'):
                                dc_id = full_user.user.dc_id
                                
                        
                        if not dc_id and hasattr(user, 'photo') and user.photo:
                            if hasattr(user.photo, 'dc_id'):
                                dc_id = user.photo.dc_id
                                
                    except Exception as e:
                        logger.error(f"Error getting DC ID: {str(e)}")
                        dc_id = None
                    
                    dc_location = DC_LOCATIONS.get(dc_id, "Unknown") if dc_id else "Unknown"
                    account_created = estimate_account_creation_date(user.id)
                    account_created_str = account_created.strftime("%B %d, %Y")
                    account_age = calculate_account_age(account_created)
                    
                    verified_status = "Verified" if getattr(user, 'verified', False) else "Not Verified"
                    
                    chat_id_display = chat.id if isinstance(chat, (Chat, Channel)) else user.id
                    full_name = f"{user.first_name} {getattr(user, 'last_name', '') or ''}".strip()
                    if getattr(user, 'bot', False):
                        response = (
                            "**🔍 Showing Bot's Profile Info 📋**\n"
                            "**━━━━━━━━━━━━━━━━**\n"
                            f"**• Bot Name:** **{full_name}**\n"
                        )
                        if user.username:
                            response += f"**• Username:** @{user.username}\n"
                        response += (
                            f"**• User ID:** `{user.id}`\n"
                            "**━━━━━━━━━━━━━━━━**\n"
                            "**👁 Thank You for Using Our Tool ✅**"
                        )
                    else:
                        response = (
                            "**🔍 Showing User's Profile Info 📋**\n"
                            "**━━━━━━━━━━━━━━━━**\n"
                            f"**• Full Name:** **{full_name}**\n"
                        )
                        if user.username:
                            response += f"**• Username:** @{user.username}\n"
                        response += (
                            f"**• User ID:** `{user.id}`\n"
                            f"**• Chat ID:** `{chat_id_display}`\n"
                            f"**• Premium User:** **{premium_status}**\n"
                            f"**• Data Center:** **{dc_location}**\n"
                            f"**• Created On:** **{account_created_str}**\n"
                            f"**• Account Age:** **{account_age}**\n"
                            "**━━━━━━━━━━━━━━━━**\n"
                            "**👁 Thank You for Using Our Tool ✅**"
                        )
                    buttons = [[KeyboardButtonCopy(text=full_name, copy_text=str(user.id))]]
                    await progress_message.edit(
                        text=response,
                        parse_mode='md',
                        buttons=buttons
                    )
                    logger.info("Replied user info fetched successfully")

                
                elif len(event.message.text.split()) > 1:
                    logger.info("Extracting username from the command")
                    username = event.message.text.split()[1].strip('@').replace('https://', '').replace('http://', '').replace('t.me/', '').replace('/', '').replace(':', '')
                    
                  
                    if username.isdigit():
                        username = int(username)
                    
                    try:
                        logger.info(f"Fetching info for entity: {username}")
                        entity = await app.get_entity(username)
                        
                        if isinstance(entity, User):
                            premium_status = "Yes" if getattr(entity, 'premium', False) else "No"
                            
                            
                            dc_id = None
                            try:
                                
                                dc_id = getattr(entity, 'dc_id', None)
                                
                              
                                if not dc_id:
                                    full_user = await app(GetFullUserRequest(entity.id))
                                    if hasattr(full_user, 'user') and hasattr(full_user.user, 'dc_id'):
                                        dc_id = full_user.user.dc_id
                                        
                             
                                if not dc_id and hasattr(entity, 'photo') and entity.photo:
                                    if hasattr(entity.photo, 'dc_id'):
                                        dc_id = entity.photo.dc_id
                                        
                            except Exception as e:
                                logger.error(f"Error getting DC ID: {str(e)}")
                                dc_id = None
                            
                            dc_location = DC_LOCATIONS.get(dc_id, "Unknown") if dc_id else "Unknown"
                            account_created = estimate_account_creation_date(entity.id)
                            account_created_str = account_created.strftime("%B %d, %Y")
                            account_age = calculate_account_age(account_created)
                            
                            verified_status = "Verified" if getattr(entity, 'verified', False) else "Not Verified"
                            
                            full_name = f"{entity.first_name} {getattr(entity, 'last_name', '') or ''}".strip()
                            if getattr(entity, 'bot', False):
                                response = (
                                    "**🔍 Showing Bot's Profile Info 📋**\n"
                                    "**━━━━━━━━━━━━━━━━**\n"
                                    f"**• Bot Name:** **{full_name}**\n"
                                )
                                if entity.username:
                                    response += f"**• Username:** @{entity.username}\n"
                                dc_id = getattr(entity, 'dc_id', None)
                                dc_location = DC_LOCATIONS.get(dc_id, "Unknown") if dc_id else "Unknown"
                                response += (
                                    f"**• User ID:** `{entity.id}`\n"
                                    "**━━━━━━━━━━━━━━━━**\n"
                                    "**👁 Thank You for Using Our Tool ✅**"
                                )
                            else:
                                response = (
                                    "**🔍 Showing User's Profile Info 📋**\n"
                                    "**━━━━━━━━━━━━━━━━**\n"
                                    f"**• Full Name:** **{full_name}**\n"
                                )
                                if entity.username:
                                    response += f"**• Username:** @{entity.username}\n"
                                response += (
                                    f"**• User ID:** `{entity.id}`\n"
                                    f"**• Chat ID:** `{entity.id}`\n"
                                    f"**• Premium User:** **{premium_status}**\n"
                                    f"**• Data Center:** **{dc_location}**\n"
                                    f"**• Created On:** **{account_created_str}**\n"
                                    f"**• Account Age:** **{account_age}**\n"
                                    "**━━━━━━━━━━━━━━━━**\n"
                                    "**👁 Thank You for Using Our Tool ✅**"
                                )
                            buttons = [[KeyboardButtonCopy(text=full_name, copy_text=str(entity.id))]]
                            await progress_message.edit(
                                text=response,
                                parse_mode='md',
                                buttons=buttons
                            )
                            logger.info("User/bot info fetched successfully with copy button")

                        elif isinstance(entity, (Chat, Channel)):
                            
                            full_chat = await app.get_entity(entity.id)
                            dc_id = getattr(full_chat, 'dc_id', None)
                            dc_location = DC_LOCATIONS.get(dc_id, "Unknown") if dc_id else "Unknown"
                            chat_type = "Channel" if isinstance(full_chat, Channel) else "Group"
                            full_name = getattr(full_chat, 'title', 'Unknown')
                            
                            
                            members_count = "Unknown"
                            try:
                                if hasattr(full_chat, 'participants_count') and full_chat.participants_count:
                                    members_count = full_chat.participants_count
                                elif isinstance(full_chat, Channel):
                                   
                                    try:
                                        participants = await app.get_participants(full_chat, limit=0)
                                        members_count = participants.total if hasattr(participants, 'total') else len(participants)
                                    except:
                                        members_count = "Unknown"
                            except Exception as e:
                                logger.error(f"Error getting member count: {str(e)}")
                                members_count = "Unknown"
                            
                            response = (
                                f"**🔍 Showing {chat_type}'s Profile Info 📋**\n"
                                "**━━━━━━━━━━━━━━━━**\n"
                                f"**• Full Name:** **{full_name}**\n"
                            )
                            if getattr(full_chat, 'username', None):
                                response += f"**• Username:** @{full_chat.username}\n"
                            response += (
                                f"**• Chat ID:** `{full_chat.id}`\n"
                                f"**• Total Members:** **{members_count}**\n"
                                "**━━━━━━━━━━━━━━━━**\n"
                                "**👁 Thank You for Using Our Tool ✅**"
                            )
                            buttons = [[KeyboardButtonCopy(text=full_name, copy_text=str(full_chat.id))]]
                            await progress_message.edit(
                                text=response,
                                parse_mode='md',
                                buttons=buttons
                            )
                            logger.info("Chat info fetched successfully with copy button")

                    except (PeerIdInvalidError, UsernameNotOccupiedError):
                        logger.error(f"Username '{username}' not found as user. Trying as chat...")
                      
                        try:
                            entity = await app.get_entity(username)
                            if isinstance(entity, (Chat, Channel)):
                                
                                full_chat = await app.get_entity(entity.id)
                                dc_id = getattr(full_chat, 'dc_id', None)
                                dc_location = DC_LOCATIONS.get(dc_id, "Unknown") if dc_id else "Unknown"
                                chat_type = "Channel" if isinstance(full_chat, Channel) else "Group"
                                full_name = getattr(full_chat, 'title', 'Unknown')
                                
                                
                                members_count = "Unknown"
                                try:
                                    if hasattr(full_chat, 'participants_count') and full_chat.participants_count:
                                        members_count = full_chat.participants_count
                                    elif isinstance(full_chat, Channel):
                                        
                                        try:
                                            participants = await app.get_participants(full_chat, limit=0)
                                            members_count = participants.total if hasattr(participants, 'total') else len(participants)
                                        except:
                                            members_count = "Unknown"
                                except Exception as e:
                                    logger.error(f"Error getting member count: {str(e)}")
                                    members_count = "Unknown"
                                
                                response = (
                                    f"**🔍 Showing {chat_type}'s Profile Info 📋**\n"
                                    "**━━━━━━━━━━━━━━━━**\n"
                                    f"**• Full Name:** **{full_name}**\n"
                                )
                                if getattr(full_chat, 'username', None):
                                    response += f"**• Username:** @{full_chat.username}\n"
                                response += (
                                    f"**• Chat ID:** `{full_chat.id}`\n"
                                    f"**• Total Members:** **{members_count}**\n"
                                    "**━━━━━━━━━━━━━━━━**\n"
                                    "**👁 Thank You for Using Our Tool ✅**"
                                )
                                buttons = [[KeyboardButtonCopy(text=full_name, copy_text=str(full_chat.id))]]
                                await progress_message.edit(
                                    text=response,
                                    parse_mode='md',
                                    buttons=buttons
                                )
                                logger.info("Chat info fetched successfully with copy button")
                            else:
                                await progress_message.edit(
                                    text="**Looks Like I Don't Have Control Over The User**",
                                    parse_mode='md'
                                )
                        except Exception as e2:
                            logger.error(f"Username '{username}' not found as chat either: {str(e2)}")
                            await progress_message.edit(
                                text="**Looks Like I Don't Have Control Over The User**",
                                parse_mode='md'
                            )
                    except ChannelInvalidError:
                        error_message = (
                            "**Looks Like I Don't Have Control Over The User**"
                            if isinstance(entity, Channel)
                            else "**Looks Like I Don't Have Control Over The User**"
                        )
                        await progress_message.edit(
                            text=error_message,
                            parse_mode='md'
                        )
                        logger.error(f"Permission error: {error_message}")
                    except Exception as e:
                        logger.error(f"Error fetching entity info: {str(e)}")
                        await progress_message.edit(
                            text="**Unable to fetch entity information**",
                            parse_mode='md'
                        )

            except Exception as e:
                logger.error(f"Unhandled exception: {str(e)}")
                await progress_message.edit(
                    text="**Looks Like I Don't Have Control Over The User**",
                    parse_mode='md'
                )

        except Exception as e:
            logger.error(f"Unhandled exception: {str(e)}")
            await event.respond(
                "**Looks Like I Don't Have Control Over The User**",
                parse_mode='md'
            )