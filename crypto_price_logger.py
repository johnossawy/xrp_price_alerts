# crypto_price_logger.py

import logging
from logging.handlers import RotatingFileHandler  # Correct import
import time
from datetime import datetime, timezone
import random

import requests

from database_handler import DatabaseHandler  # Import your updated DatabaseHandler

# Configure logging with RotatingFileHandler
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Disable propagation to avoid root logger handling stdout
logger.propagate = False

# Remove any default handlers from the root logger to prevent logging to console
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Avoid adding multiple handlers if the logger already has handlers
if not logger.handlers:
    handler = RotatingFileHandler(
        'crypto_price_logger.log', maxBytes=5*1024*1024, backupCount=5
    )
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# URLs for Bitstamp API
CRYPTO_URLS = {
    'BTC': "https://www.bitstamp.net/api/v2/ticker/btcusd/",
    'ETH': "https://www.bitstamp.net/api/v2/ticker/ethusd/",
}

# Retry configuration
MAX_RETRIES = 5
BASE_SLEEP_TIME = 2  # in seconds

# Field names corresponding to the database schema
FIELDNAMES = [
    'timestamp', 'symbol', 'last_price', 'high_price', 'low_price', 'vwap', 'volume',
    'bid', 'ask', 'open_price', 'percent_change_24h', 'percent_change'
]


def calculate_percent_change(previous_price, current_price):
    """Calculate the percentage change between two prices."""
    if previous_price != 0 and previous_price is not None:
        return ((current_price - previous_price) / previous_price) * 100
    else:
        return None


def fetch_price(url):
    """Fetch price data from the given Bitstamp API URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data from {url}: {e}")
        return None


def get_last_price(db_handler, symbol):
    """
    Retrieve the last recorded price for the given symbol from the database.

    Args:
        db_handler (DatabaseHandler): The database handler instance.
        symbol (str): The cryptocurrency symbol (e.g., 'BTC', 'ETH').

    Returns:
        float or None: The last recorded price or None if not found.
    """
    try:
        query = """
            SELECT last_price FROM crypto_prices
            WHERE symbol = %(symbol)s
            ORDER BY timestamp DESC
            LIMIT 1;
        """
        params = {'symbol': symbol}
        result = db_handler.fetch_one(query, params)
        if result and result.get('last_price') is not None:
            return float(result['last_price'])
        else:
            logger.warning(f"No previous price found in DB for {symbol}.")
            return None
    except Exception as e:
        logger.error(f"Error retrieving last price for {symbol}: {e}")
        return None


def save_price_to_db(db_handler, symbol, price_data):
    """
    Save the fetched price data to the database.

    Args:
        db_handler (DatabaseHandler): The database handler instance.
        symbol (str): The cryptocurrency symbol (e.g., 'BTC', 'ETH').
        price_data (dict): The price data fetched from the API.

    Returns:
        bool: True if the data was saved successfully, False otherwise.
    """
    try:
        insert_query = """
            INSERT INTO crypto_prices (
                timestamp, symbol, last_price, high_price, low_price, vwap, volume,
                bid, ask, open_price, percent_change_24h, percent_change
            ) VALUES (
                %(timestamp)s, %(symbol)s, %(last_price)s, %(high_price)s, %(low_price)s, %(vwap)s, %(volume)s,
                %(bid)s, %(ask)s, %(open_price)s, %(percent_change_24h)s, %(percent_change)s
            );
        """
        params = {
            'timestamp': datetime.now(timezone.utc),
            'symbol': symbol,
            'last_price': float(price_data.get('last', 0)),
            'high_price': float(price_data.get('high', 0)),
            'low_price': float(price_data.get('low', 0)),
            'vwap': float(price_data.get('vwap', 0)),
            'volume': float(price_data.get('volume', 0)),
            'bid': float(price_data.get('bid', 0)),
            'ask': float(price_data.get('ask', 0)),
            'open_price': float(price_data.get('open', 0)),
            'percent_change_24h': float(price_data.get('percent_change', 0)) if price_data.get('percent_change') else None,
            'percent_change': price_data.get('percent_change_calculated'),
        }
        success = db_handler.execute(insert_query, params)
        if success:
            logger.info(f"Saved {symbol}/USD data to DB.")
            return True
        else:
            logger.error(f"Failed to save {symbol}/USD data to DB.")
            return False
    except Exception as e:
        logger.error(f"Error saving {symbol}/USD data to DB: {e}")
        return False


def log_crypto_prices():
    """Main function to log cryptocurrency prices continuously."""
    db_handler = DatabaseHandler()

    retry_count = 0

    while True:
        try:
            current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"Starting price logging cycle at {current_time}")

            for symbol, url in CRYPTO_URLS.items():
                logger.info(f"Fetching price data for {symbol}/USD from {url}")
                price_data = fetch_price(url)

                if price_data:
                    # Retrieve the last price from the database
                    last_price = get_last_price(db_handler, symbol)

                    # Current price
                    try:
                        current_price = float(price_data['last'])
                    except (ValueError, TypeError) as e:
                        logger.error(f"Invalid 'last' price for {symbol}: {e}")
                        continue

                    # Calculate percent change
                    percent_change = calculate_percent_change(last_price, current_price)

                    # Add the calculated percent change to the price_data
                    price_data['percent_change_calculated'] = percent_change

                    # Prepare data for saving
                    save_success = save_price_to_db(db_handler, symbol, price_data)

                    if save_success and percent_change is not None:
                        logger.info(
                            f"{symbol}/USD: Current Price=${current_price:.2f}, "
                            f"Change={'+' if percent_change >=0 else ''}{percent_change:.2f}%"
                        )
                    elif save_success:
                        logger.info(
                            f"{symbol}/USD: Current Price=${current_price:.2f}, Change=N/A"
                        )

            # Reset retry count after successful fetch and save
            retry_count = 0

        except Exception as e:
            retry_count += 1
            sleep_time = BASE_SLEEP_TIME * (2 ** retry_count) + random.uniform(0, 1)
            logger.error(
                f"An error occurred during the logging cycle: {type(e).__name__} - {e}. "
                f"Retrying in {sleep_time:.2f} seconds... (Attempt {retry_count}/{MAX_RETRIES})"
            )

            if retry_count >= MAX_RETRIES:
                logger.error("Max retries reached. Skipping this cycle and waiting for the next one.")
                retry_count = 0

            time.sleep(sleep_time)
            continue

        # Wait for a minute before the next logging cycle
        time.sleep(60)


if __name__ == "__main__":
    log_crypto_prices()
