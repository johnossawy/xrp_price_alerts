import requests
import logging
import time
from requests.exceptions import RequestException
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

def send_telegram_message(message, retries=3, backoff_factor=2):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    for attempt in range(retries):
        try:
            response = requests.post(url, data=payload)
            response.raise_for_status()
            logger.info("Telegram message sent successfully.")
            return response.json()
        except RequestException as e:
            wait = backoff_factor ** attempt
            logger.error(f"Attempt {attempt+1}: Failed to send message: {e}. Retrying in {wait} seconds.")
            time.sleep(wait)
    logger.error("All retry attempts failed.")
    return None
