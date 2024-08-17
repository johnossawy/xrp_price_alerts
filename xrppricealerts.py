import time
import logging
import csv
from datetime import datetime
from app.twitter import get_twitter_client, post_tweet
from app.fetcher import fetch_xrp_price
from config import CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET

# Set up logging
logging.basicConfig(
    filename='xrp_bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Define the All-Time High (ATH) price
ALL_TIME_HIGH_PRICE = 3.65

# Define the CSV file for storing price data
CSV_FILE = 'xrp_price_data.csv'

def get_percent_change(old_price, new_price):
    """Calculate percentage change between two prices."""
    return ((new_price - old_price) / old_price) * 100 if old_price != 0 else 0

def generate_message(last_price, current_price):
    """Generate a message for Twitter based on price change."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    percent_change = get_percent_change(last_price, current_price)

    if current_price > ALL_TIME_HIGH_PRICE:
        return f"🚀🔥 $XRP just shattered its all-time high, now at an incredible ${current_price:.2f}!!! 🚀🔥\nTime: {timestamp}\n#Ripple #XRP #XRPATH #ToTheMoon"
    elif current_price == last_price:
        return f"🔔❗️ $XRP has retained a value of ${current_price:.2f} over the last hour.\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
    elif current_price > last_price:
        return f"🔔📈 $XRP is UP {get_percent_change(last_price, current_price):.2f}% over the last hour to ${current_price:.2f}!\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
    else:
        return f"🔔📉 $XRP is DOWN {abs(get_percent_change(last_price, current_price)):.2f}% over the last hour to ${current_price:.2f}!\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"

def append_to_csv(timestamp, price, percent_change=None):
    """Append price data to a CSV file."""
    with open(CSV_FILE, 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        if csvfile.tell() == 0:  # If file is empty, write the header
            csv_writer.writerow(['timestamp', 'price', 'percent_change'])
        csv_writer.writerow([timestamp, price, percent_change])

def log_full_price_data():
    """Log full XRP price data to the log file."""
    price_data = fetch_xrp_price()
    if price_data:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logging.info(f"Full price data fetched at {timestamp}: {price_data}")

def main():
    client = get_twitter_client(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    last_price = None
    last_tweet_hour = None
    last_log_time = None

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

                    # Log price data to CSV
                    append_to_csv(current_time.strftime('%Y-%m-%d %H:%M:%S'), current_price, get_percent_change(last_price, current_price))
                    
                    last_price = current_price
                else:
                    logging.warning("Failed to fetch price data.")
            
            # Log full price data every 2 minutes
            if last_log_time is None or (current_time - last_log_time).total_seconds() >= 120:
                log_full_price_data()
                last_log_time = current_time

            # Sleep for a minute before checking again
            time.sleep(60)

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
