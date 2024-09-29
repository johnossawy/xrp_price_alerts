import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from database_handler import DatabaseHandler  # Import your DatabaseHandler
from telegram_bot import send_telegram_message

# Set up logging with rotating handler
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('live_trading_signals.log', maxBytes=5*1024*1024, backupCount=5)

formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
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
            self.capital = row['capital']
            self.position = row['position']
            self.entry_price = row['entry_price']
            self.trailing_stop_price = row['trailing_stop_price']
            self.highest_price = row['highest_price']
            self.last_timestamp = row['last_timestamp']
            self.entry_time = row['entry_time']
            logger.info("Loaded state from the database.")
        else:
            logger.info("No existing state found in the database. Initializing new state from trade_signals.")
            self.initialize_state_from_signals()

    def initialize_state_from_signals(self):
        """
        Initializes the state based on the latest BUY signal from the trade_signals table.
        """
        check_state_query = "SELECT COUNT(*) FROM bot_state;"
        count = self.db_handler.fetch_one(check_state_query)['count']

        if count == 0:
            logger.info("No state found, initializing from the latest BUY signal in trade_signals.")
            query = """
                SELECT timestamp, price, updated_capital 
                FROM trade_signals 
                WHERE signal_type = 'BUY'
                ORDER BY timestamp DESC 
                LIMIT 1;
            """
            row = self.db_handler.fetch_one(query)
            if row:
                insert_query = """
                    INSERT INTO bot_state (capital, position, entry_price, trailing_stop_price, highest_price, last_timestamp, entry_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """
                trailing_stop_price = row['price'] * (1 - self.trailing_stop_loss_percentage)
                params = (
                    row['updated_capital'], 'long', row['price'],
                    trailing_stop_price, row['price'], row['timestamp'], row['timestamp']
                )
                self.db_handler.execute(insert_query, params)
                logger.info("State initialized from the latest BUY signal.")

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
        return self.db_handler.fetch_one(query)

    def process_new_data(self):
        """
        Processes the latest price data and manages buy/sell signals based on trading logic.
        """
        price_data = self.get_latest_price_data()
        if not price_data:
            return

        try:
            price = float(price_data['last_price'])
            vwap = float(price_data['vwap'])
            timestamp = price_data['timestamp']

            if self.last_timestamp and timestamp <= self.last_timestamp:
                return

            self.last_timestamp = timestamp

            if (price - vwap) / vwap <= self.oversold_threshold and self.position is None:
                self.position = 'long'
                self.entry_price = price
                self.highest_price = price
                self.trailing_stop_price = self.entry_price * (1 - self.trailing_stop_loss_percentage)
                self.entry_time = timestamp

                message = f"⚠️ *Buy Signal Triggered*\nBought at: ${price:.5f} on {timestamp}"
                logger.info(message)
                send_telegram_message(message)
                self.save_state()

            if self.position == 'long':
                if price > self.highest_price:
                    self.highest_price = price
                    self.trailing_stop_price = self.highest_price * (1 - self.trailing_stop_loss_percentage)
                    logger.info(f"🔄 Trailing Stop Updated: New Stop Price is ${self.trailing_stop_price:.5f} (Highest Price: ${self.highest_price:.5f})")
                    self.save_state()

                if price <= self.trailing_stop_price or price >= self.entry_price * (1 + self.take_profit_threshold) or price <= self.entry_price * (1 + self.stop_loss_threshold):
                    price_change = (price - self.entry_price) / self.entry_price
                    profit_loss = self.capital * price_change
                    self.capital += profit_loss

                    time_held = datetime.now() - self.entry_time
                    message = f"🚨 *Sell Signal Triggered*\nSold at ${price:.5f}\nProfit/Loss: ${profit_loss:.2f}\nUpdated Capital: ${self.capital:.2f}"
                    logger.info(message)
                    send_telegram_message(message)

                    self.save_trade_signal('SELL', price, profit_loss, price_change, time_held)

                    self.position = None
                    self.entry_price = None
                    self.trailing_stop_price = None
                    self.highest_price = None
                    self.entry_time = None

                    self.save_state()

        except Exception as e:
            logger.error(f"An error occurred while processing data: {e}")

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
