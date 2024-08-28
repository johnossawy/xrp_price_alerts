import csv
import time
import json
import os
from datetime import datetime, timedelta
from app.twitter import get_twitter_api, get_twitter_client, post_tweet, upload_media
from app.fetcher import fetch_xrp_price
from app.xrp_messaging import generate_message, get_percent_change, generate_daily_summary_message, generate_3_hour_summary
from app.xrp_logger import log_info, log_warning, log_error
from config import CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, RAPIDAPI_KEY

# Define the volatility threshold
VOLATILITY_THRESHOLD = 0.02
SUMMARY_TIMES = {(0, 0), (3, 0), (6, 0), (9, 0), (12, 0), (15, 0), (18, 0), (21, 0)}  # Hours to post 3-hour summary tweets

# Define the CSV file for storing price data and the JSON files for last summary time and last rounded price
CSV_FILE = 'xrp_price_data.csv'
LAST_SUMMARY_FILE = 'last_summary_time.json'
LAST_PRICE_FILE = 'last_rounded_price.json'

# Initialize tracking variables
daily_high = None
daily_low = None
current_day = datetime.now().date()
last_summary_time = None  # Initialize to None
last_volatility_check_time = None  # Initialize for tracking the last volatility check time
last_rounded_price = None  # Initialize for tracking the last rounded price

def generate_daily_summary_message(daily_high, daily_low):
    """Generate a message summarizing the day's price range."""
    if daily_high is not None and daily_low is not None:
        return f"📊 Daily Summary: Today’s XRP price ranged between ${daily_low:.5f} and ${daily_high:.5f}. \n#Ripple #XRP #XRPPriceAlerts"
    return None

# Utility functions to load and save last rounded price
def load_last_rounded_price():
    if os.path.exists(LAST_PRICE_FILE):
        with open(LAST_PRICE_FILE, 'r') as file:
            data = json.load(file)
            log_info(f"Loaded last_rounded_price: {data.get('last_rounded_price')}")
            return data.get('last_rounded_price')
    log_warning("last_rounded_price.json does not exist, returning None")
    return None

def save_last_rounded_price(price_value):
    try:
        with open(LAST_PRICE_FILE, 'w') as file:
            json.dump({'last_rounded_price': price_value}, file)
        log_info(f"Saved last_rounded_price: {price_value}")
    except Exception as e:
        log_error(f"Error saving last_rounded_price: {type(e).__name__} - {e}")

# Utility functions to load and save last summary time
def load_last_summary_time():
    if os.path.exists(LAST_SUMMARY_FILE):
        with open(LAST_SUMMARY_FILE, 'r') as file:
            data = json.load(file)
            return data.get('last_summary_time')
    return None

def save_last_summary_time(time_value):
    with open(LAST_SUMMARY_FILE, 'w') as file:
        json.dump({'last_summary_time': time_value}, file)

# Load the last rounded price and last summary time at the start of the script
last_rounded_price = load_last_rounded_price()
last_summary_time = load_last_summary_time()

def append_to_csv(timestamp, price_data, percent_change=None):
    with open(CSV_FILE, 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        if csvfile.tell() == 0:
            csv_writer.writerow([
                'timestamp', 'last_price', 'open', 'high', 'low', 
                'volume', 'vwap', 'bid', 'ask', 'percent_change_24', 'percent_change'
            ])
        
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
            percent_change
        ])

