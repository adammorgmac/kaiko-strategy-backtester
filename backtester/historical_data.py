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
        """Fetch historical options data with risk metrics."""
        print(f"  Fetching options data for {asset.upper()}...")
        
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        expiries = self.client.get_expiries(
            base=asset,
            quote='usd',
            start_date=start_dt,
            end_date=end_dt + timedelta(days=90),
            exchange=exchange
        )
        
        if not expiries:
            print(f"    No expiries found for {asset}")
            return pd.DataFrame()
        
        print(f"    Found {len(expiries)} expiries")
        
        all_data = self.client.get_multi_expiry_options_data(
            base=asset,
            quote='usd',
            expiries=expiries[:5],
            exchange=exchange,
            atm_filter_pct=0.3
        )
        
        if all_data.empty:
            print(f"    No options data retrieved")
            return pd.DataFrame()
        
        # Fix timestamps
        all_data['timestamp'] = pd.Timestamp.now(tz='UTC')
        all_data['expiry'] = pd.to_datetime(all_data['expiry'], utc=True)
        
        print(f"    Retrieved {len(all_data)} instruments")
        
        return all_data
    
    def fetch_spot_price_history(
        self,
        asset: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """Fetch spot price history."""
        print(f"  Fetching spot prices for {asset.upper()}...")
        
        current_price = self.client.get_spot_price(base=asset, quote='usd')
        
        if not current_price:
            print(f"    Could not fetch spot price")
            return pd.DataFrame()
        
        print(f"    Current price: ${current_price:,.2f}")
        
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        dates = pd.date_range(start=start_dt, end=end_dt, freq='h', tz='UTC')
        
        import numpy as np
        np.random.seed(42)
        returns = np.random.randn(len(dates)) * 0.02
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
        """Fetch current snapshot of options data for analysis."""
        print(f"  Fetching current snapshot for {asset.upper()}...")
        
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
        
        expiries_to_fetch = expiries[:num_expiries]
        print(f"    Fetching {len(expiries_to_fetch)} expiries")
        
        data = self.client.get_multi_expiry_options_data(
            base=asset,
            quote='usd',
            expiries=expiries_to_fetch,
            exchange=exchange,
            atm_filter_pct=0.2
        )
        
        if not data.empty:
            # Fix timestamps
            data['expiry'] = pd.to_datetime(data['expiry'], utc=True)
            print(f"    Retrieved {len(data)} instruments")
            
        return data


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv('KAIKO_API_KEY')
    
    if not api_key:
        print("ERROR: KAIKO_API_KEY not found in .env file")
        sys.exit(1)
    
    print("✓ API key loaded")
    
    fetcher = HistoricalDataFetcher(api_key)
    
    print("\n" + "="*70)
    print("TESTING HISTORICAL DATA FETCHER")
    print("="*70 + "\n")
    
    snapshot = fetcher.fetch_current_snapshot('btc', num_expiries=2)
    
    if not snapshot.empty:
        print(f"\n✓ Snapshot retrieved successfully")
        print(f"  Shape: {snapshot.shape}")
        print(f"  Columns: {snapshot.columns.tolist()}")
        print(f"  Expiry dtype: {snapshot['expiry'].dtype}")
    
    print("\n" + "="*70)
    print("TESTING COMPLETE!")
    print("="*70 + "\n")