import tweepy
import tweepy.errors

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
    except tweepy.errors.TweepyException as e:
        print(f"Tweepy error occurred during media upload: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during media upload: {e}")

def post_tweet(client, tweet_text, media_id=None):
    """Post the tweet using Twitter API v2"""
    try:
        if media_id:
            response = client.create_tweet(text=tweet_text, media_ids=[media_id])
        else:
            response = client.create_tweet(text=tweet_text)
        print(f"Tweet posted: {tweet_text}")
        return response
    except tweepy.errors.TweepyException as e:
        print(f"Tweepy error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
