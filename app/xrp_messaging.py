# app/xrp_messaging.py

import base64
import logging
import os
import glob
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO

import matplotlib.pyplot as plt
from PIL import Image  # Ensure Pillow is installed
import requests

# Assuming 'log_info' from 'app.xrp_logger' is a wrapper around the logger
from app.xrp_logger import log_info

# Constants
ALL_TIME_HIGH_PRICE = 3.65  # Update this value as per your requirements


def get_percent_change(old_price, new_price):
    """Calculate the percentage change between two prices."""
    if old_price != 0 and old_price is not None:
        return ((new_price - old_price) / old_price) * 100
    else:
        return 0


def generate_message(last_price, current_price, is_volatility_alert=False):
    """
    Generate a tweet message based on price movements.

    Args:
        last_price (float): The previous price.
        current_price (float): The current price.
        is_volatility_alert (bool): Flag to indicate if this is a volatility alert.

    Returns:
        str: The generated tweet message.
    """
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    percent_change = get_percent_change(last_price, current_price)

    log_info(f"Generating message: last_price={last_price}, current_price={current_price}, percent_change={percent_change:.2f}%")

    if current_price > ALL_TIME_HIGH_PRICE:
        return (
            f"🚀🔥 $XRP just smashed through its all-time high, now trading at an unbelievable ${current_price:.2f}! 🚀🔥\n"
            f"Can you feel the excitement? 📈\n"
            f"Time: {timestamp}\n"
            f"#Ripple #XRP #XRPATH #ToTheMoon"
        )
    elif is_volatility_alert:
        direction = "UP" if current_price > last_price else "DOWN"
        emoji = "📈" if direction == "UP" else "📉"
        return f"⚡️ $XRP is experiencing volatility! It's {direction} by {abs(percent_change):.2f}% to ${current_price:.2f} {emoji}\nTime: {timestamp}\n#Ripple #XRP #XRPVolatility"
    elif current_price == last_price:
        return f"🔔❗️ $XRP has retained a value of ${current_price:.2f} over the last hour.\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
    elif current_price > last_price:
        return f"🔔📈 $XRP is UP {percent_change:.2f}% over the last hour to ${current_price:.2f}!\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
    else:
        return f"🔔📉 $XRP is DOWN -{abs(percent_change):.2f}% over the last hour to ${current_price:.2f}!\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"


def generate_daily_summary_message(daily_high, daily_low):
    """
    Generate a daily summary tweet message.

    Args:
        daily_high (float): The highest price of the day.
        daily_low (float): The lowest price of the day.

    Returns:
        str or None: The generated daily summary message or None if data is insufficient.
    """
    if daily_high is not None and daily_low is not None:
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        return (
            f"📊 Daily Recap: Today’s $XRP traded between a low of ${daily_low:.5f} and a high of ${daily_high:.5f}.\n"
            f"What's next for XRP? Stay tuned! 📈💥\n"
            f"Time: {timestamp}\n"
            f"#Ripple #XRP #XRPPriceAlerts"
        )
    return None


def generate_3_hour_summary(db_handler, current_price, rapidapi_key):
    """
    Generate a 3-hour summary based on the price data stored in the database and save the chart.

    Args:
        db_handler (DatabaseHandler): The database handler instance.
        current_price (float): The current price of XRP.
        rapidapi_key (str): The RapidAPI key for external API calls (if needed).

    Returns:
        tuple or (None, None): The summary text and chart filename or (None, None) if failed.
    """
    try:
        # Calculate the time 3 hours ago
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=3)

        # Query the database for XRP price data in the last 3 hours
        query = """
            SELECT timestamp, last_price FROM crypto_prices
            WHERE symbol = 'XRP' AND timestamp >= %(start_time)s
            ORDER BY timestamp ASC;
        """
        params = {'start_time': start_time}
        data = db_handler.fetch_all(query, params)

        if not data:
            logging.warning("No XRP data available for the last 3 hours.")
            return None, None

        # Prepare data for chart generation
        timestamps = [row['timestamp'] for row in data]
        prices = [float(row['last_price']) for row in data]

        # Determine support and resistance levels
        support = min(prices)
        resistance = max(prices)
        three_hours_ago_price = prices[0]

        percent_change = get_percent_change(three_hours_ago_price, current_price)

        # Generate the summary text
        summary_text = (
            f"🔔🕒 3-Hour XRP Update: Price has changed by {percent_change:+.2f}%.\n"
            f"Support level at: ${support:.5f}\n"
            f"Resistance level at: ${resistance:.5f}\n"
            f"Current Price: ${current_price:.5f}\nTime: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"#Ripple #XRP #XRPPriceAlerts"
        )

        # Generate the chart
        chart_filename = create_xrp_chart(timestamps, prices)

        return summary_text, chart_filename

    except Exception as e:
        logging.error(f"Error generating 3-hour summary: {type(e).__name__} - {e}")
        return None, None


