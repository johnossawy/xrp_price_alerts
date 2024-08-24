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

# Define the CSV file for storing price data and the JSON file for last summary time
CSV_FILE = 'xrp_price_data.csv'
LAST_SUMMARY_FILE = 'last_summary_time.json'

# Initialize tracking variables
daily_high = None
daily_low = None
current_day = datetime.now().date()
last_summary_time = None  # Initialize to None
last_volatility_check_time = None  # Initialize for tracking the last volatility check time

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
    global daily_high, daily_low, current_day, last_summary_time, last_volatility_check_time
    last_full_price = None  # For logging purposes
    last_rounded_price = None  # For messaging purposes
    last_tweet_hour = None
    last_checked_price = None

    # Load the last summary time
    last_summary_time = load_last_summary_time()

    while True:
        try:
            current_time = datetime.now()
            current_hour = current_time.hour
            current_minute = current_time.minute
            timestamp = current_time.strftime('%Y-%m-%d %H:%M:%S')

            log_info(f"Checking time: Hour={current_hour}, Minute={current_minute}")

            # Reset daily high and low if a new day has started
            if current_time.date() != current_day:
                daily_summary = generate_daily_summary_message(daily_high, daily_low)
                if daily_summary:
                    try:
                        post_tweet(client, daily_summary)
                        log_info(f"Daily summary tweet posted: {daily_summary}")
                    except Exception as e:
                        log_error(f"Error posting daily summary tweet: {type(e).__name__} - {e}")
                
                daily_high = None
                daily_low = None
                current_day = current_time.date()

            # Fetch price data
            price_data = fetch_xrp_price()

            if not price_data or 'last' not in price_data:
                log_warning("Failed to fetch price data.")
                time.sleep(120)
                continue

            full_price = float(price_data['last'])
            rounded_price = round(full_price, 2)

            # Update daily high and low
            if daily_high is None or full_price > daily_high:
                daily_high = full_price
            if daily_low is None or full_price < daily_low:
                daily_low = full_price

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
                else:
                    log_warning("last_rounded_price is None, skipping hourly tweet.")

            # Generate and post 3-hour summary tweet with chart at specified times with 5-minute grace period
            log_info(f"Checking 3-hour summary condition: Current Hour={current_hour}, Minute={current_minute}, Last Summary Hour={last_summary_time}")
            if (current_hour, current_minute) in SUMMARY_TIMES and (last_summary_time is None or last_summary_time != current_hour):
                if current_minute < 5:  # Allow a 5-minute window to post the 3-hour summary
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
                            except Exception as e:
                                log_error(f"Error posting 3-hour summary tweet with chart: {type(e).__name__} - {e}")
                        else:
                            log_error("3-hour summary generation failed: No summary text or chart filename generated.")
                    except Exception as e:
                        log_error(f"Error during 3-hour summary generation: {type(e).__name__} - {e}")

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

            # Update last_rounded_price for next hour's comparison
            last_rounded_price = rounded_price

            # Sleep for 2 minutes before checking again for other conditions
            time.sleep(120)

        except Exception as e:
            log_error(f"An error occurred: {type(e).__name__} - {e}")
            time.sleep(120)

if __name__ == "__main__":
    main()
