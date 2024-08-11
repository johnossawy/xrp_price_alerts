import time
import logging
from datetime import datetime
from app.twitter import get_twitter_client, post_tweet
from app.fetcher import fetch_xrp_price
from app.utils import load_last_tweet, save_last_tweet
from app.comparisons import ComparisonsGenerator, MessageGenerator
from config import CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET

# Configure logging with timestamps
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def get_last_day_price(price_data):
    open_24_price = price_data.get('open_24')
    if open_24_price is None:
        logging.warning("Warning: 'open_24' value is None or not present in the API response.")
        return None
    try:
        return float(open_24_price)
    except ValueError as e:
        logging.error(f"Error converting 'open_24' to float: {e}")
        return None

def get_percent_change(old_price, new_price):
    return ((new_price - old_price) / old_price) * 100

def generate_hourly_message(last_price, current_price):
    # Round the prices to two decimal places
    last_price_rounded = round(last_price, 2)
    current_price_rounded = round(current_price, 2)
    
    # Get the current timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if last_price_rounded == current_price_rounded:
        # Price has retained the same value after rounding
        return f"🔔❗️ $XRP has retained a value of ${current_price_rounded:.2f} over the last hour.\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
    else:
        # Price has changed after rounding, show the percentage change
        percent_change = get_percent_change(last_price, current_price)
        if current_price_rounded > last_price_rounded:
            return f"🔔📈 $XRP is UP {percent_change:.2f}% over the last hour to ${current_price_rounded:.2f}!\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
        else:
            return f"🔔📉 $XRP is DOWN -{abs(percent_change):.2f}% over the last hour to ${current_price_rounded:.2f}!\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"

def time_until_next_hour():
    """Calculate the number of seconds until the next hour."""
    current_time = time.time()
    next_hour = (current_time // 3600 + 1) * 3600
    return max(next_hour - current_time, 0)

def main(test_mode=False):
    client = get_twitter_client(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    
    last_price = None
    last_hourly_tweet_time = None  # Track when the last hourly tweet was posted

    while True:
        try:
            price_data = fetch_xrp_price()
            if price_data:
                current_price = float(price_data['last'])
                logging.info(f"Checked price: ${current_price:.2f}")
                
                last_day_price = get_last_day_price(price_data)

                if last_day_price is None:
                    logging.warning("Skipping tweet due to missing last day price.")
                    if test_mode:
                        break  # Exit the loop in test mode
                    time.sleep(60)  # Adjusted sleep interval
                    continue

                current_time = datetime.now()

                if test_mode:
                    # Post immediately in test mode with a unique timestamp
                    timestamp = current_time.strftime('%Y-%m-%d %H:%M:%S')
                    tweet_text = f"🚨 Test Post: The $XRP price is at ${current_price:.2f} right now.\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
                    try:
                        post_tweet(client, tweet_text)
                        logging.info(f"Test tweet posted: {tweet_text}")
                    except tweepy.TweepyException as e:
                        logging.error(f"Tweepy error occurred: {e}")
                    break  # Exit after posting in test mode

                if last_price is not None:
                    percent_change = get_percent_change(last_price, current_price)
                    logging.info(f"Price change since last check: {percent_change:.2f}%")
                    
                    # Check if the rounded prices are the same
                    last_price_rounded = round(last_price, 2)
                    current_price_rounded = round(current_price, 2)

                    # Handle significant price changes (2% or more)
                    if abs(percent_change) >= 2:
                        tweet_text = f"🔔{'📈' if percent_change > 0 else '📉'} $XRP is {'UP' if percent_change > 0 else 'DOWN'} {abs(percent_change):.2f}% to ${current_price_rounded:.2f}!\nTime: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n#Ripple #XRP #XRPPriceAlerts"
                        post_tweet(client, tweet_text)
                        save_last_tweet({'text': tweet_text, 'price': current_price})
                        logging.info(f"Significant price change tweet posted: {tweet_text}")
                    # Handle hourly tweets only at the top of the hour
                    elif (last_hourly_tweet_time is None or last_hourly_tweet_time.hour != current_time.hour) and current_time.minute == 0:
                        tweet_text = generate_hourly_message(last_price, current_price)
                        post_tweet(client, tweet_text)
                        save_last_tweet({'text': tweet_text, 'price': current_price})
                        logging.info(f"Hourly tweet posted: {tweet_text}")
                        last_hourly_tweet_time = current_time  # Update the last hourly tweet time

                # Update last price for the next iteration
                last_price = current_price

            time.sleep(60)  # Adjusted sleep interval

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            if test_mode:
                break  # Exit in case of an error in test mode
            time.sleep(60)  # Adjusted sleep interval

if __name__ == "__main__":
    # Set test_mode=True to force an immediate tweet for testing
    main(test_mode=False)
