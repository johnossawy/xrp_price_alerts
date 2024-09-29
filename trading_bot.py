#trading_bot.py
import logging
import json
import os
import psycopg2
from datetime import datetime
from logging.handlers import RotatingFileHandler
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

# Database connection details (adjust as needed)
DB_CONFIG = {
    'dbname': 'crypto_data',
    'user': 'your_db_user',
    'password': 'your_db_password',
    'host': 'your_db_host',
    'port': '5432'
}

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        return None

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

        self.load_state()

    def load_state(self):
        conn = get_db_connection()
        if not conn:
            return

        query = """
            SELECT capital, position, entry_price, trailing_stop_price, highest_price, last_timestamp, entry_time
            FROM bot_state
            ORDER BY id DESC
            LIMIT 1;
        """
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                row = cur.fetchone()
                if row:
                    self.capital = row[0]
                    self.position = row[1]
                    self.entry_price = row[2]
                    self.trailing_stop_price = row[3]
                    self.highest_price = row[4]
                    self.last_timestamp = row[5]
                    self.entry_time = row[6]
                    logger.info("Loaded state from the database.")
                else:
                    logger.info("No existing state found in the database. Initializing new state from trade_signals.")
                    self.initialize_state_from_signals()
        except Exception as e:
            logger.error(f"Failed to load state from the database: {e}")
        finally:
            conn.close()

    def initialize_state_from_signals(self):
        conn = get_db_connection()
        if not conn:
            return

        check_state_query = "SELECT COUNT(*) FROM bot_state;"
        try:
            with conn.cursor() as cur:
                cur.execute(check_state_query)
                count = cur.fetchone()[0]
                if count == 0:
                    logger.info("No state found, initializing from latest BUY signal in trade_signals.")
                    query = """
                        SELECT timestamp, price, updated_capital 
                        FROM trade_signals 
                        WHERE signal_type = 'BUY'
                        ORDER BY timestamp DESC 
                        LIMIT 1;
                    """
                    cur.execute(query)
                    row = cur.fetchone()
                    if row:
                        insert_query = """
                            INSERT INTO bot_state (capital, position, entry_price, trailing_stop_price, highest_price, last_timestamp, entry_time)
                            VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """
                        trailing_stop_price = row[1] * (1 - self.trailing_stop_loss_percentage)
                        cur.execute(insert_query, (
                            row[2], 'long', row[1], trailing_stop_price, row[1], row[0], row[0]
                        ))
                        conn.commit()
                        logger.info("State initialized from the latest BUY signal.")
        except Exception as e:
            logger.error(f"Error initializing state from trade_signals: {e}")
        finally:
            conn.close()

    def save_state(self):
        conn = get_db_connection()
        if not conn:
            return

        query = """
            INSERT INTO bot_state (capital, position, entry_price, trailing_stop_price, highest_price, last_timestamp, entry_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        try:
            with conn.cursor() as cur:
                cur.execute(query, (
                    self.capital, self.position, self.entry_price,
                    self.trailing_stop_price, self.highest_price,
                    self.last_timestamp, self.entry_time
                ))
                conn.commit()
                logger.info("State saved to the database.")
        except Exception as e:
            logger.error(f"Failed to save state to the database: {e}")
        finally:
            conn.close()

    def get_latest_price_data(self):
        conn = get_db_connection()
        if not conn:
            return None

        query = """
            SELECT timestamp, last_price, vwap
            FROM crypto_prices
            WHERE symbol = 'XRP'
            ORDER BY timestamp DESC
            LIMIT 1;
        """
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                row = cur.fetchone()
                if row:
                    return {
                        'timestamp': row[0],
                        'last_price': row[1],
                        'vwap': row[2]
                    }
                else:
                    logger.warning("No XRP data found in database.")
                    return None
        except Exception as e:
            logger.error(f"Error fetching price data from DB: {e}")
            return None
        finally:
            conn.close()

    def process_new_data(self):
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
