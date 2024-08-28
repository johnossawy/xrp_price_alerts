import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, CallbackQueryHandler
import pandas as pd
from config import TELEGRAM_BOT_TOKEN  # Importing from config file

# Ensure TELEGRAM_BOT_TOKEN is not None or an empty string
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set")

updater = Updater(TELEGRAM_BOT_TOKEN)

# File paths
PRICE_DATA_FILE = 'xrp_price_data.csv'
SIGNALS_LOG_FILE = 'live_trading_signals.log'

# Function to retrieve the current XRP price
def get_xrp_price():
    df = pd.read_csv(PRICE_DATA_FILE)
    last_row = df.iloc[-1]
    price = last_row['last_price']
    return price

# Function to retrieve the last trading signal
def get_last_signal():
    with open(SIGNALS_LOG_FILE, 'r') as f:
        lines = f.readlines()
        last_signal = lines[-1] if lines else "No signals logged yet."
    return last_signal

# Command handlers
def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("📊 Get XRP Price", callback_data='price')],
        [InlineKeyboardButton("🔔 Get Last Signal", callback_data='lastsignal')],
        [InlineKeyboardButton("ℹ️ About", callback_data='about')],
        [InlineKeyboardButton("❓ Help", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Welcome to XRP Price Alerts Bot! Use the buttons below:', reply_markup=reply_markup)

def price(update: Update, context: CallbackContext) -> None:
    price = get_xrp_price()
    update.message.reply_text(f"The current XRP price is ${price:.5f}")

def lastsignal(update: Update, context: CallbackContext) -> None:
    last_signal = get_last_signal()
    update.message.reply_text(f"Last Trading Signal:\n{last_signal}")

def help_command(update: Update, context: CallbackContext) -> None:
    help_text = (
        "Available Commands:\n"
        "/start - Start the bot and show available options\n"
        "/price - Get the latest XRP price\n"
        "/lastsignal - Get the last trading signal\n"
        "/about - Learn more about this bot\n"
        "/help - Show this help message"
    )
    update.message.reply_text(help_text)

def about_command(update: Update, context: CallbackContext) -> None:
    about_text = (
        "XRP Price Alerts Bot:\n"
        "This bot provides real-time XRP price alerts and trading signals.\n"
        "You can query the current XRP price, view the last trading signal, "
        "and receive updates directly to your Telegram chat."
    )
    update.message.reply_text(about_text)

def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    if query.data == 'price':
        price = get_xrp_price()
        query.edit_message_text(f"The current XRP price is ${price:.5f}")
    elif query.data == 'lastsignal':
        last_signal = get_last_signal()
        query.edit_message_text(f"Last Trading Signal:\n{last_signal}")
    elif query.data == 'about':
        about_text = (
            "XRP Price Alerts Bot:\n"
            "This bot provides real-time XRP price alerts and trading signals.\n"
            "You can query the current XRP price, view the last trading signal, "
            "and receive updates directly to your Telegram chat."
        )
        query.edit_message_text(about_text)
    elif query.data == 'help':
        help_text = (
            "Available Commands:\n"
            "/start - Start the bot and show available options\n"
            "/price - Get the latest XRP price\n"
            "/lastsignal - Get the last trading signal\n"
            "/about - Learn more about this bot\n"
            "/help - Show this help message"
        )
        query.edit_message_text(help_text)

def main():
    # Set up the bot
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dp = updater.dispatcher

    # Add command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("price", price))
    dp.add_handler(CommandHandler("lastsignal", lastsignal))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("about", about_command))
    dp.add_handler(CallbackQueryHandler(button))

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
