import requests
import logging
import pandas as pd
import time
import os
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  # Import your Telegram credentials from the config

# Set up logging to send trade signals to a file and Telegram
logging.basicConfig(filename='live_trading_signals.log', level=logging.INFO, 
                    format='%(asctime)s - %(message)s')

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'  # You can switch to 'HTML' if there are formatting issues
    }
    
    response = requests.post(url, data=payload)
    
    # Check if the message was successfully sent
    if response.status_code == 200:
        logging.info("Telegram message sent successfully.")
    else:
        logging.error(f"Failed to send Telegram message: {response.status_code}, {response.text}")
    
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
    
    price = float(row['last_price'])
    vwap = float(row['vwap'])
    timestamp = row['timestamp']

    # Skip if this timestamp has already been processed
    if last_timestamp is not None and timestamp <= last_timestamp:
        return

    # Update last processed timestamp
    last_timestamp = timestamp

    # Check for oversold condition (Buy Signal)
    if (price - vwap) / vwap <= oversold_threshold and position is None:
        position = 'long'
        entry_price = price
        highest_price = price
        trailing_stop_price = entry_price * (1 - trailing_stop_loss_percentage)
        entry_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        
        # Update Buy Signal Message Formatting
        message = (
            f"⚠️ *Buy Signal Triggered*\n"
            f"Bought at: ${price:.5f} on {timestamp}"
        )
        logging.info(message)
        send_telegram_message(message)

    # Check for trailing stop adjustment and overbought condition (Sell Signal) or take profit/stop loss
    if position == 'long':
        # Update the highest price since the entry
        if price > highest_price:
            highest_price = price
            trailing_stop_price = highest_price * (1 - trailing_stop_loss_percentage)
            logging.info(f"🔄 Trailing Stop Updated: New Stop Price is ${trailing_stop_price:.5f} (Highest Price: ${highest_price:.5f})")

        # Check if the current price hits the trailing stop or the stop loss/take profit conditions
        if price <= trailing_stop_price or price >= entry_price * (1 + take_profit_threshold) or price <= entry_price * (1 + stop_loss_threshold):
            price_change = (price - entry_price) / entry_price
            profit_loss = capital * price_change
            capital += profit_loss
            exit_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            time_held = exit_time - entry_time

            # Update Sell Signal Message Formatting
            message = (
                f"🚨 *Sell Signal Triggered:*\n"
                f"Sold at ${price:.5f} on {timestamp}\n"
                f"Profit/Loss = ${profit_loss:.2f}, Time Held = {time_held}\n"
                f"Updated Capital: ${capital:.2f}"
            )
            logging.info(message)
            send_telegram_message(message)

            # Reset position-related variables
            position = None
            entry_price = None
            trailing_stop_price = None
            highest_price = None
            entry_time = None

# Main loop to process the live data
def monitor_live_data(csv_file):
    global last_timestamp

    while True:
        df = pd.read_csv(csv_file)
        
        for _, row in df.iterrows():
            process_new_data(row)
        
        time.sleep(60)  # Wait for 1 minute before checking for new data

if __name__ == "__main__":
    monitor_live_data('xrp_price_data.csv')
