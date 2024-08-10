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

def post_tweet(client, tweet_text):
    """Post the tweet using Twitter API v2"""
    try:
        print("Attempting to post tweet...")
        response = client.create_tweet(text=tweet_text)
        print(f"Tweet posted: {tweet_text}")
        return response
    except tweepy.errors.TweepyException as e:
        print(f"Tweepy error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")