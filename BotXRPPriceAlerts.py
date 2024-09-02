import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, CallbackQueryHandler, ConversationHandler, Filters
import pandas as pd
from config import TELEGRAM_BOT_TOKEN  # Importing from config file

# Ensure TELEGRAM_BOT_TOKEN is not None or an empty string
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set")

updater = Updater(TELEGRAM_BOT_TOKEN)

# File paths
PRICE_DATA_FILE = 'xrp_price_data.csv'
SIGNALS_LOG_FILE = 'live_trading_signals.log'
ALERTS_FILE = 'user_price_alerts.json'
PORTFOLIO_FILE = 'user_portfolios.json'

# Load or initialize portfolios
if os.path.exists(PORTFOLIO_FILE):
    with open(PORTFOLIO_FILE, 'r') as f:
        portfolios = json.load(f)
else:
    portfolios = {}

# Load or initialize price alerts
if os.path.exists(ALERTS_FILE):
    with open(ALERTS_FILE, 'r') as f:
        price_alerts = json.load(f)
else:
    price_alerts = {}

# Save portfolios to a file
def save_portfolios():
    with open(PORTFOLIO_FILE, 'w') as f:
        json.dump(portfolios, f)

# Save price alerts to a file
def save_price_alerts():
    with open(ALERTS_FILE, 'w') as f:
        json.dump(price_alerts, f)

# Function to retrieve the current XRP price
def get_xrp_price():
    df = pd.read_csv(PRICE_DATA_FILE)
    last_row = df.iloc[-1]
    price = last_row['last_price']
    return price

# Function to retrieve the last trading signal
def get_last_signal():
    with open(SIGNALS_LOG_FILE, 'rb') as f:
        # Move the pointer to the end of the file
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        buffer_size = 1024
        if file_size < buffer_size:
            buffer_size = file_size
        f.seek(-buffer_size, os.SEEK_END)
        buffer = f.read().decode('utf-8')
        lines = buffer.splitlines()
        last_signal = lines[-1] if lines else "No signals logged yet."
    return last_signal

# Command handler to set an alert
def set_alert(update: Update, context: CallbackContext) -> None:
    chat_id = str(update.message.chat_id)
    try:
        target_price = float(context.args[0])
        price_alerts[chat_id] = target_price
        save_price_alerts()
        update.message.reply_text(f"Alert set for XRP price at ${target_price:.3f}.")
    except (IndexError, ValueError):
        update.message.reply_text("Usage: /setalert <price>")

# Command handler to view the user's set alert
def view_alert(update: Update, context: CallbackContext) -> None:
    chat_id = str(update.message.chat_id)
    if chat_id in price_alerts:
        alert_price = price_alerts[chat_id]
        update.message.reply_text(f"Your current price alert is set at ${alert_price:.3f}.")
    else:
        update.message.reply_text("You have no price alerts set. Use /setalert <price> to set one.")

# Command handler to set the user's starting capital
def set_capital(update: Update, context: CallbackContext) -> None:
    chat_id = str(update.message.chat_id)
    try:
        starting_capital = float(context.args[0])
        portfolios[chat_id] = {
            'capital': starting_capital,
            'position': None,  # No open position
            'entry_price': None,
            'profit_loss': 0.0
        }
        save_portfolios()
        update.message.reply_text(f"Starting capital set to ${starting_capital:.2f}.")
    except (IndexError, ValueError):
        update.message.reply_text("Usage: /setcapital <amount>")

# Function to update portfolio on a buy signal
def buy_signal(chat_id, price):
    portfolio = portfolios.get(str(chat_id))
    if portfolio and portfolio['position'] is None:  # No open position
        portfolio['position'] = 'long'
        portfolio['entry_price'] = price
        save_portfolios()
        return f"⚠️ *Buy Signal Triggered*\nBought at: ${price:.3f}\nCapital: ${portfolio['capital']:.2f}"
    return None

# Function to update portfolio on a sell signal
def sell_signal(chat_id, price):
    portfolio = portfolios.get(str(chat_id))
    if portfolio and portfolio['position'] == 'long':  # Must have an open position to sell
        price_change = (price - portfolio['entry_price']) / portfolio['entry_price']
        profit_loss = portfolio['capital'] * price_change
        portfolio['capital'] += profit_loss
        portfolio['profit_loss'] += profit_loss
        portfolio['position'] = None  # Close position
        portfolio['entry_price'] = None
        save_portfolios()
        return f"🚨 *Sell Signal Triggered*\nSold at: ${price:.3f}\nProfit/Loss: ${profit_loss:.2f}\nUpdated Capital: ${portfolio['capital']:.2f}"
    return None

