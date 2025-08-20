import uuid
import hashlib
import time
from telethon import TelegramClient, events, types, Button, functions
from telethon.tl.types import (
    InputMediaInvoice, 
    Invoice, 
    LabeledPrice, 
    KeyboardButtonBuy, 
    KeyboardButtonCopy, 
    DataJSON,
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
from telethon.types import (
    ReplyInlineMarkup,
    KeyboardButtonRow,
    InputKeyboardButtonUserProfile
)
from telethon.utils import get_display_name
from config import COMMAND_PREFIX, OWNER_ID, DEVELOPER_USER_ID, BAN_REPLY
from utils import LOGGER
from core import banned_users

logger = LOGGER

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

def setup_donate_handler(app):
    def get_donation_buttons(amount: int = 5):
        if amount == 5:
            return [
                [Button.inline(f"{amount} ⭐️", data=f"gift_{amount}"),
                 Button.inline("+5", data=f"increment_gift_{amount}")]
            ]
        return [
            [Button.inline("-5", data=f"decrement_gift_{amount}"),
             Button.inline(f"{amount} ⭐️", data=f"gift_{amount}"),
             Button.inline("+5", data=f"increment_gift_{amount}")]
        ]

    async def generate_invoice(client: TelegramClient, chat_id: int, user_id: int, amount: int):
        if active_invoices.get(user_id):
            await client.send_message(entity=chat_id, message=DUPLICATE_INVOICE_TEXT, parse_mode='Markdown')
            return

        back_button = [[Button.inline("🔙 Back", data="show_donate_options")]]
        loading_message = await client.send_message(
            entity=chat_id,
            message=INVOICE_CREATION_TEXT.format(amount),
            parse_mode='Markdown',
            buttons=back_button
        )

        try:
            active_invoices[user_id] = True
            timestamp = int(time.time())
            unique_id = str(uuid.uuid4())[:8]
            invoice_payload = f"contribution_{user_id}_{amount}_{timestamp}_{unique_id}".encode()
            title = "Support Smart Tools"
            description = f"Contribute {amount} Stars to support ongoing development and keep the tools free, fast, and reliable for everyone 💫 Every star helps us grow!"
            currency = "XTR"
           
            invoice = types.Invoice(
                currency=currency,
                prices=[types.LabeledPrice(label=f"⭐️ {amount} Stars", amount=amount)]
            )
           
            reply_markup = [
                [Button.buy("💫 Donate Via Stars")]
            ]

            await client.send_message(
                entity=chat_id,
                message="",
                file=types.InputMediaInvoice(
                    title=title,
                    description=description,
                    invoice=invoice,
                    payload=invoice_payload,
                    provider_data=types.DataJSON(data="{}"),
                    start_param="donate-stars-to-quickutil"
                ),
                buttons=reply_markup
            )

            await client.edit_message(
                loading_message,
                INVOICE_CONFIRMATION_TEXT.format(amount),
                parse_mode='Markdown',
                buttons=back_button
            )

            logger.info(f"✅ Invoice sent for {amount} stars to user {user_id} with payload {invoice_payload}")

        except Exception as e:
            logger.error(f"❌ Failed to generate invoice for user {user_id}: {str(e)}")
            await client.edit_message(
                loading_message,
                INVOICE_FAILED_TEXT,
                parse_mode='Markdown',
                buttons=back_button
            )
        finally:
            active_invoices.pop(user_id, None)

    @app.on(events.NewMessage(pattern=f'^{COMMAND_PREFIX}(donate|gift)( .*)?$'))
    async def donate_command(event):
        user_id = event.sender_id if event.sender else None
        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await app.send_message(entity=event.chat_id, message=BAN_REPLY, parse_mode='Markdown')
            return

        logger.info(f"Donation command received: user: {user_id or 'unknown'}, chat: {event.chat_id}")

        if len(event.message.text.split()) == 1:
            reply_markup = get_donation_buttons()
            await app.send_message(
                entity=event.chat_id,
                message=DONATION_OPTIONS_TEXT,
                parse_mode='Markdown',
                buttons=reply_markup
            )
        elif len(event.message.text.split()) == 2 and event.message.text.split()[1].isdigit() and int(event.message.text.split()[1]) > 0:
            amount = int(event.message.text.split()[1])
            await generate_invoice(app, event.chat_id, event.sender_id, amount)
        else:
            await app.send_message(
                entity=event.chat_id,
                message=INVALID_INPUT_TEXT,
                parse_mode='Markdown',
                reply_to=event.message
            )

    @app.on(events.CallbackQuery(pattern=r'^(gift_\d+|increment_gift_\d+|decrement_gift_\d+|show_donate_options|refund_.+)$'))
    async def handle_donate_callback(event):
        data = event.data.decode()
        chat_id = event.chat_id
        user_id = event.sender_id

        if user_id and await banned_users.banned_users.find_one({"user_id": user_id}):
            await app.send_message(entity=chat_id, message=BAN_REPLY, parse_mode='Markdown')
            await event.answer("You are banned!", alert=True)
            return

        logger.info(f"Callback query received: data={data}, user: {user_id}, chat: {chat_id}")
       
        if data.startswith("gift_"):
            quantity = int(data.split("_")[1])
            await generate_invoice(app, chat_id, user_id, quantity)
            await event.answer("✅ Invoice Generated! Donate Now! ⭐️")

        elif data.startswith("increment_gift_"):
            current_amount = int(data.split("_")[2])
            new_amount = current_amount + 5
            reply_markup = get_donation_buttons(new_amount)
            await event.edit(
                DONATION_OPTIONS_TEXT,
                parse_mode='Markdown',
                buttons=reply_markup
            )
            await event.answer(f"Updated to {new_amount} Stars")

        elif data.startswith("decrement_gift_"):
            current_amount = int(data.split("_")[2])
            new_amount = max(5, current_amount - 5)
            reply_markup = get_donation_buttons(new_amount)
            await event.edit(
                DONATION_OPTIONS_TEXT,
                parse_mode='Markdown',
                buttons=reply_markup
            )
            await event.answer(f"Updated to {new_amount} Stars")

        elif data == "show_donate_options":
            reply_markup = get_donation_buttons()
            await event.edit(
                DONATION_OPTIONS_TEXT,
                parse_mode='Markdown',
                buttons=reply_markup
            )
            await event.answer()

        elif data.startswith("refund_"):
            admin_ids = OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]
            if user_id in admin_ids or user_id == DEVELOPER_USER_ID:
                payment_id = data.replace("refund_", "")
               
                user_info = payment_data.get(payment_id)
                if not user_info:
                    await event.answer("❌ Payment data not found!", alert=True)
                    return
               
                refund_user_id = user_info['user_id']
                refund_amount = user_info['amount']
                full_charge_id = user_info['charge_id']
                full_name = user_info['full_name']
               
                try:
                    refund_user_entity = await app.get_entity(refund_user_id)
                    result = await app(RefundStarsChargeRequest(
                        user_id=types.InputUser(user_id=refund_user_id, access_hash=refund_user_entity.access_hash),
                        charge_id=full_charge_id
                    ))
                    if result:
                        await event.edit(
                            REFUND_SUCCESS_TEXT.format(refund_amount, full_name, refund_user_id),
                            parse_mode='Markdown'
                        )
                        await event.answer("✅ Refund processed successfully!")
                        payment_data.pop(payment_id, None)
                        logger.info(f"✅ Refund successful for user {refund_user_id}: {refund_amount} Stars")
                    else:
                        await event.answer("❌ Refund failed!", alert=True)
                        logger.error(f"❌ Refund failed for user {refund_user_id}: Unknown error")
                except Exception as e:
                    logger.error(f"❌ Refund failed for user {refund_user_id}: {str(e)}")
                    await event.edit(
                        REFUND_FAILED_TEXT.format(refund_amount, full_name, refund_user_id, str(e)),
                        parse_mode='Markdown'
                    )
                    await event.answer("❌ Refund failed!", alert=True)
            else:
                await event.answer("❌ You don't have permission to refund!", alert=True)

    @app.on(events.Raw(types=(UpdateBotPrecheckoutQuery, UpdateBotShippingQuery, UpdateNewMessage)))
    async def raw_update_handler(update):
        if isinstance(update, UpdateBotPrecheckoutQuery):
            try:
                await app(SetBotPrecheckoutResultsRequest(
                    query_id=update.query_id,
                    success=True
                ))
                logger.info(f"✅ Pre-checkout query {update.query_id} OK for user {update.user_id}")
            except Exception as e:
                logger.error(f"❌ Pre-checkout query {update.query_id} failed: {str(e)}")
                try:
                    await app(SetBotPrecheckoutResultsRequest(
                        query_id=update.query_id,
                        success=False,
                        error="Failed to process pre-checkout."
                    ))
                except Exception as rollback_error:
                    logger.error(f"❌ Failed to send error response for pre-checkout: {str(rollback_error)}")

        elif isinstance(update, UpdateBotShippingQuery):
            try:
                await app(SetBotShippingResultsRequest(
                    query_id=update.query_id,
                    shipping_options=[]
                ))
                logger.info(f"✅ Shipping query {update.query_id} OK for user {update.user_id}")
            except Exception as e:
                logger.error(f"❌ Shipping query {update.query_id} failed: {str(e)}")
                try:
                    await app(SetBotShippingResultsRequest(
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
                    if isinstance(update.message.peer_id, PeerUser):
                        user_id = update.message.peer_id.user_id
                    elif hasattr(update.message.peer_id, 'user_id'):
                        user_id = update.message.peer_id.user_id

                if not user_id or user_id <= 0:
                    logger.error(f"❌ Could not determine user_id from update: {update}")
                    return

                if await banned_users.banned_users.find_one({"user_id": user_id}):
                    try:
                        await app.send_message(
                            entity=user_id,
                            message=BAN_REPLY,
                            parse_mode='Markdown'
                        )
                    except Exception as ban_msg_error:
                        logger.error(f"❌ Failed to send ban message to user {user_id}: {str(ban_msg_error)}")
                    return

                if hasattr(update.message, 'peer_id') and update.message.peer_id:
                    if isinstance(update.message.peer_id, PeerUser):
                        chat_id = update.message.peer_id.user_id
                    elif isinstance(update.message.peer_id, PeerChat):
                        chat_id = update.message.peer_id.chat_id
                    elif isinstance(update.message.peer_id, PeerChannel):
                        chat_id = update.message.peer_id.channel_id
                    else:
                        chat_id = user_id
                else:
                    chat_id = user_id

                if not chat_id:
                    logger.error(f"❌ Could not determine chat_id from update")
                    chat_id = user_id

                try:
                    user = await app.get_entity(user_id)
                    full_name = get_display_name(user) if user else "Unknown"
                    username = f"@{user.username}" if user and hasattr(user, 'username') and user.username else "@N/A"
                except Exception as user_fetch_error:
                    logger.error(f"❌ Failed to fetch user entity {user_id}: {str(user_fetch_error)}")
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

                    await app.send_message(
                        entity=chat_id,
                        message=PAYMENT_SUCCESS_TEXT.format(full_name, payment.total_amount, payment.charge.id),
                        parse_mode='Markdown',
                        buttons=success_message
                    )
                    logger.info(f"✅ Payment success message sent to user {user_id}")
                except Exception as success_msg_error:
                    logger.error(f"❌ Failed to send success message to user {user_id}: {str(success_msg_error)}")

                admin_text = ADMIN_NOTIFICATION_TEXT.format(full_name, user_id, username, payment.total_amount, payment.charge.id)
                refund_button = [
                    [Button.inline(f"Refund {payment.total_amount} ⭐️", data=f"refund_{payment_id}")]
                ]

                admin_ids = OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]
                if DEVELOPER_USER_ID and DEVELOPER_USER_ID not in admin_ids:
                    admin_ids.append(DEVELOPER_USER_ID)

                notification_sent = False
                for admin_id in admin_ids:
                    try:
                        if admin_id and admin_id > 0:
                            await app.send_message(
                                entity=admin_id,
                                message=admin_text,
                                parse_mode='Markdown',
                                buttons=refund_button
                            )
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
                        developer_entity = await app.get_entity(DEVELOPER_USER_ID)
                        user_name = get_display_name(developer_entity)
                        await app.send_message(
                            entity=chat_id,
                            message=PAYMENT_FAILED_TEXT,
                            parse_mode='Markdown',
                            buttons=ReplyInlineMarkup([
                                KeyboardButtonRow([
                                    InputKeyboardButtonUserProfile(user_name, await app.get_input_entity(DEVELOPER_USER_ID))
                                ])
                            ])
                        )
                    except Exception as failure_notify_error:
                        logger.error(f"❌ Failed to send payment failure notification: {str(failure_notify_error)}")

