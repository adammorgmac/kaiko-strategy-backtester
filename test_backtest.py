"""
Test script to run a simple backtest.
"""
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd

from backtester.historical_data import HistoricalDataFetcher
from backtester.strategies import get_strategy
from backtester.engine import BacktestEngine


def main():
    print("\n" + "="*70)
    print("KAIKO STRATEGY BACKTESTER - FULL BACKTEST")
    print("="*70 + "\n")
    
    # Load API key
    load_dotenv()
    api_key = os.getenv('KAIKO_API_KEY')
    
    if not api_key:
        print("ERROR: KAIKO_API_KEY not found in .env file")
        print("Please create a .env file with: KAIKO_API_KEY=your_key_here")
        return
    
    print("✓ API key loaded\n")
    
    # Initialize
    fetcher = HistoricalDataFetcher(api_key)
    
    # Date range (last 7 days for quick test)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    asset = 'btc'
    
    print(f"Fetching {asset.upper()} data from {start_str} to {end_str}...\n")
    
    # Fetch data
    print("=" * 70)
    print("STEP 1: Fetching Market Data")
    print("=" * 70)
    market_data = fetcher.fetch_historical_options_data(asset, start_str, end_str)
    spot_data = fetcher.fetch_spot_price_history(asset, start_str, end_str)
    
    if market_data.empty:
        print("\nERROR: No market data retrieved")
        print("This might be because there's limited historical data available.")
        print("The API returns current snapshots, not historical time series.")
        return
    
    if spot_data.empty:
        print("\nERROR: No spot data retrieved")
        return
    
    print(f"\n✓ Data Retrieved:")
    print(f"  Market data: {market_data.shape[0]:,} rows")
    print(f"  Unique instruments: {market_data['instrument'].nunique()}")
    print(f"  Expiries: {market_data['expiry'].unique().tolist()}")
    print(f"  Spot data: {spot_data.shape[0]:,} rows")
    print(f"  Columns: {market_data.columns.tolist()}\n")
    
    # Initialize strategy
    print("=" * 70)
    print("STEP 2: Initialize Strategy")
    print("=" * 70)
    strategy = get_strategy('simple_vol', params={
        'lookback_days': 7,
        'high_iv_threshold': 70,
        'low_iv_threshold': 30
    })
    print(f"✓ Strategy initialized: {strategy.name}")
    print(f"  Parameters: {strategy.params}\n")
    
    # Run backtest
    print("=" * 70)
    print("STEP 3: Run Backtest")
    print("=" * 70)
    engine = BacktestEngine(
        initial_capital=100000,
        position_size_pct=0.05,
        max_positions=10
    )
    
    results = engine.run_backtest(
        strategy=strategy,
        market_data=market_data,
        spot_data=spot_data,
        start_date=start_str,
        end_date=end_str
    )
    
    # Check if backtest was successful
    if 'error' in results:
        print(f"\n❌ Backtest failed: {results['error']}")
        print("\nNote: This is expected if we don't have true historical time-series data.")
        print("The current implementation fetches a snapshot, not historical data.")
        return
    
    # Save results
    print("\n" + "=" * 70)
    print("STEP 4: Save Results")
    print("=" * 70)
    
    if 'equity_curve' in results and not results['equity_curve'].empty:
        results['equity_curve'].to_csv('backtest_equity_curve.csv', index=False)
        print("✓ Saved equity curve to backtest_equity_curve.csv")
    
    # Save trades
    if 'trades' in results and results['trades']:
        trades_df = pd.DataFrame([{
            'entry_time': t.entry_time,
            'exit_time': t.exit_time,
            'instrument': t.instrument,
            'quantity': t.quantity,
            'entry_price': t.entry_price,
            'exit_price': t.exit_price,
            'pnl': t.pnl,
            'option_pnl': t.option_pnl,
            'hedge_pnl': t.hedge_pnl,
            'days_held': t.days_held,
            'reason': t.strategy_reason
        } for t in results['trades']])
        
        trades_df.to_csv('backtest_trades.csv', index=False)
        print("✓ Saved trades to backtest_trades.csv")
    
    print("\n" + "=" * 70)
    print("BACKTEST COMPLETE! 🎉")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()