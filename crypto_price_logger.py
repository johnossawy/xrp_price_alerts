import requests
import csv
import time
from datetime import datetime
import random

# URLs for Bitstamp API
BTC_URL = "https://www.bitstamp.net/api/v2/ticker/btcusd/"
ETH_URL = "https://www.bitstamp.net/api/v2/ticker/ethusd/"

# CSV file names
BTC_CSV_FILE = 'btc_price_data.csv'
ETH_CSV_FILE = 'eth_price_data.csv'

# Utility function to calculate percent change
def calculate_percent_change(previous_price, current_price):
    if previous_price != 0:
        return ((current_price - previous_price) / previous_price) * 100
    else:
        return None

def fetch_price(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return None

def get_last_price_from_csv(file_name):
    try:
        with open(file_name, 'r') as csvfile:
            reader = list(csv.DictReader(csvfile))
            if len(reader) > 0:
                return float(reader[-1]['last'])
    except Exception as e:
        print(f"Error reading last price from {file_name}: {e}")
    return None

def append_to_csv(file_name, data):
    fieldnames = [
        'timestamp', 'last', 'high', 'low', 'vwap', 'volume', 
        'bid', 'ask', 'open', 'percent_change_24h', 'percent_change'
    ]
    
    try:
        with open(file_name, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if csvfile.tell() == 0:
                writer.writeheader()  # Write the header only if the file is empty
            writer.writerow(data)
    except Exception as e:
        print(f"Error writing to {file_name}: {e}")

def log_crypto_prices():
    retry_count = 0
    max_retries = 5
    base_sleep_time = 2  # Base time to wait between retries (in seconds)

    while True:
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # BTC/USD price logging
            btc_data = fetch_price(BTC_URL)
            if btc_data:
                previous_btc_price = get_last_price_from_csv(BTC_CSV_FILE)
                current_btc_price = float(btc_data['last'])
                percent_change = calculate_percent_change(previous_btc_price, current_btc_price) if previous_btc_price else 'N/A'
                btc_data_formatted = {
                    'timestamp': current_time,
                    'last': current_btc_price,
                    'high': btc_data['high'],
                    'low': btc_data['low'],
                    'vwap': btc_data['vwap'],
                    'volume': btc_data['volume'],
                    'bid': btc_data['bid'],
                    'ask': btc_data['ask'],
                    'open': btc_data['open'],
                    'percent_change_24h': btc_data.get('percent_change', 'N/A'),
                    'percent_change': percent_change
                }
                append_to_csv(BTC_CSV_FILE, btc_data_formatted)
                print(f"Logged BTC/USD data at {current_time}")

            # ETH/USD price logging
            eth_data = fetch_price(ETH_URL)
            if eth_data:
                previous_eth_price = get_last_price_from_csv(ETH_CSV_FILE)
                current_eth_price = float(eth_data['last'])
                percent_change = calculate_percent_change(previous_eth_price, current_eth_price) if previous_eth_price else 'N/A'
                eth_data_formatted = {
                    'timestamp': current_time,
                    'last': current_eth_price,
                    'high': eth_data['high'],
                    'low': eth_data['low'],
                    'vwap': eth_data['vwap'],
                    'volume': eth_data['volume'],
                    'bid': eth_data['bid'],
                    'ask': eth_data['ask'],
                    'open': eth_data['open'],
                    'percent_change_24h': eth_data.get('percent_change', 'N/A'),
                    'percent_change': percent_change
                }
                append_to_csv(ETH_CSV_FILE, eth_data_formatted)
                print(f"Logged ETH/USD data at {current_time}")

            # Reset retry count on successful fetch
            retry_count = 0

        except Exception as e:
            retry_count += 1
            sleep_time = base_sleep_time * (2 ** retry_count) + random.uniform(0, 1)  # Exponential backoff with jitter
            print(f"Error occurred: {e}. Retrying in {sleep_time:.2f} seconds... (Attempt {retry_count}/{max_retries})")

            if retry_count >= max_retries:
                print("Max retries reached. Waiting for the next cycle.")
                retry_count = 0

            time.sleep(sleep_time)

        # Wait for a minute before fetching the prices again
        time.sleep(60)

if __name__ == "__main__":
    log_crypto_prices()
