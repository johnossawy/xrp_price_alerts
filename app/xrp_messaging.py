from datetime import datetime

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
        return f"📊 Daily Summary: Today’s XRP price ranged between ${daily_low:.5f} and ${daily_high:.5f}. #Ripple #XRP"
    return None
