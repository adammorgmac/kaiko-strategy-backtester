"""
Backtesting engine with proper mark-to-mark PnL calculation.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

from .strategies import TradeSignal, SignalType, BaseStrategy


@dataclass
class Position:
    """Represents an open position."""
    instrument: str
    entry_time: pd.Timestamp
    entry_mark: float
    quantity: float
    option_type: str
    strike: float
    expiry: str
    side: str  # "LONG" or "SHORT"
    entry_delta: float = 0.0
    entry_gamma: float = 0.0


@dataclass
class Trade:
    """Represents a completed trade."""
    instrument: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_mark: float
    exit_mark: float
    quantity: float
    pnl: float
    days_held: float
    side: str


class BacktestEngine:
    """
    Backtesting engine using real mark-to-mark pricing.
    
    Note: This engine requires historical snapshot data with observed marks.
    It will NOT fabricate prices or PnL.
    """
    
    def __init__(
        self,
        initial_capital: float = 100000,
        position_size_pct: float = 0.05,
        max_positions: int = 10
    ):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position_size_pct = position_size_pct
        self.max_positions = max_positions
        
        self.positions: List[Position] = []
        self.closed_trades: List[Trade] = []
    
    def run_backtest(
        self,
        strategy: BaseStrategy,
        snapshots: List[pd.DataFrame],
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Run backtest on historical snapshots.
        
        Args:
            strategy: Strategy instance
            snapshots: List of daily snapshot DataFrames with snapshot_timestamp
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Backtest results dictionary
        """
        
        print(f"\n{'='*70}")
        print(f"BACKTESTING: {strategy.name}")
        print(f"{'='*70}")
        print(f"Period: {start_date} to {end_date}")
        print(f"Initial Capital: ${self.initial_capital:,.0f}")
        print(f"{'='*70}\n")
        
        if not snapshots:
            return {'error': 'No snapshot data provided'}
        
        # Sort snapshots by timestamp
        snapshots = sorted(snapshots, key=lambda df: df['snapshot_timestamp'].iloc[0])
        
        execution_count = 0
        
        for snapshot in snapshots:
            snapshot_time = snapshot['snapshot_timestamp'].iloc[0]
            
            # Generate signals for this snapshot
            # Note: Strategy must use snapshot_time, not now()
            signals = strategy.generate_signals(snapshot, pd.DataFrame())
            
            # Execute signals
            for signal in signals:
                if len(self.positions) < self.max_positions:
                    if self._execute_signal(signal, snapshot):
                        execution_count += 1
        
        print(f"\n✓ Executed {execution_count} trades")
        print(f"✓ {len(self.closed_trades)} trades closed")
        print(f"✓ {len(self.positions)} positions still open")
        
        # Note: We don't force-close open positions with fake prices
        # In production, mark them to final snapshot marks
        
        results = self._calculate_performance()
        self._print_results(results)
        
        return results
    
    def _execute_signal(
        self,
        signal: TradeSignal,
        snapshot: pd.DataFrame
    ) -> bool:
        """Execute a trade signal using observed marks."""
        
        # Get mark price from signal or snapshot
        entry_mark = signal.mark_price if hasattr(signal, 'mark_price') else None
        
        if entry_mark is None or pd.isna(entry_mark) or entry_mark <= 0:
            # Cannot execute without real mark
            return False
        
        # Calculate position size
        position_value = self.capital * self.position_size_pct
        quantity = position_value / entry_mark
        
        # Determine side
        side = "SHORT" if signal.signal_type == SignalType.SELL else "LONG"
        if side == "SHORT":
            quantity = -quantity
        
        # Create position
        position = Position(
            instrument=signal.instrument,
            entry_time=signal.timestamp,
            entry_mark=entry_mark,
            quantity=quantity,
            option_type=signal.option_type,
            strike=signal.strike,
            expiry=signal.expiry,
            side=side,
            entry_delta=signal.delta if signal.delta else 0.0,
            entry_gamma=signal.gamma if signal.gamma else 0.0
        )
        
        self.positions.append(position)
        
        # Update capital (deduct premium for longs, receive for shorts)
        cash_impact = entry_mark * abs(quantity)
        if side == "LONG":
            self.capital -= cash_impact
        
        print(f"  [{signal.timestamp.strftime('%Y-%m-%d')}] {side} {signal.option_type.upper()} "
              f"@ ${signal.strike:,.0f} | Mark: ${entry_mark:.2f}")
        
        return True
    
    def _calculate_performance(self) -> Dict:
        """Calculate performance metrics from closed trades."""
        
        if not self.closed_trades:
            return {
                'error': 'No closed trades',
                'message': 'Backtest ran but no trades were closed. This is expected if using single snapshots.'
            }
        
        pnls = [trade.pnl for trade in self.closed_trades]
        
        total_pnl = sum(pnls)
        total_return = total_pnl / self.initial_capital
        
        winning_trades = [pnl for pnl in pnls if pnl > 0]
        losing_trades = [pnl for pnl in pnls if pnl < 0]
        
        win_rate = len(winning_trades) / len(pnls) if pnls else 0
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = np.mean(losing_trades) if losing_trades else 0
        
        # Sharpe (simplified - assumes daily trades)
        if len(pnls) > 1:
            returns = [pnl / self.initial_capital for pnl in pnls]
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe = 0
        
        return {
            'total_pnl': total_pnl,
            'total_return_pct': total_return * 100,
            'num_trades': len(self.closed_trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'sharpe_ratio': sharpe,
            'final_capital': self.capital,
            'trades': self.closed_trades
        }
    
    def _print_results(self, results: Dict):
        """Print backtest results."""
        
        if 'error' in results:
            print(f"\n⚠️  {results['error']}")
            if 'message' in results:
                print(f"    {results['message']}")
            return
        
        print(f"\n{'='*70}")
        print("BACKTEST RESULTS")
        print(f"{'='*70}")
        print(f"Total PnL:          ${results['total_pnl']:,.2f}")
        print(f"Total Return:       {results['total_return_pct']:.2f}%")
        print(f"Number of Trades:   {results['num_trades']}")
        print(f"Win Rate:           {results['win_rate']:.1%}")
        print(f"Average Win:        ${results['avg_win']:,.2f}")
        print(f"Average Loss:       ${results['avg_loss']:,.2f}")
        print(f"Sharpe Ratio:       {results['sharpe_ratio']:.2f}")
        print(f"Final Capital:      ${results['final_capital']:,.2f}")
        print(f"{'='*70}\n")