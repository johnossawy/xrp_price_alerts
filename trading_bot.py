#trading_bot.py

import logging
from datetime import datetime, timezone, timedelta
from logging.handlers import RotatingFileHandler
from database_handler import DatabaseHandler
from telegram_bot import send_telegram_message
from decimal import Decimal
import hashlib
import hmac
import time
import requests
import uuid
import os

# Set up logging with rotating handler
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Remove any default handlers if already added to avoid duplicate logs
if not logger.handlers:
    handler = RotatingFileHandler('live_trading_signals.log', maxBytes=5*1024*1024, backupCount=5)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Load API key and secret from environment variables
BITSTAMP_MAIN_KEY = os.getenv("BITSTAMP_MAIN_KEY")
BITSTAMP_MAIN_SECRET = os.getenv("BITSTAMP_MAIN_SECRET")
if BITSTAMP_MAIN_SECRET:
    BITSTAMP_MAIN_SECRET = BITSTAMP_MAIN_SECRET.encode('utf-8')

# Check if API key and secret are set
if not BITSTAMP_MAIN_KEY or not BITSTAMP_MAIN_SECRET:
    logger.error("API key or secret is missing. Please set BITSTAMP_MAIN_KEY and BITSTAMP_MAIN_SECRET.")
    raise ValueError("Missing Bitstamp API key or secret.")

