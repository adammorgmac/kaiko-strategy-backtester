"""
Strategy definitions and signal generation logic.
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
    """Represents a trading signal."""
    timestamp: pd.Timestamp
    signal_type: SignalType
    instrument: str
    strike: float
    expiry: str
    option_type: str  # 'call' or 'put'
    quantity: float
    reason: str
    iv: Optional[float] = None
    spot_price: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None


class BaseStrategy:
    """Base class for all strategies."""
    
    def __init__(self, name: str, params: Dict):
        self.name = name
        self.params = params
        
    def generate_signals(self, data: pd.DataFrame, spot_data: pd.DataFrame) -> List[TradeSignal]:
        """
        Generate trading signals based on market data.
        Must be implemented by child classes.
        """
        raise NotImplementedError


class SimpleVolatilityStrategy(BaseStrategy):
    """
    Simple strategy: Trade based on IV percentile.
    
    This is a starter strategy that's easy to understand and debug.
    """
    
    def __init__(self, params: Dict = None):
        default_params = {
            'lookback_days': 30,
            'high_iv_threshold': 75,  # Sell when IV percentile > 75
            'low_iv_threshold': 25,   # Buy when IV percentile < 25
            'min_dte': 7,             # Minimum days to expiration
            'max_dte': 60,            # Maximum days to expiration
        }
        if params:
            default_params.update(params)
        
        super().__init__("Simple Volatility Strategy", default_params)
    
    def calculate_iv_percentile(self, iv_series: pd.Series) -> float:
        """Calculate IV percentile over lookback period."""
        if len(iv_series) < 2:
            return 50.0
        
        current_iv = iv_series.iloc[-1]
        return (iv_series < current_iv).sum() / len(iv_series) * 100
    
    def generate_signals(self, data: pd.DataFrame, spot_data: pd.DataFrame) -> List[TradeSignal]:
        """Generate signals based on IV percentile."""
        signals = []
        
        print(f"  Analyzing {len(data)} data points for signals...")
        
        # Ensure we have the required columns
        required_cols = ['timestamp', 'instrument']
        if not all(col in data.columns for col in required_cols):
            print(f"    Missing required columns. Available: {data.columns.tolist()}")
            return signals
        
        # Get unique instruments
        instruments = data['instrument'].unique()
        print(f"  Found {len(instruments)} unique instruments")
        
        # For each instrument, check IV percentile
        for instrument in instruments[:10]:  # Limit to 10 for testing
            instrument_data = data[data['instrument'] == instrument].copy()
            
            if len(instrument_data) < self.params['lookback_days']:
                continue
            
            # Get IV column (might be named differently)
            iv_col = None
            for col in ['iv', 'implied_volatility', 'mark_iv']:
                if col in instrument_data.columns:
                    iv_col = col
                    break
            
            if iv_col is None:
                continue
            
            # Calculate IV percentile
            iv_percentile = self.calculate_iv_percentile(instrument_data[iv_col])
            
            # Get latest data point
            latest = instrument_data.iloc[-1]
            
            # Extract strike and expiry from instrument name if possible
            # Format usually: BTC-25MAR26-80000-C
            try:
                parts = instrument.split('-')
                if len(parts) >= 4:
                    strike = float(parts[2])
                    expiry = parts[1]
                    option_type = 'call' if parts[3] == 'C' else 'put'
                else:
                    continue
            except:
                continue
            
            # Get spot price at this timestamp
            spot_match = spot_data[spot_data['timestamp'] <= latest['timestamp']]
            if spot_match.empty:
                continue
            spot_price = spot_match.iloc[-1]['price']
            
            # Generate signal
            if iv_percentile > self.params['high_iv_threshold']:
                signals.append(TradeSignal(
                    timestamp=latest['timestamp'],
                    signal_type=SignalType.SELL,
                    instrument=instrument,
                    strike=strike,
                    expiry=expiry,
                    option_type=option_type,
                    quantity=1.0,
                    reason=f"IV percentile {iv_percentile:.1f}% > {self.params['high_iv_threshold']}%",
                    iv=latest[iv_col],
                    spot_price=spot_price,
                    delta=latest.get('delta'),
                    gamma=latest.get('gamma')
                ))
            
            elif iv_percentile < self.params['low_iv_threshold']:
                signals.append(TradeSignal(
                    timestamp=latest['timestamp'],
                    signal_type=SignalType.BUY,
                    instrument=instrument,
                    strike=strike,
                    expiry=expiry,
                    option_type=option_type,
                    quantity=1.0,
                    reason=f"IV percentile {iv_percentile:.1f}% < {self.params['low_iv_threshold']}%",
                    iv=latest[iv_col],
                    spot_price=spot_price,
                    delta=latest.get('delta'),
                    gamma=latest.get('gamma')
                ))
        
        print(f"  Generated {len(signals)} signals")
        return signals


# Strategy registry
AVAILABLE_STRATEGIES = {
    'simple_vol': SimpleVolatilityStrategy,
}


def get_strategy(strategy_name: str, params: Dict = None) -> BaseStrategy:
    """Factory function to get strategy by name."""
    if strategy_name not in AVAILABLE_STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(AVAILABLE_STRATEGIES.keys())}")
    
    return AVAILABLE_STRATEGIES[strategy_name](params)