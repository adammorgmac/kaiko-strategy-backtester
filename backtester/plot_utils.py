"""
Utility plotting functions.
"""
import plotly.graph_objects as go


def plot_iv_smile(data, expiry, spot_price):
    """Create IV smile plot."""
    expiry_data = data[data['expiry'] == expiry].copy()
    expiry_data = expiry_data.sort_values('strike_price')
    
    calls = expiry_data[expiry_data['option_type'] == 'call']
    puts = expiry_data[expiry_data['option_type'] == 'put']
    
    fig = go.Figure()
    
    if not calls.empty:
        fig.add_trace(go.Scatter(
            x=calls['strike_price'],
            y=calls['mark_iv'],
            mode='lines+markers',
            name='Calls',
            line=dict(color='#28a745', width=2),
            marker=dict(size=8)
        ))
    
    if not puts.empty:
        fig.add_trace(go.Scatter(
            x=puts['strike_price'],
            y=puts['mark_iv'],
            mode='lines+markers',
            name='Puts',
            line=dict(color='#dc3545', width=2),
            marker=dict(size=8)
        ))
    
    fig.add_vline(
        x=spot_price,
        line_dash="dash",
        line_color="gray",
        annotation_text="Spot",
        annotation_position="top"
    )
    
    fig.update_layout(
        title=f"IV Smile - {expiry}",
        xaxis_title="Strike Price",
        yaxis_title="Implied Volatility (%)",
        hovermode='x unified',
        height=500
    )
    
    return fig


def plot_open_interest(data, expiry):
    """Plot open interest by strike."""
    expiry_data = data[data['expiry'] == expiry].copy()
    expiry_data = expiry_data.sort_values('strike_price')
    
    fig = go.Figure()
    
    calls = expiry_data[expiry_data['option_type'] == 'call']
    puts = expiry_data[expiry_data['option_type'] == 'put']
    
    if not calls.empty:
        fig.add_trace(go.Bar(
            x=calls['strike_price'],
            y=calls['open_interest'],
            name='Call OI',
            marker_color='#28a745',
            opacity=0.7
        ))
    
    if not puts.empty:
        fig.add_trace(go.Bar(
            x=puts['strike_price'],
            y=puts['open_interest'],
            name='Put OI',
            marker_color='#dc3545',
            opacity=0.7
        ))
    
    fig.update_layout(
        title=f"Open Interest - {expiry}",
        xaxis_title="Strike Price",
        yaxis_title="Open Interest",
        barmode='group',
        height=400
    )
    
    return fig