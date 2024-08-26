import requests
import logging
import pandas as pd
import time
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
        'parse_mode': 'Markdown'
    }
    response = requests.post(url, data=payload)
    return response.json()

# Define thresholds for the signals
overbought_threshold = 0.01  # Price is 1% above VWAP
oversold_threshold = -0.01   # Price is 1% below VWAP

# Set stop loss and take profit thresholds
stop_loss_threshold = -0.02  # 2% stop loss
take_profit_threshold = 0.0125  # 1.25% take profit

# Initial capital for the live trading
initial_capital = 10000.0
capital = initial_capital
position = None
entry_price = None
last_timestamp = None  # To track the last processed timestamp

def process_new_data(row):
    global position, entry_price, capital, last_timestamp
    
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
        message = f"⚠️ Buy Signal Triggered: Bought at ${price:.5f} (VWAP: ${vwap:.5f}) on {timestamp}"
        logging.info(message)
        send_telegram_message(message)

    # Check for overbought condition (Sell Signal) or take profit/stop loss
    if position == 'long':
        price_change = (price - entry_price) / entry_price

        if price_change >= take_profit_threshold or price_change <= stop_loss_threshold:
            profit_loss = capital * price_change
            capital += profit_loss
            message = (
                f"🚨 Sell Signal Triggered: Sold at ${price:.5f} (VWAP: ${vwap:.5f}) on {timestamp}\n"
                f"   Trade Result: Profit/Loss = ${profit_loss:.2f}\n"
                f"   Updated Capital: ${capital:.2f}"
            )
            logging.info(message)
            send_telegram_message(message)

            position = None
            entry_price = None

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
