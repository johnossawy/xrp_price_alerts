import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler
import pandas as pd
from config import TELEGRAM_BOT_TOKEN  # Importing from config file

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
    update.message.reply_text('Welcome to XRP Price Alerts Bot! Use /price to get the latest XRP price or /lastsignal to get the last trading signal.')

def price(update: Update, context: CallbackContext) -> None:
    price = get_xrp_price()
    update.message.reply_text(f"The current XRP price is ${price:.5f}")

def lastsignal(update: Update, context: CallbackContext) -> None:
    last_signal = get_last_signal()
    update.message.reply_text(f"Last Trading Signal:\n{last_signal}")

def main():
    # Set up the bot
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dp = updater.dispatcher

    # Add command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("price", price))
    dp.add_handler(CommandHandler("lastsignal", lastsignal))

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()