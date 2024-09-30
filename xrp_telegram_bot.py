# xrp_telegram_bot.py

import logging
import time
from typing import Union  # Import Union for type annotations
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram.error import NetworkError  # Import NetworkError for better error handling
from config import TELEGRAM_BOT_TOKEN  # Importing from config file
from database_handler import DatabaseHandler  # Import your updated DatabaseHandler

# Configure logging for xrp_telegram_bot.py
logging.basicConfig(
    filename='xrp_telegram_bot.log',  # Use a distinct log file
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'  # Align with other scripts' date format
)

# Initialize the DatabaseHandler
db_handler = DatabaseHandler()

def get_xrp_price() -> Union[float, str]:
    """
    Retrieve the latest XRP price from the database.

    Returns:
        float: The latest XRP price.
        str: Error message if retrieval fails.
    """
    try:
        query = """
            SELECT last_price FROM crypto_prices
            WHERE symbol = %(symbol)s
            ORDER BY timestamp DESC
            LIMIT 1;
        """
        params = {'symbol': 'XRP'}
        result = db_handler.fetch_one(query, params)
        if result and result.get('last_price') is not None:
            price = float(result['last_price'])
            logging.info(f"Retrieved XRP price: ${price:.5f}")
            return price
        else:
            logging.warning("No XRP price data found in DB.")
            return "XRP price data not available."
    except Exception as e:
        logging.error(f"Error retrieving XRP price: {e}")
        return "Error retrieving price."

def get_last_signal() -> str:
    """
    Retrieve the last buy or sell trading signal from the database.

    Returns:
        str: The latest trading signal message or an error message.
    """
    try:
        query = """
            SELECT signal_type, price, profit_loss, percent_change, time_held, updated_capital, timestamp
            FROM trade_signals
            WHERE UPPER(signal_type) IN ('BUY', 'SELL', 'SELL_LOSS')  -- Include all relevant signal types
            ORDER BY timestamp DESC
            LIMIT 1;
        """
        params = {}
        result = db_handler.fetch_one(query, params)
        if result:
            signal_type = result.get('signal_type', 'Unknown').capitalize()
            price = result.get('price')
            profit_loss = result.get('profit_loss')
            percent_change = result.get('percent_change')
            time_held = result.get('time_held')
            updated_capital = result.get('updated_capital')
            timestamp = result.get('timestamp')
            
            # Normalize signal type for consistent handling
            normalized_signal = signal_type.upper()
            
            # Format the message based on signal type and available data
            if normalized_signal == 'BUY':
                message = (
                    f"⚠️ *Buy Signal Triggered*\n"
                    f"Bought at: ${price:.5f}\n"
                    f"Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"#Ripple #XRP #XRPPriceAlerts"
                )
            elif normalized_signal in ['SELL', 'SELL_LOSS']:
                # Determine if it's a profit or loss
                if profit_loss > 0:
                    profit_loss_msg = f"💰 Profit: ${profit_loss:.2f}"
                else:
                    profit_loss_msg = f"🔻 Loss: ${-profit_loss:.2f}"
                
                message = (
                    f"🚨 *Sell Signal Triggered:*\n"
                    f"Sold at: ${price:.5f}\n"
                    f"{profit_loss_msg}\n"
                    f"Updated Capital: ${updated_capital:.2f}\n"
                    f"Time Held: {time_held}\n"
                    f"Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"#Ripple #XRP #XRPPriceAlerts"
                )
            else:
                message = "Unknown trading signal."
            
            logging.info("Retrieved last trading signal.")
            return message
        else:
            logging.info("No trading signals found in DB.")
            return "No trading signals found."
    except Exception as e:
        logging.error(f"Error retrieving last trading signal: {e}")
        return "Error retrieving trading signal."

# Retry logic for fetching updates with exponential backoff
def get_updates_with_retry(bot, retries=5, delay=5):
    """
    Function to handle retries when fetching updates from Telegram.

    Args:
        bot: The Telegram bot instance.
        retries (int): Number of retries before giving up.
        delay (int): Initial delay in seconds between retries (with exponential backoff).

    Returns:
        Updates object or None if failure occurs.
    """
    for attempt in range(retries):
        try:
            updates = bot.get_updates()
            return updates  # Return updates if successful
        except NetworkError as e:
            logging.error(f"NetworkError: {e}. Retrying {attempt + 1}/{retries}...")
            time.sleep(delay * (attempt + 1))  # Exponential backoff
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            break  # If it's an unknown error, break out of the loop
    return None

# Command handlers
def start(update: Update, context: CallbackContext) -> None:
    """Handle the /start command."""
    update.message.reply_text(
        'Welcome to the XRP Price Alerts Bot! Use /price to get the latest XRP price or /lastsignal to get the last trading signal.'
    )

def price(update: Update, context: CallbackContext) -> None:
    """Handle the /price command."""
    price = get_xrp_price()
    if isinstance(price, float):
        update.message.reply_text(f"The current XRP price is ${price:.5f}")
    else:
        update.message.reply_text(price)  # Error message

def lastsignal(update: Update, context: CallbackContext) -> None:
    """Handle the /lastsignal command."""
    last_signal = get_last_signal()
    update.message.reply_text(f"Last Trading Signal:\n{last_signal}", parse_mode='Markdown')

def main():
    """Start the bot."""
    # Set up the Updater with your bot token
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Add command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("price", price))
    dp.add_handler(CommandHandler("lastsignal", lastsignal))

    # Start the bot with error handling and retry logic
    try:
        logging.info("Starting XRP Telegram Bot...")
        updater.start_polling()
    except NetworkError as e:
        logging.error(f"NetworkError occurred: {e}. Restarting bot...")
        get_updates_with_retry(updater.bot)  # Retry fetching updates
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        updater.idle()

if __name__ == "__main__":
    main()
