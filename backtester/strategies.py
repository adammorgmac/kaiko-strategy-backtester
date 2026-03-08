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


class BaseStrategy:
    """Base class for all strategies."""
    
    def __init__(self, name: str, params: Dict):
        self.name = name
        self.params = params
        
    def generate_signals(self, data: pd.DataFrame, spot_data: pd.DataFrame) -> List[TradeSignal]:
        """Generate trading signals. Must be implemented by child classes."""
        raise NotImplementedError


class SimpleVolatilityStrategy(BaseStrategy):
    """Simple strategy: Trade based on IV percentile."""
    
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
    
    def calculate_iv_percentile(self, iv_series: pd.Series) -> float:
        """Calculate IV percentile over lookback period."""
        if len(iv_series) < 2:
            return 50.0
        current_iv = iv_series.iloc[-1]
        return (iv_series < current_iv).sum() / len(iv_series) * 100
    
    def generate_signals(self, data: pd.DataFrame, spot_data: pd.DataFrame) -> List[TradeSignal]:
        """Generate signals based on IV percentile."""
        signals = []
        
        if data.empty or spot_data.empty:
            return signals
        
        # Get spot price
        spot_price = spot_data['price'].iloc[-1] if not spot_data.empty else None
        if spot_price is None:
            return signals
        
        # Get current timestamp
        current_time = pd.Timestamp.now(tz='UTC')
        
        # Calculate average IV and thresholds
        avg_iv = data['mark_iv'].mean()
        iv_std = data['mark_iv'].std()
        
        high_threshold = avg_iv + (self.params['high_iv_threshold'] / 100) * iv_std
        low_threshold = avg_iv - (self.params['low_iv_threshold'] / 100) * iv_std
        
        # Find ATM options
        data = data.copy()
        data['dist_from_spot'] = abs(data['strike_price'] - spot_price)
        atm_data = data.nsmallest(10, 'dist_from_spot')
        
        for _, row in atm_data.iterrows():
            iv = row['mark_iv']
            
            if iv > high_threshold:
                signals.append(TradeSignal(
                    timestamp=current_time,
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
                    gamma=row.get('gamma')
                ))
            
            elif iv < low_threshold:
                signals.append(TradeSignal(
                    timestamp=current_time,
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
                    gamma=row.get('gamma')
                ))
        
        return signals


# Strategy registry
AVAILABLE_STRATEGIES = {
    'simple_vol': SimpleVolatilityStrategy,
}


def get_strategy(strategy_name: str, params: Dict = None) -> BaseStrategy:
    """Factory function to get strategy by name."""
    if strategy_name not in AVAILABLE_STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    return AVAILABLE_STRATEGIES[strategy_name](params)