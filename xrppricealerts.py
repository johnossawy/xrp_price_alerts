# xrppricealerts.py

import csv
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler

# Configure logging with RotatingFileHandler
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Avoid adding multiple handlers if the logger already has handlers
if not logger.handlers:
    handler = RotatingFileHandler('xrp_bot.log', maxBytes=5*1024*1024, backupCount=5)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

from app.fetcher import fetch_xrp_price
from app.twitter import (
    get_twitter_api,
    get_twitter_client,
    post_tweet,
    upload_media,
)
from app.xrp_messaging import (
    generate_3_hour_summary,
    generate_daily_summary_message,
    generate_message,
    get_percent_change,
)
from config import (
    ACCESS_TOKEN,
    ACCESS_TOKEN_SECRET,
    CONSUMER_KEY,
    CONSUMER_SECRET,
    RAPIDAPI_KEY,
)

class XRPPriceAlertBot:
    """Class to handle XRP price alerts and Twitter interactions."""

    def __init__(self):
        # Define the volatility threshold
        self.VOLATILITY_THRESHOLD = 0.02
        self.SUMMARY_TIMES = {
            (0, 0),
            (3, 0),
            (6, 0),
            (9, 0),
            (12, 0),
            (15, 0),
            (18, 0),
            (21, 0),
        }  # Hours to post 3-hour summary tweets

        # Define the CSV file and JSON files for data storage
        self.CSV_FILE = 'xrp_price_data.csv'
        self.LAST_SUMMARY_FILE = 'last_summary_time.json'
        self.LAST_PRICE_FILE = 'last_rounded_price.json'

        # Initialize tracking variables
        self.daily_high = None
        self.daily_low = None
        self.current_day = datetime.now(timezone.utc).date()
        self.last_volatility_check_time = None
        self.last_rounded_price = self.load_last_rounded_price()
        self.last_summary_time = self.load_last_summary_time()
        self.last_daily_summary_time = None
        self.last_full_price = None
        self.last_tweet_hour = None
        self.last_checked_price = None

        # Initialize Twitter clients
        self.client = get_twitter_client(
            CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET
        )
        self.api = get_twitter_api(
            CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET
        )

    def load_last_rounded_price(self):
        """Load the last rounded price from a JSON file."""
        if os.path.exists(self.LAST_PRICE_FILE):
            try:
                with open(self.LAST_PRICE_FILE, 'r') as file:
                    data = json.load(file)
                    last_price = data.get('last_rounded_price')
                    logger.info(f"Loaded last_rounded_price: {last_price}")
                    return last_price
            except Exception as e:
                logger.error(
                    f"Error loading last_rounded_price: {type(e).__name__} - {e}"
                )
                return None
        logger.warning("last_rounded_price.json does not exist, returning None")
        return None

    def save_last_rounded_price(self, price_value):
        """Save the last rounded price to a JSON file."""
        try:
            with open(self.LAST_PRICE_FILE, 'w') as file:
                json.dump({'last_rounded_price': price_value}, file)
            logging.info(f"Saved last_rounded_price: {price_value}")
        except Exception as e:
            logging.error(
                f"Error saving last_rounded_price: {type(e).__name__} - {e}"
            )

    def load_last_summary_time(self):
        """Load the last summary time from a JSON file."""
        if os.path.exists(self.LAST_SUMMARY_FILE):
            try:
                with open(self.LAST_SUMMARY_FILE, 'r') as file:
                    data = json.load(file)
                    time_str = data.get('last_summary_time')
                    if isinstance(time_str, str) and time_str.strip():
                        return datetime.fromisoformat(time_str)
                    else:
                        logging.warning(
                            "No valid 'last_summary_time' found in the JSON file."
                        )
            except json.JSONDecodeError as e:
                logging.error(
                    f"Error decoding JSON from {self.LAST_SUMMARY_FILE}: {type(e).__name__} - {e}"
                )
            except Exception as e:
                logging.error(
                    f"Error loading last_summary_time: {type(e).__name__} - {e}"
                )
        else:
            logging.warning(f"{self.LAST_SUMMARY_FILE} does not exist.")
        return None

    def save_last_summary_time(self, time_value):
        """Save the last summary time to a JSON file."""
        try:
            with open(self.LAST_SUMMARY_FILE, 'w') as file:
                json.dump({'last_summary_time': time_value.isoformat()}, file)
            logging.info(f"Saved last_summary_time: {time_value.isoformat()}")
        except Exception as e:
            logging.error(
                f"Error saving last_summary_time: {type(e).__name__} - {e}"
            )

    def append_to_csv(self, timestamp, price_data, percent_change=None):
        """Append price data to a CSV file."""
        try:
            file_exists = os.path.isfile(self.CSV_FILE)
            with open(self.CSV_FILE, 'a', newline='') as csvfile:
                csv_writer = csv.writer(csvfile)
                if not file_exists or os.path.getsize(self.CSV_FILE) == 0:
                    csv_writer.writerow(
                        [
                            'timestamp',
                            'last_price',
                            'open',
                            'high',
                            'low',
                            'volume',
                            'vwap',
                            'bid',
                            'ask',
                            'percent_change_24',
                            'percent_change',
                        ]
                    )

                csv_writer.writerow(
                    [
                        timestamp,
                        price_data.get('last'),
                        price_data.get('open'),
                        price_data.get('high'),
                        price_data.get('low'),
                        price_data.get('volume'),
                        price_data.get('vwap'),
                        price_data.get('bid'),
                        price_data.get('ask'),
                        price_data.get('percent_change_24'),
                        percent_change,
                    ]
                )
            logging.info(f"Appended data to CSV at {timestamp}")
        except Exception as e:
            logging.error(f"Error appending to CSV: {type(e).__name__} - {e}")

    def run(self):
        """Run the main loop of the bot."""
        while True:
            try:
                self.main_loop()
            except Exception as e:
                logging.error(
                    f"An error occurred in the main loop: {type(e).__name__} - {e}"
                )
                time.sleep(60)

    def main_loop(self):
        """Main loop that checks price and posts tweets."""
        current_time = datetime.now(timezone.utc)
        current_hour = current_time.hour
        current_minute = current_time.minute
        timestamp = current_time.strftime('%Y-%m-%d %H:%M:%S')
        self.current_day = current_time.date()

        logging.info(f"Checking time: Hour={current_hour}, Minute={current_minute}")

        # Fetch price data
        price_data = fetch_xrp_price()

        if not price_data or 'last' not in price_data:
            logging.warning("Failed to fetch price data.")
            time.sleep(60)
            return

        try:
            full_price = float(price_data['last'])
        except (ValueError, TypeError) as e:
            logging.error(f"Error parsing price data: {type(e).__name__} - {e}")
            time.sleep(60)
            return

        rounded_price = round(full_price, 2)

        # Update daily high and low
        if self.daily_high is None or full_price > self.daily_high:
            self.daily_high = full_price
        if self.daily_low is None or full_price < self.daily_low:
            self.daily_low = full_price

        # Force save the rounded price on first run if it is None
        if self.last_rounded_price is None:
            self.save_last_rounded_price(rounded_price)
            self.last_rounded_price = rounded_price

        # Calculate percent change for logging purposes
        if self.last_full_price is not None:
            percent_change = get_percent_change(self.last_full_price, full_price)
        else:
            percent_change = None

        # Log the price data
        self.append_to_csv(timestamp, price_data, percent_change)

        # Update last_full_price
        self.last_full_price = full_price

        # Hourly tweet logic with 5-minute grace period
        if self.last_tweet_hour != current_hour and current_minute < 5:
            if self.last_rounded_price is not None:
                logging.info(
                    f"Comparing last_rounded_price={self.last_rounded_price} with rounded_price={rounded_price}"
                )
                percent_change = get_percent_change(
                    self.last_rounded_price, rounded_price
                )
                logging.info(f"Calculated percent_change={percent_change:.2f}%")

                tweet_text = generate_message(
                    self.last_rounded_price, rounded_price
                )
                try:
                    post_tweet(self.client, tweet_text)
                    logging.info(f"Hourly tweet posted: {tweet_text}")
                    self.last_tweet_hour = current_hour
                except Exception as e:
                    logging.error(f"Error posting tweet: {type(e).__name__} - {e}")

                # Save the current rounded price after posting
                self.save_last_rounded_price(rounded_price)
                self.last_rounded_price = rounded_price
            else:
                logging.warning("last_rounded_price is None, skipping hourly tweet.")

        # Generate and post 3-hour summary tweet with chart
        logging.info(
            f"Checking 3-hour summary condition: Current Hour={current_hour}, Minute={current_minute}, Last Summary Time={self.last_summary_time}"
        )
        if (
            (current_hour, 0) in self.SUMMARY_TIMES
            and (self.last_summary_time is None or self.last_summary_time.hour != current_hour)
        ):
            if current_minute < 5:
                logging.info("3-hour summary condition met. Attempting to generate and post.")
                try:
                    summary_text, chart_filename = generate_3_hour_summary(
                        self.CSV_FILE, full_price, RAPIDAPI_KEY
                    )
                    if summary_text and chart_filename:
                        try:
                            media_id = upload_media(self.api, chart_filename)
                            post_tweet(self.client, summary_text, media_id)
                            logging.info(
                                f"3-hour summary tweet with chart posted: {summary_text}"
                            )
                            self.last_summary_time = current_time
                            self.save_last_summary_time(self.last_summary_time)
                            logging.info(
                                f"Updated last_summary_time to: {self.last_summary_time}"
                            )
                        except Exception as e:
                            logging.error(
                                f"Error posting 3-hour summary tweet with chart: {type(e).__name__} - {e}"
                            )
                    else:
                        logging.error(
                            "3-hour summary generation failed: No summary text or chart filename generated."
                        )
                except Exception as e:
                    logging.error(
                        f"Error during 3-hour summary generation: {type(e).__name__} - {e}"
                    )
            else:
                logging.info("Not within the 5-minute grace period for 3-hour summary.")
        else:
            logging.info("3-hour summary condition not met.")

        # Volatility check logic with 15-minute interval
        if self.last_volatility_check_time is None or (
            current_time - self.last_volatility_check_time
        ) >= timedelta(minutes=15):
            logging.info(
                f"Checking for volatility: last_checked_price={self.last_checked_price}, full_price={full_price}"
            )
            if self.last_checked_price is not None:
                percent_change = get_percent_change(
                    self.last_checked_price, full_price
                )
                if abs(percent_change) >= self.VOLATILITY_THRESHOLD * 100:
                    tweet_text = generate_message(
                        self.last_checked_price,
                        rounded_price,
                        is_volatility_alert=True,
                    )
                    try:
                        post_tweet(self.client, tweet_text)
                        logging.info(f"Volatility alert tweet posted: {tweet_text}")
                    except Exception as e:
                        logging.error(
                            f"Error posting volatility alert tweet: {type(e).__name__} - {e}"
                        )
                self.last_checked_price = rounded_price
            else:
                self.last_checked_price = rounded_price

            self.last_volatility_check_time = current_time

        # Daily summary posting at 8 PM UTC
        if current_hour == 20 and 0 <= current_minute < 5:
            if (
                self.last_daily_summary_time is None
                or self.last_daily_summary_time.date() < self.current_day
            ):
                if self.daily_high is not None and self.daily_low is not None:
                    # Generate and post the daily summary
                    summary_text = generate_daily_summary_message(
                        self.daily_high, self.daily_low
                    )
                    try:
                        post_tweet(self.client, summary_text)
                        logging.info(f"Daily summary tweet posted: {summary_text}")
                    except Exception as e:
                        logging.error(
                            f"Error posting daily summary tweet: {type(e).__name__} - {e}"
                        )

                    # Update the last summary time to prevent multiple posts
                    self.last_daily_summary_time = current_time
                    logging.info(
                        f"Updated last_daily_summary_time to: {self.last_daily_summary_time}"
                    )

                    # Reset daily high and low for the next day
                    self.daily_high = None
                    self.daily_low = None
                    logging.info("Reset daily_high and daily_low after posting daily summary.")
                else:
                    logging.warning(
                        "Daily high and low are None, cannot post daily summary."
                    )
            else:
                logging.info("Daily summary already posted for today.")
        else:
            logging.info("Not time for daily summary yet.")

        # Sleep for 1 minute before next iteration
        time.sleep(60)

if __name__ == "__main__":
    bot = XRPPriceAlertBot()
    bot.run()
