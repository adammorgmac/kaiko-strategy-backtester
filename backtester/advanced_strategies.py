"""
Advanced trading strategies for options.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional

from .strategies import BaseStrategy, TradeSignal, SignalType


class SkewStrategy(BaseStrategy):
    """Trade the put/call skew."""
    
    def __init__(self, params: Dict = None):
        default_params = {
            'skew_threshold': 5.0,
            'atm_range': 0.05,
        }
        if params:
            default_params.update(params)
        super().__init__("Skew Trading Strategy", default_params)
    
    def generate_signals(self, data: pd.DataFrame, spot_data: pd.DataFrame) -> List[TradeSignal]:
        """Generate signals based on put/call skew."""
        signals = []
        
        if data.empty or spot_data.empty:
            return signals
        
        current_spot = spot_data['price'].iloc[-1]
        current_time = pd.Timestamp.now(tz='UTC')
        
        for expiry in data['expiry'].unique():
            expiry_data = data[data['expiry'] == expiry]
            
            atm_lower = current_spot * (1 - self.params['atm_range'])
            atm_upper = current_spot * (1 + self.params['atm_range'])
            
            atm_strikes = expiry_data[
                (expiry_data['strike_price'] >= atm_lower) &
                (expiry_data['strike_price'] <= atm_upper)
            ]['strike_price'].unique()
            
            for strike in atm_strikes[:3]:  # Limit to 3 strikes
                strike_data = expiry_data[expiry_data['strike_price'] == strike]
                
                call_data = strike_data[strike_data['option_type'] == 'call']
                put_data = strike_data[strike_data['option_type'] == 'put']
                
                if call_data.empty or put_data.empty:
                    continue
                
                call_iv = call_data['mark_iv'].iloc[0]
                put_iv = put_data['mark_iv'].iloc[0]
                skew = put_iv - call_iv
                
                if skew > self.params['skew_threshold']:
                    signals.append(TradeSignal(
                        timestamp=current_time,
                        signal_type=SignalType.SELL,
                        instrument=put_data['instrument'].iloc[0],
                        strike=strike,
                        expiry=str(expiry),
                        option_type='put',
                        quantity=1.0,
                        reason=f"Put skew {skew:.1f}% > threshold",
                        iv=put_iv,
                        spot_price=current_spot,
                        delta=put_data['delta'].iloc[0],
                        gamma=put_data['gamma'].iloc[0]
                    ))
        
        return signals


class GammaScalpStrategy(BaseStrategy):
    """Target high gamma options for scalping."""
    
    def __init__(self, params: Dict = None):
        default_params = {
            'min_gamma': 0.0001,
            'atm_range': 0.03,
        }
        if params:
            default_params.update(params)
        super().__init__("Gamma Scalping Strategy", default_params)
    
    def generate_signals(self, data: pd.DataFrame, spot_data: pd.DataFrame) -> List[TradeSignal]:
        """Generate gamma scalping signals."""
        signals = []
        
        if data.empty or spot_data.empty:
            return signals
        
        current_spot = spot_data['price'].iloc[-1]
        current_time = pd.Timestamp.now(tz='UTC')
        
        high_gamma = data[data['gamma'] > self.params['min_gamma']].copy()
        
        atm_lower = current_spot * (1 - self.params['atm_range'])
        atm_upper = current_spot * (1 + self.params['atm_range'])
        
        high_gamma = high_gamma[
            (high_gamma['strike_price'] >= atm_lower) &
            (high_gamma['strike_price'] <= atm_upper)
        ]
        
        for _, row in high_gamma.head(5).iterrows():
            signals.append(TradeSignal(
                timestamp=current_time,
                signal_type=SignalType.BUY,
                instrument=row['instrument'],
                strike=row['strike_price'],
                expiry=str(row['expiry']),
                option_type=row['option_type'],
                quantity=1.0,
                reason=f"High gamma {row['gamma']:.5f}",
                iv=row['mark_iv'],
                spot_price=current_spot,
                delta=row['delta'],
                gamma=row['gamma']
            ))
        
        return signals


class CalendarSpreadStrategy(BaseStrategy):
    """Trade the term structure."""
    
    def __init__(self, params: Dict = None):
        default_params = {
            'min_iv_diff': 5.0,
            'atm_range': 0.05
        }
        if params:
            default_params.update(params)
        super().__init__("Calendar Spread Strategy", default_params)
    
    def generate_signals(self, data: pd.DataFrame, spot_data: pd.DataFrame) -> List[TradeSignal]:
        """Generate calendar spread signals."""
        signals = []
        
        if data.empty or spot_data.empty or len(data['expiry'].unique()) < 2:
            return signals
        
        current_spot = spot_data['price'].iloc[-1]
        current_time = pd.Timestamp.now(tz='UTC')
        
        # Simple implementation for now
        return signals


class StraddleScreener(BaseStrategy):
    """Screen for optimal straddle entry points."""
    
    def __init__(self, params: Dict = None):
        default_params = {
            'max_iv': 70.0,
            'min_gamma': 0.0001,
            'min_oi': 10.0,
            'atm_range': 0.02
        }
        if params:
            default_params.update(params)
        super().__init__("Straddle Screener", default_params)
    
    def generate_signals(self, data: pd.DataFrame, spot_data: pd.DataFrame) -> List[TradeSignal]:
        """Screen for straddle opportunities."""
        signals = []
        
        if data.empty or spot_data.empty:
            return signals
        
        current_spot = spot_data['price'].iloc[-1]
        current_time = pd.Timestamp.now(tz='UTC')
        
        candidates = data[
            (data['mark_iv'] < self.params['max_iv']) &
            (data['gamma'] > self.params['min_gamma']) &
            (data['open_interest'] > self.params['min_oi'])
        ].copy()
        
        atm_lower = current_spot * (1 - self.params['atm_range'])
        atm_upper = current_spot * (1 + self.params['atm_range'])
        
        candidates = candidates[
            (candidates['strike_price'] >= atm_lower) &
            (candidates['strike_price'] <= atm_upper)
        ]
        
        for _, row in candidates.head(5).iterrows():
            signals.append(TradeSignal(
                timestamp=current_time,
                signal_type=SignalType.BUY,
                instrument=row['instrument'],
                strike=row['strike_price'],
                expiry=str(row['expiry']),
                option_type=row['option_type'],
                quantity=1.0,
                reason=f"Straddle: IV {row['mark_iv']:.1f}%, Γ {row['gamma']:.5f}",
                iv=row['mark_iv'],
                spot_price=current_spot,
                delta=row['delta'],
                gamma=row['gamma']
            ))
        
        return signals


# Strategy registry
ADVANCED_STRATEGIES = {
    'skew': SkewStrategy,
    'gamma_scalp': GammaScalpStrategy,
    'calendar': CalendarSpreadStrategy,
    'straddle_screen': StraddleScreener
}


def get_advanced_strategy(strategy_name: str, params: Dict = None) -> BaseStrategy:
    """Factory function for advanced strategies."""
    if strategy_name not in ADVANCED_STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    return ADVANCED_STRATEGIES[strategy_name](params)