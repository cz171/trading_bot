import logging
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, time
import zoneinfo
from .multi_etf_strategy_simple import MultiETFStrategySimple, Action

class TestMultiETFStrategySimple(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure logging to show all levels and output to console
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
    def setUp(self):
        self.mock_client = Mock()
        self.account_hash = "test_hash"
        self.total_amount = 10000
        self.strategy = MultiETFStrategySimple(self.mock_client, self.account_hash, self.total_amount)

    def test_get_last_price(self):
        # Mock the quotes response
        self.mock_client.quotes.return_value.json.return_value = {
            'IBIT': {'lastPrice': '50.00'},
            'MSTZ': {'lastPrice': '30.00'}
        }

        # Test valid price
        price = self.strategy.get_last_price('IBIT')
        self.assertEqual(price, 50.00)

    def test_place_order(self):
        # Mock successful order placement
        self.mock_client.order_place.return_value.json.return_value = {'status': 'success'}

        # Test buy order
        self.strategy.place_order('IBIT', 100, Action.BUY)
        self.assertEqual(self.strategy.orders['IBIT'], 100)
        self.assertFalse(self.strategy.check_all_orders_placed(['IBIT', 'MSTZ']))
        self.strategy.place_order('MSTZ', 100, Action.BUY)
        self.assertEqual(self.strategy.orders['MSTZ'], 100)
        self.assertTrue(self.strategy.check_all_orders_placed(['IBIT', 'MSTZ']))
        
        # Test sell order
        self.strategy.place_order('IBIT', 100, Action.SELL)
        self.strategy.place_order('MSTZ', 100, Action.SELL)
        self.assertNotIn('IBIT', self.strategy.orders)
        self.assertNotIn('MSTZ', self.strategy.orders)

    def test_calculate_allocation_amounts(self):
        allocations = self.strategy.calculate_allocation_amounts()
        self.assertEqual(allocations['IBIT'], 7000)
        self.assertEqual(allocations['MSTZ'], 3000)

    def test_check_all_orders_placed(self):
        self.assertFalse(self.strategy.check_all_orders_placed(['IBIT']))
        self.assertFalse(self.strategy.check_all_orders_placed(['MSTZ']))

    # @patch('strategies.multi_etf_strategy_simple.datetime')
    # def test_start_market_closed(self, mock_datetime):
    #     # Mock time before market open
    #     mock_now = Mock()
    #     mock_now.time.return_value = time(9, 0)
    #     mock_now.return_value = mock_now
    #     mock_datetime.now = mock_now

    #     # Mock quotes for price checks
    #     self.mock_client.quotes.return_value.json.return_value = {
    #         'IBIT': {'lastPrice': '50.00'},
    #         'MSTZ': {'lastPrice': '30.00'}
    #     }

    #     with patch('strategies.multi_etf_strategy_simple.sleep') as mock_sleep:
    #         self.strategy.start()
    #         mock_sleep.assert_called()

if __name__ == '__main__':
    unittest.main()
