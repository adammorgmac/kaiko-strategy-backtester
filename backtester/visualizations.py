"""
Advanced visualization tools for options analysis.
Robust error handling and timezone-aware calculations.
"""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Optional, List


def days_until(expiry_timestamp):
    """Calculate days until expiry, handling timezones properly."""
    try:
        now = pd.Timestamp.now(tz='UTC')
        expiry = pd.to_datetime(expiry_timestamp)
        
        # Make timezone aware if needed
        if expiry.tz is None:
            expiry = expiry.tz_localize('UTC')
        
        delta_seconds = (expiry - now).total_seconds()
        days = delta_seconds / 86400
        
        return max(0.1, days)  # At least 0.1 day to avoid division errors
    except Exception:
        return 1.0  # Fallback


class OptionsVisualizer:
    """Advanced plotting tools for options data."""
    
    @staticmethod
    def plot_iv_surface_3d(data: pd.DataFrame, spot_price: float) -> go.Figure:
        """Create 3D surface plot of implied volatility."""
        try:
            if data.empty:
                return OptionsVisualizer._empty_chart("No data available")
            
            data = data.copy()
            data['moneyness'] = data['strike_price'] / spot_price
            
            # Calculate days to expiry
            now = pd.Timestamp.now(tz='UTC')
            data['days_to_expiry'] = data['expiry'].apply(
                lambda x: max(0.1, (pd.to_datetime(x) - now).total_seconds() / 86400)
            )
            
            # Filter valid data
            data = data[
                (data['days_to_expiry'] > 0) &
                (data['mark_iv'].notna()) &
                (data['moneyness'] > 0)
            ]
            
            if len(data) < 4:
                return OptionsVisualizer._empty_chart("Insufficient data for 3D surface (need at least 4 points)")
            
            # Create pivot table
            pivot = data.pivot_table(
                values='mark_iv',
                index='moneyness',
                columns='days_to_expiry',
                aggfunc='mean'
            )
            
            if pivot.empty or pivot.shape[0] < 2 or pivot.shape[1] < 2:
                return OptionsVisualizer._empty_chart("Not enough unique strikes/expiries for surface")
            
            # Create surface plot
            fig = go.Figure(data=[go.Surface(
                x=pivot.columns,
                y=pivot.index,
                z=pivot.values,
                colorscale='Viridis',
                colorbar=dict(title="IV (%)", x=1.1)
            )])
            
            fig.update_layout(
                title="3D Implied Volatility Surface",
                scene=dict(
                    xaxis_title="Days to Expiry",
                    yaxis_title="Moneyness (Strike/Spot)",
                    zaxis_title="IV (%)",
                    camera=dict(eye=dict(x=1.5, y=1.5, z=1.3))
                ),
                height=700,
                margin=dict(l=0, r=0, t=40, b=0)
            )
            
            return fig
            
        except Exception as e:
            return OptionsVisualizer._error_chart(f"Error: {str(e)}")
    
    @staticmethod
    def plot_iv_heatmap(data: pd.DataFrame, spot_price: float) -> go.Figure:
        """Create heatmap of IV across strikes and expiries."""
        try:
            if data.empty:
                return OptionsVisualizer._empty_chart("No data available")
            
            data = data.copy()
            data['days_to_expiry'] = data['expiry'].apply(days_until)
            
            # Filter valid data
            data = data[
                (data['days_to_expiry'] > 0) &
                (data['mark_iv'].notna())
            ]
            
            if len(data) < 3:
                return OptionsVisualizer._empty_chart("Insufficient data for heatmap")
            
            # Create pivot
            pivot = data.pivot_table(
                values='mark_iv',
                index='strike_price',
                columns='days_to_expiry',
                aggfunc='mean'
            )
            
            if pivot.empty:
                return OptionsVisualizer._empty_chart("Could not create pivot table")
            
            fig = go.Figure(data=go.Heatmap(
                x=pivot.columns,
                y=pivot.index,
                z=pivot.values,
                colorscale='RdYlGn_r',
                colorbar=dict(title="IV (%)"),
                hovertemplate='DTE: %{x:.1f}<br>Strike: %{y:.0f}<br>IV: %{z:.1f}%<extra></extra>'
            ))
            
            # Add spot price line
            fig.add_hline(
                y=spot_price,
                line_dash="dash",
                line_color="white",
                line_width=2,
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
            
        except Exception as e:
            return OptionsVisualizer._error_chart(f"Error: {str(e)}")
    
    @staticmethod
    def plot_greeks_dashboard(data: pd.DataFrame, expiry: str) -> go.Figure:
        """Multi-panel dashboard of all Greeks for an expiry."""
        try:
            expiry_data = data[data['expiry'] == expiry].sort_values('strike_price')
            
            if expiry_data.empty:
                return OptionsVisualizer._empty_chart("No data for this expiry")
            
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
                # Check if greek exists
                if greek not in calls.columns:
                    continue
                
                # Calls
                if not calls.empty and calls[greek].notna().any():
                    fig.add_trace(
                        go.Scatter(
                            x=calls['strike_price'],
                            y=calls[greek],
                            mode='lines+markers',
                            name='Call',
                            line=dict(color='#28a745', width=2),
                            marker=dict(size=6),
                            showlegend=(row == 1 and col == 1),
                            legendgroup='call'
                        ),
                        row=row, col=col
                    )
                
                # Puts
                if not puts.empty and puts[greek].notna().any():
                    fig.add_trace(
                        go.Scatter(
                            x=puts['strike_price'],
                            y=puts[greek],
                            mode='lines+markers',
                            name='Put',
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
                title=f"Greeks Dashboard - {str(expiry)[:10]}",
                height=700,
                showlegend=True,
                legend=dict(x=0.5, y=1.1, xanchor='center', orientation='h')
            )
            
            return fig
            
        except Exception as e:
            return OptionsVisualizer._error_chart(f"Error: {str(e)}")
    
    @staticmethod
    def plot_gex_profile(data: pd.DataFrame, spot_price: float, expiry: str = None) -> go.Figure:
        """Plot Gamma Exposure (GEX) profile."""
        try:
            if data.empty:
                return OptionsVisualizer._empty_chart("No data available")
            
            plot_data = data.copy()
            
            if expiry:
                plot_data = plot_data[plot_data['expiry'] == expiry]
            
            if plot_data.empty:
                return OptionsVisualizer._empty_chart("No data for selected expiry")
            
            # Calculate GEX
            plot_data['gex'] = (
                plot_data['gamma'].fillna(0) * 
                plot_data['open_interest'].fillna(0) * 
                spot_price * spot_price * 0.01
            )
            
            # Group by strike and type
            calls = plot_data[plot_data['option_type'] == 'call'].groupby('strike_price')['gex'].sum()
            puts = plot_data[plot_data['option_type'] == 'put'].groupby('strike_price')['gex'].sum()
            puts = -puts  # Negative for dealers
            
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
            
            fig.add_vline(
                x=spot_price,
                line_dash="dash",
                line_color="gray",
                annotation_text="Spot",
                annotation_position="top"
            )
            
            fig.add_hline(y=0, line_color="black", line_width=1)
            
            fig.update_layout(
                title="Gamma Exposure (GEX) Profile",
                xaxis_title="Strike Price",
                yaxis_title="GEX",
                barmode='relative',
                height=500,
                hovermode='x unified'
            )
            
            return fig
            
        except Exception as e:
            return OptionsVisualizer._error_chart(f"Error: {str(e)}")
    
    @staticmethod
    def plot_skew_term_structure(data: pd.DataFrame, spot_price: float) -> go.Figure:
        """Plot put/call skew across expiries."""
        try:
            if data.empty:
                return OptionsVisualizer._empty_chart("No data available")
            
            data = data.copy()
            data['days_to_expiry'] = data['expiry'].apply(days_until)
            
            atm_skews = []
            
            for expiry in data['expiry'].unique():
                expiry_data = data[data['expiry'] == expiry]
                expiry_data['dist'] = (expiry_data['strike_price'] - spot_price).abs()
                
                if expiry_data.empty:
                    continue
                
                # Find ATM strike
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
                        'expiry': str(expiry)[:10]
                    })
            
            if not atm_skews:
                return OptionsVisualizer._empty_chart("Could not calculate skew")
            
            skew_df = pd.DataFrame(atm_skews).sort_values('days_to_expiry')
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=skew_df['days_to_expiry'],
                y=skew_df['skew'],
                mode='lines+markers',
                name='ATM Put/Call Skew',
                line=dict(color='#1f77b4', width=3),
                marker=dict(size=10),
                text=skew_df['expiry'],
                hovertemplate='<b>%{text}</b><br>DTE: %{x:.1f}<br>Skew: %{y:.2f}%<extra></extra>'
            ))
            
            fig.add_hline(y=0, line_dash="dash", line_color="gray")
            
            fig.update_layout(
                title="Put/Call Skew Term Structure",
                xaxis_title="Days to Expiry",
                yaxis_title="Skew (Put IV - Call IV) %",
                height=400,
                hovermode='x unified'
            )
            
            return fig
            
        except Exception as e:
            return OptionsVisualizer._error_chart(f"Error: {str(e)}")
    
    @staticmethod
    def plot_signal_timeline(signals: List, spot_data: pd.DataFrame = None) -> go.Figure:
        """Plot trading signals on a timeline."""
        try:
            if not signals:
                return OptionsVisualizer._empty_chart("No signals to display")
            
            signal_df = pd.DataFrame([{
                'timestamp': s.timestamp,
                'action': s.signal_type.name,
                'strike': s.strike,
                'instrument': s.instrument,
                'reason': s.reason
            } for s in signals])
            
            fig = go.Figure()
            
            # Buy signals
            buy_signals = signal_df[signal_df['action'] == 'BUY']
            if not buy_signals.empty:
                fig.add_trace(go.Scatter(
                    x=buy_signals['timestamp'],
                    y=buy_signals['strike'],
                    mode='markers',
                    name='BUY',
                    marker=dict(
                        symbol='triangle-up',
                        size=15,
                        color='#28a745',
                        line=dict(width=2, color='white')
                    ),
                    text=buy_signals['reason'],
                    hovertemplate='<b>BUY</b><br>Strike: %{y}<br>%{text}<extra></extra>'
                ))
            
            # Sell signals
            sell_signals = signal_df[signal_df['action'] == 'SELL']
            if not sell_signals.empty:
                fig.add_trace(go.Scatter(
                    x=sell_signals['timestamp'],
                    y=sell_signals['strike'],
                    mode='markers',
                    name='SELL',
                    marker=dict(
                        symbol='triangle-down',
                        size=15,
                        color='#dc3545',
                        line=dict(width=2, color='white')
                    ),
                    text=sell_signals['reason'],
                    hovertemplate='<b>SELL</b><br>Strike: %{y}<br>%{text}<extra></extra>'
                ))
            
            fig.update_layout(
                title="Trading Signals",
                xaxis_title="Time",
                yaxis_title="Strike Price",
                height=500,
                hovermode='closest'
            )
            
            return fig
            
        except Exception as e:
            return OptionsVisualizer._error_chart(f"Error: {str(e)}")
    
    @staticmethod
    def _empty_chart(message: str) -> go.Figure:
        """Create an empty chart with a message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            showarrow=False,
            font=dict(size=16, color="#666"),
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5
        )
        fig.update_layout(
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            height=400
        )
        return fig
    
    @staticmethod
    def _error_chart(message: str) -> go.Figure:
        """Create an error chart."""
        fig = go.Figure()
        fig.add_annotation(
            text=f"⚠️ {message}",
            showarrow=False,
            font=dict(size=14, color="red"),
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5
        )
        fig.update_layout(
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            height=400
        )
        return fig


if __name__ == "__main__":
    print("Visualization module loaded successfully!")
    print("Available visualizations:")
    print("  - plot_iv_surface_3d()")
    print("  - plot_iv_heatmap()")
    print("  - plot_greeks_dashboard()")
    print("  - plot_gex_profile()")
    print("  - plot_skew_term_structure()")
    print("  - plot_signal_timeline()")