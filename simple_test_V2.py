"""
Simple test: Analyze current options data with snapshot-friendly strategy.
"""
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd
import numpy as np


def analyze_current_options(api_key: str):
    """Analyze current options and generate signals."""
    
    from backtester.historical_data import HistoricalDataFetcher
    
    print("\n" + "="*70)
    print("KAIKO OPTIONS ANALYSIS - IV SMILE & ABSOLUTE LEVELS")
    print("="*70 + "\n")
    
    # Fetch current snapshot
    fetcher = HistoricalDataFetcher(api_key)
    
    print("Fetching current BTC options data...\n")
    market_data = fetcher.fetch_current_snapshot('btc', num_expiries=5)
    
    if market_data.empty:
        print("ERROR: No market data retrieved")
        return
    
    print(f"✓ Retrieved {len(market_data)} instruments")
    print(f"  Expiries: {sorted(market_data['expiry'].unique())}\n")
    
    # Get current spot price
    current_price = fetcher.client.get_spot_price('btc', 'usd')
    print(f"✓ Current BTC Price: ${current_price:,.2f}\n")
    
    # Analyze IV levels
    print("="*70)
    print("IV ANALYSIS")
    print("="*70)
    
    avg_iv = market_data['mark_iv'].mean()
    iv_std = market_data['mark_iv'].std()
    
    print(f"\nOverall IV Stats:")
    print(f"  Average IV: {avg_iv:.1f}%")
    print(f"  Std Dev: {iv_std:.1f}%")
    print(f"  Min IV: {market_data['mark_iv'].min():.1f}%")
    print(f"  Max IV: {market_data['mark_iv'].max():.1f}%")
    
    # Define thresholds
    HIGH_IV = avg_iv + 0.5 * iv_std  # Above average
    LOW_IV = avg_iv - 0.5 * iv_std    # Below average
    
    print(f"\nDefined Thresholds:")
    print(f"  High IV (sell threshold): >{HIGH_IV:.1f}%")
    print(f"  Low IV (buy threshold): <{LOW_IV:.1f}%")
    
    # Find ATM options
    print("\n" + "="*70)
    print("ATM OPTIONS ANALYSIS")
    print("="*70)
    
    signals = []
    
    for expiry in sorted(market_data['expiry'].unique())[:3]:  # First 3 expiries
        expiry_data = market_data[market_data['expiry'] == expiry].copy()
        
        # Find ATM strike (closest to spot)
        expiry_data['dist_from_spot'] = abs(expiry_data['strike_price'] - current_price)
        atm_data = expiry_data.nsmallest(5, 'dist_from_spot')  # Get 5 closest strikes
        
        print(f"\nExpiry: {expiry}")
        print(f"  ATM strikes: {sorted(atm_data['strike_price'].unique())}")
        
        # Analyze calls vs puts
        for strike in atm_data['strike_price'].unique()[:2]:  # Top 2 strikes
            strike_data = atm_data[atm_data['strike_price'] == strike]
            
            call_data = strike_data[strike_data['option_type'] == 'call']
            put_data = strike_data[strike_data['option_type'] == 'put']
            
            if not call_data.empty:
                call = call_data.iloc[0]
                iv = call['mark_iv']
                
                print(f"\n  {call['instrument']}:")
                print(f"    Strike: ${call['strike_price']:,.0f}")
                print(f"    IV: {iv:.1f}%")
                print(f"    Delta: {call['delta']:.3f}")
                print(f"    Gamma: {call['gamma']:.5f}")
                print(f"    OI: {call['open_interest']}")
                
                # Generate signal based on IV
                if iv > HIGH_IV:
                    signal = {
                        'action': 'SELL',
                        'instrument': call['instrument'],
                        'type': 'CALL',
                        'strike': call['strike_price'],
                        'expiry': expiry,
                        'iv': iv,
                        'delta': call['delta'],
                        'reason': f"IV {iv:.1f}% > {HIGH_IV:.1f}% (high)"
                    }
                    signals.append(signal)
                    print(f"    → SIGNAL: SELL (IV HIGH)")
                
                elif iv < LOW_IV:
                    signal = {
                        'action': 'BUY',
                        'instrument': call['instrument'],
                        'type': 'CALL',
                        'strike': call['strike_price'],
                        'expiry': expiry,
                        'iv': iv,
                        'delta': call['delta'],
                        'reason': f"IV {iv:.1f}% < {LOW_IV:.1f}% (low)"
                    }
                    signals.append(signal)
                    print(f"    → SIGNAL: BUY (IV LOW)")
            
            if not put_data.empty:
                put = put_data.iloc[0]
                iv = put['mark_iv']
                
                print(f"\n  {put['instrument']}:")
                print(f"    Strike: ${put['strike_price']:,.0f}")
                print(f"    IV: {iv:.1f}%")
                print(f"    Delta: {put['delta']:.3f}")
                print(f"    Gamma: {put['gamma']:.5f}")
                print(f"    OI: {put['open_interest']}")
                
                # Generate signal
                if iv > HIGH_IV:
                    signal = {
                        'action': 'SELL',
                        'instrument': put['instrument'],
                        'type': 'PUT',
                        'strike': put['strike_price'],
                        'expiry': expiry,
                        'iv': iv,
                        'delta': put['delta'],
                        'reason': f"IV {iv:.1f}% > {HIGH_IV:.1f}% (high)"
                    }
                    signals.append(signal)
                    print(f"    → SIGNAL: SELL (IV HIGH)")
                
                elif iv < LOW_IV:
                    signal = {
                        'action': 'BUY',
                        'instrument': put['instrument'],
                        'type': 'PUT',
                        'strike': put['strike_price'],
                        'expiry': expiry,
                        'iv': iv,
                        'delta': put['delta'],
                        'reason': f"IV {iv:.1f}% < {LOW_IV:.1f}% (low)"
                    }
                    signals.append(signal)
                    print(f"    → SIGNAL: BUY (IV LOW)")
    
    # Summary
    print("\n" + "="*70)
    print("TRADING SIGNALS SUMMARY")
    print("="*70)
    
    if signals:
        print(f"\n✓ Generated {len(signals)} signals:\n")
        
        buy_signals = [s for s in signals if s['action'] == 'BUY']
        sell_signals = [s for s in signals if s['action'] == 'SELL']
        
        print(f"BUY signals: {len(buy_signals)}")
        for sig in buy_signals:
            print(f"  • {sig['type']} @ ${sig['strike']:,.0f} - {sig['reason']}")
        
        print(f"\nSELL signals: {len(sell_signals)}")
        for sig in sell_signals:
            print(f"  • {sig['type']} @ ${sig['strike']:,.0f} - {sig['reason']}")
        
        # Export
        signals_df = pd.DataFrame(signals)
        signals_df.to_csv('trading_signals.csv', index=False)
        print(f"\n✓ Saved to trading_signals.csv")
    else:
        print("\nNo signals generated.")
        print("Current IVs are within normal range.")
    
    # IV Smile Analysis
    print("\n" + "="*70)
    print("IV SMILE ANALYSIS (Nearest Expiry)")
    print("="*70)
    
    nearest_expiry = sorted(market_data['expiry'].unique())[0]
    smile_data = market_data[market_data['expiry'] == nearest_expiry].copy()
    smile_data = smile_data.sort_values('strike_price')
    
    print(f"\nExpiry: {nearest_expiry}")
    print(f"\nStrike    Type    IV      Delta    Gamma      OI")
    print("-" * 60)
    
    for _, row in smile_data.head(15).iterrows():
        print(f"{row['strike_price']:>6.0f}    {row['option_type']:>4s}  {row['mark_iv']:>5.1f}%  "
              f"{row['delta']:>6.3f}  {row['gamma']:>8.5f}  {row['open_interest']:>6.1f}")
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE!")
    print("="*70 + "\n")


def main():
    load_dotenv()
    api_key = os.getenv('KAIKO_API_KEY')
    
    if not api_key:
        print("ERROR: KAIKO_API_KEY not found")
        return
    
    analyze_current_options(api_key)


if __name__ == "__main__":
    main()