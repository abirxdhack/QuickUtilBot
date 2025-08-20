import logging
import uuid
import hashlib
import time
from telethon import TelegramClient, events, types, functions
from telethon.tl.types import (
    InputPeerUser, 
    InputPeerChat, 
    InputPeerChannel, 
    KeyboardButtonBuy, 
    ReplyInlineMarkup, 
    KeyboardButtonRow, 
    InputKeyboardButtonUserProfile, 
    InputMediaInvoice, 
    LabeledPrice, 
    Invoice, 
    DataJSON, 
    KeyboardButtonCopy,
    UpdateBotPrecheckoutQuery,
    UpdateBotShippingQuery,
    UpdateNewMessage,
    MessageActionPaymentSentMe,
    PeerUser,
    PeerChat,
    PeerChannel
)
from telethon.tl.functions.payments import RefundStarsChargeRequest
from telethon.tl.functions.messages import SetBotPrecheckoutResultsRequest, SetBotShippingResultsRequest
from telethon.tl.custom import Button
from telethon.utils import get_display_name
from config import OWNER_ID, DEVELOPER_USER_ID

logger = logging.getLogger(__name__)

DONATION_OPTIONS_TEXT = """
**Why support Quick Util?**
**━━━━━━━━━━━━━━━━━━**
🌟 **Love the service?**
Your support helps keep **QuickUtil** fast, reliable, and free for everyone.
Even a small **Gift or Donation** makes a big difference! 💖

👇 **Choose an amount to contribute:**

**Why contribute?**
More support = more motivation
More motivation = better tools
Better tools = more productivity
More productivity = less wasted time
Less wasted time = more done with **Quick Util** 💡
**More Muhahaha… 🤓🔥**
"""

PAYMENT_SUCCESS_TEXT = """
**✅ Donation Successful!**

🎉 Huge thanks **{0}** for donating **{1}** ⭐️ to support **Quick Util!**
Your contribution helps keep everything running smooth and awesome 🚀

**🧾 Transaction ID:** `{2}`
"""

ADMIN_NOTIFICATION_TEXT = """
**Hey New Donation Received 🤗**
**━━━━━━━━━━━━━━━**
**From: ** {0}
**Username:** {2}
**UserID:** `{1}`
**Amount:** {3} ⭐️
**Transaction ID:** `{4}`
**━━━━━━━━━━━━━━━**
**Click Below Button If Need Refund 💸**
"""

INVOICE_CREATION_TEXT = "Generating invoice for {0} Stars...\nPlease wait ⏳"
INVOICE_CONFIRMATION_TEXT = "**✅ Invoice for {0} Stars has been generated! You can now proceed to pay via the button below.**"
DUPLICATE_INVOICE_TEXT = "**🚫 Wait Bro! Contribution Already in Progress!**"
INVALID_INPUT_TEXT = "**❌ Sorry Bro! Invalid Input! Use a positive number.**"
INVOICE_FAILED_TEXT = "**❌ Invoice Creation Failed, Bruh! Try Again!**"
PAYMENT_FAILED_TEXT = "**❌ Sorry Bro! Payment Declined! Contact Support!**"
REFUND_SUCCESS_TEXT = "**✅ Refund Successfully Completed Bro!**\n\n**{0} Stars** have been refunded to **[{1}](tg://user?id={2})**"
REFUND_FAILED_TEXT = "**❌ Refund Failed!**\n\nFailed to refund **{0} Stars** to **{1}** (ID: `{2}`)\nError: {3}"

active_invoices = {}
payment_data = {}

