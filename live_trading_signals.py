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

# Additional thresholds and parameters
sudden_drop_threshold = -0.02  # 2% drop in price in a short time
cooldown_period = 5 * 60  # 5 minutes cooldown between trades

# Initial capital for the live trading
initial_capital = 10000.0
capital = initial_capital
position = None
entry_price = None
last_timestamp = None  # To track the last processed timestamp
last_trade_time = None  # To track the last trade time

def process_new_data(row, df):
    global position, entry_price, capital, last_timestamp, last_trade_time
    
    price = float(row['last_price'])
    vwap = float(row['vwap'])
    timestamp = row['timestamp']
    volume = float(row['volume'])

    # Convert timestamp to datetime object for time-based calculations
    current_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")

    # Skip if this timestamp has already been processed
    if last_timestamp is not None and timestamp <= last_timestamp:
        return

    # Update last processed timestamp
    last_timestamp = timestamp

    # Calculate time since last trade
    if last_trade_time is not None:
        time_since_last_trade = (current_time - last_trade_time).total_seconds()
    else:
        time_since_last_trade = float('inf')  # No previous trade, so ignore cooldown

    # Enforce cooldown period for all trades
    if time_since_last_trade <= cooldown_period:
        logging.info(f"Cooldown period active. Skipping trade. Time since last trade: {time_since_last_trade} seconds.")
        return

    # Check for sudden price drop
    if position is None:
        previous_price = df.iloc[-2]['last_price']  # Get the previous row's price
        price_drop = (price - previous_price) / previous_price
        
        if price_drop < sudden_drop_threshold:
            # Detected sudden drop, do not buy
            message = (
                f"⚠️ *Sudden Price Drop Detected!*\n"
                f"Price dropped by {price_drop:.2%} from ${previous_price:.5f} to ${price:.5f}.\n"
                f"_Skipping buy to avoid potential loss._"
            )
            logging.info(message)
            send_telegram_message(message)  # Send the alert to Telegram
            return

    # Check for oversold condition (Buy Signal)
    if (price - vwap) / vwap <= oversold_threshold and position is None:
        position = 'long'
        entry_price = price
        last_trade_time = current_time
        message = (
            f"⚠️ *Buy Signal Triggered*\n"
            f"Bought at: ${price:.5f} (VWAP: ${vwap:.5f})\n"
            f"Time: {timestamp}"
        )
        logging.info(message)
        send_telegram_message(message)

    # Check for overbought condition (Sell Signal) or take profit/stop loss
    if position == 'long':
        price_change = (price - entry_price) / entry_price

        if price_change >= take_profit_threshold or price_change <= stop_loss_threshold:
            profit_loss = capital * price_change
            capital += profit_loss
            last_trade_time = current_time
            message = (
                f"🚨 *Sell Signal Triggered*\n"
                f"Sold at: ${price:.5f} (VWAP: ${vwap:.5f})\n"
                f"Time: {timestamp}\n\n"
                f"*Trade Result:* ${profit_loss:.2f}\n"
                f"*Updated Capital:* ${capital:.2f}"
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
            process_new_data(row, df)
        
        time.sleep(60)  # Wait for 1 minute before checking for new data

if __name__ == "__main__":
    monitor_live_data('xrp_price_data.csv')
