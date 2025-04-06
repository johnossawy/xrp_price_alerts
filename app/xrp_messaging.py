import base64
import logging
import os
import glob
import time
from datetime import datetime, timedelta
from io import BytesIO

from PIL import Image  # Ensure Pillow is installed
import requests
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt

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
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return (
            f"📊 Daily Recap: Today's $XRP traded between a low of ${daily_low:.5f} and a high of ${daily_high:.5f}.\n"
            f"What's next for XRP? Stay tuned! 📈💥\n"
            f"Time: {timestamp}\n"
            f"#Ripple #XRP #XRPPriceAlerts"
        )
    return None


def generate_xrp_chart(rapidapi_key=None, db_handler=None):
    """
    Generate and save the XRP candlestick chart using data from the database.

    Args:
        rapidapi_key (str): Not used anymore, kept for backward compatibility.
        db_handler (DatabaseHandler): The database handler instance.

    Returns:
        str or None: The filename of the saved chart or None if failed.
    """
    try:
        if db_handler is None:
            logging.error("Database handler is required for chart generation.")
            return None

        # Calculate the time 3 hours ago
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=3)

        # Query the database for XRP price data in the last 3 hours
        query = """
            SELECT timestamp, last_price, volume
            FROM crypto_prices
            WHERE symbol = 'XRP' AND timestamp >= %(start_time)s
            ORDER BY timestamp ASC;
        """
        params = {'start_time': start_time}
        data = db_handler.fetch_all(query, params)

        if not data:
            logging.warning("No XRP data available for the last 3 hours.")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)

        # Use last_price for OHLC resampling
        df['price'] = pd.to_numeric(df['last_price'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

        # 🎯 Proper OHLC construction (based on real price action)
        ohlc = df['price'].resample('15min').ohlc()
        ohlc['volume'] = df['volume'].resample('15min').sum()
        ohlc.dropna(inplace=True)

        # 📈 Calculate Moving Averages
        ohlc['SMA_5'] = ohlc['close'].rolling(window=5).mean()
        ohlc['EMA_21'] = ohlc['close'].ewm(span=21, adjust=False).mean()

        # 🟠 Overlay EMA as a custom addplot
        ema_21_plot = mpf.make_addplot(
            ohlc['EMA_21'],
            color='orange',
            width=1.2,
            linestyle='--'
        )

        # Create and save chart
        chart_filename = f"xrp_candlestick_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

        # 🎨 Custom dark style
        custom_style = mpf.make_mpf_style(
            base_mpf_style='nightclouds',
            rc={
                "axes.labelcolor": "white",
                "xtick.color": "white",
                "ytick.color": "white",
            },
            marketcolors=mpf.make_marketcolors(
                up='green',
                down='red',
                edge='inherit',
                wick='inherit',
                volume='inherit',
                ohlc='inherit',
            )
        )

        # 🔹 Manually create both overlays for full control
        sma_5_plot = mpf.make_addplot(
            ohlc['SMA_5'],
            color='cyan',
            width=1.2,
            linestyle='-'
        )

        ema_21_plot = mpf.make_addplot(
            ohlc['EMA_21'],
            color='orange',
            width=1.2,
            linestyle='--'
        )

        # 🧠 Plot with full matplotlib access
        fig, axlist = mpf.plot(
            ohlc,
            type='candle',
            style=custom_style,
            title='XRP/USDT 3-Hour Price Movement',
            ylabel='Price (USDT)',
            volume=False,
            addplot=[sma_5_plot, ema_21_plot],  # Both overlays added manually
            returnfig=True
        )

        # 🎯 Get the plot handles for legend
        price_ax = axlist[0]
        sma_line = price_ax.lines[-2]  # Second last added line (SMA-5)
        ema_line = price_ax.lines[-1]  # Last added line (EMA-21)

        # 🏷️ Add accurate legend with correct colour + style
        price_ax.legend(
            [sma_line, ema_line],
            ['SMA-5 (cyan)', 'EMA-21 (orange dashed)'],
            loc='upper left',
            fontsize=8,
            facecolor='#111111',
            labelcolor='white',
            edgecolor='white'
        )

        # 💧 Add watermark
        price_ax.text(
            1.0, -0.12,
            '@xrppricealerts',
            transform=price_ax.transAxes,
            ha='right',
            va='top',
            fontsize=8,
            color='gray',
            alpha=0.7
        )

        # 💾 Save chart
        fig.savefig(chart_filename, bbox_inches='tight')
        plt.close(fig)

        logging.info(f"Chart saved as '{chart_filename}'.")
        return chart_filename

    except Exception as e:
        logging.error(f"An error occurred while generating the chart: {type(e).__name__} - {e}")

    return None

def generate_3_hour_summary(db_handler, current_price, rapidapi_key=None):
    """
    Generate a 3-hour summary based on the price data stored in the database and save the chart.

    Args:
        db_handler (DatabaseHandler): The database handler instance.
        current_price (float): The current price of XRP.
        rapidapi_key (str): Not used anymore, kept for backward compatibility.

    Returns:
        tuple or (None, None): The summary text and chart filename or (None, None) if failed.
    """
    try:
        # Calculate the time 3 hours ago
        end_time = datetime.now()
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

        # Generate the chart using data from the database
        chart_filename = generate_xrp_chart(rapidapi_key, db_handler)

        return summary_text, chart_filename

    except Exception as e:
        logging.error(f"Error generating 3-hour summary: {type(e).__name__} - {e}")
        return None, None


def cleanup_old_charts(directory='./', days=1):
    """
    Delete chart files older than a specified number of days.

    Args:
        directory (str): The directory to search for chart files.
        days (int): The age threshold in days. Files older than this will be deleted.
    """
    try:
        now = time.time()
        cutoff = now - (days * 86400)  # 86400 seconds in a day
        pattern = os.path.join(directory, 'xrp_candlestick_chart_*.png')
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
