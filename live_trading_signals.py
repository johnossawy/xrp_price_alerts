import requests
import logging
import pandas as pd
import time
import os
from datetime import datetime
# import pytz  # Uncomment if using timezone handling
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Set up logging with custom date format
logging.basicConfig(
    filename='live_trading_signals.log',
    level=logging.INFO, 
    format='%(asctime)s - %(message)s',
    datefmt='%b %d, %Y %I:%M:%S %p'
)
logger = logging.getLogger(__name__)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        logger.info("Telegram message sent successfully.")
    else:
        logger.error(f"Failed to send Telegram message: {response.status_code}, {response.text}")
    
    return response.json()

# Define thresholds for the signals
overbought_threshold = 0.01  # Price is 1% above VWAP
oversold_threshold = -0.019   # Price is 1% below VWAP

# Set stop loss and take profit thresholds
stop_loss_threshold = -0.02  # 2% stop loss
take_profit_threshold = 0.015  # 1.25% take profit

# Set trailing stop percentage
trailing_stop_loss_percentage = 0.005  # 0.5% trailing stop

# Initial capital for the live trading
initial_capital = 12800.0
capital = initial_capital
position = None
entry_price = None
trailing_stop_price = None  # Variable to track trailing stop price
highest_price = None  # Variable to track the highest price since entry
last_timestamp = None  # To track the last processed timestamp
entry_time = None  # To track the entry time of the position

def process_new_data(row):
    global position, entry_price, capital, trailing_stop_price, highest_price, last_timestamp, entry_time
    
    try:
        price = float(row['last_price'])
        vwap = float(row['vwap'])
        timestamp = row['timestamp']

        # Skip if this timestamp has already been processed
        if last_timestamp is not None and timestamp <= last_timestamp:
            return

        # Update last processed timestamp
        last_timestamp = timestamp

        # Parse and format timestamp
        timestamp_dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        formatted_timestamp = timestamp_dt.strftime('%B %d, %Y at %I:%M %p')

        # Check for oversold condition (Buy Signal)
        if (price - vwap) / vwap <= oversold_threshold and position is None:
            position = 'long'
            entry_price = price
            highest_price = price
            trailing_stop_price = entry_price * (1 - trailing_stop_loss_percentage)
            entry_time = timestamp_dt

            message = (
                f"⚠️ *Buy Signal Triggered*\n"
                f"Bought at: ${price:.5f} on {formatted_timestamp}"
            )
            logger.info(message)
            send_telegram_message(message)

        # Check for trailing stop adjustment and overbought condition (Sell Signal) or take profit/stop loss
        if position == 'long':
            # Update the highest price since the entry
            if price > highest_price:
                highest_price = price
                trailing_stop_price = highest_price * (1 - trailing_stop_loss_percentage)
                logger.info(
                    f"🔄 Trailing Stop Updated: New Stop Price is ${trailing_stop_price:.5f} "
                    f"(Highest Price: ${highest_price:.5f})"
                )

            # Check exit conditions
            if (price <= trailing_stop_price or 
                price >= entry_price * (1 + take_profit_threshold) or 
                price <= entry_price * (1 + stop_loss_threshold)):
                
                price_change = (price - entry_price) / entry_price
                profit_loss = capital * price_change
                capital += profit_loss
                exit_time = timestamp_dt
                time_held = exit_time - entry_time

                # Format time held
                hours, remainder = divmod(time_held.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                time_held_formatted = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

                message = (
                    f"🚨 *Sell Signal Triggered:*\n"
                    f"Sold at ${price:.5f} on {formatted_timestamp}\n"
                    f"Profit/Loss = ${profit_loss:.2f}, Time Held = {time_held_formatted}\n"
                    f"Updated Capital: ${capital:.2f}"
                )
                logger.info(message)
                send_telegram_message(message)

                # Reset position-related variables
                position = None
                entry_price = None
                trailing_stop_price = None
                highest_price = None
                entry_time = None

    except Exception as e:
        logger.error(f"An error occurred while processing data: {e}")

# Main loop to process the live data
def monitor_live_data(csv_file):
    global last_timestamp

    while True:
        try:
            df = pd.read_csv(csv_file)
        except FileNotFoundError:
            logger.error(f"File {csv_file} not found.")
            time.sleep(60)
            continue
        except pd.errors.EmptyDataError:
            logger.error(f"File {csv_file} is empty.")
            time.sleep(60)
            continue
        except Exception as e:
            logger.error(f"An error occurred while reading the file: {e}")
            time.sleep(60)
            continue

        # Process only new data
        if last_timestamp is not None:
            df = df[df['timestamp'] > last_timestamp]

        for _, row in df.iterrows():
            process_new_data(row)

        time.sleep(60)

if __name__ == "__main__":
    monitor_live_data('xrp_price_data.csv')
