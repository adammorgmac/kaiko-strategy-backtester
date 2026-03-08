"""
Daily snapshot capture tool.
Run this daily (or via cron/GitHub Actions) to build historical database.
"""
import os
import pandas as pd
from dotenv import load_dotenv
from typing import Optional

from backtester.historical_data import HistoricalDataFetcher
from backtester.historical_storage import HistoricalStorage


def get_spot_from_options_data(data: pd.DataFrame) -> Optional[float]:
    """
    Extract implied spot price from ATM options strikes.
    
    This is a fallback when API spot price is unavailable.
    Uses median strike as proxy for current spot.
    """
    if data.empty or 'strike_price' not in data.columns:
        return None
    
    strikes = pd.to_numeric(data['strike_price'], errors='coerce').dropna()
    
    if len(strikes) > 0:
        # Median is more robust than mean for this purpose
        return float(strikes.median())
    
    return None


def main():
    load_dotenv()
    api_key = os.getenv('KAIKO_API_KEY')
    
    if not api_key:
        print("ERROR: KAIKO_API_KEY not found in environment")
        print("Create a .env file with: KAIKO_API_KEY=your_key_here")
        return
    
    print("\n" + "="*70)
    print("DAILY SNAPSHOT CAPTURE")
    print("="*70 + "\n")
    
    fetcher = HistoricalDataFetcher(api_key)
    storage = HistoricalStorage()
    
    # Capture BTC and ETH
    assets_captured = 0
    
    for asset in ['btc', 'eth']:
        print(f"\n📸 Capturing {asset.upper()} snapshot...")
        
        try:
            # Fetch options data first
            data = fetcher.fetch_current_snapshot(asset, num_expiries=10)
            
            if data.empty:
                print(f"  ⚠️  No options data retrieved for {asset}")
                continue
            
            print(f"  ✓ Retrieved {len(data)} instruments")
            
            # Try to get spot price from API
            spot_price = fetcher.client.get_spot_price(asset, 'usd')
            
            # Fallback: estimate from options strikes if API fails
            if spot_price is None or pd.isna(spot_price) or spot_price <= 0:
                print(f"  ⚠️  API spot price unavailable, estimating from options strikes...")
                spot_price = get_spot_from_options_data(data)
                
                if spot_price and spot_price > 0:
                    print(f"  ✓ Estimated spot from median strike: ${spot_price:,.2f}")
                else:
                    print(f"  ❌ Cannot determine valid spot price, skipping {asset}")
                    continue
            else:
                print(f"  ✓ Spot price from API: ${spot_price:,.2f}")
            
            # Save snapshot to database
            storage.save_snapshot(asset, data, spot_price)
            assets_captured += 1
            
        except Exception as e:
            print(f"  ❌ Error capturing {asset}: {e}")
            import traceback
            traceback.print_exc()
    
    # Show database statistics
    print("\n" + "="*70)
    print("DATABASE STATISTICS")
    print("="*70)
    
    stats = storage.get_stats()
    print(f"Total Snapshots: {stats['num_snapshots']}")
    print(f"Total Data Points: {stats['num_datapoints']:,}")
    
    if stats['date_range'][0]:
        print(f"Date Range: {stats['date_range'][0]} to {stats['date_range'][1]}")
    
    if stats['assets']:
        print(f"Assets: {', '.join(stats['assets'])}")
    
    # List recent snapshots
    print("\n📅 Recent Snapshots:")
    snapshots = storage.list_snapshots()
    if not snapshots.empty:
        print(snapshots.head(10).to_string(index=False))
    else:
        print("  (none yet)")
    
    print("\n" + "="*70)
    if assets_captured > 0:
        print(f"✅ SNAPSHOT CAPTURE COMPLETE - {assets_captured} asset(s) saved")
    else:
        print("⚠️  SNAPSHOT CAPTURE FAILED - No assets saved")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()