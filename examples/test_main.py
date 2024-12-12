import threading
import time
import logging
import dotenv
import os
from datetime import datetime
from pprint import pprint

import schwabdev
from schwabdev import Client
from strategies.test_multi_etf_strategy import TestMultiETFStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TestMain')

def main():
        # set logging level
    logging.basicConfig(level=logging.INFO)

    #load environment variables and make client
    dotenv.load_dotenv()
    client = schwabdev.Client(os.getenv('app_key'), os.getenv('app_secret'), os.getenv('callback_url'))

    # get account number and hashes for linked accounts
    linked_accounts = client.account_linked().json()
    pprint(linked_accounts)

    # select the first account to use for orders
    account_hash = linked_accounts[0].get('hashValue')
    pprint(client.account_details(account_hash, fields="positions").json())

    # Initialize test strategy
    strategy = TestMultiETFStrategy(
        client=client,
        account_hash=account_hash,
        total_amount=1000,  # Use smaller amount for testing
        test_duration_minutes=15  # 15-minute test run
    )

    logger.info(f"Starting test strategy at {datetime.now()}")
    strategy.start()

    # Monitor threads
    try:
        while True:
            active_threads = threading.enumerate()
            logger.info("\nActive Threads:")
            for thread in active_threads:
                logger.info(f"Name: {thread.name}, Alive: {thread.is_alive()}, Daemon: {thread.daemon}")
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("\nTest run complete - shutting down...")

if __name__ == "__main__":
    main()