def timeof_fmt(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    return f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"

def get_donation_buttons(amount: int = 5):
    if amount == 5:
        return [
            [Button.inline(f"{amount} ⭐️", f"donate_{amount}".encode()), Button.inline("+5", f"increment_donate_{amount}".encode())],
            [Button.inline("🔙 Back", b"about_me")]
        ]
    return [
        [Button.inline("-5", f"decrement_donate_{amount}".encode()), Button.inline(f"{amount} ⭐️", f"donate_{amount}".encode()), Button.inline("+5", f"increment_donate_{amount}".encode())],
        [Button.inline("🔙 Back", b"about_me")]
    ]

async def generate_invoice(client: TelegramClient, chat_id: int, user_id: int, quantity: int, is_callback: bool = False, callback_query=None):
    if user_id in active_invoices:
        if is_callback and callback_query:
            await callback_query.answer("Contribution already in progress!")
        else:
            await client.send_message(chat_id, DUPLICATE_INVOICE_TEXT, parse_mode='md')
        return
   
    active_invoices[user_id] = True
    back_button = [[Button.inline("🔙 Back", b"about_me")]]
   
    try:
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        invoice_payload = f"contribution_{user_id}_{quantity}_{timestamp}_{unique_id}"
        title = "Support QuickUtil"
        description = f"Contribute {quantity} Stars to support ongoing development and keep the tools free, fast, and reliable for everyone 💫 Every star helps us grow!"
        currency = "XTR"
        reply_markup = [[KeyboardButtonBuy(text="💫 Donate Via Stars")]]
       
        loading_message = None
        if not is_callback:
            loading_message = await client.send_message(chat_id, INVOICE_CREATION_TEXT.format(quantity), parse_mode='md', buttons=back_button)
       
        invoice = Invoice(
            currency=currency,
            prices=[LabeledPrice(label=f"⭐️ {quantity} Stars", amount=quantity)]
        )
       
        invoice_media = InputMediaInvoice(
            title=title,
            description=description,
            invoice=invoice,
            payload=invoice_payload.encode(),
            provider="",
            provider_data=DataJSON(data="{}"),
            start_param="donate-stars-to-quickutil"
        )
       
        await client.send_message(
            chat_id,
            "",
            file=invoice_media,
            buttons=reply_markup
        )
       
        if is_callback and callback_query:
            await callback_query.edit(INVOICE_CONFIRMATION_TEXT.format(quantity), parse_mode='md', buttons=back_button)
            await callback_query.answer("✅ Invoice Generated! Donate Now! ⭐️")
        elif loading_message:
            await loading_message.edit(INVOICE_CONFIRMATION_TEXT.format(quantity), parse_mode='md', buttons=back_button)
       
        logger.info(f"✅ Invoice sent for {quantity} stars to user {user_id} with payload {invoice_payload}")
       
    except Exception as e:
        logger.error(f"❌ Failed to generate invoice for user {user_id}: {str(e)}")
        if is_callback and callback_query:
            await callback_query.answer("Failed to create invoice.")
            try:
                await callback_query.edit(INVOICE_FAILED_TEXT, parse_mode='md', buttons=back_button)
            except Exception as edit_error:
                logger.error(f"❌ Failed to edit callback message: {str(edit_error)}")
        else:
            await client.send_message(chat_id, INVOICE_FAILED_TEXT, parse_mode='md', buttons=back_button)
    finally:
        active_invoices.pop(user_id, None)

async def handle_donate_callback(client: TelegramClient, callback_query):
    data = callback_query.data.decode()
    chat_id = callback_query.chat_id
    user_id = callback_query.sender_id
   
    logger.info(f"Callback query received: data={data}, user: {user_id}, chat: {chat_id}")
   
    try:
        if data == "donate":
            reply_markup = get_donation_buttons()
            await callback_query.edit(DONATION_OPTIONS_TEXT, parse_mode='md', buttons=reply_markup)
            await callback_query.answer()
       
        elif data.startswith("donate_"):
            quantity = int(data.split("_")[1])
            await generate_invoice(client, chat_id, user_id, quantity, is_callback=True, callback_query=callback_query)
       
        elif data.startswith("increment_donate_"):
            current_amount = int(data.split("_")[2])
            new_amount = current_amount + 5
            reply_markup = get_donation_buttons(new_amount)
            await callback_query.edit(DONATION_OPTIONS_TEXT, parse_mode='md', buttons=reply_markup)
            await callback_query.answer(f"Updated to {new_amount} Stars")
       
        elif data.startswith("decrement_donate_"):
            current_amount = int(data.split("_")[2])
            new_amount = max(5, current_amount - 5)
            reply_markup = get_donation_buttons(new_amount)
            await callback_query.edit(DONATION_OPTIONS_TEXT, parse_mode='md', buttons=reply_markup)
            await callback_query.answer(f"Updated to {new_amount} Stars")
       
        elif data == "show_donate_options":
            reply_markup = get_donation_buttons()
            await callback_query.edit(DONATION_OPTIONS_TEXT, parse_mode='md', buttons=reply_markup)
            await callback_query.answer()
       
        elif data.startswith("refund_"):
            admin_ids = OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]
            if user_id in admin_ids or user_id == DEVELOPER_USER_ID:
                payment_id = data.replace("refund_", "")
                user_info = payment_data.get(payment_id)
               
                if not user_info:
                    await callback_query.answer("❌ Payment data not found!", show_alert=True)
                    return
               
                refund_user_id = user_info['user_id']
                refund_amount = user_info['amount']
                full_charge_id = user_info['charge_id']
                full_name = user_info['full_name']
               
                try:
                    refund_user_entity = await client.get_entity(refund_user_id)
                    result = await client(RefundStarsChargeRequest(
                        user_id=types.InputUser(user_id=refund_user_id, access_hash=refund_user_entity.access_hash),
                        charge_id=full_charge_id
                    ))
                    if result:
                        await callback_query.edit(REFUND_SUCCESS_TEXT.format(refund_amount, full_name, refund_user_id), parse_mode='md')
                        await callback_query.answer("✅ Refund processed successfully!")
                        payment_data.pop(payment_id, None)
                        logger.info(f"✅ Refund successful for user {refund_user_id}: {refund_amount} Stars")
                    else:
                        await callback_query.answer("❌ Refund failed!", show_alert=True)
                        logger.error(f"❌ Refund failed for user {refund_user_id}: Unknown error")
                except Exception as e:
                    logger.error(f"❌ Refund failed for user {refund_user_id}: {str(e)}")
                    await callback_query.edit(REFUND_FAILED_TEXT.format(refund_amount, full_name, refund_user_id, str(e)), parse_mode='md')
                    await callback_query.answer("❌ Refund failed!", show_alert=True)
            else:
                await callback_query.answer("❌ You don't have permission to refund!", show_alert=True)
                
    except Exception as callback_error:
        logger.error(f"❌ Error handling callback {data}: {str(callback_error)}")
        try:
            await callback_query.answer("❌ An error occurred!", show_alert=True)
        except Exception as answer_error:
            logger.error(f"❌ Failed to send error answer: {str(answer_error)}")

