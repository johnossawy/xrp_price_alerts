import os
import requests
import logging
import pandas as pd
import time
import json
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  # Import your Telegram credentials from the config

# Set up logging to send trade signals to a file and Telegram
logging.basicConfig(filename='live_trading_signals.log', level=logging.INFO, 
                    format='%(asctime)s - %(message)s')

# Constants for the JSON file
LAST_TRADE_TIME_FILE = 'last_trade_time.json'

# Function to load the last trade time from the JSON file
def load_last_trade_time():
    if os.path.exists(LAST_TRADE_TIME_FILE):
        with open(LAST_TRADE_TIME_FILE, 'r') as f:
            data = json.load(f)
            return data.get('last_trade_time')
    return None

# Function to save the last trade time to the JSON file
def save_last_trade_time(time_value):
    with open(LAST_TRADE_TIME_FILE, 'w') as f:
        json.dump({'last_trade_time': time_value}, f)

# Function to initialize the last trade time JSON file if it's empty or does not exist
def initialize_last_trade_time_file():
    if not os.path.exists(LAST_TRADE_TIME_FILE) or os.path.getsize(LAST_TRADE_TIME_FILE) == 0:
        with open(LAST_TRADE_TIME_FILE, 'w') as f:
            json.dump({'last_trade_time': None}, f)
        logging.info(f"{LAST_TRADE_TIME_FILE} initialized with null last_trade_time.")

# Initialize the last trade time file if necessary
initialize_last_trade_time_file()

# Load the last trade time at the start of the script
last_trade_time = load_last_trade_time()

# Load user portfolios
PORTFOLIO_FILE = 'user_portfolios.json'
if os.path.exists(PORTFOLIO_FILE):
    with open(PORTFOLIO_FILE, 'r') as f:
        portfolios = json.load(f)
else:
    portfolios = {}

def save_portfolios():
    with open(PORTFOLIO_FILE, 'w') as f:
        json.dump(portfolios, f)

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
oversold_threshold = -0.019   # Price is 1% below VWAP

# Set stop loss and take profit thresholds
stop_loss_threshold = -0.02  # 2% stop loss
take_profit_threshold = 0.015  # 1.5% take profit

# Additional thresholds and parameters
sudden_drop_threshold = -0.02  # 2% drop in price in a short time
cooldown_period = 5 * 60  # 5 minutes cooldown between trades

position = None
entry_price = None
last_timestamp = None  # To track the last processed timestamp

def process_new_data(row, df):
    global position, entry_price, last_timestamp, last_trade_time
    
    price = float(row['last_price'])
    vwap = float(row['vwap'])
    timestamp = row['timestamp']
    volume = float(row['volume'])

    current_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")

    if last_timestamp is not None and timestamp <= last_timestamp:
        return

    last_timestamp = timestamp

    # Convert last_trade_time from string to datetime if it's not already a datetime object
    if isinstance(last_trade_time, str):
        last_trade_time = datetime.strptime(last_trade_time, "%Y-%m-%d %H:%M:%S")

    if last_trade_time is not None:
        time_since_last_trade = (current_time - last_trade_time).total_seconds()
    else:
        time_since_last_trade = float('inf')

    if time_since_last_trade <= cooldown_period:
        logging.info(f"Cooldown period active. Skipping trade. Time since last trade: {time_since_last_trade} seconds.")
        return

    if position is None:
        previous_price = df.iloc[-2]['last_price']
        price_drop = (price - previous_price) / previous_price
        
        if price_drop < sudden_drop_threshold:
            message = (
                f"⚠️ *Sudden Price Drop Detected!*\n"
                f"Price dropped by {price_drop:.2%} from ${previous_price:.5f} to ${price:.5f}.\n"
                f"_Skipping buy to avoid potential loss._"
            )
            logging.info(message)
            send_telegram_message(message)
            return

    if (price - vwap) / vwap <= oversold_threshold and position is None:
        position = 'long'
        entry_price = price
        last_trade_time = current_time
        save_last_trade_time(last_trade_time.strftime('%Y-%m-%d %H:%M:%S'))

        if TELEGRAM_CHAT_ID in portfolios:
            message = buy_signal(TELEGRAM_CHAT_ID, price)
            if message:
                logging.info(message)
                send_telegram_message(message)

    if position == 'long':
        price_change = (price - entry_price) / entry_price

        if price_change >= take_profit_threshold or price_change <= stop_loss_threshold:
            last_trade_time = current_time
            save_last_trade_time(last_trade_time.strftime('%Y-%m-%d %H:%M:%S'))

            if TELEGRAM_CHAT_ID in portfolios:
                message = sell_signal(TELEGRAM_CHAT_ID, price)
                if message:
                    logging.info(message)
                    send_telegram_message(message)

            position = None
            entry_price = None

# Function to handle buy signal and update user's portfolio
def buy_signal(chat_id, price):
    portfolio = portfolios.get(str(chat_id))
    if portfolio and portfolio['position'] is None:  # No open position
        portfolio['position'] = 'long'
        portfolio['entry_price'] = price
        save_portfolios()
        return f"⚠️ *Buy Signal Triggered*\nBought at: ${price:.3f}\nCapital: ${portfolio['capital']:.2f}"
    return None

# Function to handle sell signal and update user's portfolio
def sell_signal(chat_id, price):
    portfolio = portfolios.get(str(chat_id))
    if portfolio and portfolio['position'] == 'long':  # Must have an open position to sell
        price_change = (price - portfolio['entry_price']) / portfolio['entry_price']
        profit_loss = portfolio['capital'] * price_change
        portfolio['capital'] += profit_loss
        portfolio['profit_loss'] += profit_loss
        portfolio['position'] = None  # Close position
        portfolio['entry_price'] = None
        save_portfolios()
        return f"🚨 *Sell Signal Triggered*\nSold at: ${price:.3f}\nProfit/Loss: ${profit_loss:.2f}\nUpdated Capital: ${portfolio['capital']:.2f}"
    return None

# Main loop to process the live data
def monitor_live_data(csv_file):
    global last_timestamp

    while True:
        df = pd.read_csv(csv_file)
        
        for _, row in df.iterrows():
            process_new_data(row, df)
        
        time.sleep(60)  # Wait for 1 minute before checking for new data

if __name__ == "__main__":
    monitor_live_data('xrp_price_data.csv')
