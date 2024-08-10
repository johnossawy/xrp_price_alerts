
# XRP Price Alerts

This project is a Python-based bot that automatically posts updates to Twitter about the price of XRP (Ripple) every hour. The bot fetches the latest price from an API, compares it to the price from the previous hour and the last 24 hours, and tweets the results.

## Table of Contents

- [Features](#features)
- [Setup](#setup)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Usage](#usage)
- [Deployment on AWS](#deployment-on-aws)
- [File Structure](#file-structure)
- [Contributing](#contributing)
- [License](#license)

## Features

- Fetches the latest XRP price from the Bitstamp API.
- Compares the current price with the price from the last hour and the last 24 hours.
- Posts an update to Twitter every hour, highlighting significant changes in the price.
- Automatically saves the last posted price for future comparisons.

## Setup

### Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.7+
- Pip (Python package installer)
- Git (optional, if you want to clone from a repository)
- An AWS account (for deployment)
- Twitter Developer Account and API keys

### Installation

1. **Clone the repository** (if not already done):

   ```bash
   git clone https://github.com/your-username/xrp_price_alerts.git
   cd xrp_price_alerts
   ```

2. **Set up a virtual environment**:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install the required packages**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:

   Create a `.env` file in the project root directory and add your Twitter API credentials and other configurations:

   ```plaintext
   CONSUMER_KEY=your-consumer-key
   CONSUMER_SECRET=your-consumer-secret
   ACCESS_TOKEN=your-access-token
   ACCESS_TOKEN_SECRET=your-access-token-secret
   LAST_TWEET_FILE=last_tweet.json
   ```

5. **Run the bot locally**:

   You can manually run the bot to see if everything is set up correctly:

   ```bash
   python3 xrppricealerts.py
   ```

## Usage

- The bot automatically fetches the latest XRP price and compares it with the previous hour and the last 24 hours.
- If a significant change is detected, it posts an update to Twitter.
- The bot is designed to run continuously and post updates every hour.

## Deployment on AWS

To deploy this project on AWS EC2 and automate the hourly Twitter posts:

1. **Launch an EC2 Instance**:
   - Use Amazon Linux 2 or Ubuntu AMI.
   - Ensure the instance has the necessary IAM role with SSM permissions.

2. **Connect to the EC2 instance via SSM**:
   - Set up the environment by following the [Installation](#installation) steps.

3. **Automate with Cron**:
   - Schedule the script to run every hour using cron:

     ```bash
     crontab -e
     ```

     Add the following line to schedule the script:

     ```bash
     0 * * * * /path/to/your/project/venv/bin/python3 /path/to/your/project/xrppricealerts.py >> /path/to/your/project/cron.log 2>&1
     ```

## File Structure

```plaintext
xrp_price_alerts/
├── README.md
├── __pycache__
├── app/
│   ├── __init__.py
│   ├── comparisons.py
│   ├── fetcher.py
│   ├── notifier.py
│   ├── twitter.py
│   └── utils.py
├── config.py
├── last_tweet.json
├── requirements.txt
├── tests/
│   ├── __init__.py
│   ├── test_fetcher.py
│   ├── test_notifier.py
│   └── test_twitter.py
└── xrppricealerts.py
```

## Contributing

If you'd like to contribute to this project, please fork the repository, create a new branch, and submit a pull request. All contributions are welcome!

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
