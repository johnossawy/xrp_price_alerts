import tweepy
import tweepy.errors
import logging
import time
import requests

def get_twitter_client(api_key, api_secret, access_token, access_token_secret):
    """Get Twitter client"""
    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )
    return client

def get_twitter_api(api_key, api_secret, access_token, access_token_secret):
    """Get Twitter API for media uploads"""
    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
    api = tweepy.API(auth)
    return api

def upload_media(api, filename):
    """Upload media to Twitter using v2 endpoint and return media_id"""
    url = "https://api.x.com/2/media/upload"
    try:
        files = {'media': open(filename, 'rb')}
        headers = {'Authorization': f'Bearer {api.auth.access_token}'}
        response = requests.post(url, files=files, headers=headers)
        if response.status_code == 200:
            media_id = response.json()['media_id']
            logging.info(f"Media uploaded successfully: {media_id}")
            return media_id
        else:
            logging.error(f"Error uploading media: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error during media upload: {e}")
        return None

def post_tweet(client, tweet_text, media_id=None):
    """Post the tweet using Twitter API v2"""
    url = "https://api.x.com/2/posts"
    try:
        payload = {"status": tweet_text}
        if media_id:
            payload["media_ids"] = [media_id]
        
        headers = {
            "Authorization": f"Bearer {client.access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 201:
            logging.info(f"Tweet posted: {tweet_text}")
            return response.json()
        else:
            logging.error(f"Error posting tweet: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error during tweet posting: {e}")
    return None
