import json
from config import LAST_TWEET_FILE

def load_last_tweet():
    """Load the last tweet data from file"""
    try:
        with open(LAST_TWEET_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return None
    
def save_last_tweet(data):
    """Save the last tweet data to file, including both text and price"""
    with open(LAST_TWEET_FILE, 'w') as file:
        json.dump(data, file)
