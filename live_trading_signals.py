import csv
import logging
import time
from datetime import datetime

# Configure logging for trade signals
logging.basicConfig(filename='live_trading_signals.log', level=logging.INFO, 
                    format='%(asctime)s - %(message)s')

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
        logging.info(f"⚠️ Buy Signal Triggered: Bought at ${price:.5f} (VWAP: ${vwap:.5f}) on {timestamp}")

    # Check for overbought condition (Sell Signal) or take profit/stop loss
    if position == 'long':
        price_change = (price - entry_price) / entry_price

        if price_change >= take_profit_threshold or price_change <= stop_loss_threshold:
            profit_loss = capital * price_change
            capital += profit_loss
            logging.info(f"🚨 Sell Signal Triggered: Sold at ${price:.5f} (VWAP: ${vwap:.5f}) on {timestamp}")
            logging.info(f"   Trade Result: Profit/Loss = ${profit_loss:.2f}, Time Held = {timestamp}")
            logging.info(f"   Updated Capital: ${capital:.2f}")

            position = None
            entry_price = None

# Main loop to process the live data
def monitor_live_data(csv_file):
    global last_timestamp

    while True:
        with open(csv_file, 'r') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            
            for row in csv_reader:
                process_new_data(row)
        
        time.sleep(60)  # Wait for 1 minutes before checking for new data

if __name__ == "__main__":
    monitor_live_data('xrp_price_data.csv')
