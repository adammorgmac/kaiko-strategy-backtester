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
        Fetch historical options data.
        
        NOTE: This method is NOT implemented for real historical time series.
        Use HistoricalStorage.get_date_range() to retrieve stored daily snapshots.
        """
        raise NotImplementedError(
            "True historical options time series not available. "
            "Use HistoricalStorage to access stored snapshots instead."
        )
    
    def fetch_spot_price_history(
        self,
        asset: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Fetch spot price history.
        
        NOTE: This currently raises NotImplementedError.
        Use HistoricalStorage to get real snapshot-based spot prices.
        """
        raise NotImplementedError(
            "Historical spot price time series not implemented. "
            "Use HistoricalStorage.get_date_range() to retrieve "
            "spot prices from stored snapshots instead."
        )
    
    def fetch_current_snapshot(
        self,
        asset: str,
        num_expiries: int = 3,
        exchange: str = 'drbt'
    ) -> pd.DataFrame:
        """Fetch current snapshot of options data for analysis."""
        print(f"  Fetching current snapshot for {asset.upper()}...")
        
        today = pd.Timestamp.now(tz='UTC')
        future = today + pd.Timedelta(days=90)
        
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
            snapshot_ts = pd.Timestamp.now(tz='UTC')
            data['snapshot_timestamp'] = snapshot_ts
            data['expiry'] = pd.to_datetime(data['expiry'], utc=True)
            print(f"    Retrieved {len(data)} instruments")
            
            # Validate data
            try:
                from .validation import DataValidator
                DataValidator.validate_and_report(data, f"{asset.upper()} Snapshot")
            except ImportError:
                # Validation module not available, skip
                pass
            except Exception as e:
                print(f"    ⚠️  Validation warning: {e}")
            
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