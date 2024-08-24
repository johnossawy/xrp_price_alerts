import csv
import requests
import base64
from PIL import Image
from io import BytesIO
from datetime import datetime, timedelta

ALL_TIME_HIGH_PRICE = 3.65

def get_percent_change(old_price, new_price):
    if old_price != 0:
        return ((new_price - old_price) / old_price) * 100
    else:
        return 0

def generate_message(last_price, current_price, is_volatility_alert=False):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    percent_change = get_percent_change(last_price, current_price)
    
    log_info(f"Generating message: last_price={last_price}, current_price={current_price}, percent_change={percent_change:.2f}%")

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
        return f"🔔📉 $XRP is DOWN -{abs(percent_change):.2f}% over the last hour to ${current_price:.2f}!\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"

def generate_daily_summary_message(daily_high, daily_low):
    """Generate a message summarizing the day's price range."""
    if daily_high is not None and daily_low is not None:
        return f"📊 Daily Summary: Today’s XRP price ranged between ${daily_low:.5f} and ${daily_high:.5f}. \n#Ripple #XRP #XRPPriceAlerts"
    return None

def generate_3_hour_summary(csv_file, current_price, rapidapi_key):
    """Generate a 3-hour summary based on the price data stored in the CSV file and save the chart."""
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=3)
    
    support = None
    resistance = None
    three_hours_ago_price = None

    with open(csv_file, 'r') as csvfile:
        csv_reader = csv.DictReader(csvfile)
        for row in csv_reader:
            timestamp = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
            price = float(row['last_price'])

            if start_time <= timestamp <= end_time:
                if support is None or price < support:
                    support = price
                if resistance is None or price > resistance:
                    resistance = price
                if three_hours_ago_price is None:
                    three_hours_ago_price = price

    if three_hours_ago_price is not None and support is not None and resistance is not None:
        percent_change = get_percent_change(three_hours_ago_price, current_price)

        # Generate the summary text
        summary_text = (
            f"🔔🕒 #XRP Price in last 3 hours: {percent_change:+.2f}% change\n"
            f"Support around ${support:.5f}\n"
            f"Resistance around ${resistance:.5f}\n"
            f"Last $XRP Price: ${current_price:.5f}\nTime: {timestamp}\n#Ripple #XRP #XRPPriceAlerts"
        )

        # Generate the chart
        chart_filename = generate_xrp_chart(rapidapi_key)

        return summary_text, chart_filename
    return None, None

def generate_xrp_chart(rapidapi_key):
    """Generate and save the XRP chart over the last 3 hours."""
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
                chart_filename = 'candlestick_chart.png'
                image.save(chart_filename)
                print(f"Chart saved as '{chart_filename}'.")
                return chart_filename
            else:
                print("No image data found in the response.")
        else:
            print(f"Failed to fetch candlestick chart: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"An error occurred while generating the chart: {e}")

    return None