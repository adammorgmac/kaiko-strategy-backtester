"""
Backtesting engine with PnL calculation and delta hedging.
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
    entry_price: float
    quantity: float
    option_type: str
    strike: float
    expiry: str
    entry_delta: float = 0.0
    entry_gamma: float = 0.0
    hedge_quantity: float = 0.0
    entry_spot: float = 0.0


@dataclass
class Trade:
    """Represents a completed trade."""
    instrument: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    option_pnl: float
    hedge_pnl: float
    days_held: float
    strategy_reason: str


class BacktestEngine:
    """Core backtesting engine."""
    
    def __init__(
        self,
        initial_capital: float = 100000,
        position_size_pct: float = 0.05,  # 5% of capital per trade
        max_positions: int = 10
    ):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position_size_pct = position_size_pct
        self.max_positions = max_positions
        
        self.positions: List[Position] = []
        self.closed_trades: List[Trade] = []
        self.equity_curve = []
        
    def run_backtest(
        self,
        strategy: BaseStrategy,
        market_data: pd.DataFrame,
        spot_data: pd.DataFrame,
        start_date: str,
        end_date: str
    ) -> Dict:
        """Run backtest for a strategy."""
        
        print(f"\n{'='*70}")
        print(f"BACKTESTING: {strategy.name}")
        print(f"{'='*70}")
        print(f"Period: {start_date} to {end_date}")
        print(f"Initial Capital: ${self.initial_capital:,.0f}")
        print(f"Position Size: {self.position_size_pct*100:.0f}% per trade")
        print(f"Max Positions: {self.max_positions}")
        print(f"{'='*70}\n")
        
        # Filter data
        market_data = market_data[
            (market_data['timestamp'] >= start_date) &
            (market_data['timestamp'] <= end_date)
        ].copy()
        
        spot_data = spot_data[
            (spot_data['timestamp'] >= start_date) &
            (spot_data['timestamp'] <= end_date)
        ].copy()
        
        if market_data.empty or spot_data.empty:
            print("ERROR: No data in date range")
            return {'error': 'No data'}
        
        print(f"Market data points: {len(market_data):,}")
        print(f"Spot data points: {len(spot_data):,}\n")
        
        # Generate signals
        print("Generating trading signals...")
        signals = strategy.generate_signals(market_data, spot_data)
        
        if not signals:
            print("\nNo signals generated!")
            return {'error': 'No signals'}
        
        print(f"Generated {len(signals)} total signals\n")
        
        # Group signals by timestamp and execute
        signals_df = pd.DataFrame([{
            'timestamp': s.timestamp,
            'signal': s
        } for s in signals])
        
        execution_count = 0
        
        for timestamp in signals_df['timestamp'].unique():
            day_signals = signals_df[signals_df['timestamp'] == timestamp]['signal'].tolist()
            
            for signal in day_signals:
                if len(self.positions) < self.max_positions:
                    if self._execute_signal(signal, market_data, spot_data):
                        execution_count += 1
            
            # Update equity curve
            equity = self._calculate_equity(timestamp, market_data, spot_data)
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': equity,
                'num_positions': len(self.positions),
                'cash': self.capital
            })
        
        print(f"\nExecuted {execution_count} trades")
        
        # Close remaining positions
        print("Closing remaining positions...")
        self._close_all_positions(end_date, market_data, spot_data)
        
        # Calculate results
        results = self._calculate_performance()
        self._print_results(results)
        
        return results
    
    def _execute_signal(
        self,
        signal: TradeSignal,
        market_data: pd.DataFrame,
        spot_data: pd.DataFrame
    ) -> bool:
        """Execute a trade signal."""
        
        # Get option price (simplified - use IV * spot * 0.1 as proxy)
        if signal.iv and signal.spot_price:
            entry_price = signal.iv * signal.spot_price * 0.1
        else:
            return False
        
        # Calculate position size
        position_value = self.capital * self.position_size_pct
        quantity = position_value / entry_price if entry_price > 0 else 0
        
        if quantity == 0:
            return False
        
        # Adjust for signal type
        if signal.signal_type == SignalType.SELL:
            quantity = -quantity
        
        # Get delta for hedging
        delta = signal.delta if signal.delta else 0.5
        gamma = signal.gamma if signal.gamma else 0.01
        
        # Create position
        position = Position(
            instrument=signal.instrument,
            entry_time=signal.timestamp,
            entry_price=entry_price,
            quantity=quantity,
            option_type=signal.option_type,
            strike=signal.strike,
            expiry=signal.expiry,
            entry_delta=delta,
            entry_gamma=gamma,
            hedge_quantity=-delta * quantity,
            entry_spot=signal.spot_price
        )
        
        self.positions.append(position)
        self.capital -= abs(entry_price * quantity) * 0.1  # Simplified margin
        
        print(f"  [{signal.timestamp.strftime('%Y-%m-%d')}] {signal.signal_type.name} {signal.option_type.upper()} "
              f"@ ${signal.strike:,.0f} | {signal.reason}")
        
        return True
    
    def _close_all_positions(
        self,
        exit_time: str,
        market_data: pd.DataFrame,
        spot_data: pd.DataFrame
    ):
        """Close all open positions."""
        exit_timestamp = pd.Timestamp(exit_time)
        
        for position in self.positions:
            # Simplified exit price
            exit_price = position.entry_price * 0.95  # Assume some profit/loss
            
            # Calculate PnL
            option_pnl = (exit_price - position.entry_price) * position.quantity
            
            # Hedge PnL
            spot_exit = spot_data[spot_data['timestamp'] <= exit_timestamp]['price'].iloc[-1] if not spot_data.empty else position.entry_spot
            hedge_pnl = (spot_exit - position.entry_spot) * position.hedge_quantity
            
            total_pnl = option_pnl + hedge_pnl
            
            days_held = (exit_timestamp - position.entry_time).days
            
            trade = Trade(
                instrument=position.instrument,
                entry_time=position.entry_time,
                exit_time=exit_timestamp,
                entry_price=position.entry_price,
                exit_price=exit_price,
                quantity=position.quantity,
                pnl=total_pnl,
                option_pnl=option_pnl,
                hedge_pnl=hedge_pnl,
                days_held=days_held,
                strategy_reason="End of backtest"
            )
            
            self.closed_trades.append(trade)
            self.capital += total_pnl
        
        self.positions = []
    
    def _calculate_equity(
        self,
        timestamp: pd.Timestamp,
        market_data: pd.DataFrame,
        spot_data: pd.DataFrame
    ) -> float:
        """Calculate current equity."""
        unrealized_pnl = 0
        
        for position in self.positions:
            # Simplified: assume 5% move
            unrealized_pnl += position.entry_price * position.quantity * 0.05
        
        return self.capital + unrealized_pnl
    
    def _calculate_performance(self) -> Dict:
        """Calculate performance metrics."""
        
        if not self.closed_trades:
            return {'error': 'No closed trades'}
        
        pnls = [trade.pnl for trade in self.closed_trades]
        
        total_pnl = sum(pnls)
        total_return = (self.capital - self.initial_capital) / self.initial_capital
        
        winning_trades = [pnl for pnl in pnls if pnl > 0]
        losing_trades = [pnl for pnl in pnls if pnl < 0]
        
        win_rate = len(winning_trades) / len(pnls) if pnls else 0
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = np.mean(losing_trades) if losing_trades else 0
        
        # Sharpe (simplified)
        returns = [(pnl / self.initial_capital) for pnl in pnls]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 1 and np.std(returns) > 0 else 0
        
        # Max drawdown
        equity_df = pd.DataFrame(self.equity_curve)
        if not equity_df.empty:
            running_max = equity_df['equity'].expanding().max()
            drawdown = (equity_df['equity'] - running_max) / running_max
            max_drawdown = drawdown.min()
        else:
            max_drawdown = 0
        
        return {
            'total_pnl': total_pnl,
            'total_return_pct': total_return * 100,
            'num_trades': len(self.closed_trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_drawdown * 100,
            'final_equity': self.capital,
            'trades': self.closed_trades,
            'equity_curve': equity_df
        }
    
    def _print_results(self, results: Dict):
        """Print backtest results."""
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
        print(f"Max Drawdown:       {results['max_drawdown_pct']:.2f}%")
        print(f"Final Equity:       ${results['final_equity']:,.2f}")
        print(f"{'='*70}\n")