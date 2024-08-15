import time
import logging
from datetime import datetime
from app.twitter import get_twitter_client, post_tweet
from app.fetcher import fetch_xrp_price
from config import CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def main():
    client = get_twitter_client(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    last_tweet_hour = None

    while True:
        try:
            current_time = datetime.now()
            current_hour = current_time.hour

            # Check if an hour has passed since the last tweet
            if last_tweet_hour != current_hour:
                price_data = fetch_xrp_price()
                
                if price_data and 'last' in price_data:
                    current_price = float(price_data['last'])
                    timestamp = current_time.strftime('%Y-%m-%d %H:%M:%S')
                    tweet_text = f"🔔 Current $XRP price: ${current_price:.2f}\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"

                    try:
                        post_tweet(client, tweet_text)
                        logging.info(f"Tweet posted: {tweet_text}")
                        last_tweet_hour = current_hour
                    except Exception as e:
                        logging.error(f"Error posting tweet: {e}")
                else:
                    logging.warning("Failed to fetch price data.")
            
            # Sleep for a minute before checking again
            time.sleep(60)

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
