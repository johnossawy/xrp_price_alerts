import tweepy
import tweepy.errors
import logging
import time

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
    """Upload media to Twitter and return media_id"""
    try:
        media = api.media_upload(filename=filename)
        return media.media_id_string
    except tweepy.TweepyException as e:
        logging.error(f"Tweepy error during media upload: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error during media upload: {e}")
        return None

def post_tweet(client, tweet_text, media_id=None):
    """Post the tweet using Twitter API v2"""
    try:
        if media_id:
            response = client.create_tweet(text=tweet_text, media_ids=[media_id])
        else:
            response = client.create_tweet(text=tweet_text)
        logging.info(f"Tweet posted: {tweet_text}")
        return response
    except tweepy.TooManyRequests as e:
        logging.warning("Rate limit reached. Sleeping for 15 minutes.")
        time.sleep(900)  # Sleep for 15 minutes
        return post_tweet(client, tweet_text, media_id)
    except tweepy.TweepyException as e:
        logging.error(f"Tweepy error occurred: {e}")
    except Exception as e:
        logging.error(f"Unexpected error occurred: {e}")
    return None
