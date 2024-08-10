import json  # Make sure to import the JSON module
import time
from app.twitter import get_twitter_client, post_tweet
from app.fetcher import fetch_xrp_price
from app.notifier import create_tweet_text, compare_tweets
from app.utils import load_last_tweet, save_last_tweet  # Ensure you're importing these if they exist in utils.py
from app.comparisons import ComparisonsGenerator, MessageGenerator
from config import CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, LAST_TWEET_FILE

def get_last_day_price(price_data):
    """
    Retrieves the price from 24 hours ago.
    
    :param price_data: The current price data dictionary returned by the API.
    :return: The price from 24 hours ago or None if not available.
    """
    open_24_price = price_data.get('open_24')
    if open_24_price is None:
        print("Warning: 'open_24' value is None or not present in the API response.")
        return None
    try:
        return float(open_24_price)
    except ValueError as e:
        print(f"Error converting 'open_24' to float: {e}")
        return None

def main():
    """Main function to run the bot"""
    client = get_twitter_client(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    
    comparisons_generator = ComparisonsGenerator()
    message_generator = MessageGenerator(coin_name="Ripple", coin_code="XRP")

    while True:
        print("Fetching price data...")
        price_data = fetch_xrp_price()
        if price_data:
            # Check if 'last' is in price_data and not None
            current_price_str = price_data.get('last')
            if current_price_str is None:
                print("Error: 'last' price is missing in the API response.")
                time.sleep(3600)
                continue
            
            try:
                current_price = float(current_price_str)
            except ValueError as e:
                print(f"Error converting 'last' to float: {e}")
                time.sleep(3600)
                continue
            
            # Use the open_24 value to get the last day price
            last_day_price = get_last_day_price(price_data)
            
            if last_day_price is None:
                print("Skipping tweet due to missing last day price.")
                time.sleep(3600)
                continue

            # Load the last tweet data, including the last hour price
            last_tweet_data = load_last_tweet()
            last_hour_price = None
            if last_tweet_data:
                last_tweet_text = last_tweet_data.get('text')
                last_hour_price = last_tweet_data.get('price')
                if last_hour_price is not None:
                    try:
                        comparisons_generator.set_last_tweet_price(float(last_hour_price))
                    except ValueError as e:
                        print(f"Error converting last hour price to float: {e}")
                        comparisons_generator.set_last_tweet_price(None)
            else:
                last_tweet_text = None

            # Get the hourly and daily comparisons
            comparisons = comparisons_generator.get_comparisons(current_price, last_day_price)

            # Add hourly comparison to the tweet
            if last_hour_price is not None:
                hourly_comparison = comparisons_generator.get_change(current_price, float(last_hour_price))
                comparisons.append({
                    'intro': 'In the last hour,',
                    'change': hourly_comparison
                })

            tweet_text = message_generator.create_message(current_price, comparisons)

            # Post the tweet if there's a significant change
            if not last_tweet_text or compare_tweets(tweet_text, last_tweet_text):
                post_tweet(client, tweet_text)
                save_last_tweet({'text': tweet_text, 'price': current_price})
            else:
                print("No significant change. Skipping tweet.")
        
        # Wait for 60 minutes before the next tweet
        time.sleep(3600)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {e}")
