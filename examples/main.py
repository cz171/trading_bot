from pprint import pprint
import threading
import time
import schwabdev
import logging
import dotenv
import os
from strategies.multi_etf_strategy import MultiETFStrategy  # Import the strategy class

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

    strategy = MultiETFStrategy(client, account_hash, total_amount=2000)

    strategy.start()

    # Keep the main thread alive and monitor threads
    try:
        while True:
            active_threads = threading.enumerate()
            print("\nActive Threads:")
            for thread in active_threads:
                print(f"Name: {thread.name}, Alive: {thread.is_alive()}, Daemon: {thread.daemon}")
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        print("\nGracefully shutting down...")
        # Add any cleanup if needed

if __name__ == "__main__":
    main()