async def raw_update_handler(client: TelegramClient, update, entities=None):
    if isinstance(update, UpdateBotPrecheckoutQuery):
        try:
            await client(SetBotPrecheckoutResultsRequest(
                query_id=update.query_id,
                success=True
            ))
            logger.info(f"✅ Pre-checkout query {update.query_id} OK for user {update.user_id}")
        except Exception as e:
            logger.error(f"❌ Pre-checkout query {update.query_id} failed: {str(e)}")
            try:
                await client(SetBotPrecheckoutResultsRequest(
                    query_id=update.query_id,
                    success=False,
                    error="Failed to process pre-checkout."
                ))
            except Exception as rollback_error:
                logger.error(f"❌ Failed to send error response for pre-checkout: {str(rollback_error)}")
   
    elif isinstance(update, UpdateBotShippingQuery):
        try:
            await client(SetBotShippingResultsRequest(
                query_id=update.query_id,
                shipping_options=[]
            ))
            logger.info(f"✅ Shipping query {update.query_id} OK for user {update.user_id}")
        except Exception as e:
            logger.error(f"❌ Shipping query {update.query_id} failed: {str(e)}")
            try:
                await client(SetBotShippingResultsRequest(
                    query_id=update.query_id,
                    error="Shipping not needed for contributions."
                ))
            except Exception as rollback_error:
                logger.error(f"❌ Failed to send error response for shipping: {str(rollback_error)}")
   
    elif isinstance(update, UpdateNewMessage) and hasattr(update.message, 'action') and isinstance(update.message.action, MessageActionPaymentSentMe):
        payment = update.message.action
        user_id = None
        chat_id = None
       
        try:
            if hasattr(update.message, 'from_id') and update.message.from_id:
                if hasattr(update.message.from_id, 'user_id'):
                    user_id = update.message.from_id.user_id
                else:
                    user_id = update.message.from_id
            elif hasattr(update.message, 'peer_id') and update.message.peer_id:
                if isinstance(update.message.peer_id, (PeerUser, InputPeerUser)):
                    user_id = update.message.peer_id.user_id
                elif hasattr(update.message.peer_id, 'user_id'):
                    user_id = update.message.peer_id.user_id
            elif entities:
                for entity_id, entity in entities.items():
                    if hasattr(entity, 'id') and entity.id > 0 and hasattr(entity, 'first_name'):
                        user_id = entity.id
                        break
           
            if not user_id or user_id <= 0:
                logger.error(f"❌ Could not determine user_id from update: {update}")
                return
           
            if hasattr(update.message, 'peer_id') and update.message.peer_id:
                if isinstance(update.message.peer_id, (PeerUser, InputPeerUser)):
                    chat_id = update.message.peer_id.user_id
                elif isinstance(update.message.peer_id, (PeerChat, InputPeerChat)):
                    chat_id = update.message.peer_id.chat_id
                elif isinstance(update.message.peer_id, (PeerChannel, InputPeerChannel)):
                    chat_id = update.message.peer_id.channel_id
                else:
                    chat_id = user_id
            else:
                chat_id = user_id
           
            if not chat_id:
                logger.error(f"❌ Could not determine chat_id from update")
                chat_id = user_id
           
            try:
                user = await client.get_entity(user_id)
                full_name = get_display_name(user) if user else "Unknown"
                username = f"@{user.username}" if user and hasattr(user, 'username') and user.username else "@N/A"
            except Exception as user_fetch_error:
                logger.error(f"❌ Failed to fetch user entity {user_id}: {str(user_fetch_error)}")
                if entities and user_id in entities:
                    user = entities[user_id]
                    full_name = f"{user.first_name} {getattr(user, 'last_name', '')}".strip() or "Unknown" if user else "Unknown"
                    username = f"@{user.username}" if user and hasattr(user, 'username') and user.username else "@N/A"
                else:
                    full_name = "Unknown"
                    username = "@N/A"
           
            payment_id = str(uuid.uuid4())[:16]
            payment_data[payment_id] = {
                'user_id': user_id,
                'full_name': full_name,
                'username': username,
                'amount': payment.total_amount,
                'charge_id': payment.charge.id
            }
           
            try:
                success_message = ReplyInlineMarkup([
                    KeyboardButtonRow([
                        KeyboardButtonCopy("Transaction ID", payment.charge.id)
                    ])
                ])
                await client.send_message(chat_id, PAYMENT_SUCCESS_TEXT.format(full_name, payment.total_amount, payment.charge.id), parse_mode='md', buttons=success_message)
                logger.info(f"✅ Payment success message sent to user {user_id}")
            except Exception as success_msg_error:
                logger.error(f"❌ Failed to send success message to user {user_id}: {str(success_msg_error)}")
           
            admin_text = ADMIN_NOTIFICATION_TEXT.format(full_name, user_id, username, payment.total_amount, payment.charge.id)
            refund_button = [[Button.inline(f"Refund {payment.total_amount} ⭐️", f"refund_{payment_id}".encode())]]
           
            admin_ids = OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]
            if DEVELOPER_USER_ID and DEVELOPER_USER_ID not in admin_ids:
                admin_ids.append(DEVELOPER_USER_ID)
           
            notification_sent = False
            for admin_id in admin_ids:
                try:
                    if admin_id and admin_id > 0:
                        await client.send_message(admin_id, admin_text, parse_mode='md', buttons=refund_button)
                        logger.info(f"✅ Admin notification sent to {admin_id}")
                        notification_sent = True
                except Exception as admin_notify_error:
                    logger.error(f"❌ Failed to notify admin {admin_id}: {str(admin_notify_error)}")
                    
            if not notification_sent:
                logger.error("❌ Failed to send admin notification to any admin")
                
            logger.info(f"✅ Payment processed successfully: {payment.total_amount} Stars from user {user_id}")
                   
        except Exception as e:
            logger.error(f"❌ Payment processing failed for user {user_id if user_id else 'unknown'}: {str(e)}")
            if chat_id:
                try:
                    developer_entity = await client.get_entity(DEVELOPER_USER_ID)
                    user_name = get_display_name(developer_entity)
                    await client.send_message(
                        chat_id,
                        PAYMENT_FAILED_TEXT,
                        parse_mode='md',
                        buttons=ReplyInlineMarkup([
                            KeyboardButtonRow([
                                InputKeyboardButtonUserProfile(user_name, await client.get_input_entity(DEVELOPER_USER_ID))
                            ])
                        ])
                    )
                except Exception as failure_notify_error:
                    logger.error(f"❌ Failed to send payment failure notification: {str(failure_notify_error)}")
