"""
Historical data fetching for strategy backtesting.
Uses existing Kaiko API client.
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.kaiko_api import KaikoAPI


class HistoricalDataFetcher:
    """Fetches historical options data for backtesting using existing KaikoAPI."""
    
    def __init__(self, api_key: str):
        self.client = KaikoAPI(api_key=api_key)
        
    def fetch_historical_options_data(
        self,
        asset: str,
        start_date: str,
        end_date: str,
        exchange: str = "drbt"
    ) -> pd.DataFrame:
        """
        Fetch historical options data with risk metrics.
        
        Args:
            asset: 'btc' or 'eth'
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'
            exchange: Exchange code (default: drbt = Deribit)
            
        Returns:
            DataFrame with options data including Greeks, OI, IV
        """
        print(f"  Fetching options data for {asset.upper()}...")
        
        # Get expiries in the date range
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        expiries = self.client.get_expiries(
            base=asset,
            quote='usd',
            start_date=start_dt,
            end_date=end_dt + timedelta(days=90),  # Look ahead for future expiries
            exchange=exchange
        )
        
        if not expiries:
            print(f"    No expiries found for {asset}")
            return pd.DataFrame()
        
        print(f"    Found {len(expiries)} expiries")
        
        # Fetch options data for recent expiries
        # Use ATM filter to speed up (only get strikes near ATM)
        all_data = self.client.get_multi_expiry_options_data(
            base=asset,
            quote='usd',
            expiries=expiries[:5],  # Limit to 5 expiries for speed
            exchange=exchange,
            atm_filter_pct=0.3  # Only strikes within ±30% of ATM
        )
        
        if all_data.empty:
            print(f"    No options data retrieved")
            return pd.DataFrame()
        
        # Add timestamp (current snapshot)
        all_data['timestamp'] = pd.Timestamp.now()
        
        print(f"    Retrieved {len(all_data)} instruments")
        
        return all_data
    
    def fetch_spot_price_history(
        self,
        asset: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Fetch spot price history.
        
        Note: For MVP, creates synthetic price history based on current price.
        In production, would fetch actual historical OHLCV data.
        
        Returns:
            DataFrame with columns: timestamp, price
        """
        print(f"  Fetching spot prices for {asset.upper()}...")
        
        # Get current spot price using existing method
        current_price = self.client.get_spot_price(base=asset, quote='usd')
        
        if not current_price:
            print(f"    Could not fetch spot price")
            return pd.DataFrame()
        
        print(f"    Current price: ${current_price:,.2f}")
        
        # Create time series (for MVP testing)
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        dates = pd.date_range(start=start_dt, end=end_dt, freq='1H')
        
        # Simulate some price movement (±2% random walk for testing)
        # In production: Replace with actual historical data from Kaiko
        import numpy as np
        np.random.seed(42)  # Reproducible
        returns = np.random.randn(len(dates)) * 0.02  # 2% volatility
        prices = current_price * np.exp(np.cumsum(returns))
        
        df = pd.DataFrame({
            'timestamp': dates,
            'price': prices
        })
        
        print(f"    Generated {len(df)} hourly price points")
        
        return df
    
    def fetch_current_snapshot(
        self,
        asset: str,
        num_expiries: int = 3,
        exchange: str = 'drbt'
    ) -> pd.DataFrame:
        """
        Fetch current snapshot of options data for analysis.
        
        Args:
            asset: 'btc' or 'eth'
            num_expiries: Number of expiries to fetch (default: 3)
            exchange: Exchange code
            
        Returns:
            DataFrame with current options data
        """
        print(f"  Fetching current snapshot for {asset.upper()}...")
        
        # Get upcoming expiries
        today = datetime.now()
        future = today + timedelta(days=90)
        
        expiries = self.client.get_expiries(
            base=asset,
            quote='usd',
            start_date=today,
            end_date=future,
            exchange=exchange
        )
        
        if not expiries:
            print("    No expiries found")
            return pd.DataFrame()
        
        # Take the nearest expiries
        expiries_to_fetch = expiries[:num_expiries]
        print(f"    Fetching {len(expiries_to_fetch)} expiries: {expiries_to_fetch}")
        
        # Fetch with ATM filter for speed
        data = self.client.get_multi_expiry_options_data(
            base=asset,
            quote='usd',
            expiries=expiries_to_fetch,
            exchange=exchange,
            atm_filter_pct=0.2  # ±20% of ATM
        )
        
        if not data.empty:
            print(f"    Retrieved {len(data)} instruments")
            
        return data


# Test function
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv('KAIKO_API_KEY')
    
    if not api_key:
        print("ERROR: KAIKO_API_KEY not found in .env file")
        print("Please create a .env file with: KAIKO_API_KEY=your_key_here")
        sys.exit(1)
    
    print("✓ API key loaded")
    
    fetcher = HistoricalDataFetcher(api_key)
    
    print("\n" + "="*70)
    print("TESTING HISTORICAL DATA FETCHER")
    print("="*70 + "\n")
    
    # Test 1: Fetch current snapshot
    print("Test 1: Current options snapshot")
    print("-" * 70)
    snapshot = fetcher.fetch_current_snapshot('btc', num_expiries=2)
    
    if not snapshot.empty:
        print(f"\n✓ Snapshot retrieved successfully")
        print(f"  Shape: {snapshot.shape}")
        print(f"  Columns: {snapshot.columns.tolist()}")
        
        print(f"\n  Sample instruments:")
        sample_cols = ['instrument', 'strike_price', 'option_type', 'expiry', 
                       'mark_iv', 'delta', 'gamma', 'open_interest']
        available_cols = [col for col in sample_cols if col in snapshot.columns]
        
        if available_cols:
            print(snapshot[available_cols].head(10).to_string(index=False))
        else:
            print(snapshot.head())
    else:
        print("\n✗ No snapshot data retrieved")
    
    # Test 2: Spot prices
    print("\n" + "="*70)
    print("Test 2: Spot price history")
    print("-" * 70)
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    spot_data = fetcher.fetch_spot_price_history('btc', start_date, end_date)
    
    if not spot_data.empty:
        print(f"\n✓ Spot data generated successfully")
        print(f"  Shape: {spot_data.shape}")
        print(f"  Date range: {spot_data['timestamp'].min()} to {spot_data['timestamp'].max()}")
        print(f"  Price range: ${spot_data['price'].min():,.2f} - ${spot_data['price'].max():,.2f}")
        print(f"\n  Sample prices:")
        print(spot_data.head(10).to_string(index=False))
    else:
        print("\n✗ No spot data retrieved")
    
    # Test 3: Historical options data
    print("\n" + "="*70)
    print("Test 3: Historical options data")
    print("-" * 70)
    
    hist_data = fetcher.fetch_historical_options_data('btc', start_date, end_date)
    
    if not hist_data.empty:
        print(f"\n✓ Historical data retrieved successfully")
        print(f"  Shape: {hist_data.shape}")
        print(f"  Expiries: {hist_data['expiry'].unique().tolist()}")
    else:
        print("\n✗ No historical data retrieved")
    
    print("\n" + "="*70)
    print("TESTING COMPLETE!")
    print("="*70 + "\n")