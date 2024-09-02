import requests
import logging
import pandas as pd
import time
import json
import os
from datetime import datetime, timedelta
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  # Import your Telegram credentials from the config

# Set up logging to send trade signals to a file and Telegram
logging.basicConfig(filename='live_trading_signals.log', level=logging.INFO, 
                    format='%(asctime)s - %(message)s')

# Set the threshold for what is considered "recent" (e.g., 10 minutes)
RECENT_THRESHOLD = timedelta(minutes=10)

LAST_TRADE_TIME_FILE = 'last_trade_time.json'
LAST_TIMESTAMP_FILE = 'last_timestamp.json'
PORTFOLIO_FILE = 'user_portfolios.json'

# Load or initialize portfolios
if os.path.exists(PORTFOLIO_FILE):
    with open(PORTFOLIO_FILE, 'r') as f:
        portfolios = json.load(f)
else:
    portfolios = {}

# Save portfolios to a file
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

def initialize_last_trade_time_file():
    """Initialize the last trade time file if it doesn't exist."""
    if not os.path.exists(LAST_TRADE_TIME_FILE):
        with open(LAST_TRADE_TIME_FILE, 'w') as f:
            json.dump({"last_trade_time": None}, f)

def load_last_trade_time():
    """Load the last trade time from the JSON file."""
    with open(LAST_TRADE_TIME_FILE, 'r') as f:
        data = json.load(f)
        if data['last_trade_time'] is not None:
            return datetime.strptime(data['last_trade_time'], "%Y-%m-%d %H:%M:%S")
        else:
            return None

def save_last_trade_time(last_trade_time):
    """Save the last trade time to the JSON file."""
    with open(LAST_TRADE_TIME_FILE, 'w') as f:
        json.dump({"last_trade_time": last_trade_time.strftime("%Y-%m-%d %H:%M:%S")}, f)

def initialize_last_timestamp_file():
    """Initialize the last timestamp file if it doesn't exist."""
    if not os.path.exists(LAST_TIMESTAMP_FILE):
        with open(LAST_TIMESTAMP_FILE, 'w') as f:
            json.dump({"last_timestamp": None}, f)

def load_last_timestamp():
    """Load the last timestamp from the JSON file."""
    with open(LAST_TIMESTAMP_FILE, 'r') as f:
        data = json.load(f)
        return data.get("last_timestamp")

def save_last_timestamp(last_timestamp):
    """Save the last timestamp to the JSON file."""
    with open(LAST_TIMESTAMP_FILE, 'w') as f:
        json.dump({"last_timestamp": last_timestamp}, f)

# Define thresholds for the signals
overbought_threshold = 0.01  # Price is 1% above VWAP
oversold_threshold = -0.019   # Price is 1% below VWAP

# Set stop loss and take profit thresholds
stop_loss_threshold = -0.02  # 2% stop loss
take_profit_threshold = 0.015  # 1.25% take profit

# Additional thresholds and parameters
sudden_drop_threshold = -0.02  # 2% drop in price in a short time
cooldown_period = 5 * 60  # 5 minutes cooldown between trades

# Load the last trade time and last timestamp when the script starts
initialize_last_trade_time_file()
last_trade_time = load_last_trade_time()

initialize_last_timestamp_file()
last_timestamp = load_last_timestamp()

