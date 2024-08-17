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

# Define the All-Time High (ATH) price
ALL_TIME_HIGH_PRICE = 3.65

# Define the volatility threshold
VOLATILITY_THRESHOLD = 0.02

def get_percent_change(old_price, new_price):
    return ((new_price - old_price) / old_price) * 100 if old_price != 0 else 0

def generate_message(last_price, current_price, is_volatility_alert=False):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    percent_change = get_percent_change(last_price, current_price)

    if current_price > ALL_TIME_HIGH_PRICE:
        return f"🚀🔥 $XRP just shattered its all-time high, now at an incredible ${current_price:.2f}!!! 🚀🔥\nTime: {timestamp}\n#Ripple #XRP #XRPATH #ToTheMoon"
    elif is_volatility_alert:
        direction = "UP" if current_price > last_price else "DOWN"
        emoji = "📈" if direction == "UP" else "📉"
        return f"⚡️ $XRP is experiencing volatility! It's {direction} by {abs(percent_change):.2f}% to ${current_price:.2f} {emoji}\nTime: {timestamp}\n#Ripple #XRP #XRPVolatility"
    elif current_price == last_price:
        return f"🔔❗️ $XRP has retained a value of ${current_price:.2f} over the last hour.\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
    elif current_price > last_price:
        return f"🔔📈 $XRP is UP {percent_change:.2f}% over the last hour to ${current_price:.2f}!\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
    else:
        return f"🔔📉 $XRP is DOWN {abs(percent_change):.2f}% over the last hour to ${current_price:.2f}!\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"

def main():
    client = get_twitter_client(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    last_price = None
    last_tweet_hour = None
    last_checked_price = None

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
                            logging.info(f"Hourly tweet posted: {tweet_text}")
                            last_tweet_hour = current_hour
                        except Exception as e:
                            logging.error(f"Error posting tweet: {e}")

                    last_price = current_price
                else:
                    logging.warning("Failed to fetch price data.")
            
            # Volatility check every 2 minutes
            if last_checked_price is not None:
                price_data = fetch_xrp_price()
                
                if price_data and 'last' in price_data:
                    current_price = round(float(price_data['last']), 2)
                    
                    if abs(current_price - last_checked_price) > VOLATILITY_THRESHOLD:
                        tweet_text = generate_message(last_checked_price, current_price, is_volatility_alert=True)

                        try:
                            post_tweet(client, tweet_text)
                            logging.info(f"Volatility alert tweet posted: {tweet_text}")
                        except Exception as e:
                            logging.error(f"Error posting volatility alert tweet: {e}")

                    last_checked_price = current_price

            else:
                # Set the initial last_checked_price
                last_checked_price = last_price

            # Sleep for 2 minutes before checking again for volatility
            time.sleep(120)

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            time.sleep(120)

if __name__ == "__main__":
    main()
