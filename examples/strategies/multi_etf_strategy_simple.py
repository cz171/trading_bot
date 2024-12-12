from datetime import datetime, time, timedelta
from enum import Enum
import logging
# import time
from time import sleep
import zoneinfo

SLEEP_TIME = 30

class Action(Enum):
    BUY = "Buy"
    SELL = "Sell"

class MultiETFStrategySimple:
    
    def __init__(self, client, account_hash, total_amount):
        self.client = client
        self.account_hash = account_hash
        self.total_amount = total_amount
        self.allocation_ratios = {
            'IBIT': 0.7,
            'MSTZ': 0.3
        }
        self.orders = {}
        
    def start(self):
        """Start the simple strategy by placing market orders"""
        # Define trading symbols and their allocations
        symbols = ['IBIT', 'MSTZ'] 
        

        # Calculate allocation amounts
        allocations = self.calculate_allocation_amounts()

        logging.info(f"Allocations: {allocations}")
        placed_order = False
        while True:
            # Check if current time is 9:30 AM EST
            current_time = datetime.now(zoneinfo.ZoneInfo("America/New_York")).time()
            market_open = time(9, 30)
            market_close = time(16, 0)
            near_market_close = time(15, 55)

            if current_time < market_open:
                logging.info("Waiting for market open at 9:30 AM EST...")
                sleep(SLEEP_TIME)
                continue
            
            # logging.info("Market is opening")
            if current_time >= market_open and not placed_order:
                logging.info("Market is opening, proceeding with orders")
                for symbol, amount in allocations.items():
                    last_price = self.get_last_price(symbol)
                    if last_price is None:
                        logging.error(f"Unable to get last price for {symbol}")
                        continue
                    
                    # Calculate shares based on last price
                    shares = int(amount / last_price)
                    logging.info(f"Calculated {shares} shares of {symbol} at ${last_price:.2f} per share")
                    
                    if symbol not in self.orders:
                        self.place_order(symbol, shares, Action.BUY)
                    else:
                        logging.info(f"Order for {symbol} already placed, skipping")
                
                placed_order = self.check_all_orders_placed(symbols)

                sleep(SLEEP_TIME)
                continue
            
            if current_time >= near_market_close:
                logging.info("Market is closing, placing sell orders")
                for symbol, shares in self.orders.items():
                    if symbol in self.orders:
                        bought_shares = self.orders[symbol]
                        self.place_order(symbol, bought_shares, Action.SELL)
                    
                
                # Exit after placing sell orders
                logging.info("All sell orders placed, exiting strategy")
                break
                
    
    def calculate_allocation_amounts(self):
        allocations = {
            symbol: ratio * self.total_amount 
            for symbol, ratio in self.allocation_ratios.items()
        }
        return allocations

    def check_all_orders_placed(self, symbols):
        """Check if all orders for given symbols have been placed successfully"""
        if len(self.orders) != len(symbols):
            return False

        return all(
            symbol in self.orders and 
            self.orders[symbol] is not None 
            for symbol in symbols
        )

    def place_order(self, symbol, shares, action):  
        # Place market order
        order = {
            "symbol": symbol,
            "quantity": shares, 
            "orderType": "Market",
            "side": action.value,
            "duration": "Day"
        }
    
        try:
            response = self.client.order_place(self.account_hash, order).json()
            if action == Action.BUY:
                self.orders[symbol] = shares
            elif action == Action.SELL:
                del self.orders[symbol]
            logging.info(f"Placed {action.value} order for {shares} shares of {symbol}: {response}")
        except Exception as e:
            logging.error(f"Error placing order for {symbol}: {e}")
   
    def get_last_price(self, symbol):
        quote = self.client.quotes([symbol]).json()
        if not quote or symbol not in quote:
            logging.error(f"Unable to get quote for {symbol}")
            return None
            
        last_price = float(quote[symbol].get('lastPrice', 0))
        if last_price <= 0:
            logging.error(f"Invalid last price for {symbol}: {last_price}")
            return None
            
        logging.info(f"Last price for {symbol}: ${last_price:.2f}")
        return last_price