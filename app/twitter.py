import tweepy
import tweepy.errors

def get_twitter_client(api_key, api_secret, access_token, access_token_secret) -> tweepy.Client:
    """Get Twitter client"""
    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )
    return client

def upload_media(client, filename):
    """Upload media to Twitter and return the media ID"""
    try:
        media = client.media_upload(filename=filename)
        return media.media_id_string
    except tweepy.errors.TweepyException as e:
        print(f"Tweepy error occurred during media upload: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during media upload: {e}")
    return None

def post_tweet(client, tweet_text, media_id=None):
    """Post the tweet using Twitter API v2"""
    try:
        print("Attempting to post tweet...")
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