"""
Kaiko Options Research Dashboard
Real-time options analysis and signal generation (not a full backtester)
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from backtester.historical_data import HistoricalDataFetcher
from backtester.strategies import SimpleVolatilityStrategy

# Page config - MUST BE FIRST
st.set_page_config(
    page_title="Kaiko Options Research Dashboard",
    page_icon="📊",
    layout="wide"
)

# Load environment
load_dotenv()

# Title
st.markdown("""
<h1 style='text-align: center; color: #1f77b4;'>
    📊 Kaiko Options Research Dashboard
</h1>
<p style='text-align: center; color: #666;'>
    Real-time Options Analysis & Signal Generation
</p>
""", unsafe_allow_html=True)

# Warning banner
st.info("""
💡 **Research Tool**: This dashboard analyzes current market snapshots and generates trading signals.
Not a full backtesting platform. For historical analysis, use the Advanced Dashboard.
""")


@st.cache_data(ttl=300)
def fetch_options_data(asset: str, num_expiries: int = 5):
    """
    Fetch current options snapshot.
    
    Args:
        asset: Asset code (btc, eth)
        num_expiries: Number of expiries to fetch
    
    Returns:
        Tuple of (options_data, spot_price)
    """
    api_key = os.getenv('KAIKO_API_KEY')
    
    if not api_key:
        raise ValueError(
            "KAIKO_API_KEY not found in environment.\n"
            "Create a .env file with: KAIKO_API_KEY=your_key_here"
        )
    
    fetcher = HistoricalDataFetcher(api_key)
    data = fetcher.fetch_current_snapshot(asset, num_expiries=num_expiries)
    
    if data.empty:
        return data, None
    
    # Get spot price from data or API
    spot_price = None
    if 'spot_price' in data.columns:
        spot_price = data['spot_price'].iloc[0]
    else:
        spot_price = fetcher.client.get_spot_price(asset, 'usd')
    
    return data, spot_price


def plot_iv_smile(data: pd.DataFrame, expiry: str, spot_price: float) -> go.Figure:
    """Create IV smile plot for a specific expiry."""
    expiry_data = data[data['expiry'] == expiry].copy()
    expiry_data = expiry_data.sort_values('strike_price')
    
    calls = expiry_data[expiry_data['option_type'] == 'call']
    puts = expiry_data[expiry_data['option_type'] == 'put']
    
    fig = go.Figure()
    
    if not calls.empty and 'mark_iv' in calls.columns:
        fig.add_trace(go.Scatter(
            x=calls['strike_price'],
            y=calls['mark_iv'],
            mode='lines+markers',
            name='Calls',
            line=dict(color='#28a745', width=2),
            marker=dict(size=8)
        ))
    
    if not puts.empty and 'mark_iv' in puts.columns:
        fig.add_trace(go.Scatter(
            x=puts['strike_price'],
            y=puts['mark_iv'],
            mode='lines+markers',
            name='Puts',
            line=dict(color='#dc3545', width=2),
            marker=dict(size=8)
        ))
    
    if spot_price:
        fig.add_vline(
            x=spot_price,
            line_dash="dash",
            line_color="gray",
            annotation_text="Spot",
            annotation_position="top"
        )
    
    fig.update_layout(
        title=f"IV Smile - {str(expiry)[:10]}",
        xaxis_title="Strike Price",
        yaxis_title="Implied Volatility (%)",
        hovermode='x unified',
        height=500
    )
    
    return fig


def plot_greeks_surface(data: pd.DataFrame, greek: str) -> go.Figure:
    """Create 3D surface plot for a Greek."""
    data = data.copy()
    
    if greek not in data.columns:
        fig = go.Figure()
        fig.add_annotation(
            text=f"{greek.capitalize()} data not available",
            showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    # Calculate days to expiry
    now = pd.Timestamp.now(tz='UTC')
    data['days_to_expiry'] = data['expiry'].apply(
        lambda x: max(0.1, (pd.to_datetime(x) - now).total_seconds() / 86400)
    )
    
    data = data[data['days_to_expiry'] > 0]
    
    if data.empty or len(data) < 4:
        fig = go.Figure()
        fig.add_annotation(
            text="Insufficient data for surface plot",
            showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    pivot = data.pivot_table(
        values=greek,
        index='strike_price',
        columns='days_to_expiry',
        aggfunc='mean'
    )
    
    if pivot.shape[0] < 2 or pivot.shape[1] < 2:
        fig = go.Figure()
        fig.add_annotation(
            text="Not enough data points for surface",
            showarrow=False,
            font=dict(size=16)
        )
        return fig
    
    fig = go.Figure(data=[go.Surface(
        x=pivot.columns,
        y=pivot.index,
        z=pivot.values,
        colorscale='Viridis'
    )])
    
    fig.update_layout(
        title=f"{greek.capitalize()} Surface",
        scene=dict(
            xaxis_title="Days to Expiry",
            yaxis_title="Strike Price",
            zaxis_title=greek.capitalize()
        ),
        height=600
    )
    
    return fig


def plot_open_interest(data: pd.DataFrame, expiry: str) -> go.Figure:
    """Plot open interest by strike for an expiry."""
    expiry_data = data[data['expiry'] == expiry].copy()
    expiry_data = expiry_data.sort_values('strike_price')
    
    fig = go.Figure()
    
    calls = expiry_data[expiry_data['option_type'] == 'call']
    puts = expiry_data[expiry_data['option_type'] == 'put']
    
    if not calls.empty and 'open_interest' in calls.columns:
        fig.add_trace(go.Bar(
            x=calls['strike_price'],
            y=calls['open_interest'],
            name='Call OI',
            marker_color='#28a745',
            opacity=0.7
        ))
    
    if not puts.empty and 'open_interest' in puts.columns:
        fig.add_trace(go.Bar(
            x=puts['strike_price'],
            y=puts['open_interest'],
            name='Put OI',
            marker_color='#dc3545',
            opacity=0.7
        ))
    
    fig.update_layout(
        title=f"Open Interest - {str(expiry)[:10]}",
        xaxis_title="Strike Price",
        yaxis_title="Open Interest",
        barmode='group',
        height=400
    )
    
    return fig


# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    asset = st.selectbox("Asset", ['btc', 'eth'], index=0)
    num_expiries = st.slider("Number of Expiries", 1, 10, 5)
    
    st.markdown("---")
    st.subheader("🎯 Signal Parameters")
    
    high_iv_threshold = st.slider(
        "High IV Threshold (%)",
        50, 100, 75,
        help="Sell when IV exceeds mean + (threshold% × std)"
    )
    
    low_iv_threshold = st.slider(
        "Low IV Threshold (%)",
        0, 50, 25,
        help="Buy when IV falls below mean - (threshold% × std)"
    )
    
    strikes_per_expiry = st.slider(
        "Strikes per Expiry",
        1, 5, 2,
        help="Number of ATM strikes to analyze per expiry"
    )
    
    st.markdown("---")
    
    if st.button("🔄 Refresh Data", type="primary"):
        st.cache_data.clear()
        st.rerun()

# Fetch data
with st.spinner(f"Fetching {asset.upper()} options data..."):
    try:
        data, spot_price = fetch_options_data(asset, num_expiries)
        
        if data.empty:
            st.error("❌ No data retrieved. Check API connection.")
            st.stop()
        
        if spot_price is None:
            st.error("❌ Could not determine spot price")
            st.stop()
            
    except ValueError as e:
        st.error(f"❌ Configuration Error: {e}")
        st.stop()
    except Exception as e:
        st.error(f"❌ Error: {e}")
        st.stop()

# Metrics
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("💰 Spot Price", f"${spot_price:,.2f}")

with col2:
    st.metric("📊 Instruments", f"{len(data):,}")

with col3:
    avg_iv = data['mark_iv'].mean() if 'mark_iv' in data.columns else 0
    st.metric("📈 Avg IV", f"{avg_iv:.1f}%")

with col4:
    total_oi = data['open_interest'].sum() if 'open_interest' in data.columns else 0
    st.metric("🔢 Total OI", f"{total_oi:,.0f}")

with col5:
    st.metric("📅 Expiries", len(data['expiry'].unique()))

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 Trading Signals",
    "📊 IV Analysis",
    "📈 Greeks Analysis",
    "📋 Raw Data"
])

# TAB 1: Trading Signals
with tab1:
    st.subheader("Trading Signal Generation")
    
    # Validate required columns
    required_cols = ['instrument', 'strike_price', 'option_type', 'mark_iv', 'expiry']
    missing_cols = [col for col in required_cols if col not in data.columns]
    
    if missing_cols:
        st.error(f"❌ Missing required columns: {missing_cols}")
    else:
        # Create strategy
        strategy = SimpleVolatilityStrategy(params={
            'high_iv_std_pct': high_iv_threshold,
            'low_iv_std_pct': low_iv_threshold,
            'strikes_per_expiry': strikes_per_expiry
        })
        
        st.success(f"✅ Strategy: **{strategy.name}**")
        
        with st.expander("📋 Strategy Parameters", expanded=False):
            st.json(strategy.params)
        
        # Prepare spot data
        snapshot_ts = data['snapshot_timestamp'].iloc[0] if 'snapshot_timestamp' in data.columns else pd.Timestamp.now(tz='UTC')
        
        spot_data = pd.DataFrame({
            'timestamp': [snapshot_ts],
            'price': [spot_price]
        })
        
        # Generate signals
        with st.spinner("Generating signals..."):
            try:
                signals = strategy.generate_signals(data, spot_data)
                
                if signals:
                    st.success(f"✅ Generated **{len(signals)}** trading signals")
                    
                    # Separate buy and sell
                    buy_signals = [s for s in signals if s.signal_type.name == 'BUY']
                    sell_signals = [s for s in signals if s.signal_type.name == 'SELL']
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("### 🟢 BUY Signals")
                        if buy_signals:
                            buy_df = pd.DataFrame([{
                                'Instrument': s.instrument,
                                'Strike': f"${s.strike:,.0f}",
                                'Type': s.option_type.upper(),
                                'IV': f"{s.iv:.1f}%",
                                'Delta': f"{s.delta:.3f}" if s.delta else "N/A",
                                'Reason': s.reason
                            } for s in buy_signals])
                            st.dataframe(buy_df, hide_index=True, use_container_width=True)
                        else:
                            st.info("No buy signals")
                    
                    with col2:
                        st.markdown("### 🔴 SELL Signals")
                        if sell_signals:
                            sell_df = pd.DataFrame([{
                                'Instrument': s.instrument,
                                'Strike': f"${s.strike:,.0f}",
                                'Type': s.option_type.upper(),
                                'IV': f"{s.iv:.1f}%",
                                'Delta': f"{s.delta:.3f}" if s.delta else "N/A",
                                'Reason': s.reason
                            } for s in sell_signals])
                            st.dataframe(sell_df, hide_index=True, use_container_width=True)
                        else:
                            st.info("No sell signals")
                    
                    # Download signals
                    signals_df = pd.DataFrame([{
                        'timestamp': s.timestamp,
                        'action': s.signal_type.name,
                        'instrument': s.instrument,
                        'strike': s.strike,
                        'option_type': s.option_type,
                        'iv': s.iv,
                        'spot_price': s.spot_price,
                        'delta': s.delta,
                        'gamma': s.gamma,
                        'reason': s.reason
                    } for s in signals])
                    
                    csv = signals_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Signals CSV",
                        data=csv,
                        file_name=f"signals_{asset}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("⚠️ No signals generated. Try adjusting parameters.")
                    
            except Exception as e:
                st.error(f"❌ Error generating signals: {e}")
                st.exception(e)

# TAB 2: IV Analysis
with tab2:
    st.subheader("Implied Volatility Analysis")
    
    if 'mark_iv' not in data.columns:
        st.error("❌ IV data not available")
    else:
        # Expiry selector
        expiry = st.selectbox("Select Expiry", sorted(data['expiry'].unique()), format_func=lambda x: str(x)[:10])
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### IV Smile")
            fig = plot_iv_smile(data, expiry, spot_price)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### IV Statistics")
            expiry_data = data[data['expiry'] == expiry]
            
            if not expiry_data.empty and 'mark_iv' in expiry_data.columns:
                stats = expiry_data.groupby('option_type')['mark_iv'].agg(['mean', 'std', 'min', 'max'])
                st.dataframe(stats, use_container_width=True)
            else:
                st.info("No IV data for this expiry")

# TAB 3: Greeks Analysis
with tab3:
    st.subheader("Greeks Analysis")
    
    greek = st.selectbox("Select Greek", ['delta', 'gamma', 'vega', 'theta'])
    
    if greek not in data.columns:
        st.warning(f"⚠️ {greek.capitalize()} data not available")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"### {greek.capitalize()} Surface")
            fig = plot_greeks_surface(data, greek)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### Open Interest")
            expiry_greek = st.selectbox(
                "Expiry",
                sorted(data['expiry'].unique()),
                format_func=lambda x: str(x)[:10],
                key='greek_expiry'
            )
            fig = plot_open_interest(data, expiry_greek)
            st.plotly_chart(fig, use_container_width=True)

# TAB 4: Raw Data
with tab4:
    st.subheader("Raw Market Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        expiry_filter = st.selectbox(
            "Filter by Expiry",
            ['All'] + sorted([str(e)[:10] for e in data['expiry'].unique()])
        )
    
    with col2:
        type_filter = st.multiselect(
            "Filter by Type",
            options=['call', 'put'],
            default=['call', 'put']
        )
    
    # Apply filters
    filtered = data.copy()
    
    if expiry_filter != 'All':
        filtered = filtered[filtered['expiry'].astype(str).str.startswith(expiry_filter)]
    
    if type_filter:
        filtered = filtered[filtered['option_type'].isin(type_filter)]
    
    st.dataframe(
        filtered.sort_values('strike_price'),
        hide_index=True,
        use_container_width=True
    )
    
    # Download data
    csv_data = filtered.to_csv(index=False)
    st.download_button(
        label="📥 Download Market Data CSV",
        data=csv_data,
        file_name=f"market_data_{asset}_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

# Footer
st.markdown("---")
st.markdown(
    f"<div style='text-align: center; color: #666;'>"
    f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
    f"Powered by Kaiko API"
    f"</div>",
    unsafe_allow_html=True
)