"""
Main execution file for Multi ETF Strategy
"""

from schwabdev import Client
from strategies.multi_etf_strategy import MultiETFStrategy
import logging

def main(): 
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize client
    client = Client()
    client.login()
    
    # Get account hash
    accounts = client.accounts().json()
    account_hash = accounts[0]['hashValue']
    
    # Create and start strategy
    strategy = MultiETFStrategy(
        client=client,
        account_hash=account_hash,
        buy_amount=1
    )
    
    strategy.start()

if __name__ == "__main__":
    main()