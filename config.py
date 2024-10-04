import os
from dotenv import load_dotenv

load_dotenv()

# Twitter API credentials
CONSUMER_KEY = os.getenv("CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("CONSUMER_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BITSTAMP_MAIN_KEY = os.getenv("BITSTAMP_MAIN_KEY")
BITSTAMP_MAIN_SECRET = os.getenv("BITSTAMP_MAIN_SECRET")
BITSTAMP_KEY = os.getenv("BITSTAMP_KEY")
BITSTAMP_SECRET = os.getenv("BITSTAMP_SECRET")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# File to store the last tweet data
LAST_TWEET_FILE = 'last_tweet.json'
