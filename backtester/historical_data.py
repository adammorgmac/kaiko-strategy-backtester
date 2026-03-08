"""
Current snapshot fetching for options data.
Does NOT provide true historical time series - use HistoricalStorage for that.
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

from utils.kaiko_api import KaikoAPI


class HistoricalDataFetcher:
    """
    Fetches current options snapshots using Kaiko API.
    
    Important: This class does NOT provide true historical time series.
    For backtesting on historical data, use HistoricalStorage to access
    stored daily snapshots.
    """
    
    def __init__(self, api_key: str):
        """Initialize with Kaiko API key."""
        self.client = KaikoAPI(api_key=api_key)
    
    def fetch_current_snapshot(
        self,
        asset: str,
        num_expiries: int = 3,
        exchange: str = 'drbt'
    ) -> pd.DataFrame:
        """
        Fetch current snapshot of options data.
        
        Args:
            asset: Base asset (e.g., 'btc', 'eth')
            num_expiries: Number of expiries to fetch
            exchange: Exchange code (default: 'drbt' for Deribit)
        
        Returns:
            DataFrame with current options data including:
            - snapshot_timestamp: When this snapshot was captured
            - timestamp: Alias for snapshot_timestamp (for compatibility)
            - expiry: UTC-aware datetime
            - All option fields (strike, IV, Greeks, etc.)
        """
        print(f"  Fetching current snapshot for {asset.upper()}...")
        
        # Use UTC-aware timestamps
        today = pd.Timestamp.now(tz='UTC')
        future = today + pd.Timedelta(days=90)
        
        # Get available expiries
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
        
        # Fetch data for requested expiries
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
            # Normalize snapshot data
            data = self._normalize_snapshot_dataframe(data)
            print(f"    Retrieved {len(data)} instruments")
        
        return data
    
    def _normalize_snapshot_dataframe(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize snapshot data with proper timestamps.
        
        Args:
            data: Raw data from API
        
        Returns:
            Normalized DataFrame with UTC-aware timestamps
        """
        data = data.copy()
        
        # Capture snapshot timestamp
        snapshot_ts = pd.Timestamp.now(tz='UTC')
        data['snapshot_timestamp'] = snapshot_ts
        data['timestamp'] = snapshot_ts  # Compatibility alias
        
        # Ensure expiry is UTC-aware datetime
        if 'expiry' in data.columns:
            data['expiry'] = pd.to_datetime(data['expiry'], utc=True, errors='coerce')
        
        return data
    
    def fetch_historical_options_data(
        self,
        asset: str,
        start_date: str,
        end_date: str,
        exchange: str = "drbt"
    ) -> pd.DataFrame:
        """
        NOT IMPLEMENTED: True historical options time series not available.
        
        This method intentionally raises NotImplementedError because:
        - Current API endpoints return snapshots, not historical time series
        - Assigning current timestamp to all rows is dishonest
        - Backtesting requires real historical observations
        
        For backtesting, use HistoricalStorage.get_date_range() to access
        stored daily snapshots.
        
        Raises:
            NotImplementedError: Always
        """
        raise NotImplementedError(
            "True historical options time series not available from this fetch path.\n"
            "This would require:\n"
            "  1. Historical snapshot API endpoints (not currently available), or\n"
            "  2. Pre-stored daily snapshots\n"
            "\n"
            "For backtesting, use:\n"
            "  from backtester.historical_storage import HistoricalStorage\n"
            "  storage = HistoricalStorage()\n"
            "  data = storage.get_date_range(asset, start_date, end_date)"
        )
    
    def fetch_spot_price_history(
        self,
        asset: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        NOT IMPLEMENTED: Synthetic spot price generation removed.
        
        Generating synthetic random walk prices for backtesting is dishonest
        and produces meaningless results.
        
        For real spot history, use:
        - Historical snapshot spot prices from HistoricalStorage
        - External data source with true historical prices
        
        Raises:
            NotImplementedError: Always
        """
        raise NotImplementedError(
            "Synthetic spot price generation is not permitted.\n"
            "Fabricating price history for backtesting produces invalid results.\n"
            "\n"
            "For spot prices, use:\n"
            "  1. HistoricalStorage snapshots (includes spot_price column), or\n"
            "  2. External historical price data source\n"
            "\n"
            "Do not use synthetic/random data for research or backtesting."
        )


# Module-level functions for convenience
def get_current_snapshot(api_key: str, asset: str, num_expiries: int = 3) -> pd.DataFrame:
    """
    Convenience function to fetch current snapshot.
    
    Args:
        api_key: Kaiko API key
        asset: Asset to fetch (e.g., 'btc', 'eth')
        num_expiries: Number of expiries
    
    Returns:
        Current options snapshot DataFrame
    """
    fetcher = HistoricalDataFetcher(api_key)
    return fetcher.fetch_current_snapshot(asset, num_expiries=num_expiries)


if __name__ == "__main__":
    """
    Test current snapshot fetching.
    
    Note: Historical methods are intentionally NOT implemented in this module.
    Use HistoricalStorage for accessing stored daily snapshots.
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv('KAIKO_API_KEY')
    
    if not api_key:
        print("ERROR: KAIKO_API_KEY not found in environment")
        print("Create a .env file with: KAIKO_API_KEY=your_key_here")
        exit(1)
    
    print("="*70)
    print("TESTING CURRENT SNAPSHOT FETCHER")
    print("="*70)
    print("\nNote: This module provides current snapshots only.")
    print("For historical backtesting, use HistoricalStorage.\n")
    
    fetcher = HistoricalDataFetcher(api_key)
    
    # Test BTC snapshot
    print("\nFetching BTC snapshot...")
    snapshot = fetcher.fetch_current_snapshot('btc', num_expiries=2)
    
    if not snapshot.empty:
        print(f"\n✓ Snapshot retrieved successfully")
        print(f"  Shape: {snapshot.shape}")
        print(f"  Snapshot time: {snapshot['snapshot_timestamp'].iloc[0]}")
        print(f"  Columns: {snapshot.columns.tolist()}")
        
        # Check timestamp types
        print(f"\n  Timestamp checks:")
        print(f"    - snapshot_timestamp dtype: {snapshot['snapshot_timestamp'].dtype}")
        print(f"    - expiry dtype: {snapshot['expiry'].dtype}")
        print(f"    - snapshot_timestamp has tz: {snapshot['snapshot_timestamp'].iloc[0].tz is not None}")
        print(f"    - expiry has tz: {snapshot['expiry'].iloc[0].tz is not None}")
    else:
        print("\n✗ No data retrieved")
    
    # Demonstrate that historical methods are disabled
    print("\n" + "="*70)
    print("TESTING HISTORICAL METHODS (SHOULD FAIL)")
    print("="*70)
    
    try:
        fetcher.fetch_historical_options_data('btc', '2026-01-01', '2026-03-01')
        print("\n✗ ERROR: Historical fetch should have raised NotImplementedError!")
    except NotImplementedError as e:
        print("\n✓ Historical options fetch correctly disabled:")
        print(f"  {str(e)[:100]}...")
    
    try:
        fetcher.fetch_spot_price_history('btc', '2026-01-01', '2026-03-01')
        print("\n✗ ERROR: Spot history should have raised NotImplementedError!")
    except NotImplementedError as e:
        print("\n✓ Spot price history correctly disabled:")
        print(f"  {str(e)[:100]}...")
    
    print("\n" + "="*70)
    print("✅ TESTING COMPLETE")
    print("="*70)
    print("\nThis module is honest about its limitations.")
    print("Use HistoricalStorage for real backtesting.\n")