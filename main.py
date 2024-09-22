import time
import pandas as pd
import logging
from trading_bot import TradingBot
from filelock import FileLock

# Set up logging with rotating handler
from logging.handlers import RotatingFileHandler

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('live_trading_signals.log', maxBytes=5*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def monitor_live_data(csv_file, bot):
    while True:
        try:
            df = pd.read_csv(csv_file)
            # Only process new rows based on last_timestamp
            if bot.last_timestamp:
                new_df = df[df['timestamp'] > bot.last_timestamp]
            else:
                new_df = df

            for _, row in new_df.iterrows():
                bot.process_new_data(row)
        except FileNotFoundError:
            logger.error(f"File {csv_file} not found.")
        except pd.errors.EmptyDataError:
            logger.warning(f"File {csv_file} is empty.")
        except Exception as e:
            logger.error(f"An error occurred while reading the file: {e}")
        time.sleep(60)

if __name__ == "__main__":
    lock = FileLock("trading_bot.lock")
    with lock:
        bot = TradingBot()
        monitor_live_data('xrp_price_data.csv', bot)
