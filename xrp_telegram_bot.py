import logging
import time
from typing import Union
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram.error import NetworkError
from config import TELEGRAM_BOT_TOKEN
from database_handler import DatabaseHandler

# Configure logging
logging.basicConfig(
    filename='xrp_telegram_bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Initialize the DatabaseHandler
db_handler = DatabaseHandler()

# Function to retry fetching updates with exponential backoff
def get_updates_with_retry(updater, retries=5, delay=5):
    """Function to handle retries when fetching updates from Telegram."""
    for attempt in range(retries):
        try:
            updater.start_polling()
            return  # If successful, break out of the loop
        except NetworkError as e:
            logging.error(f"NetworkError: {e}. Retrying {attempt + 1}/{retries}...")
            time.sleep(delay * (attempt + 1))  # Exponential backoff
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            break  # If it's an unknown error, break out of the loop

# Function to retrieve XRP price
def get_xrp_price() -> Union[float, str]:
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

# Function to retrieve the last trading signal
def get_last_signal() -> str:
    try:
        query = """
            SELECT signal_type, price, profit_loss, percent_change, time_held, updated_capital, timestamp
            FROM trade_signals
            WHERE UPPER(signal_type) IN ('BUY', 'SELL', 'SELL_LOSS')
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
            
            normalized_signal = signal_type.upper()
            
            if normalized_signal == 'BUY':
                message = (
                    f"⚠️ *Buy Signal Triggered*\n"
                    f"Bought at: ${price:.5f}\n"
                    f"Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"#Ripple #XRP #XRPPriceAlerts"
                )
            elif normalized_signal in ['SELL', 'SELL_LOSS']:
                profit_loss_msg = f"💰 Profit: ${profit_loss:.2f}" if profit_loss > 0 else f"🔻 Loss: ${-profit_loss:.2f}"
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

# Function to get current capital
def get_current_capital() -> Union[float, str]:
    try:
        query = """
            SELECT updated_capital
            FROM trade_signals
            ORDER BY timestamp DESC
            LIMIT 1;
        """
        result = db_handler.fetch_one(query)
        if result and result.get('updated_capital') is not None:
            capital = float(result['updated_capital'])
            logging.info(f"Retrieved current capital: ${capital:.2f}")
            return capital
        else:
            logging.warning("No capital data found in DB.")
            return "Capital data not available."
    except Exception as e:
        logging.error(f"Error retrieving current capital: {e}")
        return "Error retrieving capital."

# Function to update current capital
def set_current_capital(new_capital: float) -> str:
    try:
        query = """
            INSERT INTO trade_signals (updated_capital, timestamp, signal_type)
            VALUES (%(new_capital)s, NOW(), 'UPDATE');  -- Default 'UPDATE' signal type
        """
        params = {'new_capital': new_capital}
        db_handler.execute(query, params)
        logging.info(f"Updated current capital to ${new_capital:.2f}")
        return f"Capital updated to ${new_capital:.2f}"
    except Exception as e:
        logging.error(f"Error updating capital: {e}")
        return "Error updating capital."

# Telegram command handlers
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Welcome to the XRP Price Alerts Bot! Use /price to get the latest XRP price or /lastsignal to get the last trading signal.')

def price(update: Update, context: CallbackContext) -> None:
    price = get_xrp_price()
    if isinstance(price, float):
        update.message.reply_text(f"The current XRP price is ${price:.5f}")
    else:
        update.message.reply_text(price)

def lastsignal(update: Update, context: CallbackContext) -> None:
    last_signal = get_last_signal()
    update.message.reply_text(f"Last Trading Signal:\n{last_signal}", parse_mode='Markdown')

# Command to show current capital
def capital(update: Update, context: CallbackContext) -> None:
    capital = get_current_capital()
    if isinstance(capital, float):
        update.message.reply_text(f"Your current capital is ${capital:.2f}")
    else:
        update.message.reply_text(capital)

# Command to update current capital
def setcapital(update: Update, context: CallbackContext) -> None:
    try:
        new_capital = float(context.args[0])  # First argument is the new capital
        message = set_current_capital(new_capital)
        update.message.reply_text(message)
    except (IndexError, ValueError):
        update.message.reply_text("Please provide a valid number for the capital. Usage: /setcapital <amount>")

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Add command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("price", price))
    dp.add_handler(CommandHandler("lastsignal", lastsignal))
    dp.add_handler(CommandHandler("capital", capital))
    dp.add_handler(CommandHandler("setcapital", setcapital))

    try:
        logging.info("Starting XRP Telegram Bot...")
        updater.start_polling()
    except NetworkError as e:
        logging.error(f"NetworkError occurred: {e}. Restarting bot...")
        get_updates_with_retry(updater)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        updater.idle()

if __name__ == "__main__":
    main()