class TradingBot:
    def __init__(self):
        # Remove the initial_capital argument and assignment
        self.capital = None
        self.position = None
        self.entry_price = None
        self.trailing_stop_price = None
        self.highest_price = None
        self.last_timestamp = None
        self.entry_time = None
        self.last_loss_time = None  # Track the time of the last loss

        # Define thresholds
        self.overbought_threshold = 0.01
        self.oversold_threshold = -0.019
        self.stop_loss_threshold = -0.02
        self.take_profit_threshold = 0.015
        self.trailing_stop_loss_percentage = 0.005

        # Initialize DatabaseHandler
        self.db_handler = DatabaseHandler()
        self.load_state()

    def load_state(self):
        """
        Loads the last processed state from the database.
        """
        query = """
            SELECT capital, position, entry_price, trailing_stop_price, highest_price, last_timestamp, entry_time
            FROM bot_state
            ORDER BY id DESC
            LIMIT 1;
        """
        row = self.db_handler.fetch_one(query)
        if row:
            self.capital = float(row['capital'])  # Ensure values are converted to float
            self.position = row['position']
            self.entry_price = float(row['entry_price']) if row['entry_price'] else None
            self.trailing_stop_price = float(row['trailing_stop_price']) if row['trailing_stop_price'] else None
            self.highest_price = float(row['highest_price']) if row['highest_price'] else None
            self.last_timestamp = row['last_timestamp']
            self.entry_time = row['entry_time']
            logger.info("Loaded state from the database.")
        else:
            logger.info("No existing state found in the database. Initializing new state from trade_signals.")
            self.initialize_state_from_signals()

    def get_latest_price_data(self):
        """
        Fetches the latest price data for XRP from the PostgreSQL database.
        """
        query = """
            SELECT timestamp, last_price, vwap
            FROM crypto_prices
            WHERE symbol = 'XRP'
            ORDER BY timestamp DESC
            LIMIT 1;
        """
        row = self.db_handler.fetch_one(query)
        if row:
            return {
                'timestamp': row['timestamp'],
                'last_price': float(row['last_price']),  # Convert Decimal to float
                'vwap': float(row['vwap'])  # Convert Decimal to float
            }
        else:
            logger.warning("No XRP data found in the database.")
            return None

    def get_trading_fees(self, market_symbol: str) -> dict:
        """
        Fetch trading fees for the specified market.
        """
        try:
            timestamp = str(int(round(time.time() * 1000)))
            nonce = str(uuid.uuid4())

            message = 'BITSTAMP ' + BITSTAMP_MAIN_KEY + \
                      'POST' + \
                      'www.bitstamp.net' + \
                      f'/api/v2/fees/trading/{market_symbol}/' + \
                      '' + \
                      '' + \
                      nonce + \
                      timestamp + \
                      'v2' + \
                      ''  # No payload in this case

            message = message.encode('utf-8')
            signature = hmac.new(BITSTAMP_MAIN_SECRET, msg=message, digestmod=hashlib.sha256).hexdigest()

            # Set up headers
            headers = {
                'X-Auth': 'BITSTAMP ' + BITSTAMP_MAIN_KEY,
                'X-Auth-Signature': signature,
                'X-Auth-Nonce': nonce,
                'X-Auth-Timestamp': timestamp,
                'X-Auth-Version': 'v2'
            }

            # Make the POST request to the trading fees endpoint
            url = f'https://www.bitstamp.net/api/v2/fees/trading/{market_symbol}/'
            response = requests.post(url, headers=headers)

            if response.status_code == 200:
                return response.json()
            else:
                return {'error': response.text}

        except Exception as e:
            return {'error': str(e)}

    def calculate_trade_fees(self, price: float, amount: float, fee_percentage: float) -> float:
        """
        Calculate the fee for a trade based on price, amount, and fee percentage.
        """
        trade_value = price * amount  # Total trade value in USD
        fee = trade_value * (fee_percentage / 100)  # Fee as a percentage of trade value
        return fee

    def process_new_data(self):
        """
        Processes the latest price data and manages buy/sell signals based on trading logic.
        """
        price_data = self.get_latest_price_data()
        if not price_data:
            return

        try:
            price = price_data['last_price']
            vwap = price_data['vwap']
            timestamp = price_data['timestamp']

            if self.last_timestamp and timestamp <= self.last_timestamp:
                return

            self.last_timestamp = timestamp

            now = datetime.now(timezone.utc)

            # Fetch trading fees
            fees = self.get_trading_fees("xrpusd")
            if 'error' in fees:
                logger.error(f"Error fetching fees: {fees['error']}")
                return
            fee_percentage = float(fees['fees'].get('maker', '0').strip('%'))
            if fee_percentage == 0:
                logger.warning("Defaulting to 0% trading fee as no valid fee was returned.")


            # Buy signal logic with delay if previous trade resulted in a loss
            if (price - vwap) / vwap <= self.oversold_threshold and self.position is None:
                if self.last_loss_time is None or (now - self.last_loss_time) >= timedelta(minutes=30):
                    self.position = 'long'
                    self.entry_price = price
                    self.highest_price = price
                    self.trailing_stop_price = self.entry_price * (1 - self.trailing_stop_loss_percentage)
                    self.entry_time = timestamp

                    # Calculate trading fee for buy
                    amount_traded = self.capital / price
                    buy_fee = self.calculate_trade_fees(price, amount_traded, fee_percentage)
                    self.capital -= buy_fee  # Deduct buy fee from capital

                    formatted_entry_time = self.entry_time.strftime('%Y-%m-%d %H:%M:%S')

                    message = (
                        f"⚠️ *Buy Signal Triggered*\n\n"
                        f"📅 *Date/Time:* {formatted_entry_time}\n"
                        f"💰 *Bought at:* ${price:.5f}\n"
                        f"💸 *Trading Fee Applied:* ${buy_fee:.2f}\n"
                        f"💡 Stay tuned for the next update!\n"
                        f"#Ripple #XRP"
                    )
                    logger.info(message)

                    # Save the BUY signal to the database
                    self.save_trade_signal('BUY', price, profit_loss=None, percent_change=None, time_held=None)

                    send_telegram_message(message)
                    self.save_state()
                else:
                    logger.info("Buy signal delayed due to recent trade loss.")
            # Sell signal logic
            if self.position == 'long':
                if price > self.highest_price:
                    self.highest_price = price
                    self.trailing_stop_price = self.highest_price * (1 - self.trailing_stop_loss_percentage)
                    logger.info(f"🔄 Trailing Stop Updated: New Stop Price is ${self.trailing_stop_price:.5f} (Highest Price: ${self.highest_price:.5f})")
                    self.save_state()

                if price <= self.trailing_stop_price or price >= self.entry_price * (1 + self.take_profit_threshold) or price <= self.entry_price * (1 + self.stop_loss_threshold):
                    price_change = (price - self.entry_price) / self.entry_price
                    profit_loss = self.capital * price_change
                    
                    # Calculate trading fee for sell
                    amount_traded = self.capital / self.entry_price
                    sell_fee = self.calculate_trade_fees(price, amount_traded, fee_percentage)
                    profit_loss -= sell_fee  # Deduct sell fee from profit/loss
                    self.capital += (profit_loss - sell_fee)

                    time_held = now - self.entry_time

                    # Format time held as hours, minutes, and seconds
                    hours, remainder = divmod(time_held.total_seconds(), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_held_formatted = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

                    # Format the sell execution time to YYYY-MM-DD HH:MM:SS
                    formatted_sell_time = now.strftime('%Y-%m-%d %H:%M:%S')

                    # Determine if it is a profit or loss and adjust the message accordingly
                    if profit_loss >= 0:
                        result_message = f"💰 Profit: ${profit_loss:.2f}"
                        self.last_loss_time = None  # Reset the loss time if profit
                    else:
                        result_message = f"🔻 Loss: ${abs(profit_loss):.2f}"
                        self.last_loss_time = now  # Set the last loss time if loss

                    message = (
                        f"🚨 *Sell Signal Triggered*\n\n"
                        f"📅 *Date/Time:* {formatted_sell_time}\n"
                        f"💸 *Sold at:* ${price:.5f}\n"
                        f"💸 *Trading Fee Applied:* ${sell_fee:.2f}\n"
                        f"{result_message}\n"
                        f"⏳ *Time Held:* {time_held_formatted}\n"
                        f"💼 *Updated Capital:* ${self.capital:.2f}\n"
                    )

                    logger.info(message)
                    send_telegram_message(message)

                    # Save the SELL signal to the database
                    self.save_trade_signal('SELL', price, profit_loss, price_change, time_held_formatted)

                    self.position = None
                    self.entry_price = None
                    self.trailing_stop_price = None
                    self.highest_price = None
                    self.entry_time = None

                    self.save_state()

        except Exception as e:
            logger.error(f"An error occurred while processing data: {e}")

    def save_state(self):
        """
        Saves the current state to the database.
        """
        query = """
            INSERT INTO bot_state (capital, position, entry_price, trailing_stop_price, highest_price, last_timestamp, entry_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        params = (
            self.capital, self.position, self.entry_price,
            self.trailing_stop_price, self.highest_price,
            self.last_timestamp, self.entry_time
        )
        self.db_handler.execute(query, params)
        logger.info("State saved to the database.")

    def save_trade_signal(self, signal_type, price, profit_loss, percent_change, time_held):
        """
        Inserts a trade signal into the trade_signals table in the database.
        """
        query = """
            INSERT INTO trade_signals (timestamp, signal_type, price, profit_loss, percent_change, time_held, updated_capital)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        params = (
            datetime.now(), signal_type, price, profit_loss, percent_change, time_held, self.capital
        )
        self.db_handler.execute(query, params)
        logger.info(f"Trade signal ({signal_type}) saved to DB.")
