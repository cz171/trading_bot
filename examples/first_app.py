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
        self.positions = {
            'IBIT': None,
            'MSTZ': None
        }
        
        # Calculate allocation amounts (7:3 ratio)
        self.allocations = {
            'IBIT': Decimal('0.7') * Decimal(str(total_amount)),
            'MSTZ': Decimal('0.3') * Decimal(str(total_amount))
        }
        
        # Setup logging
        self.logger = logging.getLogger('MultiETFStrategy')
        self.logger.setLevel(logging.INFO)
        fh = logging.FileHandler('multi_etf_strategy.log')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(fh)

    @retry_on_failure(max_attempts=3, delay_seconds=1)
    def execute_market_buy(self, symbol):
        """Execute market buy order for specified symbol with retries"""
        try:
            if not self.validate_order('buy', symbol):
                return False

            shares = self.calculate_shares(symbol)
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
                    'timestamp': datetime.now()
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
                time_module.sleep(2)  # Wait before retrying all failed positions
            
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

    def handle_stream_message(self, message):
        """Handle streaming data and auto-retry on position establishment/closure"""
        try:
            data = json.loads(message)
            if 'content' in data:
                now = datetime.now(zoneinfo.ZoneInfo("America/New_York"))
                
                # Try to establish positions at market open
                if now.time() == time(9, 30, 0):
                    if not any(self.positions.values()):  # If no positions are established
                        self.logger.info("Market opened - establishing positions")
                        self.execute_open_positions()
                
                # Try to close positions before market close
                elif now.time() == time(15, 55, 0):
                    if any(self.positions.values()):  # If any positions are still open
                        self.logger.info("Market closing - closing positions")
                        self.execute_close_positions()
                
                # Regular price updates
                symbol = data.get('key')
                price = data['content'].get('1')
                if price and symbol in self.positions:
                    self.logger.debug(f"{symbol} price update: ${price}")
                    
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")