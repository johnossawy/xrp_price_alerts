import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD  # Import DB credentials

class Backtest:
    def __init__(self, initial_capital, overbought_threshold, oversold_threshold, stop_loss, take_profit, trailing_stop_loss):
        self.initial_capital = initial_capital
        self.overbought_threshold = overbought_threshold
        self.oversold_threshold = oversold_threshold
        self.stop_loss_threshold = stop_loss
        self.take_profit_threshold = take_profit
        self.trailing_stop_loss_percentage = trailing_stop_loss
        self.reset()

    def reset(self):
        self.capital = self.initial_capital
        self.in_position = False
        self.buy_price = None
        self.buy_time = None
        self.trailing_stop_price = None
        self.total_trades = 0
        self.total_profit_loss = 0.0

    def calculate_profit_loss(self, buy_price, sell_price):
        return (sell_price - buy_price) * (self.capital / buy_price)

    def print_trade_summary(self, sell_price, vwap, buy_price, buy_time, sell_time, trade_profit_loss):
        time_held = sell_time - buy_time
        print(f"🚨 Sell Signal Triggered: Sold at ${sell_price:.5f} (VWAP: ${vwap:.5f}) on {sell_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Trade Result: Profit/Loss = ${trade_profit_loss:.2f}, Time Held = {time_held}")
        print(f"   Updated Capital: ${self.capital:.2f}\n")

    def adjust_thresholds(self, df):
        df['price_change'] = df['last_price'].pct_change()
        volatility = df['price_change'].std()
        self.overbought_threshold *= (1 + volatility)
        self.oversold_threshold *= (1 - volatility)

    def process_row(self, row):
        price = row['last_price']
        vwap = row['vwap']
        timestamp = row['timestamp']

        if not self.in_position and (price - vwap) / vwap <= self.oversold_threshold:
            self.buy_price = price
            self.buy_time = timestamp
            self.trailing_stop_price = self.buy_price * (1 - self.trailing_stop_loss_percentage)
            self.in_position = True
            print(f"⚠️ Buy Signal Triggered: Bought at ${self.buy_price:.5f} (VWAP: ${vwap:.5f}) on {self.buy_time.strftime('%Y-%m-%d %H:%M:%S')}")

        if self.in_position:
            price_change = (price - self.buy_price) / self.buy_price
            if price_change >= self.take_profit_threshold or price <= self.trailing_stop_price:
                trade_profit_loss = self.calculate_profit_loss(self.buy_price, price)
                self.capital += trade_profit_loss
                self.print_trade_summary(price, vwap, self.buy_price, self.buy_time, timestamp, trade_profit_loss)
                self.in_position = False
                self.total_trades += 1
                self.total_profit_loss += trade_profit_loss
            else:
                if price > self.buy_price * (1 + self.trailing_stop_loss_percentage):
                    self.trailing_stop_price = max(self.trailing_stop_price, price * (1 - self.trailing_stop_loss_percentage))

    def run(self, df):
        self.adjust_thresholds(df)
        df.apply(self.process_row, axis=1)

        print("Backtesting Complete")
        print(f"Total Trades: {self.total_trades}")
        print(f"Total Profit/Loss: ${self.total_profit_loss:.2f}")
        print(f"Final Capital: ${self.capital:.2f}")

def fetch_data_from_db():
    """
    Fetches BTC price data from the PostgreSQL database.
    Returns a pandas DataFrame.
    """
    # Create a connection string using the environmental variables from config.py
    db_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    # Create a connection to the database
    engine = create_engine(db_url)

    # SQL query to get the data from the database
    query = """
        SELECT timestamp, last_price, vwap
        FROM crypto_prices
        WHERE symbol = 'BTC'
        ORDER BY timestamp ASC;
    """

    # Read data from the database into a DataFrame
    df = pd.read_sql(query, con=engine)

    # Ensure that 'timestamp' is treated as a datetime object
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    return df

def main():
    # Define your initial thresholds and parameters
    initial_capital = 12800
    initial_overbought_threshold = 0.01
    initial_oversold_threshold = -0.019
    stop_loss_threshold = -0.02
    take_profit_threshold = 0.015
    trailing_stop_loss_percentage = 0.005  # 0.5% trailing stop loss

    # Create the Backtest object with the specified parameters
    backtest = Backtest(
        initial_capital=initial_capital,
        overbought_threshold=initial_overbought_threshold,
        oversold_threshold=initial_oversold_threshold,
        stop_loss=stop_loss_threshold,
        take_profit=take_profit_threshold,
        trailing_stop_loss=trailing_stop_loss_percentage
    )

    # Fetch data from the database
    df = fetch_data_from_db()

    # Run the backtest
    backtest.run(df)

if __name__ == "__main__":
    main()
