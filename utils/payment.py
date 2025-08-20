import logging
import uuid
import hashlib
import time
from telethon import TelegramClient, events
from telethon.tl.types import InputPeerUser, InputPeerChat, InputPeerChannel, KeyboardButtonBuy, ReplyInlineMarkup, KeyboardButtonRow, InputKeyboardButtonUserProfile, InputMediaInvoice, LabeledPrice, Invoice, DataJSON, KeyboardButtonCopy
from telethon.tl.custom import Button
from telethon.utils import get_display_name
from config import OWNER_ID, DEVELOPER_USER_ID
logger = logging.getLogger(__name__)
DONATION_OPTIONS_TEXT = """
**Why support Smart Tools?**
**━━━━━━━━━━━━━━━━━━**
🌟 **Love the service?**
Your support helps keep **SmartTools** fast, reliable, and free for everyone.
Even a small **Gift or Donation** makes a big difference! 💖
👇 **Choose an amount to contribute:**
**Why contribute?**
More support = more motivation
More motivation = better tools
Better tools = more productivity
More productivity = less wasted time
Less wasted time = more done with **Smart Tools** 💡
**More Muhahaha… 🤓🔥**
"""
PAYMENT_SUCCESS_TEXT = """
**✅ Donation Successful!**
🎉 Huge thanks **{0}** for donating **{1}** ⭐️ to support **Smart Tool!**
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
        if is_callback:
            await callback_query.answer("Contribution already in progress!")
        else:
            await client.send_message(chat_id, INVOICE_CREATION_TEXT.format(quantity), parse_mode='md')
        return
   
    active_invoices[user_id] = True
    back_button = [[Button.inline("🔙 Back", b"about_me")]]
   
    try:
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        invoice_payload = f"contribution_{user_id}_{quantity}_{timestamp}_{unique_id}"
        title = "Support Smart Tools"
        description = f"Contribute {quantity} Stars to support ongoing development and keep the tools free, fast, and reliable for everyone 💫 Every star helps us grow!"
        currency = "XTR"
        prices = [{'label': f"⭐️ {quantity} Stars", 'amount': quantity}]
        reply_markup = [[KeyboardButtonBuy(text="💫 Donate Via Stars")]]
       
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
            start_param="Basic"
        )
       
        await client.send_message(
            chat_id,
            "",
            file=invoice_media,
            buttons=reply_markup
        )
       
        if is_callback:
            await callback_query.edit(INVOICE_CONFIRMATION_TEXT.format(quantity), parse_mode='md', buttons=back_button)
            await callback_query.answer("✅ Invoice Generated! Donate Now! ⭐️")
        else:
            await loading_message.edit(INVOICE_CONFIRMATION_TEXT.format(quantity), parse_mode='md', buttons=back_button)
       
        logger.info(f"✅ Invoice sent for {quantity} stars to user {user_id} with payload {invoice_payload}")
       
    except Exception as e:
        logger.error(f"❌ Failed to generate invoice for user {user_id}: {str(e)}")
        await client.send_message(chat_id, INVOICE_FAILED_TEXT, parse_mode='md', buttons=back_button)
        if is_callback:
            await callback_query.answer("Failed to create invoice.")
    finally:
        active_invoices.pop(user_id, None)
async def handle_donate_callback(client: TelegramClient, callback_query):
    data = callback_query.data.decode()
    chat_id = callback_query.chat_id
    user_id = callback_query.sender_id
   
    logger.info(f"Callback query received: data={data}, user: {user_id}, chat: {chat_id}")
   
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
                result = await client.refund_star_payment(refund_user_id, full_charge_id)
                if result:
                    await callback_query.edit(REFUND_SUCCESS_TEXT.format(refund_amount, full_name, refund_user_id), parse_mode='md')
                    await callback_query.answer("✅ Refund processed successfully!")
                    payment_data.pop(payment_id, None)
                else:
                    await callback_query.answer("❌ Refund failed!", show_alert=True)
            except Exception as e:
                logger.error(f"❌ Refund failed for user {refund_user_id}: {str(e)}")
                await callback_query.edit(REFUND_FAILED_TEXT.format(refund_amount, full_name, refund_user_id, str(e)), parse_mode='md')
                await callback_query.answer("❌ Refund failed!", show_alert=True)
        else:
            await callback_query.answer("❌ You don't have permission to refund!", show_alert=True)
async def raw_update_handler(client: TelegramClient, update, entities):
    if isinstance(update, UpdateBotPrecheckoutQuery):
        try:
            await client.answer_pre_checkout_query(update.query_id, ok=True)
            logger.info(f"✅ Pre-checkout query {update.query_id} OK for user {update.user_id}")
        except Exception as e:
            logger.error(f"❌ Pre-checkout query {update.query_id} failed: {str(e)}")
            await client.answer_pre_checkout_query(update.query_id, ok=False, error="Failed to process pre-checkout.")
   
    elif isinstance(update, UpdateBotShippingQuery):
        try:
            await client.invoke(SetBotShippingResults(query_id=update.query_id, shipping_options=[]))
            logger.info(f"✅ Shipping query {update.query_id} OK for user {update.user_id}")
        except Exception as e:
            logger.error(f"❌ Shipping query {update.query_id} failed: {str(e)}")
            await client.invoke(SetBotShippingResults(query_id=update.query_id, error="Shipping not needed for contributions."))
   
    elif isinstance(update, UpdateNewMessage) and isinstance(update.message.action, MessageActionPaymentSentMe):
        payment = update.message.action
        user_id = None
        chat_id = None
       
        try:
            if update.message.from_id and hasattr(update.message.from_id, 'user_id'):
                user_id = update.message.from_id.user_id
            elif entities:
                possible_user_ids = [uid for uid in entities if isinstance(uid, InputPeerUser) and uid.user_id > 0]
                user_id = possible_user_ids[0].user_id if possible_user_ids else None
           
            if not user_id:
                raise ValueError(f"Invalid user_id ({user_id})")
           
            if isinstance(update.message.peer_id, InputPeerUser):
                chat_id = update.message.peer_id.user_id
            elif isinstance(update.message.peer_id, InputPeerChat):
                chat_id = update.message.peer_id.chat_id
            elif isinstance(update.message.peer_id, InputPeerChannel):
                chat_id = update.message.peer_id.channel_id
            else:
                chat_id = user_id
           
            if not chat_id:
                raise ValueError(f"Invalid chat_id ({chat_id})")
           
            user = entities.get(user_id) if entities else None
            full_name = f"{user.first_name} {getattr(user, 'last_name', '')}".strip() or "Unknown" if user else "Unknown"
            username = f"@{user.username}" if user and user.username else "@N/A"
           
            payment_id = str(uuid.uuid4())[:16]
            payment_data[payment_id] = {
                'user_id': user_id,
                'full_name': full_name,
                'username': username,
                'amount': payment.total_amount,
                'charge_id': payment.charge.id
            }
           
            success_message = ReplyInlineMarkup([
                KeyboardButtonRow([
                    KeyboardButtonCopy("Transaction ID", payment.charge.id)
                ])
            ])
            await client.send_message(chat_id, PAYMENT_SUCCESS_TEXT.format(full_name, payment.total_amount, payment.charge.id), parse_mode='md', buttons=success_message)
           
            admin_text = ADMIN_NOTIFICATION_TEXT.format(full_name, user_id, username, payment.total_amount, payment.charge.id)
            refund_button = [[Button.inline(f"Refund {payment.total_amount} ⭐️", f"refund_{payment_id}".encode())]]
           
            admin_ids = OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]
            if DEVELOPER_USER_ID not in admin_ids:
                admin_ids.append(DEVELOPER_USER_ID)
           
            for admin_id in admin_ids:
                try:
                    await client.send_message(admin_id, admin_text, parse_mode='md', buttons=refund_button)
                except Exception as e:
                    logger.error(f"❌ Failed to notify admin {admin_id}: {str(e)}")
                   
        except Exception as e:
            logger.error(f"❌ Payment processing failed for user {user_id if user_id else 'unknown'}: {str(e)}")
            if chat_id:
                user_name = get_display_name(await client.get_entity(DEVELOPER_USER_ID))
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
