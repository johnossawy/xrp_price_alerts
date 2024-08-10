class ComparisonsGenerator:
    def __init__(self):
        self.last_tweet_price = None

    @staticmethod
    def add_comparison(comparisons_list, comparison):
        if comparison['change']['price'] != 0:
            comparisons_list.append(comparison)

    @staticmethod
    def get_change(current_price, previous_price):
        price_change = current_price - previous_price
        percent_change = (price_change / previous_price) * 100 if previous_price != 0 else 0
        return {'price': price_change, 'percent': percent_change}

    def get_comparisons(self, current_price, last_day_price):
        comparisons = []

        # Comparison with the last tweet
        if self.last_tweet_price is not None:
            comparison = {
                'intro': 'Compared to the last tweet,',
                'change': self.get_change(current_price, self.last_tweet_price)
            }
            self.add_comparison(comparisons, comparison)

        # Comparison with the last 24 hours
        comparison = {
            'intro': 'In the last 24 hours',
            'change': self.get_change(current_price, last_day_price)
        }
        self.add_comparison(comparisons, comparison)

        return comparisons

    def set_last_tweet_price(self, price):
        self.last_tweet_price = price

class MessageGenerator:
    def __init__(self, coin_name, coin_code, decimals_amount=2, has_hashtags=True):
        self.coin_name = coin_name
        self.coin_code = coin_code
        self.decimals_amount = decimals_amount
        self.has_hashtags = has_hashtags

    def format(self, number, is_percentage=False):
        absolute_number = abs(number)
        formatted_number = f"{absolute_number:.{self.decimals_amount}f}"
        return formatted_number

    def create_comparison_message(self, comparison):
        change = comparison['change']
        formatted_price = self.format(change['price'])
        formatted_percent = self.format(change['percent'], is_percentage=True)
        return f"{'🟢' if change['price'] > 0 else '🔴'} {comparison['intro']} the price has {'increased' if change['price'] > 0 else 'dropped'} by ${formatted_price} ({formatted_percent}%).\n"

    def get_hashtags(self):
        hashtags = ''
        if self.has_hashtags:
            hashtags += f"#{self.coin_name.capitalize()}"
            if self.coin_code != self.coin_name:
                hashtags += f" #{self.coin_code}"
        return hashtags

    def get_comparisons_messages(self, comparisons):
        message = ''
        for comparison in comparisons:
            message += self.create_comparison_message(comparison)
        return message

    def create_message(self, price, comparisons):
        formatted_price = self.format(price)

        message = f"The ${self.coin_code} price is at ${formatted_price} right now.\n"
        message += self.get_comparisons_messages(comparisons)
        message += f"\n{self.get_hashtags()}"

        return message