client = get_twitter_client(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = get_twitter_api(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

def main():
    global daily_high, daily_low, current_day, last_summary_time, last_volatility_check_time, last_rounded_price
    last_full_price = None  # For logging purposes
    last_tweet_hour = None
    last_checked_price = None

    while True:
        try:
            current_time = datetime.now()
            current_hour = current_time.hour
            current_minute = current_time.minute
            timestamp = current_time.strftime('%Y-%m-%d %H:%M:%S')

            log_info(f"Checking time: Hour={current_hour}, Minute={current_minute}")

            # Fetch price data
            price_data = fetch_xrp_price()

            if not price_data or 'last' not in price_data:
                log_warning("Failed to fetch price data.")
                time.sleep(60)
                continue

            full_price = float(price_data['last'])
            rounded_price = round(full_price, 2)

            # Update daily high and low
            if daily_high is None or full_price > daily_high:
                daily_high = full_price
            if daily_low is None or full_price < daily_low:
                daily_low = full_price

            # Force save the rounded price on first run if it is None
            if last_rounded_price is None:
                save_last_rounded_price(rounded_price)
                last_rounded_price = rounded_price

            # Calculate percent change against last_full_price for logging purposes
            if last_full_price is not None:
                percent_change = get_percent_change(last_full_price, full_price)
            else:
                percent_change = None

            # Log the price data with calculated percent change
            append_to_csv(timestamp, price_data, percent_change)

            # Update last_full_price for the next iteration
            last_full_price = full_price

            # Hourly tweet logic with 5-minute grace period
            if last_tweet_hour != current_hour and current_minute < 5:
                if last_rounded_price is not None:
                    log_info(f"Comparing last_rounded_price={last_rounded_price} with rounded_price={rounded_price}")
                    percent_change = get_percent_change(last_rounded_price, rounded_price)
                    log_info(f"Calculated percent_change={percent_change:.2f}%")
                    
                    tweet_text = generate_message(last_rounded_price, rounded_price)
                    try:
                        post_tweet(client, tweet_text)
                        log_info(f"Hourly tweet posted: {tweet_text}")
                        last_tweet_hour = current_hour
                    except Exception as e:
                        log_error(f"Error posting tweet: {type(e).__name__} - {e}")
                    
                    # Save the current rounded price after posting
                    save_last_rounded_price(rounded_price)
                    last_rounded_price = rounded_price  # Update for next comparison
                else:
                    log_warning("last_rounded_price is None, skipping hourly tweet.")

            # Generate and post 3-hour summary tweet with chart at specified times, with 5-minute grace period
            log_info(f"Checking 3-hour summary condition: Current Hour={current_hour}, Minute={current_minute}, Last Summary Hour={last_summary_time}")
            if current_hour in [hour for hour, _ in SUMMARY_TIMES] and (last_summary_time is None or last_summary_time != current_hour):
                if current_minute < 5:  # Grace period of 5 minutes
                    log_info("3-hour summary condition met. Attempting to generate and post.")
                    try:
                        summary_text, chart_filename = generate_3_hour_summary(CSV_FILE, full_price, RAPIDAPI_KEY)
                        if summary_text and chart_filename:
                            try:
                                media_id = upload_media(api, chart_filename)
                                post_tweet(client, summary_text, media_id)
                                log_info(f"3-hour summary tweet with chart posted: {summary_text}")
                                last_summary_time = current_hour  # Update the hour after posting
                                save_last_summary_time(last_summary_time)  # Save the updated summary time
                                log_info(f"Updated last_summary_time to: {last_summary_time}")
                            except Exception as e:
                                log_error(f"Error posting 3-hour summary tweet with chart: {type(e).__name__} - {e}")
                        else:
                            log_error("3-hour summary generation failed: No summary text or chart filename generated.")
                    except Exception as e:
                        log_error(f"Error during 3-hour summary generation: {type(e).__name__} - {e}")
            else:
                log_info("3-hour summary condition not met.")

            # Volatility check logic with 15-minute interval
            if last_volatility_check_time is None or (current_time - last_volatility_check_time) >= timedelta(minutes=15):
                log_info(f"Checking for volatility: last_checked_price={last_checked_price}, full_price={full_price}")
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
                
                last_volatility_check_time = current_time  # Update the last check time

            # Daily summary posting at 11 PM
            if current_hour == 2 and current_minute < 5:
                if daily_high is not None and daily_low is not None:
                    # Generate and post the daily summary
                    summary_text = generate_daily_summary_message(daily_high, daily_low)
                    try:
                        post_tweet(client, summary_text)
                        log_info(f"Daily summary tweet posted: {summary_text}")
                    except Exception as e:
                        log_error(f"Error posting daily summary tweet: {type(e).__name__} - {e}")

                    # Reset daily high and low for the next day
                    daily_high = None
                    daily_low = None
                    current_day = datetime.now().date()

            # Sleep for 1 minute before checking again for other conditions
            time.sleep(60)

        except Exception as e:
            log_error(f"An error occurred: {type(e).__name__} - {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
