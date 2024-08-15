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

def get_percent_change(old_price, new_price):
    return ((new_price - old_price) / old_price) * 100 if old_price != 0 else 0

def generate_message(last_price, current_price):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    percent_change = get_percent_change(last_price, current_price)

    if current_price == last_price:
        return f"🔔❗️ $XRP has retained a value of ${current_price:.2f} over the last hour.\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
    elif current_price > last_price:
        return f"🔔📈 $XRP is UP {percent_change:.2f}% over the last hour to ${current_price:.2f}!\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
    else:
        return f"🔔📉 $XRP is DOWN {abs(percent_change):.2f}% over the last hour to ${current_price:.2f}!\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"

def main():
    client = get_twitter_client(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    last_price = None
    last_tweet_hour = None

    while True:
        try:
            current_time = datetime.now()
            current_hour = current_time.hour

            # Check if an hour has passed since the last tweet
            if last_tweet_hour != current_hour:
                price_data = fetch_xrp_price()
                
                if price_data and 'last' in price_data:
                    current_price = round(float(price_data['last']), 2)
                    
                    if last_price is not None:
                        tweet_text = generate_message(last_price, current_price)

                        try:
                            post_tweet(client, tweet_text)
                            logging.info(f"Tweet posted: {tweet_text}")
                            last_tweet_hour = current_hour
                        except Exception as e:
                            logging.error(f"Error posting tweet: {e}")

                    last_price = current_price
                else:
                    logging.warning("Failed to fetch price data.")
            
            # Sleep for a minute before checking again
            time.sleep(60)

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
