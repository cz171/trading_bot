from pprint import pprint
from dotenv import load_dotenv
# from schwab_api import SchwabApi
import schwabdev
import os
from strategies.multi_etf_strategy_simple import MultiETFStrategySimple
import logging

# Clear existing log file
with open('trading_bot.log', 'w') as f:
    f.write('')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)

#load environment variables and make client
load_dotenv()
client = schwabdev.Client(os.getenv('app_key'), os.getenv('app_secret'), os.getenv('callback_url'))

# get account number and hashes for linked accounts
linked_accounts = client.account_linked().json()
pprint(linked_accounts)

# select the first account to use for orders
account_hash = linked_accounts[0].get('hashValue')
pprint(client.account_details(account_hash, fields="positions").json())

# Initialize and run strategy
total_amount = 100000  # Total amount to invest in USD
strategy = MultiETFStrategySimple(client, account_hash, total_amount)
strategy.start()
