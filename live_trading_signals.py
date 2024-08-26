import pandas as pd
import logging
import time

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

def process_new_data(df):
    global position, entry_price, capital, last_timestamp
    
    for index, row in df.iterrows():
        price = row['last_price']
        vwap = row['vwap']
        timestamp = row['timestamp']

        # Skip if this timestamp has already been processed
        if last_timestamp is not None and timestamp <= last_timestamp:
            continue

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
                logging.info(f"   Trade Result: Profit/Loss = ${profit_loss:.2f}")
                logging.info(f"   Updated Capital: ${capital:.2f}")

                position = None
                entry_price = None

# Main loop to process the live data
def monitor_live_data(csv_file):
    global last_timestamp

    while True:
        try:
            df = pd.read_csv(csv_file)

            # If the timestamp is already in datetime format, no need to convert
            # Filter data to process only new rows
            if last_timestamp:
                df = df[df['timestamp'] > last_timestamp]

            if not df.empty:
                process_new_data(df)
        
        except Exception as e:
            logging.error(f"Error processing data: {e}")

        time.sleep(60)  # Wait for 1 minute before checking for new data

if __name__ == "__main__":
    monitor_live_data('xrp_price_data.csv')
