import time
import logging
from app.twitter import get_twitter_client, post_tweet
from app.fetcher import fetch_xrp_price
from app.notifier import create_tweet_text, compare_tweets
from app.utils import load_last_tweet, save_last_tweet
from app.comparisons import ComparisonsGenerator, MessageGenerator
from config import CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, LAST_TWEET_FILE

# Configure logging
logging.basicConfig(level=logging.INFO)

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

def main():
    client = get_twitter_client(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    
    comparisons_generator = ComparisonsGenerator()
    message_generator = MessageGenerator(coin_name="Ripple", coin_code="XRP")
    
    last_hourly_tweet_time = time.time()
    last_price = None

    while True:
        try:
            price_data = fetch_xrp_price()
            if price_data:
                current_price = float(price_data['last'])
                last_day_price = get_last_day_price(price_data)

                if last_day_price is None:
                    logging.warning("Skipping tweet due to missing last day price.")
                    time.sleep(60)
                    continue

                if last_price is not None:
                    percent_change = get_percent_change(last_price, current_price)
                    if abs(percent_change) >= 2:  # Check for significant price change
                        tweet_text = f"The $XRP price is at ${current_price:.2f} right now.\n"
                        tweet_text += f"{'🟢' if percent_change > 0 else '🔴'} In the last minute, the price has {'increased' if percent_change > 0 else 'decreased'} by ${abs(current_price - last_price):.2f} ({abs(percent_change):.2f}%).\n"
                        tweet_text += "\n#Ripple #XRP"
                        
                        post_tweet(client, tweet_text)
                        save_last_tweet({'text': tweet_text, 'price': current_price})
                        logging.info(f"Significant price change tweet posted: {tweet_text}")

                # Handle hourly tweets
                if time.time() - last_hourly_tweet_time >= 3600:  # Check if an hour has passed
                    comparisons = comparisons_generator.get_comparisons(current_price, last_day_price)
                    tweet_text = message_generator.create_message(current_price, comparisons)

                    post_tweet(client, tweet_text)
                    save_last_tweet({'text': tweet_text, 'price': current_price})
                    logging.info(f"Hourly tweet posted: {tweet_text}")

                    last_hourly_tweet_time = time.time()

                # Update last price for the next iteration
                last_price = current_price

            time.sleep(60)  # Sleep for 1 minute before checking again

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            time.sleep(60)  # Wait a minute before retrying if an error occurs

if __name__ == "__main__":
    main()
