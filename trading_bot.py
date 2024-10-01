import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from database_handler import DatabaseHandler
from telegram_bot import send_telegram_message
from decimal import Decimal

# Set up logging with rotating handler
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Remove any default handlers if already added to avoid duplicate logs
if not logger.handlers:
    handler = RotatingFileHandler('live_trading_signals.log', maxBytes=5*1024*1024, backupCount=5)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class TradingBot:
    def __init__(self, initial_capital=12800.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = None
        self.entry_price = None
        self.trailing_stop_price = None
        self.highest_price = None
        self.last_timestamp = None
        self.entry_time = None

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

            # Buy signal logic
            if (price - vwap) / vwap <= self.oversold_threshold and self.position is None:
                self.position = 'long'
                self.entry_price = price
                self.highest_price = price
                self.trailing_stop_price = self.entry_price * (1 - self.trailing_stop_loss_percentage)
                self.entry_time = timestamp

                # Format timestamp to YYYY-MM-DD HH:MM:SS
                formatted_entry_time = self.entry_time.strftime('%Y-%m-%d %H:%M:%S')

                # Improved buy signal message formatting
                message = (
                    f"⚠️ *Buy Signal Triggered*\n\n"
                    f"📅 *Date/Time:* {formatted_entry_time}\n"
                    f"💰 *Bought at:* ${price:.5f}\n"
                    f"💡 Stay tuned for the next update!\n"
                    f"#Ripple #XRP"
                )
                logger.info(message)

                # Save the BUY signal to the database
                self.save_trade_signal('BUY', price, profit_loss=None, percent_change=None, time_held=None)

                send_telegram_message(message)
                self.save_state()

            # Sell signal logic
            if self.position == 'long':
                if price > self.highest_price:
                    self.highest_price = price
                    self.trailing_stop_price = self.highest_price * (1 - self.trailing_stop_loss_percentage)
                    logger.info(f"🔄 Trailing Stop Updated: New Stop Price is ${self.trailing_stop_price:.5f} (Highest Price: ${self.highest_price:.5f})")
                    self.save_state()

                now = datetime.now(timezone.utc)

                if price <= self.trailing_stop_price or price >= self.entry_price * (1 + self.take_profit_threshold) or price <= self.entry_price * (1 + self.stop_loss_threshold):
                    price_change = (price - self.entry_price) / self.entry_price
                    profit_loss = self.capital * price_change
                    self.capital += profit_loss

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
                    else:
                        result_message = f"🔻 Loss: ${abs(profit_loss):.2f}"

                    message = (
                        f"🚨 *Sell Signal Triggered*\n\n"
                        f"📅 *Date/Time:* {formatted_sell_time}\n"
                        f"💸 *Sold at:* ${price:.5f}\n"
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
