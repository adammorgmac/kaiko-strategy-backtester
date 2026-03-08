"""
Backtesting engine with honest mark-to-mark PnL calculation.
No fabricated prices or synthetic assumptions.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

from .strategies import TradeSignal, SignalType, BaseStrategy


@dataclass
class Position:
    """Represents an open position with observed entry prices."""
    instrument: str
    entry_time: pd.Timestamp
    entry_mark_price: float
    entry_bid_price: float
    entry_ask_price: float
    quantity: float
    option_type: str
    strike: float
    expiry: str
    side: str  # "LONG" or "SHORT"
    snapshot_timestamp: Optional[pd.Timestamp] = None
    entry_delta: float = 0.0
    entry_gamma: float = 0.0


@dataclass
class Trade:
    """Represents a completed trade with observed entry and exit prices."""
    instrument: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_mark: float
    exit_mark: float
    quantity: float
    pnl: float
    days_held: float
    side: str
    option_type: str
    strike: float


class BacktestEngine:
    """
    Backtesting engine using only observed market prices.
    
    Rules:
    - Only execute trades when real mark prices are available
    - Only close positions when exit marks can be observed
    - No fabricated pricing or synthetic PnL
    - Long-only for simplicity (shorts require margin modeling)
    """
    
    def __init__(
        self,
        initial_capital: float = 100000,
        position_size_pct: float = 0.05,
        max_positions: int = 10
    ):
        """
        Initialize backtest engine.
        
        Args:
            initial_capital: Starting capital
            position_size_pct: Position size as % of capital (0.05 = 5%)
            max_positions: Maximum concurrent positions
        """
        self.initial_capital = initial_capital
        self.position_size_pct = position_size_pct
        self.max_positions = max_positions
        
        # State - reset at start of each backtest
        self.capital = initial_capital
        self.positions: List[Position] = []
        self.closed_trades: List[Trade] = []
        self.equity_curve: List[Dict] = []
    
    def run_backtest(
        self,
        strategy: BaseStrategy,
        market_data: pd.DataFrame,
        spot_data: pd.DataFrame,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Run backtest using historical market data.
        
        Args:
            strategy: Strategy instance
            market_data: DataFrame with timestamp, instrument, mark_price, etc.
            spot_data: DataFrame with timestamp, price (for reference)
            start_date: Start date YYYY-MM-DD
            end_date: End date YYYY-MM-DD
        
        Returns:
            Dictionary with backtest results
        """
        
        # Reset state
        self.capital = self.initial_capital
        self.positions = []
        self.closed_trades = []
        self.equity_curve = []
        
        print(f"\n{'='*70}")
        print(f"BACKTESTING: {strategy.name}")
        print(f"{'='*70}")
        print(f"Period: {start_date} to {end_date}")
        print(f"Initial Capital: ${self.initial_capital:,.0f}\n")
        
        if market_data.empty:
            return {'error': 'No market data provided'}
        
        # Convert dates to timezone-aware timestamps
        start_ts = pd.Timestamp(start_date, tz='UTC')
        end_ts = pd.Timestamp(end_date, tz='UTC')
        
        # Ensure timestamps are timezone-aware
        market_data = market_data.copy()
        if 'timestamp' in market_data.columns:
            market_data['timestamp'] = pd.to_datetime(market_data['timestamp'], utc=True)
        
        if not spot_data.empty and 'timestamp' in spot_data.columns:
            spot_data = spot_data.copy()
            spot_data['timestamp'] = pd.to_datetime(spot_data['timestamp'], utc=True)
        
        # Filter to date range
        market_data = market_data[
            (market_data['timestamp'] >= start_ts) &
            (market_data['timestamp'] <= end_ts)
        ]
        
        if not spot_data.empty:
            spot_data = spot_data[
                (spot_data['timestamp'] >= start_ts) &
                (spot_data['timestamp'] <= end_ts)
            ]
        
        if market_data.empty:
            return {'error': 'No market data in specified date range'}
        
        print(f"Market data: {len(market_data)} rows")
        print(f"Date range: {market_data['timestamp'].min()} to {market_data['timestamp'].max()}\n")
        
        # Generate signals
        # Note: For multi-day backtests, this should be called per-day snapshot
        # For now, generate once (assumes single snapshot or similar)
        signals = strategy.generate_signals(market_data, spot_data)
        
        print(f"Generated {len(signals)} signals\n")
        
        # Execute signals
        executed = 0
        for signal in signals:
            if len(self.positions) >= self.max_positions:
                print(f"  Max positions reached, skipping remaining signals")
                break
            
            if self._execute_signal(signal, market_data):
                executed += 1
        
        print(f"\n✓ Executed {executed}/{len(signals)} signals")
        print(f"✓ {len(self.positions)} positions open")
        print(f"✓ {len(self.closed_trades)} trades closed\n")
        
        # For now, do not force-close positions
        # In real backtest, you'd mark-to-market at end date
        
        # Calculate results
        results = self._calculate_performance()
        self._print_results(results)
        
        return results
    
    def _execute_signal(
        self,
        signal: TradeSignal,
        market_data: pd.DataFrame
    ) -> bool:
        """
        Execute a trade signal using observed mark price.
        
        Returns:
            True if executed, False if skipped
        """
        
        # Require observed mark price
        entry_mark = getattr(signal, 'mark_price', None)
        
        if entry_mark is None or pd.isna(entry_mark) or entry_mark <= 0:
            # No valid mark price available, skip execution
            return False
        
        # Get optional bid/ask if available
        entry_bid = getattr(signal, 'bid_price', None)
        entry_ask = getattr(signal, 'ask_price', None)
        
        if entry_bid is None or pd.isna(entry_bid):
            entry_bid = entry_mark
        if entry_ask is None or pd.isna(entry_ask):
            entry_ask = entry_mark
        
        # Determine side
        side = "SHORT" if signal.signal_type == SignalType.SELL else "LONG"
        
        # For simplicity, only support long trades
        # Shorting requires margin modeling and collateral tracking
        if side == "SHORT":
            # Skip short positions for now
            return False
        
        # Calculate position size
        position_value = self.capital * self.position_size_pct
        quantity = position_value / entry_mark
        
        # Check if we have enough capital (for longs only)
        cash_required = entry_mark * quantity
        if cash_required > self.capital:
            # Not enough capital
            return False
        
        # Create position
        position = Position(
            instrument=signal.instrument,
            entry_time=signal.timestamp,
            entry_mark_price=entry_mark,
            entry_bid_price=entry_bid,
            entry_ask_price=entry_ask,
            quantity=quantity,
            option_type=signal.option_type,
            strike=signal.strike,
            expiry=signal.expiry,
            side=side,
            snapshot_timestamp=signal.timestamp,
            entry_delta=signal.delta if signal.delta else 0.0,
            entry_gamma=signal.gamma if signal.gamma else 0.0
        )
        
        self.positions.append(position)
        
        # Update capital (deduct premium paid for long)
        self.capital -= cash_required
        
        print(f"  [{signal.timestamp.strftime('%Y-%m-%d')}] {side} {signal.option_type.upper()} "
              f"@ ${signal.strike:,.0f} | Mark: ${entry_mark:.2f} | Qty: {quantity:.2f}")
        
        return True
    
    def _lookup_mark_price(
        self,
        instrument: str,
        timestamp: pd.Timestamp,
        market_data: pd.DataFrame
    ) -> Optional[float]:
        """
        Look up observed mark price for an instrument at or before timestamp.
        
        Returns:
            Mark price if found, None otherwise
        """
        rows = market_data[
            (market_data['instrument'] == instrument) &
            (market_data['timestamp'] <= timestamp)
        ].sort_values('timestamp')
        
        if rows.empty:
            return None
        
        # Use most recent available mark
        latest = rows.iloc[-1]
        
        mark = latest.get('mark_price')
        if mark is None or pd.isna(mark) or mark <= 0:
            return None
        
        return float(mark)
    
    def _close_position(
        self,
        position: Position,
        exit_time: pd.Timestamp,
        exit_mark: float
    ) -> Trade:
        """
        Close a position with observed exit mark.
        
        Returns:
            Trade object with PnL
        """
        
        # Calculate option PnL
        option_pnl = (exit_mark - position.entry_mark_price) * position.quantity
        
        # Days held
        days_held = (exit_time - position.entry_time).total_seconds() / 86400
        
        # Create trade record
        trade = Trade(
            instrument=position.instrument,
            entry_time=position.entry_time,
            exit_time=exit_time,
            entry_mark=position.entry_mark_price,
            exit_mark=exit_mark,
            quantity=position.quantity,
            pnl=option_pnl,
            days_held=days_held,
            side=position.side,
            option_type=position.option_type,
            strike=position.strike
        )
        
        # Update capital (receive exit proceeds for longs)
        self.capital += exit_mark * position.quantity
        
        return trade
    
    def _calculate_equity(self, current_time: pd.Timestamp, market_data: pd.DataFrame) -> float:
        """
        Calculate current portfolio equity using observed marks where available.
        
        Args:
            current_time: Current timestamp
            market_data: Market data for mark lookup
        
        Returns:
            Total equity (cash + marked positions)
        """
        
        unrealized_pnl = 0.0
        
        for position in self.positions:
            # Try to get current mark
            current_mark = self._lookup_mark_price(
                position.instrument,
                current_time,
                market_data
            )
            
            if current_mark is None:
                # No mark available, use entry mark (zero unrealized PnL)
                current_mark = position.entry_mark_price
            
            # Mark-to-market
            position_value = current_mark * position.quantity
            entry_value = position.entry_mark_price * position.quantity
            unrealized_pnl += (position_value - entry_value)
        
        return self.capital + unrealized_pnl
    
    def _calculate_performance(self) -> Dict:
        """Calculate performance metrics from closed trades only."""
        
        if not self.closed_trades:
            return {
                'error': 'No closed trades',
                'message': 'Backtest completed but no positions were closed. '
                          'This is expected if using single snapshot or if exit marks are unavailable.',
                'initial_capital': self.initial_capital,
                'final_capital': self.capital,
                'open_positions': len(self.positions)
            }
        
        pnls = [trade.pnl for trade in self.closed_trades]
        
        total_pnl = sum(pnls)
        total_return = total_pnl / self.initial_capital
        
        winning_trades = [pnl for pnl in pnls if pnl > 0]
        losing_trades = [pnl for pnl in pnls if pnl < 0]
        
        win_rate = len(winning_trades) / len(pnls) if pnls else 0
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = np.mean(losing_trades) if losing_trades else 0
        
        # Sharpe ratio (simplified - assumes each trade is independent)
        if len(pnls) > 1:
            returns = [pnl / self.initial_capital for pnl in pnls]
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0
        else:
            sharpe = 0
        
        # Max drawdown (if equity curve exists)
        max_dd = 0
        if len(self.equity_curve) > 1:
            equity_values = [e['equity'] for e in self.equity_curve]
            peak = equity_values[0]
            for equity in equity_values:
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd
        
        return {
            'total_pnl': total_pnl,
            'total_return_pct': total_return * 100,
            'num_trades': len(self.closed_trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_dd * 100,
            'final_capital': self.capital,
            'open_positions': len(self.positions),
            'trades': self.closed_trades
        }
    
    def _print_results(self, results: Dict):
        """Print backtest results in readable format."""
        
        if 'error' in results:
            print(f"\n⚠️  {results['error']}")
            if 'message' in results:
                print(f"    {results['message']}")
            if 'open_positions' in results:
                print(f"    Open positions: {results['open_positions']}")
            return
        
        print(f"\n{'='*70}")
        print("BACKTEST RESULTS")
        print(f"{'='*70}")
        print(f"Total P&L:          ${results['total_pnl']:,.2f}")
        print(f"Total Return:       {results['total_return_pct']:.2f}%")
        print(f"Number of Trades:   {results['num_trades']}")
        print(f"Win Rate:           {results['win_rate']:.1%}")
        print(f"Average Win:        ${results['avg_win']:,.2f}")
        print(f"Average Loss:       ${results['avg_loss']:,.2f}")
        print(f"Sharpe Ratio:       {results['sharpe_ratio']:.2f}")
        print(f"Max Drawdown:       {results['max_drawdown_pct']:.2f}%")
        print(f"Final Capital:      ${results['final_capital']:,.2f}")
        print(f"Open Positions:     {results['open_positions']}")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    print("Backtest engine loaded")
    print("This engine requires observed mark prices and will not fabricate data")