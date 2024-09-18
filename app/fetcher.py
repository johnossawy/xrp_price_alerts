import requests
import logging

def fetch_xrp_price():
    """Fetch the current XRP price from Bitstamp API"""
    url = "https://www.bitstamp.net/api/v2/ticker/xrpusd/"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'last' not in data:
            logging.error("Key 'last' not found in response data.")
            return None
        return data
    except requests.Timeout:
        logging.error("Request timed out while fetching XRP price.")
    except requests.RequestException as e:
        logging.error(f"RequestException while fetching XRP price: {e}")
    except ValueError as e:
        logging.error(f"JSON decoding failed: {e}")
    if not isinstance(data.get('last'), str) or not data['last'].replace('.', '', 1).isdigit():
        logging.error("Invalid 'last' price format in response data.")
        return None
    return data
