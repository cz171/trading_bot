from datetime import datetime, timedelta
import zoneinfo
from .multi_etf_strategy import MultiETFStrategy

class TestMultiETFStrategy(MultiETFStrategy):
    """Test version of MultiETFStrategy with modified trading hours and additional logging"""
    
    def __init__(self, client, account_hash, total_amount, test_duration_minutes=60):
        super().__init__(client, account_hash, total_amount)
        self.test_duration_minutes = test_duration_minutes
        self.logger.info("Initialized TEST strategy - This is not for production use!")

    def start(self):
        """Override start method with test-specific timing"""
        current_time = datetime.now(zoneinfo.ZoneInfo("America/New_York"))
        test_start_time = (current_time - timedelta(minutes=1)).time()
        test_stop_time = (current_time + timedelta(minutes=self.test_duration_minutes)).time()
        
        self.logger.info(f"Starting TEST strategy from {test_start_time} to {test_stop_time}")
        
        self.streamer.start_auto(
            receiver=self.handle_stream_message,
            start_time=test_start_time,
            stop_time=test_stop_time,
            on_days=[0,1,2,3,4,5,6],  # Allow testing any day
            now_timezone=zoneinfo.ZoneInfo("America/New_York")
        )
        
        self.streamer.send(
            self.streamer.level_one_equities(
                "IBIT,MSTZ", 
                "0,1,2,3,4,5,6,7,8"
            )
        )

    def execute_market_buy(self, symbol):
        """Override to add additional logging for testing"""
        self.logger.info(f"TEST: Attempting to execute market buy for {symbol}")
        result = super().execute_market_buy(symbol)
        self.logger.info(f"TEST: Market buy for {symbol} {'succeeded' if result else 'failed'}")
        return result

    def execute_market_sell(self, symbol):
        """Override to add additional logging for testing"""
        self.logger.info(f"TEST: Attempting to execute market sell for {symbol}")
        result = super().execute_market_sell(symbol)
        self.logger.info(f"TEST: Market sell for {symbol} {'succeeded' if result else 'failed'}")
        return result

    def handle_stream_message(self, message):
        """Override to add additional logging for testing"""
        self.logger.debug(f"TEST: Received message: {message}")
        super().handle_stream_message(message)