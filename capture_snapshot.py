"""
Daily snapshot capture tool.
Run this daily (or via cron) to build historical database.
"""
import os
from dotenv import load_dotenv
from backtester.historical_data import HistoricalDataFetcher
from backtester.historical_storage import HistoricalStorage


def main():
    load_dotenv()
    api_key = os.getenv('KAIKO_API_KEY')
    
    if not api_key:
        print("ERROR: KAIKO_API_KEY not found")
        return
    
    print("\n" + "="*70)
    print("DAILY SNAPSHOT CAPTURE")
    print("="*70 + "\n")
    
    fetcher = HistoricalDataFetcher(api_key)
    storage = HistoricalStorage()
    
    # Capture BTC and ETH
    for asset in ['btc', 'eth']:
        print(f"\n📸 Capturing {asset.upper()} snapshot...")
        
        try:
            # Fetch data
            data = fetcher.fetch_current_snapshot(asset, num_expiries=10)
            spot_price = fetcher.client.get_spot_price(asset, 'usd')
            
            if data.empty:
                print(f"  ⚠️  No data for {asset}")
                continue
            
            # Save snapshot
            storage.save_snapshot(asset, data, spot_price)
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    # Show database stats
    print("\n" + "="*70)
    print("DATABASE STATISTICS")
    print("="*70)
    
    stats = storage.get_stats()
    print(f"Total Snapshots: {stats['num_snapshots']}")
    print(f"Total Data Points: {stats['num_datapoints']:,}")
    
    if stats['date_range'][0]:
        print(f"Date Range: {stats['date_range'][0]} to {stats['date_range'][1]}")
    
    print(f"Assets: {', '.join(stats['assets'])}")
    
    # List recent snapshots
    print("\n📅 Recent Snapshots:")
    snapshots = storage.list_snapshots()
    if not snapshots.empty:
        print(snapshots.head(10).to_string(index=False))
    
    print("\n" + "="*70)
    print("✅ SNAPSHOT CAPTURE COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()