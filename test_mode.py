from app.xrp_messaging import generate_3_hour_summary
from app.twitter import get_twitter_api, get_twitter_client, post_tweet, upload_media
from database_handler import DatabaseHandler
from config import ACCESS_TOKEN, ACCESS_TOKEN_SECRET, CONSUMER_KEY, CONSUMER_SECRET

if __name__ == "__main__":
    db_handler = DatabaseHandler()
    client = get_twitter_client(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = get_twitter_api(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

    current_price = float(input("Enter current XRP price: "))

    summary_text, chart_filename = generate_3_hour_summary(db_handler, current_price)

    if summary_text and chart_filename:
        media_id = upload_media(api, chart_filename)
        post_tweet(client, summary_text, media_id)
        print("✅ Test tweet posted!")
    else:
        print("❌ Failed to generate summary or chart.")
