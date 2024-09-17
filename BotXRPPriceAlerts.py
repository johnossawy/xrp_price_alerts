#BotXRPPriceAlerts.py
import os
import re
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
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

def get_last_signal():
    """
    Retrieves the last buy or sell signal from the log file using regex for details.

    Returns:
        str: The last buy or sell signal message.
    """
    try:
        if not os.path.exists(SIGNALS_LOG_FILE):
            return "Signals log file not found."

        # Patterns to identify signals and details
        buy_pattern = re.compile(r'⚠️ \*Buy Signal Triggered\*')
        sell_pattern = re.compile(r'🚨 \*Sell Signal Triggered:\*')
        detail_patterns = [
            re.compile(r'Bought at:.*'),
            re.compile(r'Sold at.*'),
            re.compile(r'Profit/Loss.*'),
            re.compile(r'Updated Capital.*'),
            re.compile(r'Time Held.*')
        ]

        with open(SIGNALS_LOG_FILE, 'r') as f:
            lines = f.readlines()

        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if buy_pattern.search(line) or sell_pattern.search(line):
                signal_lines = [line]
                # Look ahead for detail lines
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if any(pattern.search(next_line) for pattern in detail_patterns):
                        signal_lines.append(next_line)
                        j += 1
                    else:
                        break
                return "\n".join(signal_lines)
        return "No buy or sell signals found."
    except Exception as e:
        return f"An error occurred while reading the signals: {e}"

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
