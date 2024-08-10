import requests

def fetch_xrp_price():
    """Fetch the current XRP price from Bitstamp API"""
    url = "https://www.bitstamp.net/api/v2/ticker/xrpusd/"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.RequestException as e:
        print(f"Error fetching XRP price: {e}")
        return None