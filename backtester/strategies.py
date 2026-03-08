"""
Strategy definitions and signal generation logic.
All strategies use observed timestamps from data, never wall-clock time.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class SignalType(Enum):
    """Trade signal types."""
    BUY = 1
    SELL = -1
    HOLD = 0


@dataclass
class TradeSignal:
    """
    Represents a trading signal with all information needed for execution.
    """
    timestamp: pd.Timestamp
    signal_type: SignalType
    instrument: str
    strike: float
    expiry: str
    option_type: str
    quantity: float
    reason: str
    
    # Market data for execution
    iv: Optional[float] = None
    spot_price: Optional[float] = None
    mark_price: Optional[float] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    
    # Greeks (optional)
    delta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    theta: Optional[float] = None
    
    # Metadata
    snapshot_timestamp: Optional[pd.Timestamp] = None


def get_data_timestamp(data: pd.DataFrame) -> pd.Timestamp:
    """
    Extract timestamp from data, preferring snapshot_timestamp.
    
    Args:
        data: DataFrame with timestamp column(s)
    
    Returns:
        UTC-aware pandas Timestamp
    
    Raises:
        ValueError: If no valid timestamp found
    """
    if data.empty:
        raise ValueError("Cannot extract timestamp from empty DataFrame")
    
    # Prefer snapshot_timestamp
    if 'snapshot_timestamp' in data.columns:
        ts = pd.to_datetime(data['snapshot_timestamp'].iloc[0])
        if ts.tz is None:
            ts = ts.tz_localize('UTC')
        return ts
    
    # Fall back to timestamp
    if 'timestamp' in data.columns:
        ts = pd.to_datetime(data['timestamp'].iloc[0])
        if ts.tz is None:
            ts = ts.tz_localize('UTC')
        return ts
    
    raise ValueError(
        "Data must include 'snapshot_timestamp' or 'timestamp' column. "
        "Strategies cannot use wall-clock time for signal generation."
    )


def validate_required_columns(data: pd.DataFrame, required: List[str]) -> None:
    """
    Validate that required columns exist in DataFrame.
    
    Args:
        data: DataFrame to validate
        required: List of required column names
    
    Raises:
        ValueError: If any required columns are missing
    """
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}\n"
            f"Available columns: {data.columns.tolist()}"
        )


class BaseStrategy:
    """Base class for all strategies."""
    
    def __init__(self, name: str, params: Dict):
        self.name = name
        self.params = params
        
    def generate_signals(self, data: pd.DataFrame, spot_data: pd.DataFrame) -> List[TradeSignal]:
        """Generate trading signals. Must be implemented by child classes."""
        raise NotImplementedError


class SimpleVolatilityStrategy(BaseStrategy):
    """
    Cross-sectional IV deviation strategy.
    
    Trades based on how far current IV deviates from the cross-sectional mean,
    measured in standard deviations.
    
    Note: This is NOT a true IV percentile strategy (which would require
    historical time series). It uses cross-sectional statistics from the
    current snapshot only.
    """
    
    def __init__(self, params: Dict = None):
        default_params = {
            'lookback_days': 30,  # Not currently used
            'high_iv_std_pct': 75,  # Sell when IV > mean + (75% of std)
            'low_iv_std_pct': 25,   # Buy when IV < mean - (25% of std)
            'min_dte': 7,
            'max_dte': 60,
            'strikes_per_expiry': 2  # Nearest N strikes per expiry
        }
        
        if params:
            # Backward compatibility: map old names
            if 'high_iv_threshold' in params:
                params['high_iv_std_pct'] = params.pop('high_iv_threshold')
            if 'low_iv_threshold' in params:
                params['low_iv_std_pct'] = params.pop('low_iv_threshold')
            
            default_params.update(params)
        
        super().__init__(
            "Cross-Sectional IV Deviation Strategy",
            default_params
        )
    
    def generate_signals(self, data: pd.DataFrame, spot_data: pd.DataFrame) -> List[TradeSignal]:
        """
        Generate signals based on cross-sectional IV deviation.
        
        Args:
            data: Options data with required columns
            spot_data: Spot price data (optional, can use data['spot_price'])
        
        Returns:
            List of TradeSignal objects
        """
        signals = []
        
        if data.empty:
            return signals
        
        # Validate required columns
        required_cols = [
            'instrument',
            'strike_price',
            'option_type',
            'mark_iv',
            'expiry'
        ]
        
        try:
            validate_required_columns(data, required_cols)
        except ValueError as e:
            print(f"Cannot generate signals: {e}")
            return signals
        
        # Get timestamp from data (never use now())
        try:
            snapshot_time = get_data_timestamp(data)
        except ValueError as e:
            print(f"Cannot generate signals: {e}")
            return signals
        
        # Get spot price
        spot_price = None
        if 'spot_price' in data.columns and data['spot_price'].notna().any():
            spot_price = data['spot_price'].iloc[0]
        elif not spot_data.empty and 'price' in spot_data.columns:
            spot_data = spot_data.sort_values('timestamp')
            spot_price = spot_data['price'].iloc[-1]
        
        if spot_price is None or spot_price <= 0:
            print("Cannot generate signals: no valid spot price")
            return signals
        
        # Calculate cross-sectional thresholds
        avg_iv = data['mark_iv'].mean()
        iv_std = data['mark_iv'].std()
        
        # Use percentage of std dev for thresholds
        high_threshold = avg_iv + (self.params['high_iv_std_pct'] / 100) * iv_std
        low_threshold = avg_iv - (self.params['low_iv_std_pct'] / 100) * iv_std
        
        # Find ATM options per expiry (not globally)
        atm_rows = []
        strikes_per_expiry = self.params['strikes_per_expiry']
        
        for expiry, expiry_df in data.groupby('expiry'):
            expiry_df = expiry_df.copy()
            expiry_df['dist_from_spot'] = (expiry_df['strike_price'] - spot_price).abs()
            
            # Take nearest N strikes for this expiry
            nearest = expiry_df.nsmallest(strikes_per_expiry, 'dist_from_spot')
            atm_rows.append(nearest)
        
        atm_data = pd.concat(atm_rows, ignore_index=True) if atm_rows else pd.DataFrame()
        
        if atm_data.empty:
            return signals
        
        # Generate signals
        for _, row in atm_data.iterrows():
            iv = row['mark_iv']
            
            # Get market prices for execution
            mark_price = row.get('mark_price')
            bid_price = row.get('bid_price')
            ask_price = row.get('ask_price')
            
            # Estimate mark if not available (rough estimate for signal generation)
            if mark_price is None or pd.isna(mark_price):
                mark_price = iv * spot_price * 0.08  # Rough approximation
            
            # High IV: sell signal
            if iv > high_threshold:
                signal = TradeSignal(
                    timestamp=snapshot_time,
                    signal_type=SignalType.SELL,
                    instrument=row['instrument'],
                    strike=row['strike_price'],
                    expiry=str(row['expiry']),
                    option_type=row['option_type'],
                    quantity=1.0,
                    reason=f"IV {iv:.1f}% > threshold {high_threshold:.1f}%",
                    iv=iv,
                    spot_price=spot_price,
                    mark_price=mark_price,
                    bid_price=bid_price,
                    ask_price=ask_price,
                    delta=row.get('delta'),
                    gamma=row.get('gamma'),
                    vega=row.get('vega'),
                    theta=row.get('theta'),
                    snapshot_timestamp=snapshot_time
                )
                signals.append(signal)
            
            # Low IV: buy signal
            elif iv < low_threshold:
                signal = TradeSignal(
                    timestamp=snapshot_time,
                    signal_type=SignalType.BUY,
                    instrument=row['instrument'],
                    strike=row['strike_price'],
                    expiry=str(row['expiry']),
                    option_type=row['option_type'],
                    quantity=1.0,
                    reason=f"IV {iv:.1f}% < threshold {low_threshold:.1f}%",
                    iv=iv,
                    spot_price=spot_price,
                    mark_price=mark_price,
                    bid_price=bid_price,
                    ask_price=ask_price,
                    delta=row.get('delta'),
                    gamma=row.get('gamma'),
                    vega=row.get('vega'),
                    theta=row.get('theta'),
                    snapshot_timestamp=snapshot_time
                )
                signals.append(signal)
        
        return signals
    
    def calculate_iv_percentile(self, iv_series: pd.Series) -> float:
        """
        Calculate IV percentile over lookback period.
        
        NOTE: This method is not currently used.
        True percentile calculation requires historical IV time series,
        which is not available from single snapshots.
        
        Kept for potential future use with multi-day snapshot data.
        """
        if len(iv_series) < 2:
            return 50.0
        current_iv = iv_series.iloc[-1]
        return (iv_series < current_iv).sum() / len(iv_series) * 100


# Strategy registry
AVAILABLE_STRATEGIES = {
    'simple_vol': SimpleVolatilityStrategy,
}


def get_strategy(strategy_name: str, params: Dict = None) -> BaseStrategy:
    """
    Factory function to get strategy by name.
    
    Args:
        strategy_name: Strategy identifier
        params: Strategy parameters (optional)
    
    Returns:
        Strategy instance
    
    Raises:
        ValueError: If strategy name unknown
    """
    if strategy_name not in AVAILABLE_STRATEGIES:
        available = ', '.join(AVAILABLE_STRATEGIES.keys())
        raise ValueError(
            f"Unknown strategy: {strategy_name}\n"
            f"Available strategies: {available}"
        )
    return AVAILABLE_STRATEGIES[strategy_name](params)


if __name__ == "__main__":
    """Test strategy with mock data."""
    
    print("="*70)
    print("TESTING STRATEGY MODULE")
    print("="*70)
    
    # Create mock data
    snapshot_time = pd.Timestamp('2026-03-08 12:00:00', tz='UTC')
    
    mock_data = pd.DataFrame({
        'instrument': ['btc-call-1', 'btc-put-1', 'btc-call-2'],
        'strike_price': [50000, 50000, 55000],
        'option_type': ['call', 'put', 'call'],
        'expiry': [pd.Timestamp('2026-03-15', tz='UTC')] * 3,
        'mark_iv': [90, 50, 70],
        'snapshot_timestamp': [snapshot_time] * 3,
        'spot_price': [50000] * 3,
        'delta': [0.5, -0.5, 0.3],
        'gamma': [0.001, 0.001, 0.0008],
        'mark_price': [2000, 1500, 800]
    })
    
    spot_data = pd.DataFrame({
        'timestamp': [snapshot_time],
        'price': [50000]
    })
    
    # Test strategy
    print("\n1. Creating strategy...")
    strategy = SimpleVolatilityStrategy(params={
        'high_iv_std_pct': 50,
        'low_iv_std_pct': 50
    })
    print(f"   ✓ Strategy: {strategy.name}")
    
    print("\n2. Generating signals...")
    signals = strategy.generate_signals(mock_data, spot_data)
    print(f"   ✓ Generated {len(signals)} signals")
    
    if signals:
        print("\n3. Signal details:")
        for i, signal in enumerate(signals, 1):
            print(f"\n   Signal {i}:")
            print(f"     Action: {signal.signal_type.name}")
            print(f"     Instrument: {signal.instrument}")
            print(f"     Timestamp: {signal.timestamp}")
            print(f"     Has snapshot_timestamp: {signal.snapshot_timestamp is not None}")
            print(f"     Mark price: ${signal.mark_price:.2f}" if signal.mark_price else "     Mark price: None")
            print(f"     Reason: {signal.reason}")
    
    # Test timestamp extraction
    print("\n4. Testing timestamp utilities...")
    try:
        ts = get_data_timestamp(mock_data)
        print(f"   ✓ Extracted timestamp: {ts}")
        print(f"   ✓ Timezone: {ts.tz}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test validation
    print("\n5. Testing column validation...")
    try:
        validate_required_columns(mock_data, ['instrument', 'strike_price'])
        print(f"   ✓ Validation passed")
    except ValueError as e:
        print(f"   ✗ Validation failed: {e}")
    
    # Test with missing columns
    print("\n6. Testing with missing columns...")
    bad_data = pd.DataFrame({'instrument': ['test']})
    try:
        validate_required_columns(bad_data, ['instrument', 'strike_price'])
        print(f"   ✗ Should have raised ValueError")
    except ValueError as e:
        print(f"   ✓ Correctly caught missing columns")
    
    print("\n" + "="*70)
    print("✅ STRATEGY MODULE TESTS COMPLETE")
    print("="*70)
    print("\nKey improvements:")
    print("  - Timestamps from data, never now()")
    print("  - Proper column validation")
    print("  - Market prices on signals")
    print("  - Honest naming (cross-sectional, not percentile)")
    print("  - Per-expiry ATM selection")
    print()