def create_xrp_chart(timestamps, prices):
    """
    Generate and save the XRP chart over the last 3 hours.

    Args:
        timestamps (list of datetime): The timestamps of the price data.
        prices (list of float): The corresponding prices of XRP.

    Returns:
        str or None: The filename of the saved chart or None if failed.
    """
    try:
        plt.figure(figsize=(10, 5))
        plt.plot(timestamps, prices, marker='o', linestyle='-', color='blue')
        plt.title('XRP Price Over Last 3 Hours')
        plt.xlabel('Time')
        plt.ylabel('Price (USD)')
        plt.grid(True)
        plt.tight_layout()

        # Format x-axis for better readability
        plt.gcf().autofmt_xdate()

        # Save the chart to a BytesIO buffer
        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        plt.close()
        buffer.seek(0)

        # Save the image to disk
        timestamp_str = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        chart_filename = f"xrp_price_chart_{timestamp_str}.png"
        with open(chart_filename, 'wb') as f:
            f.write(buffer.read())

        logging.info(f"Price chart saved as '{chart_filename}'.")
        return chart_filename

    except Exception as e:
        logging.error(f"Error creating price chart: {type(e).__name__} - {e}")
        return None


def generate_xrp_chart_external(rapidapi_key):
    """
    Generate and save the XRP chart using an external API (if preferred).

    Args:
        rapidapi_key (str): The RapidAPI key for external API calls.

    Returns:
        str or None: The filename of the saved chart or None if failed.
    """
    url = 'https://candlestick-chart.p.rapidapi.com/binance'
    querystring = {'symbol': 'XRPUSDT', 'interval': '15m', 'limit': '16'}
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'x-rapidapi-host': 'candlestick-chart.p.rapidapi.com',
        'x-rapidapi-key': rapidapi_key  # Use the key passed as an argument
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)

        if response.status_code == 200:
            data = response.json()
            base64_image = data.get('chartImage')

            if base64_image:
                image_data = base64.b64decode(base64_image)
                image = Image.open(BytesIO(image_data))
                timestamp_str = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                chart_filename = f"candlestick_chart_{timestamp_str}.png"
                image.save(chart_filename)
                logging.info(f"Chart saved as '{chart_filename}'.")
                return chart_filename
            else:
                logging.error("No image data found in the response.")
        else:
            logging.error(f"Failed to fetch candlestick chart: {response.status_code}")
            logging.error(response.text)
    except Exception as e:
        logging.error(f"An error occurred while generating the chart: {type(e).__name__} - {e}")

    return None


def cleanup_old_charts(directory='.', days=7):
    """
    Delete chart files older than a specified number of days.

    Args:
        directory (str): The directory to search for chart files.
        days (int): The age threshold in days. Files older than this will be deleted.
    """
    try:
        now = time.time()
        cutoff = now - (days * 86400)  # 86400 seconds in a day
        pattern = os.path.join(directory, 'xrp_price_chart_*.png')
        files = glob.glob(pattern)

        deleted_files = []

        for file_path in files:
            if os.path.isfile(file_path):
                file_mtime = os.path.getmtime(file_path)
                if file_mtime < cutoff:
                    os.remove(file_path)
                    deleted_files.append(file_path)

        if deleted_files:
            log_info(f"Deleted old chart files: {deleted_files}")
        else:
            log_info("No old chart files to delete.")

    except Exception as e:
        logging.error(f"Error during cleanup of old charts: {type(e).__name__} - {e}")
