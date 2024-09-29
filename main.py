# main.py
import time
import logging
from trading_bot import TradingBot
from filelock import FileLock
from logging.handlers import RotatingFileHandler

# Set up logging with rotating handler
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('live_trading_signals.log', maxBytes=5*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def monitor_live_data(bot):
    """
    Monitors live data by periodically calling the bot to process new data from the database.
    """
    while True:
        try:
            bot.process_new_data()  # Bot now fetches the latest data directly from the DB
        except Exception as e:
            logger.error(f"An error occurred while processing live data: {e}")
        time.sleep(60)  # Sleep for 60 seconds before checking again

if __name__ == "__main__":
    lock = FileLock("trading_bot.lock")
    with lock:
        bot = TradingBot()
        monitor_live_data(bot)
