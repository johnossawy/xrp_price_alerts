import logging
import time
from datetime import datetime, timezone, timedelta
from logging.handlers import RotatingFileHandler

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
)
from database_handler import DatabaseHandler
from app.xrp_messaging import cleanup_old_charts  # Import the cleanup function

ENABLE_HOURLY_TWEET = False        # Set to False to disable hourly tweets
ENABLE_3_HOUR_SUMMARY = True      # Set to False to disable 3-hour summaries
ENABLE_VOLATILITY_ALERT = True    # Set to False to disable volatility alerts
ENABLE_DAILY_SUMMARY = True       # Set to False to disable daily summary

# Configure logging with RotatingFileHandler
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Avoid adding multiple handlers if the logger already has handlers
if not logger.handlers:
    handler = RotatingFileHandler('xrp_bot.log', maxBytes=5*1024*1024, backupCount=5)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


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

        # Initialize tracking variables
        self.daily_high = None
        self.daily_low = None
        self.current_day = datetime.now(timezone.utc).date()
        self.last_volatility_check_time = None
        self.last_rounded_price = None
        self.last_summary_time = None
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

        # Initialize the DatabaseHandler
        self.db_handler = DatabaseHandler()

        # Load state from the database
        self.load_state_from_db()

    def load_state_from_db(self):
        """Load the last rounded price and summary time from the database."""
        try:
            # Load last rounded price for XRP
            query_price = """
                SELECT last_price FROM crypto_prices
                WHERE symbol = 'XRP'
                ORDER BY timestamp DESC LIMIT 1;
            """
            result = self.db_handler.fetch_one(query_price)
            if result and result.get('last_price') is not None:
                self.last_rounded_price = round(float(result['last_price']), 2)
                logger.info(f"Loaded last_rounded_price from DB: {self.last_rounded_price}")
            else:
                logger.warning("No last_rounded_price found in DB for XRP, starting fresh.")

            # Load last summary time for 3-hour summary from `twitter_bot_activity`
            query_summary = """
                SELECT timestamp FROM twitter_bot_activity
                WHERE activity_type = '3_hour_summary'
                ORDER BY timestamp DESC LIMIT 1;
            """
            result = self.db_handler.fetch_one(query_summary)
            if result and result.get('timestamp') is not None:
                self.last_summary_time = result['timestamp']
                logger.info(f"Loaded last_summary_time from DB: {self.last_summary_time}")
            else:
                logger.warning("No last_summary_time found in DB, starting fresh.")

        except Exception as e:
            logger.error(f"Error loading state from DB: {type(e).__name__} - {e}")

    def save_state_to_db(self, price_data):
        """Save price data to the database."""
        try:
            insert_query = """
                INSERT INTO crypto_prices (
                    timestamp, symbol, last_price, open_price, high_price,
                    low_price, volume, vwap, bid, ask, percent_change_24h, percent_change
                ) VALUES (
                    %(timestamp)s, %(symbol)s, %(last_price)s, %(open_price)s, %(high_price)s,
                    %(low_price)s, %(volume)s, %(vwap)s, %(bid)s, %(ask)s, %(percent_change_24h)s, %(percent_change)s
                );
            """
            params = {
                'timestamp': datetime.now(timezone.utc),
                'symbol': 'XRP',
                'last_price': price_data.get('last'),
                'open_price': price_data.get('open'),
                'high_price': price_data.get('high'),
                'low_price': price_data.get('low'),
                'volume': price_data.get('volume'),
                'vwap': price_data.get('vwap'),
                'bid': price_data.get('bid'),
                'ask': price_data.get('ask'),
                'percent_change_24h': price_data.get('percent_change_24'),
                'percent_change': price_data.get('percent_change'),
            }
            success = self.db_handler.execute(insert_query, params)
            if success:
                logger.info("Saved price data to DB.")
            else:
                logger.error("Failed to save price data to DB.")

        except Exception as e:
            logger.error(f"Error saving price data to DB: {type(e).__name__} - {e}")

    def save_bot_activity_to_db(self, activity_type, price, summary_text=None):
        """
        Save non-trading bot activities to the twitter_bot_activity table.

        Args:
            activity_type (str): Type of activity ('hourly_update', '3_hour_summary', 'daily_summary').
            price (float): The XRP price at the time of the activity.
            summary_text (str, optional): The content of the summary/update.
        """
        try:
            insert_query = """
                INSERT INTO twitter_bot_activity (timestamp, activity_type, price, summary_text)
                VALUES (%(timestamp)s, %(activity_type)s, %(price)s, %(summary_text)s);
            """
            params = {
                'timestamp': datetime.now(timezone.utc),
                'activity_type': activity_type,
                'price': price,
                'summary_text': summary_text
            }
            success = self.db_handler.execute(insert_query, params)
            if success:
                logger.info(f"{activity_type} saved to twitter_bot_activity table.")
            else:
                logger.error(f"Failed to save {activity_type} to twitter_bot_activity table.")

        except Exception as e:
            logger.error(f"Error saving {activity_type} to twitter_bot_activity table: {type(e).__name__} - {e}")

    def save_trade_signal_to_db(
        self, signal_type, price, profit_loss=None, percent_change=None, time_held=None, updated_capital=None
    ):
        """Save trade signal data to the database."""
        try:
            insert_query = """
                INSERT INTO trade_signals (
                    timestamp, signal_type, price, profit_loss, percent_change, time_held, updated_capital
                ) VALUES (
                    %(timestamp)s, %(signal_type)s, %(price)s, %(profit_loss)s, %(percent_change)s, %(time_held)s, %(updated_capital)s
                );
            """
            params = {
                'timestamp': datetime.now(timezone.utc),
                'signal_type': signal_type,
                'price': price,
                'profit_loss': profit_loss,
                'percent_change': percent_change,
                'time_held': time_held,
                'updated_capital': updated_capital,
            }
            success = self.db_handler.execute(insert_query, params)
            if success:
                logger.info(f"Saved trade signal '{signal_type}' to DB.")
            else:
                logger.error(f"Failed to save trade signal '{signal_type}' to DB.")

        except Exception as e:
            logger.error(f"Error saving trade signal to DB: {type(e).__name__} - {e}")

    def run(self):
        """Run the main loop of the bot."""
        while True:
            try:
                self.main_loop()
            except Exception as e:
                logger.error(
                    f"An error occurred in the main loop: {type(e).__name__} - {e}"
                )
                time.sleep(60)

    def main_loop(self):
        """Main loop that checks price and posts tweets."""
        current_time = datetime.now(timezone.utc)
        current_hour = current_time.hour
        current_minute = current_time.minute
        self.current_day = current_time.date()

        logger.info(f"Checking time: Hour={current_hour}, Minute={current_minute}")

        # Fetch price data
        price_data = fetch_xrp_price()

        if not price_data or 'last' not in price_data:
            logger.warning("Failed to fetch price data.")
            time.sleep(60)
            return

        try:
            full_price = float(price_data['last'])
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing price data: {type(e).__name__} - {e}")
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
            self.last_rounded_price = rounded_price

        # Calculate percent change for logging purposes
        if self.last_full_price is not None:
            percent_change = get_percent_change(self.last_full_price, full_price)
        else:
            percent_change = 0.0  # Assuming 0% change if no previous price

        # Save price data to the database
        price_data['percent_change'] = percent_change
        self.save_state_to_db(price_data)

        # Update last_full_price
        self.last_full_price = full_price

        # Hourly tweet logic with 5-minute grace period
        if ENABLE_HOURLY_TWEET:
            if self.last_tweet_hour != current_hour and current_minute < 5:
                if self.last_rounded_price is not None:
                    logger.info(
                        f"Comparing last_rounded_price={self.last_rounded_price} with rounded_price={rounded_price}"
                    )
                    percent_change = get_percent_change(
                        self.last_rounded_price, rounded_price
                    )
                    logger.info(f"Calculated percent_change={percent_change:.2f}%")

                    tweet_text = generate_message(
                        self.last_rounded_price, rounded_price
                    )
                    try:
                        post_tweet(self.client, tweet_text)
                        logger.info(f"Hourly tweet posted: {tweet_text}")
                        self.last_tweet_hour = current_hour
                        
                        # Save hourly update to the new twitter_bot_activity table
                        self.save_bot_activity_to_db('hourly_update', rounded_price)

                    except Exception as e:
                        logger.error(f"Error posting tweet: {type(e).__name__} - {e}")

                    # Save the current rounded price after posting
                    self.last_rounded_price = rounded_price
                else:
                    logger.warning("last_rounded_price is None, skipping hourly tweet.")

        # Generate and post 3-hour summary tweet with chart
        if ENABLE_3_HOUR_SUMMARY:
            if (
                (current_hour, 0) in self.SUMMARY_TIMES
                and (self.last_summary_time is None or self.last_summary_time.hour != current_hour)
            ):
                if current_minute < 5:
                    logger.info("3-hour summary condition met. Attempting to generate and post.")
                    try:
                        summary_text, chart_filename = generate_3_hour_summary(
                            self.db_handler, full_price, None  # No longer passing RAPIDAPI_KEY
                        )
                        if summary_text and chart_filename:
                            media_id = upload_media(self.api, chart_filename)
                            post_tweet(self.client, summary_text, media_id)
                            logger.info(
                                f"3-hour summary tweet with chart posted: {summary_text}"
                            )
                            self.last_summary_time = current_time
                            
                            # Save 3-hour summary to the new twitter_bot_activity table
                            self.save_bot_activity_to_db('3_hour_summary', rounded_price, summary_text=summary_text)

                        else:
                            logger.error(
                                "3-hour summary generation failed: No summary text or chart filename generated."
                            )
                    except Exception as e:
                        logger.error(
                            f"Error during 3-hour summary generation: {type(e).__name__} - {e}"
                        )

        # Volatility check logic with 15-minute interval
        if ENABLE_VOLATILITY_ALERT:
            if self.last_volatility_check_time is None or (
                current_time - self.last_volatility_check_time
            ) >= timedelta(minutes=15):
                logger.info(
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
                            logger.info(f"Volatility alert tweet posted: {tweet_text}")
                        except Exception as e:
                            logger.error(
                                f"Error posting volatility alert tweet: {type(e).__name__} - {e}"
                            )
                    self.last_checked_price = rounded_price
                else:
                    self.last_checked_price = rounded_price

                self.last_volatility_check_time = current_time

        # Daily summary posting at 8 PM UTC
        if ENABLE_DAILY_SUMMARY:
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
                            logger.info(f"Daily summary tweet posted: {summary_text}")
                            
                            # Save daily summary to the new twitter_bot_activity table
                            self.save_bot_activity_to_db('daily_summary', rounded_price, summary_text=summary_text)

                        except Exception as e:
                            logger.error(
                                f"Error posting daily summary tweet: {type(e).__name__} - {e}"
                            )

                        # Update the last summary time to prevent multiple posts
                        self.last_daily_summary_time = current_time
                        logger.info(
                            f"Updated last_daily_summary_time to: {self.last_daily_summary_time}"
                        )

                        # Reset daily high and low for the next day
                        self.daily_high = None
                        self.daily_low = None
                        logger.info("Reset daily_high and daily_low after posting daily summary.")
                    else:
                        logger.warning(
                            "Daily high and low are None, cannot post daily summary."
                        )
                else:
                    logger.info("Daily summary already posted for today.")
            else:
                logger.info("Not time for daily summary yet.")

        # Cleanup old charts to conserve disk space
        cleanup_old_charts()

        # Sleep for 1 minute before next iteration
        time.sleep(60)

    def __del__(self):
        """Ensure the database connection is closed."""
        self.db_handler.close()


if __name__ == "__main__":
    bot = XRPPriceAlertBot()
    bot.run()
