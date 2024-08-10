def create_tweet_text(price_data):
    """Format tweet text with XRP price data"""
    if price_data:
        last_price = price_data['last']
        percent_change_24 = price_data['percent_change_24']
        tweet_text = (
            f"📈 XRP Price Update:\n"
            f"💵 Last Price: ${last_price}\n"
            f"🔺 24h Change: {percent_change_24}%\n"
        )
        return tweet_text
    else:
        return None
    
def compare_tweets(current_tweet_text, last_tweet_text):
    """Compare the current tweet text with the last tweet text"""
    return current_tweet_text != last_tweet_text