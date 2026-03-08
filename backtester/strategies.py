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
    option_type: str
    quantity: float
    reason: str
    iv: Optional[float] = None
    spot_price: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    mark_price: Optional[float] = None  # Add this field


class BaseStrategy:
    """Base class for all strategies."""
    
    def __init__(self, name: str, params: Dict):
        self.name = name
        self.params = params
        
    def generate_signals(self, data: pd.DataFrame, spot_data: pd.DataFrame) -> List[TradeSignal]:
        """Generate trading signals. Must be implemented by child classes."""
        raise NotImplementedError


class SimpleVolatilityStrategy(BaseStrategy):
    """Simple strategy: Trade based on IV levels."""
    
    def __init__(self, params: Dict = None):
        default_params = {
            'lookback_days': 30,
            'high_iv_threshold': 75,
            'low_iv_threshold': 25,
            'min_dte': 7,
            'max_dte': 60,
        }
        if params:
            default_params.update(params)
        
        super().__init__("Simple Volatility Strategy", default_params)
    
    def generate_signals(self, data: pd.DataFrame, spot_data: pd.DataFrame) -> List[TradeSignal]:
        """Generate signals based on IV levels."""
        signals = []
        
        if data.empty:
            return signals
        
        # Get snapshot timestamp from data
        if 'snapshot_timestamp' not in data.columns:
            raise ValueError(
                "Data must include 'snapshot_timestamp' column. "
                "Strategies cannot use wall-clock time for signal generation."
            )
        
        snapshot_time = pd.to_datetime(data['snapshot_timestamp'].iloc[0])
        
        # Get spot price from data if available
        spot_price = None
        if 'spot_price' in data.columns and data['spot_price'].notna().any():
            spot_price = data['spot_price'].iloc[0]
        elif not spot_data.empty and 'price' in spot_data.columns:
            spot_data = spot_data.sort_values('timestamp')
            spot_price = spot_data['price'].iloc[-1]
        
        if spot_price is None:
            return signals
        
        # Calculate thresholds
        avg_iv = data['mark_iv'].mean()
        iv_std = data['mark_iv'].std()
        
        high_threshold = avg_iv + (self.params['high_iv_threshold'] / 100) * iv_std
        low_threshold = avg_iv - (self.params['low_iv_threshold'] / 100) * iv_std
        
        # Find ATM options per expiry
        atm_rows = []
        for expiry, expiry_df in data.groupby('expiry'):
            expiry_df = expiry_df.copy()
            expiry_df['dist_from_spot'] = (expiry_df['strike_price'] - spot_price).abs()
            atm_rows.append(expiry_df.nsmallest(2, 'dist_from_spot'))
        
        atm_data = pd.concat(atm_rows, ignore_index=True) if atm_rows else pd.DataFrame()
        
        # Generate signals
        for _, row in atm_data.iterrows():
            iv = row['mark_iv']
            
            # Get mark price if available, else estimate
            mark_price = row.get('mark_price')
            if mark_price is None or pd.isna(mark_price):
                # Rough estimate for demonstration
                mark_price = iv * spot_price * 0.08
            
            if iv > high_threshold:
                signal = TradeSignal(
                    timestamp=snapshot_time,
                    signal_type=SignalType.SELL,
                    instrument=row['instrument'],
                    strike=row['strike_price'],
                    expiry=str(row['expiry']),
                    option_type=row['option_type'],
                    quantity=1.0,
                    reason=f"IV {iv:.1f}% > {high_threshold:.1f}%",
                    iv=iv,
                    spot_price=spot_price,
                    delta=row.get('delta'),
                    gamma=row.get('gamma'),
                    mark_price=mark_price
                )
                signals.append(signal)
            
            elif iv < low_threshold:
                signal = TradeSignal(
                    timestamp=snapshot_time,
                    signal_type=SignalType.BUY,
                    instrument=row['instrument'],
                    strike=row['strike_price'],
                    expiry=str(row['expiry']),
                    option_type=row['option_type'],
                    quantity=1.0,
                    reason=f"IV {iv:.1f}% < {low_threshold:.1f}%",
                    iv=iv,
                    spot_price=spot_price,
                    delta=row.get('delta'),
                    gamma=row.get('gamma'),
                    mark_price=mark_price
                )
                signals.append(signal)
        
        return signals


# Strategy registry - MUST BE AT END
AVAILABLE_STRATEGIES = {
    'simple_vol': SimpleVolatilityStrategy,
}


def get_strategy(strategy_name: str, params: Dict = None) -> BaseStrategy:
    """Factory function to get strategy by name."""
    if strategy_name not in AVAILABLE_STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(AVAILABLE_STRATEGIES.keys())}")
    return AVAILABLE_STRATEGIES[strategy_name](params)