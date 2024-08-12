from collections import deque
import time
import logging
from datetime import datetime
from app.twitter import get_twitter_client, post_tweet
from app.fetcher import fetch_xrp_price
from app.utils import load_last_tweet, save_last_tweet
from config import CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET

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
    # Get the current timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Calculate the percentage change
    percent_change = get_percent_change(last_price, current_price)
    
    if round(last_price, 2) == round(current_price, 2):
        # Prices are effectively the same
        return f"🔔❗️ $XRP has retained a value of ${current_price:.2f} over the last hour.\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
    else:
        # Prices have changed
        if current_price > last_price:
            return f"🔔📈 $XRP is UP {percent_change:.2f}% over the last hour to ${current_price:.2f}!\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
        else:
            return f"🔔📉 $XRP is DOWN {abs(percent_change):.2f}% over the last hour to ${current_price:.2f}!\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"

def main(test_mode=False):
    client = get_twitter_client(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    
    last_price = None
    last_hourly_tweet_time = None  # Track when the last hourly tweet was posted
    price_window = deque(maxlen=10)  # Track the last 10 checks for trend analysis

    while True:
        try:
            price_data = fetch_xrp_price()
            if price_data:
                current_price = float(price_data['last'])
                logging.info(f"Checked price: ${current_price:.2f}")
                
                if last_price is not None:
                    percent_change = get_percent_change(last_price, current_price)
                    logging.info(f"Price change since last check: {percent_change:.2f}%")
                
                last_day_price = get_last_day_price(price_data)

                if last_day_price is None:
                    logging.warning("Skipping tweet due to missing last day price.")
                    if test_mode:
                        break  # Exit the loop in test mode
                    time.sleep(60)
                    continue

                current_time = datetime.now()

                if test_mode:
                    timestamp = current_time.strftime('%Y-%m-%d %H:%M:%S')
                    tweet_text = f"🚨 Test Post: The $XRP price is at ${current_price:.2f} right now.\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
                    try:
                        post_tweet(client, tweet_text)
                        logging.info(f"Test tweet posted: {tweet_text}")
                    except tweepy.TweepyException as e:
                        logging.error(f"Tweepy error occurred: {e}")
                    break

                if last_price is not None:
                    # Handle hourly tweets only at the top of the hour
                    if (last_hourly_tweet_time is None or last_hourly_tweet_time.hour != current_time.hour) and current_time.minute == 0:
                        tweet_text = generate_hourly_message(last_price, current_price)
                        if tweet_text:  # Ensure there's a valid tweet to post
                            post_tweet(client, tweet_text)
                            save_last_tweet({'text': tweet_text, 'price': current_price})
                            logging.info(f"Hourly tweet posted: {tweet_text}")
                            last_hourly_tweet_time = current_time

                # Trend-based tweets
                price_window.append(current_price)
                if len(price_window) == price_window.maxlen:
                    initial_price = price_window[0]
                    trend_percent_change = get_percent_change(initial_price, current_price)
                    if abs(trend_percent_change) >= 2:
                        direction = "UP" if trend_percent_change > 0 else "DOWN"
                        tweet_text = f"🔔📈 $XRP is {direction} {abs(trend_percent_change):.2f}% over the last {len(price_window)} minutes to ${current_price:.2f}!\nTime: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n#Ripple #XRP #XRPPriceAlerts"
                        post_tweet(client, tweet_text)
                        logging.info(f"Trend tweet posted: {tweet_text}")
                    # Reset the price window for the next trend check
                    price_window.clear()

                # Update last price for the next iteration
                last_price = current_price

            time.sleep(60)

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            if test_mode:
                break
            time.sleep(60)

if __name__ == "__main__":
    main(test_mode=False)
