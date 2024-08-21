import csv
import time
from datetime import datetime
from app.twitter import get_twitter_client, post_tweet
from app.fetcher import fetch_xrp_price
from app.xrp_messaging import generate_message, get_percent_change
from app.xrp_logger import log_info, log_warning, log_error
from config import CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET

# Define the volatility threshold
VOLATILITY_THRESHOLD = 0.02

# Define the CSV file for storing price data
CSV_FILE = 'xrp_price_data.csv'

# Update the append_to_csv function to include percent_change
def append_to_csv(timestamp, price_data, percent_change=None):
    with open(CSV_FILE, 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        # Write the header if the file is empty
        if csvfile.tell() == 0:
            csv_writer.writerow([
                'timestamp', 'last_price', 'open', 'high', 'low', 
                'volume', 'vwap', 'bid', 'ask', 'percent_change_24', 'percent_change'
            ])
        
        # Write the row of data
        csv_writer.writerow([
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
            percent_change  # Include your calculated percent change here
        ])

def main():
    client = get_twitter_client(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    last_full_price = None  # For logging purposes
    last_rounded_price = None  # For messaging purposes
    last_tweet_hour = None
    last_checked_price = None

    while True:
        try:
            current_time = datetime.now()
            current_hour = current_time.hour
            timestamp = current_time.strftime('%Y-%m-%d %H:%M:%S')

            # Fetch price data
            price_data = fetch_xrp_price()

            if not price_data or 'last' not in price_data:
                log_warning("Failed to fetch price data.")
                time.sleep(120)
                continue

            full_price = float(price_data['last'])
            rounded_price = round(full_price, 2)

            # Calculate percent change against last_full_price for logging purposes
            if last_full_price is not None:
                percent_change = get_percent_change(last_full_price, full_price)
            else:
                percent_change = None

            # Log the price data with calculated percent change
            append_to_csv(timestamp, price_data, percent_change)

            # Update last_full_price for the next iteration
            last_full_price = full_price

            # Hourly tweet logic - continue using rounded_price for comparisons
            if last_tweet_hour != current_hour:
                if last_rounded_price is not None:
                    tweet_text = generate_message(last_rounded_price, rounded_price)
                    try:
                        post_tweet(client, tweet_text)
                        log_info(f"Hourly tweet posted: {tweet_text}")
                        last_tweet_hour = current_hour
                    except Exception as e:
                        log_error(f"Error posting tweet: {type(e).__name__} - {e}")

            # Update last_rounded_price for next hour's comparison
            last_rounded_price = rounded_price

            # Volatility check logic (unchanged)
            if last_checked_price is not None:
                percent_change = get_percent_change(last_checked_price, full_price)
                if abs(rounded_price - last_checked_price) > VOLATILITY_THRESHOLD:
                    tweet_text = generate_message(last_checked_price, rounded_price, is_volatility_alert=True)
                    try:
                        post_tweet(client, tweet_text)
                        log_info(f"Volatility alert tweet posted: {tweet_text}")
                    except Exception as e:
                        log_error(f"Error posting volatility alert tweet: {type(e).__name__} - {e}")

                last_checked_price = rounded_price
            else:
                last_checked_price = rounded_price

            # Sleep for 2 minutes before checking again for volatility
            time.sleep(120)

        except Exception as e:
            log_error(f"An error occurred: {type(e).__name__} - {e}")
            time.sleep(120)

if __name__ == "__main__":
    main()
