# trading_bot.py
import logging
from datetime import datetime
import json
import os
import pandas as pd
import logging
from logging.handlers import RotatingFileHandler
from telegram_bot import send_telegram_message

# Set up logging with rotating handler
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('live_trading_signals.log', maxBytes=5*1024*1024, backupCount=5)

# Updated formatter without milliseconds
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'  # Specifies the date format without milliseconds
)

handler.setFormatter(formatter)
logger.addHandler(handler)

class TradingBot:
    def __init__(self, initial_capital=12800.0, state_file='state.json'):
        """
        Initializes the TradingBot with default parameters and loads the existing state.

        Args:
            initial_capital (float): The starting capital for trading.
            state_file (str): The filename where the state is persisted.
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = None
        self.entry_price = None
        self.trailing_stop_price = None
        self.highest_price = None
        self.last_timestamp = None
        self.entry_time = None
        self.state_file = state_file

        # Define thresholds
        self.overbought_threshold = 0.01    # 1% above VWAP
        self.oversold_threshold = -0.019     # 1.9% below VWAP
        self.stop_loss_threshold = -0.02      # 2% stop loss
        self.take_profit_threshold = 0.015    # 1.5% take profit
        self.trailing_stop_loss_percentage = 0.005  # 0.5% trailing stop

        self.load_state()

    def load_state(self, csv_file='xrp_price_data.csv'):
        """
        Loads the last processed state from the state file. If the state file doesn't exist,
        initializes the last_timestamp to the latest timestamp in the CSV to prevent backlogged signals.

        Args:
            csv_file (str): The CSV file to read the latest timestamp from if state file is absent.
        """
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.capital = state.get('capital', self.initial_capital)
                    self.position = state.get('position')
                    self.entry_price = state.get('entry_price')
                    self.trailing_stop_price = state.get('trailing_stop_price')
                    self.highest_price = state.get('highest_price')
                    self.last_timestamp = state.get('last_timestamp')
                    entry_time_str = state.get('entry_time')
                    self.entry_time = datetime.strptime(entry_time_str, '%Y-%m-%d %H:%M:%S') if entry_time_str else None
                logger.info(f"Loaded state from {self.state_file}.")
            except Exception as e:
                logger.error(f"Failed to load state from {self.state_file}: {e}")
                # Initialize with the latest timestamp to prevent reprocessing
                self.initialize_last_timestamp(csv_file)
        else:
            logger.info(f"No existing state file found. Initializing with latest CSV timestamp.")
            self.initialize_last_timestamp(csv_file)

    def initialize_last_timestamp(self, csv_file):
        """
        Initializes the last_timestamp to the latest timestamp in the CSV file to prevent processing old data.

        Args:
            csv_file (str): The CSV file to read the latest timestamp from.
        """
        try:
            df = pd.read_csv(csv_file)
            if not df.empty:
                latest_timestamp = df['timestamp'].max()
                self.last_timestamp = latest_timestamp
                self.save_state()
                logger.info(f"Initialized last_timestamp to latest CSV timestamp: {latest_timestamp}")
            else:
                logger.warning("CSV file is empty. Starting with no last_timestamp.")
        except Exception as e:
            logger.error(f"Failed to initialize last_timestamp from {csv_file}: {e}")

    def save_state(self):
        """
        Saves the current state to the state file in JSON format.
        """
        state = {
            'capital': self.capital,
            'position': self.position,
            'entry_price': self.entry_price,
            'trailing_stop_price': self.trailing_stop_price,
            'highest_price': self.highest_price,
            'last_timestamp': self.last_timestamp,
            'entry_time': self.entry_time.strftime('%Y-%m-%d %H:%M:%S') if self.entry_time else None
        }
        try:
            temp_file = self.state_file + '.tmp'
            with open(temp_file, 'w') as f:
                json.dump(state, f)
            os.replace(temp_file, self.state_file)  # Atomic operation
            logger.info(f"State saved to {self.state_file}.")
        except Exception as e:
            logger.error(f"Failed to save state to {self.state_file}: {e}")

    def process_new_data(self, row):
        """
        Processes a single row of data from the CSV. Determines if a buy or sell signal should be triggered.

        Args:
            row (pandas.Series): A row of data from the CSV containing 'last_price', 'vwap', and 'timestamp'.
        """
        try:
            price = float(row['last_price'])
            vwap = float(row['vwap'])
            timestamp = row['timestamp']

            # Skip if this timestamp has already been processed
            if self.last_timestamp and timestamp <= self.last_timestamp:
                return

            # Update last processed timestamp
            self.last_timestamp = timestamp

            # Parse and format timestamp
            timestamp_dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            formatted_timestamp = timestamp_dt.strftime('%B %d, %Y at %I:%M %p')

            # Check for oversold condition (Buy Signal)
            if (price - vwap) / vwap <= self.oversold_threshold and self.position is None:
                self.position = 'long'
                self.entry_price = price
                self.highest_price = price
                self.trailing_stop_price = self.entry_price * (1 - self.trailing_stop_loss_percentage)
                self.entry_time = timestamp_dt

                message = (
                    f"⚠️ *Buy Signal Triggered*\n"
                    f"Bought at: ${price:.5f} on {formatted_timestamp}"
                )
                logger.info(message)
                send_telegram_message(message)
                self.save_state()  # Save state after processing

            # Manage existing position
            if self.position == 'long':
                # Update the highest price since the entry
                if price > self.highest_price:
                    self.highest_price = price
                    self.trailing_stop_price = self.highest_price * (1 - self.trailing_stop_loss_percentage)
                    logger.info(
                        f"🔄 Trailing Stop Updated: New Stop Price is ${self.trailing_stop_price:.5f} "
                        f"(Highest Price: ${self.highest_price:.5f})"
                    )
                    self.save_state()  # Save state after updating trailing stop

                # Check exit conditions
                exit_condition = (
                    price <= self.trailing_stop_price or
                    price >= self.entry_price * (1 + self.take_profit_threshold) or
                    price <= self.entry_price * (1 + self.stop_loss_threshold)
                )

                if exit_condition:
                    price_change = (price - self.entry_price) / self.entry_price
                    profit_loss = self.capital * price_change
                    self.capital += profit_loss
                    exit_time = timestamp_dt
                    time_held = exit_time - self.entry_time

                    # Format time held
                    hours, remainder = divmod(time_held.total_seconds(), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_held_formatted = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

                    message = (
                        f"🚨 *Sell Signal Triggered:*\n"
                        f"Sold at ${price:.5f} on {formatted_timestamp}\n"
                        f"Profit/Loss = ${profit_loss:.2f}, Time Held = {time_held_formatted}\n"
                        f"Updated Capital: ${self.capital:.2f}"
                    )
                    logger.info(message)
                    send_telegram_message(message)

                    # Reset position-related variables
                    self.position = None
                    self.entry_price = None
                    self.trailing_stop_price = None
                    self.highest_price = None
                    self.entry_time = None

                    self.save_state()  # Save state after processing

        except Exception as e:
            logger.error(f"An error occurred while processing data: {e}")
