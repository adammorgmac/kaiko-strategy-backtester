"""
Advanced visualization tools for options analysis.
"""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Optional, List


def days_until(expiry_timestamp):
    """Calculate days until expiry, handling timezones properly."""
    now = pd.Timestamp.now(tz='UTC')
    if expiry_timestamp.tz is None:
        expiry_timestamp = pd.Timestamp(expiry_timestamp, tz='UTC')
    delta = (expiry_timestamp - now).total_seconds()
    return max(0, delta / 86400)


class OptionsVisualizer:
    """Advanced plotting tools for options data."""
    
    @staticmethod
    def plot_iv_surface_3d(data: pd.DataFrame, spot_price: float) -> go.Figure:
        """Create 3D surface plot of implied volatility."""
        data = data.copy()
        data['moneyness'] = data['strike_price'] / spot_price
        data['days_to_expiry'] = data['expiry'].apply(days_until)
        
        # Remove any with negative or zero DTE
        data = data[data['days_to_expiry'] > 0]
        
        if data.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available for IV surface",
                showarrow=False,
                font=dict(size=20)
            )
            return fig
        
        pivot = data.pivot_table(
            values='mark_iv',
            index='moneyness',
            columns='days_to_expiry',
            aggfunc='mean'
        )
        
        fig = go.Figure(data=[go.Surface(
            x=pivot.columns,
            y=pivot.index,
            z=pivot.values,
            colorscale='Viridis',
            colorbar=dict(title="IV (%)")
        )])
        
        fig.update_layout(
            title="3D Implied Volatility Surface",
            scene=dict(
                xaxis_title="Days to Expiry",
                yaxis_title="Moneyness (Strike/Spot)",
                zaxis_title="Implied Volatility (%)",
                camera=dict(eye=dict(x=1.5, y=1.5, z=1.3))
            ),
            height=700
        )
        
        return fig
    
    @staticmethod
    def plot_iv_heatmap(data: pd.DataFrame, spot_price: float) -> go.Figure:
        """Create heatmap of IV across strikes and expiries."""
        data = data.copy()
        data['days_to_expiry'] = data['expiry'].apply(days_until)
        data = data[data['days_to_expiry'] > 0]
        
        if data.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available", showarrow=False, font=dict(size=20))
            return fig
        
        pivot = data.pivot_table(
            values='mark_iv',
            index='strike_price',
            columns='days_to_expiry',
            aggfunc='mean'
        )
        
        fig = go.Figure(data=go.Heatmap(
            x=pivot.columns,
            y=pivot.index,
            z=pivot.values,
            colorscale='RdYlGn_r',
            colorbar=dict(title="IV (%)")
        ))
        
        fig.add_hline(
            y=spot_price,
            line_dash="dash",
            line_color="white",
            annotation_text="ATM",
            annotation_position="right"
        )
        
        fig.update_layout(
            title="IV Heatmap",
            xaxis_title="Days to Expiry",
            yaxis_title="Strike Price",
            height=600
        )
        
        return fig
    
    @staticmethod
    def plot_greeks_dashboard(data: pd.DataFrame, expiry: str) -> go.Figure:
        """Multi-panel dashboard of all Greeks for an expiry."""
        expiry_data = data[data['expiry'] == expiry].sort_values('strike_price')
        
        if expiry_data.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data for this expiry", showarrow=False)
            return fig
        
        calls = expiry_data[expiry_data['option_type'] == 'call']
        puts = expiry_data[expiry_data['option_type'] == 'put']
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Delta', 'Gamma', 'Vega', 'Theta'),
            vertical_spacing=0.12,
            horizontal_spacing=0.1
        )
        
        greeks = [
            ('delta', 1, 1),
            ('gamma', 1, 2),
            ('vega', 2, 1),
            ('theta', 2, 2)
        ]
        
        for greek, row, col in greeks:
            if not calls.empty:
                fig.add_trace(
                    go.Scatter(
                        x=calls['strike_price'],
                        y=calls[greek],
                        mode='lines+markers',
                        name=f'Call',
                        line=dict(color='#28a745', width=2),
                        marker=dict(size=6),
                        showlegend=(row == 1 and col == 1),
                        legendgroup='call'
                    ),
                    row=row, col=col
                )
            
            if not puts.empty:
                fig.add_trace(
                    go.Scatter(
                        x=puts['strike_price'],
                        y=puts[greek],
                        mode='lines+markers',
                        name=f'Put',
                        line=dict(color='#dc3545', width=2),
                        marker=dict(size=6),
                        showlegend=(row == 1 and col == 1),
                        legendgroup='put'
                    ),
                    row=row, col=col
                )
            
            fig.update_xaxes(title_text="Strike", row=row, col=col)
            fig.update_yaxes(title_text=greek.capitalize(), row=row, col=col)
        
        fig.update_layout(
            title=f"Greeks Dashboard - {expiry}",
            height=700,
            showlegend=True,
            legend=dict(x=0.5, y=1.15, xanchor='center', orientation='h')
        )
        
        return fig
    
    @staticmethod
    def plot_gex_profile(data: pd.DataFrame, spot_price: float, expiry: str = None) -> go.Figure:
        """Plot Gamma Exposure (GEX) profile."""
        if expiry:
            data = data[data['expiry'] == expiry].copy()
        
        data = data.copy()
        data['gex'] = data['gamma'] * data['open_interest'] * spot_price * spot_price * 0.01
        
        calls = data[data['option_type'] == 'call'].groupby('strike_price')['gex'].sum()
        puts = data[data['option_type'] == 'put'].groupby('strike_price')['gex'].sum()
        puts = -puts
        
        fig = go.Figure()
        
        if not calls.empty:
            fig.add_trace(go.Bar(
                x=calls.index,
                y=calls.values,
                name='Call GEX',
                marker_color='#28a745',
                opacity=0.7
            ))
        
        if not puts.empty:
            fig.add_trace(go.Bar(
                x=puts.index,
                y=puts.values,
                name='Put GEX',
                marker_color='#dc3545',
                opacity=0.7
            ))
        
        fig.add_vline(x=spot_price, line_dash="dash", line_color="gray", annotation_text="Spot")
        fig.add_hline(y=0, line_color="black", line_width=1)
        
        fig.update_layout(
            title="Gamma Exposure (GEX) Profile",
            xaxis_title="Strike Price",
            yaxis_title="GEX",
            barmode='relative',
            height=500
        )
        
        return fig
    
    @staticmethod
    def plot_skew_term_structure(data: pd.DataFrame, spot_price: float) -> go.Figure:
        """Plot put/call skew across expiries."""
        data = data.copy()
        data['days_to_expiry'] = data['expiry'].apply(days_until)
        
        atm_skews = []
        
        for expiry in data['expiry'].unique():
            expiry_data = data[data['expiry'] == expiry]
            expiry_data['dist'] = abs(expiry_data['strike_price'] - spot_price)
            
            if expiry_data.empty:
                continue
            
            atm_strike = expiry_data.nsmallest(1, 'dist')['strike_price'].iloc[0]
            atm_data = expiry_data[expiry_data['strike_price'] == atm_strike]
            
            call_iv = atm_data[atm_data['option_type'] == 'call']['mark_iv']
            put_iv = atm_data[atm_data['option_type'] == 'put']['mark_iv']
            
            if not call_iv.empty and not put_iv.empty:
                skew = put_iv.iloc[0] - call_iv.iloc[0]
                dte = atm_data['days_to_expiry'].iloc[0]
                
                atm_skews.append({
                    'days_to_expiry': dte,
                    'skew': skew,
                    'expiry': str(expiry)
                })
        
        if not atm_skews:
            fig = go.Figure()
            fig.add_annotation(text="No skew data available", showarrow=False)
            return fig
        
        skew_df = pd.DataFrame(atm_skews).sort_values('days_to_expiry')
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=skew_df['days_to_expiry'],
            y=skew_df['skew'],
            mode='lines+markers',
            name='ATM Put/Call Skew',
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=10)
        ))
        
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        
        fig.update_layout(
            title="Put/Call Skew Term Structure",
            xaxis_title="Days to Expiry",
            yaxis_title="Skew (Put IV - Call IV) %",
            height=400
        )
        
        return fig
    
    @staticmethod
    def plot_signal_timeline(signals: List, spot_data: pd.DataFrame = None) -> go.Figure:
        """Plot trading signals on a timeline."""
        if not signals:
            fig = go.Figure()
            fig.add_annotation(text="No signals to display", showarrow=False, font=dict(size=20))
            return fig
        
        signal_df = pd.DataFrame([{
            'timestamp': s.timestamp,
            'action': s.signal_type.name,
            'strike': s.strike,
            'instrument': s.instrument,
            'reason': s.reason
        } for s in signals])
        
        fig = go.Figure()
        
        buy_signals = signal_df[signal_df['action'] == 'BUY']
        if not buy_signals.empty:
            fig.add_trace(go.Scatter(
                x=buy_signals['timestamp'],
                y=buy_signals['strike'],
                mode='markers',
                name='BUY',
                marker=dict(symbol='triangle-up', size=15, color='#28a745')
            ))
        
        sell_signals = signal_df[signal_df['action'] == 'SELL']
        if not sell_signals.empty:
            fig.add_trace(go.Scatter(
                x=sell_signals['timestamp'],
                y=sell_signals['strike'],
                mode='markers',
                name='SELL',
                marker=dict(symbol='triangle-down', size=15, color='#dc3545')
            ))
        
        fig.update_layout(
            title="Trading Signals",
            xaxis_title="Time",
            yaxis_title="Strike Price",
            height=500
        )
        
        return fig


if __name__ == "__main__":
    print("Visualization module loaded successfully!")