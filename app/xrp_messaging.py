import csv
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

def generate_3_hour_summary(csv_file, current_price):
    """Generate a 3-hour summary based on the price data stored in the CSV file."""
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
        return (
            f"🔔🕒 #XRP Price in last 3 hours: {percent_change:+.2f}% change\n"
            f"Support around ${support:.5f}\n"
            f"Resistance around ${resistance:.5f}\n"
            f"Last $XRP Price: ${current_price:.5f}\n#Ripple #XRP #XRPPriceAlerts"
        )
    return None