# Command handler to view the user's portfolio
# Function to view the user's portfolio
def view_portfolio(update: Update, context: CallbackContext) -> None:
    chat_id = str(update.message.chat_id)
    portfolio = portfolios.get(chat_id)
    if portfolio:
        position = portfolio['position']
        capital = portfolio['capital'] if portfolio['capital'] is not None else 0.0
        profit_loss = portfolio['profit_loss'] if portfolio['profit_loss'] is not None else 0.0
        entry_price = portfolio['entry_price'] if portfolio['entry_price'] is not None else "N/A"

        position_info = f"Open Position: {position} at ${entry_price:.3f}" if position else "No open positions."
        update.message.reply_text(
            f"💼 *Your Portfolio*\nCapital: ${capital:.2f}\nTotal Profit/Loss: ${profit_loss:.2f}\n{position_info}"
        )
    else:
        update.message.reply_text("No portfolio found. Set your starting capital with /setcapital <amount>.")

# Command handlers
def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("📊 Get XRP Price", callback_data='price')],
        [InlineKeyboardButton("🔔 Get Last Signal", callback_data='lastsignal')],
        [InlineKeyboardButton("💼 View Portfolio", callback_data='portfolio')],
        [InlineKeyboardButton("🔔 Set Price Alert", callback_data='setalert')],
        [InlineKeyboardButton("🔍 View Price Alert", callback_data='viewalert')],
        [InlineKeyboardButton("ℹ️ About", callback_data='about')],
        [InlineKeyboardButton("❓ Help", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Welcome to XRP Price Alerts Bot! Use the buttons below:', reply_markup=reply_markup)

def price(update: Update, context: CallbackContext) -> None:
    price = get_xrp_price()
    update.message.reply_text(f"The current XRP price is ${price:.5f}")

def lastsignal(update: Update, context: CallbackContext) -> None:
    last_signal = get_last_signal()
    update.message.reply_text(f"Last Trading Signal:\n{last_signal}")

def portfolio(update: Update, context: CallbackContext) -> None:
    view_portfolio(update, context)

def help_command(update: Update, context: CallbackContext) -> None:
    help_text = (
        "Available Commands:\n"
        "/start - Start the bot and show available options\n"
        "/price - Get the latest XRP price\n"
        "/lastsignal - Get the last trading signal\n"
        "/setcapital <amount> - Set your starting capital\n"
        "/portfolio - View your portfolio\n"
        "/setalert <price> - Set a custom price alert\n"
        "/viewalert - View your current price alert\n"
        "/about - Learn more about this bot\n"
        "/help - Show this help message"
    )
    update.message.reply_text(help_text)

def about_command(update: Update, context: CallbackContext) -> None:
    about_text = (
        "XRP Price Alerts Bot:\n"
        "This bot provides real-time XRP price alerts and trading signals.\n"
        "You can query the current XRP price, view the last trading signal, "
        "track your portfolio, set custom price alerts, and receive updates directly to your Telegram chat."
    )
    update.message.reply_text(about_text)

def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    if query.data == 'price':
        price = get_xrp_price()
        query.edit_message_text(f"The current XRP price is ${price:.5f}")
    elif query.data == 'lastsignal':
        last_signal = get_last_signal()
        query.edit_message_text(f"Last Trading Signal:\n{last_signal}")
    elif query.data == 'portfolio':
        view_portfolio(query, context)
    elif query.data == 'setalert':
        query.edit_message_text("Use /setalert <price> to set a custom price alert.")
    elif query.data == 'viewalert':
        chat_id = str(query.message.chat_id)
        if chat_id in price_alerts:
            alert_price = price_alerts[chat_id]
            query.edit_message_text(f"Your current price alert is set at ${alert_price:.3f}.")
        else:
            query.edit_message_text("You have no price alerts set. Use /setalert <price> to set one.")
    elif query.data == 'about':
        about_text = (
            "XRP Price Alerts Bot:\n"
            "This bot provides real-time XRP price alerts and trading signals.\n"
            "You can query the current XRP price, view the last trading signal, "
            "track your portfolio, set custom price alerts, and receive updates directly to your Telegram chat."
        )
        query.edit_message_text(about_text)
    elif query.data == 'help':
        help_text = (
            "Available Commands:\n"
            "/start - Start the bot and show available options\n"
            "/price - Get the latest XRP price\n"
            "/lastsignal - Get the last trading signal\n"
            "/setcapital <amount> - Set your starting capital\n"
            "/portfolio - View your portfolio\n"
            "/setalert <price> - Set a custom price alert\n"
            "/viewalert - View your current price alert\n"
            "/about - Learn more about this bot\n"
            "/help - Show this help message"
        )
        query.edit_message_text(help_text)

def main():
    # Set up the bot
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dp = updater.dispatcher

    # Add command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("price", price))
    dp.add_handler(CommandHandler("lastsignal", lastsignal))
    dp.add_handler(CommandHandler("portfolio", view_portfolio))
    dp.add_handler(CommandHandler("setalert", set_alert))
    dp.add_handler(CommandHandler("viewalert", view_alert))
    dp.add_handler(CommandHandler("setcapital", set_capital))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("about", about_command))
    dp.add_handler(CallbackQueryHandler(button))

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
