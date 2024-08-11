import time
import logging
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
    percent_change = get_percent_change(last_price, current_price)
    if percent_change == 0:
        return f"🔔❗️ $XRP has retained a value of ${current_price:.2f} over the last hour.\n#Ripple #XRP #XRPPriceAlerts"
    elif percent_change > 0:
        return f"🔔📈 $XRP is UP {percent_change:.2f}% over the last hour to ${current_price:.2f}!\n#Ripple #XRP #XRPPriceAlerts"
    else:
        return f"🔔📉 $XRP is DOWN {abs(percent_change):.2f}% over the last hour to ${current_price:.2f}!\n#Ripple #XRP #XRPPriceAlerts"

def time_until_next_hour():
    """Calculate the number of seconds until the next hour."""
    current_time = time.time()
    next_hour = (current_time // 3600 + 1) * 3600
    return max(next_hour - current_time, 0)

def main():
    client = get_twitter_client(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    
    last_price = None

    while True:
        try:
            price_data = fetch_xrp_price()
            if price_data:
                current_price = float(price_data['last'])
                logging.info(f"Checked price: ${current_price:.2f}")
                
                last_day_price = get_last_day_price(price_data)

                if last_day_price is None:
                    logging.warning("Skipping tweet due to missing last day price.")
                    time.sleep(30)  # Reduced sleep interval
                    continue

                if last_price is not None:
                    percent_change = get_percent_change(last_price, current_price)
                    logging.info(f"Price change since last check: {percent_change:.2f}%")
                    
                    if abs(percent_change) >= 2:  # Check for significant price change
                        tweet_text = f"The $XRP price is at ${current_price:.2f} right now.\n"
                        tweet_text += f"{'🟢' if percent_change > 0 else '🔴'} In the last minute, the price has {'increased' if percent_change > 0 else 'decreased'} by ${abs(current_price - last_price):.2f} ({abs(percent_change):.2f}%).\n"
                        tweet_text += "\n#Ripple #XRP"
                        
                        post_tweet(client, tweet_text)
                        save_last_tweet({'text': tweet_text, 'price': current_price})
                        logging.info(f"Significant price change tweet posted: {tweet_text}")

                # Handle hourly tweets
                time_to_next_hour = time_until_next_hour()
                if time_to_next_hour <= 60:  # If we're within a minute of the next hour
                    tweet_text = generate_hourly_message(last_price, current_price)

                    post_tweet(client, tweet_text)
                    save_last_tweet({'text': tweet_text, 'price': current_price})
                    logging.info(f"Hourly tweet posted: {tweet_text}")

                    # Wait until the next hour before continuing
                    time.sleep(time_to_next_hour)

                # Update last price for the next iteration
                last_price = current_price

            time.sleep(30)  # Reduced sleep interval

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            time.sleep(30)  # Reduced sleep interval

if __name__ == "__main__":
    main()
