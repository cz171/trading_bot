from datetime import datetime, time, timedelta
import zoneinfo
import logging
import json
from decimal import Decimal, ROUND_DOWN
import time as time_module
from functools import wraps

def retry_on_failure(max_attempts=3, delay_seconds=1):
    """Decorator for retrying failed operations"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    result = func(self, *args, **kwargs)
                    if result:  # If operation succeeded
                        return True
                    attempts += 1
                    if attempts < max_attempts:
                        self.logger.warning(
                            f"Attempt {attempts} failed for {func.__name__}, "
                            f"retrying in {delay_seconds} seconds..."
                        )
                        time_module.sleep(delay_seconds)
                except Exception as e:
                    attempts += 1
                    if attempts < max_attempts:
                        self.logger.error(
                            f"Attempt {attempts} failed for {func.__name__} with error: {e}, "
                            f"retrying in {delay_seconds} seconds..."
                        )
                        time_module.sleep(delay_seconds)
            self.logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
            return False
        return wrapper
    return decorator

class MultiETFStrategy:
    
    def __init__(self, client, account_hash, total_amount):
        self.client = client
        self.account_hash = account_hash
        self.total_amount = total_amount
        self.streamer = client.stream
        
        # Define trading symbols and their allocations
        self.symbols = ['IBIT', 'MSTZ']
        self.allocation_ratios = {
            'IBIT': Decimal('0.7'),
            'MSTZ': Decimal('0.3')
        }
        
        # Initialize positions
        self.positions = {symbol: None for symbol in self.symbols}
        self.last_prices = {symbol: None for symbol in self.symbols}
        self.sold_shares = False
        # Calculate allocation amounts
        self.allocations = {
            symbol: ratio * Decimal(str(total_amount))
            for symbol, ratio in self.allocation_ratios.items()
        }
        
        # Setup logging
        self.logger = logging.getLogger('MultiETFStrategy')
        self.logger.setLevel(logging.INFO)
        fh = logging.FileHandler('multi_etf_strategy.log')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(fh)

    def calculate_shares(self, symbol, market_price):
        """Calculate the number of shares to buy for a given symbol"""
        # current_price = Decimal(str(quote[symbol].get('askPrice', 0)))
        return int(self.allocations[symbol] / market_price)  
    
    def validate_order(self, side, symbol):
        """
        Validate if an order can be placed
        
        Args:
            side (str): 'buy' or 'sell'
            symbol (str): The trading symbol
            
        Returns:
            bool: True if order is valid, False otherwise
        """
        try:
            # Check if symbol is valid
            if symbol not in self.symbols:
                self.logger.error(f"Invalid symbol: {symbol}")
                return False
                
            # Get current market data
            quote = self.client.quotes([symbol]).json()
            if not quote or symbol not in quote:
                self.logger.error(f"Unable to get quote for {symbol}")
                return False
                
            # Validate based on order side
            if side.lower() == 'buy':
                # Check if position already exists
                if self.positions[symbol] is not None:
                    self.logger.warning(f"Position already exists for {symbol}")
                    return False
                    
                # Verify sufficient funds (using ask price for buy)
                ask_price = Decimal(str(quote[symbol].get('askPrice', 0)))
                if ask_price <= 0:
                    self.logger.error(f"Invalid ask price for {symbol}: {ask_price}")
                    return False
                    
                shares = self.calculate_shares(symbol, ask_price)
                if shares <= 0:
                    self.logger.error(f"Insufficient funds to buy {symbol}")
                    return False
                    
            elif side.lower() == 'sell':
                # Check if position exists to sell
                if self.positions[symbol] is None:
                    self.logger.warning(f"No position exists for {symbol}")
                    return False
                    
                # Verify bid price is valid
                bid_price = Decimal(str(quote[symbol].get('bidPrice', 0)))
                if bid_price <= 0:
                    self.logger.error(f"Invalid bid price for {symbol}: {bid_price}")
                    return False
            else:
                self.logger.error(f"Invalid order side: {side}")
                return False
                
            return True
        
        except Exception as e:
            self.logger.error(f"Error validating {side} order for {symbol}: {e}")
            return False
    
    @retry_on_failure(max_attempts=3, delay_seconds=1)
    def execute_market_buy(self, symbol):
        """Execute market buy order for specified symbol with retries"""
        if symbol in self.positions and self.positions[symbol] is not None:
            return False
        try:
            if not self.validate_order('buy', symbol):
                return False
            # market_price = self.client.quotes([symbol]).json()[symbol].get('lastPrice')
            shares = self.calculate_shares(self.last_prices[symbol])
            if shares == 0:
                self.logger.warning(f"Cannot buy 0 shares of {symbol}")
                return False

            order = {
                "symbol": symbol,
                "quantity": shares,
                "orderType": "Market",
                "duration": "Day",
                "side": "Buy"
            }
            
            response = self.client.order_place(self.account_hash, order)
            if response.status_code in [200, 201]:
                quote = self.client.quotes([symbol]).json()
                current_price = quote[symbol].get('askPrice')
                self.positions[symbol] = {
                    'quantity': shares,
                    'entry_price': current_price,
                    'timestamp': datetime.now(zoneinfo.ZoneInfo("America/New_York"))
                }
                self.logger.info(f"Placed buy order for {shares} {symbol} @ ~${current_price}")
                return True
            else:
                self.logger.error(f"Order failed for {symbol}: {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Error in buy execution for {symbol}: {e}")
            return False

    @retry_on_failure(max_attempts=3, delay_seconds=1)
    def execute_market_sell(self, symbol):
        """Execute market sell order for specified symbol with retries"""
        if not self.positions[symbol]:
            self.logger.warning(f"No position to sell for {symbol}")
            return False

        try:
            if not self.validate_order('sell', symbol):
                return False

            order = {
                "symbol": symbol,
                "quantity": self.positions[symbol]['quantity'],
                "orderType": "Market",
                "duration": "Day",
                "side": "Sell"
            }

            response = self.client.order_place(self.account_hash, order)
            if response.status_code in [200, 201]:
                quote = self.client.quotes([symbol]).json()
                current_price = quote[symbol].get('bidPrice')
                profit_loss = (current_price - self.positions[symbol]['entry_price']) * self.positions[symbol]['quantity']
                self.logger.info(f"Placed sell order for {self.positions[symbol]['quantity']} {symbol} @ ~${current_price}")
                self.logger.info(f"{symbol} P&L: ${profit_loss:.2f}")
                self.positions[symbol] = None
                return True
            else:
                self.logger.error(f"Order failed for {symbol}: {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Error in sell execution for {symbol}: {e}")
            return False

    def execute_open_positions(self, max_attempts=3):
        """Execute market open positions with retries for the entire portfolio"""
        attempt = 0
        while attempt < max_attempts:
            failed_symbols = []
            for symbol in ['IBIT', 'MSTZ']:
                if not self.execute_market_buy(symbol):
                    failed_symbols.append(symbol)
            
            if not failed_symbols:
                self.logger.info("Successfully established all positions")
                return True
                
            attempt += 1
            if attempt < max_attempts:
                self.logger.warning(
                    f"Failed to establish positions for {failed_symbols}, "
                    f"attempt {attempt + 1} of {max_attempts}"
                )
                time_module.sleep(1)  # Wait before retrying all failed positions
            
        self.logger.error(f"Failed to establish positions after {max_attempts} attempts")
        return False

    def execute_close_positions(self, max_attempts=3):
        """Execute market close positions with retries for the entire portfolio"""
        attempt = 0
        while attempt < max_attempts:
            failed_symbols = []
            for symbol in ['IBIT', 'MSTZ']:
                if self.positions[symbol] and not self.execute_market_sell(symbol):
                    failed_symbols.append(symbol)
            
            if not failed_symbols:
                self.logger.info("Successfully closed all positions")
                self.sold_shares = True
                return True
                
            attempt += 1
            if attempt < max_attempts:
                self.logger.warning(
                    f"Failed to close positions for {failed_symbols}, "
                    f"attempt {attempt + 1} of {max_attempts}"
                )
                time_module.sleep(2)  # Wait before retrying all failed positions
            
        self.logger.error(f"Failed to close positions after {max_attempts} attempts")
        return False

    def start(self):

        """Start the strategy"""
        self.streamer.start_auto(
            receiver=self.handle_stream_message,
            start_time=time(9, 29, 0), 
            stop_time=time(16, 0, 0),
            on_days=[0,1,2,3,4],  # 0: Monday, 1: Tuesday, 2: Wednesday, 3: Thursday, 4: Friday
            now_timezone=zoneinfo.ZoneInfo("America/New_York")
        )
        
        self.streamer.send(
            self.streamer.level_one_equities(
                # "ADD",
                "IBIT,MSTZ", 
                "0,1,2,3"  # Fields for price, volume, etc.
            )
        )

    def handle_stream_message(self, message):
        """Handle streaming data and auto-retry on position establishment/closure"""
        try:
            if 'data' not in message:
                logging.warning("No 'data' in message, skipping")
                return
        
            now = datetime.now(zoneinfo.ZoneInfo("America/New_York"))
            if now < time(9, 30):
                logging.info("Market not open yet, skipping")
                time_module.sleep(30)
                return 
            
            if self.sold_shares: 
                time_module.sleep(30)
                return 
            if now > time(15, 55) and not self.sold_shares:
                self.execute_close_positions()
                return 
            
            if any(position is None for position in self.positions.values()) and all(price is not None for price in self.last_prices.values()):
                logging.info("Got all required prices, executing buy order")
                self.execute_open_positions()
                self.positions = {symbol: price for symbol, price in self.last_prices.items()}
                return 

            data = json.loads(message)
            # logging.info(f"data: {data}")
            # logging.info(f"data['data']: {data['data']}")

            if 'content' in data['data'][0]:
                # Regular price updates
                data0 = data['data'][0]
                content = data0['content']
                for dict0 in content:     
                    symbol = dict0['key']
                    # doesn't guarantee to be successful
                    if '3' in dict0:
                        last_price = dict0['3']
                        self.last_prices[symbol] = dict0['3']
                        
                        logging.info(f"symbol: {symbol}, last_price: {last_price}")
                # if data['']
                # mstz_price = data['content'][3]
                # c = data['content']
                
                # time_module.sleep(5)
                # if price and symbol in self.positions:
                #     self.logger.debug(f"{symbol} price update: ${price}")
                    
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")