def process_new_data(row, df, user_id):
    global last_timestamp, last_trade_time
    
    price = float(row['last_price'])
    vwap = float(row['vwap'])
    timestamp = row['timestamp']
    volume = float(row['volume'])

    # Ensure the user's portfolio exists
    if user_id not in portfolios:
        portfolios[user_id] = {
            'capital': 12800.0,  # Default starting capital
            'position': None,
            'entry_price': None,
            'profit_loss': 0.0
        }
        save_portfolios()

    user_portfolio = portfolios[user_id]
    capital = user_portfolio['capital']
    position = user_portfolio['position']
    entry_price = user_portfolio['entry_price']

    # Convert timestamp to datetime object for time-based calculations
    current_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")

    # Skip if this timestamp has already been processed
    if last_timestamp is not None and timestamp <= last_timestamp:
        return

    # Update last processed timestamp
    last_timestamp = timestamp
    save_last_timestamp(last_timestamp)

    # Calculate time since last trade
    if last_trade_time is not None:
        time_since_last_trade = (current_time - last_trade_time).total_seconds()
    else:
        time_since_last_trade = float('inf')  # No previous trade, so ignore cooldown

    # Check for sudden price drop
    if position is None and time_since_last_trade > cooldown_period:
        previous_price = df.iloc[-2]['last_price']  # Get the previous row's price
        price_drop = (price - previous_price) / previous_price
        
        if price_drop < sudden_drop_threshold:
            # Detected sudden drop, decide whether to notify
            message = (
                f"⚠️ *Sudden Price Drop Detected!*\n"
                f"Price dropped by {price_drop:.2%} from ${previous_price:.5f} to ${price:.5f}.\n"
                f"_Skipping buy to avoid potential loss._"
            )
            logging.info(message)

            # Only send Telegram message if the data is recent
            if datetime.now() - current_time <= RECENT_THRESHOLD:
                send_telegram_message(message)
            return

    # Check for oversold condition (Buy Signal)
    if (price - vwap) / vwap <= oversold_threshold and position is None:
        position = 'long'
        entry_price = price
        last_trade_time = current_time
        save_last_trade_time(last_trade_time)  # Save last trade time after buying
        
        user_portfolio['position'] = position
        user_portfolio['entry_price'] = entry_price
        save_portfolios()  # Save portfolio changes
        
        message = (
            f"⚠️ *Buy Signal Triggered*\n"
            f"Bought at: ${price:.5f} (VWAP: ${vwap:.5f})\n"
            f"Time: {timestamp}"
        )
        logging.info(message)

        if datetime.now() - current_time <= RECENT_THRESHOLD:
            send_telegram_message(message)

    # Check for overbought condition (Sell Signal) or take profit/stop loss
    if position == 'long':
        price_change = (price - entry_price) / entry_price

        if price_change >= take_profit_threshold or price_change <= stop_loss_threshold:
            profit_loss = capital * price_change
            user_portfolio['capital'] += profit_loss
            user_portfolio['profit_loss'] += profit_loss
            last_trade_time = current_time
            save_last_trade_time(last_trade_time)  # Save last trade time after selling
            
            user_portfolio['position'] = None
            user_portfolio['entry_price'] = None
            save_portfolios()  # Save portfolio changes
            
            message = (
                f"🚨 *Sell Signal Triggered*\n"
                f"Sold at: ${price:.5f} (VWAP: ${vwap:.5f})\n"
                f"Time: {timestamp}\n\n"
                f"*Trade Result:* ${profit_loss:.2f}\n"
                f"*Updated Capital:* ${user_portfolio['capital']:.2f}"
            )
            logging.info(message)

            if datetime.now() - current_time <= RECENT_THRESHOLD:
                send_telegram_message(message)

# Main loop to process the live data
def monitor_live_data(csv_file, user_id):
    global last_timestamp

    df = pd.read_csv(csv_file)
    
    # Only process data from the last 24 hours, or the last trade time, whichever is more recent
    if last_timestamp:
        cutoff_time = max(datetime.strptime(last_timestamp, "%Y-%m-%d %H:%M:%S"), datetime.now() - timedelta(hours=24))
        df = df[df['timestamp'] >= cutoff_time.strftime("%Y-%m-%d %H:%M:%S")]

    for _, row in df.iterrows():
        process_new_data(row, df, user_id)
    
    time.sleep(60)  # Wait for 1 minute before checking for new data

if __name__ == "__main__":
    # Replace with actual user ID for testing
    user_id = '757670515'
    monitor_live_data('xrp_price_data.csv', user_id)
