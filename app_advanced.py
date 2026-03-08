"""
Advanced Streamlit dashboard with enhanced visualizations.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv

from backtester.historical_data import HistoricalDataFetcher
from backtester.visualizations import OptionsVisualizer
from backtester.advanced_strategies import get_advanced_strategy, ADVANCED_STRATEGIES
from backtester.strategies import get_strategy, AVAILABLE_STRATEGIES
from backtester.plot_utils import plot_iv_smile, plot_open_interest

# Page config - MUST BE FIRST
st.set_page_config(
    page_title="Kaiko Advanced Backtester",
    page_icon="🚀",
    layout="wide"
)

# Title
st.markdown("""
<h1 style='text-align: center; color: #1f77b4;'>
    🚀 Kaiko Advanced Options Backtester
</h1>
""", unsafe_allow_html=True)

# Load API key
load_dotenv()

@st.cache_data(ttl=300)
def fetch_data(asset, num_expiries):
    """Fetch options data"""
    api_key = os.getenv('KAIKO_API_KEY')
    fetcher = HistoricalDataFetcher(api_key)
    data = fetcher.fetch_current_snapshot(asset, num_expiries=num_expiries)
    spot = fetcher.client.get_spot_price(asset, 'usd')
    return data, spot

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    asset = st.selectbox("Asset", ['btc', 'eth'], index=0)
    num_expiries = st.slider("Expiries", 1, 10, 5)
    
    st.markdown("---")
    st.subheader("📊 Strategy")
    
    all_strategies = {**AVAILABLE_STRATEGIES, **ADVANCED_STRATEGIES}
    strategy_names = list(all_strategies.keys())
    
    strategy_type = st.selectbox(
        "Type",
        strategy_names,
        format_func=lambda x: x.replace('_', ' ').title()
    )
    
    st.markdown("---")
    st.subheader("🎯 Parameters")
    
    params = {}
    
    if strategy_type == 'simple_vol':
        params['high_iv_threshold'] = st.slider("High IV %", 50, 100, 75)
        params['low_iv_threshold'] = st.slider("Low IV %", 0, 50, 25)
    
    elif strategy_type == 'skew':
        params['skew_threshold'] = st.slider("Skew %", 1.0, 20.0, 5.0)
    
    elif strategy_type == 'gamma_scalp':
        params['min_gamma'] = st.number_input("Min Gamma", 0.0001, 0.01, 0.0001, format="%.4f")
    
    elif strategy_type == 'straddle_screen':
        params['max_iv'] = st.slider("Max IV", 50, 100, 70)
        params['min_gamma'] = st.number_input("Min Gamma", 0.0001, 0.01, 0.0001, format="%.4f")
    
    if st.button("🔄 Refresh", type="primary"):
        st.cache_data.clear()

# Fetch data
with st.spinner(f"Fetching {asset.upper()} data..."):
    try:
        data, spot_price = fetch_data(asset, num_expiries)
        
        if data.empty:
            st.error("No data retrieved")
            st.stop()
            
    except Exception as e:
        st.error(f"Error: {e}")
        st.stop()

# Metrics
col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("💰 Spot", f"${spot_price:,.0f}")
col2.metric("📊 Instruments", f"{len(data):,}")
col3.metric("📈 Avg IV", f"{data['mark_iv'].mean():.1f}%")
col4.metric("🔢 Total OI", f"{data['open_interest'].sum():,.0f}")
col5.metric("📅 Expiries", len(data['expiry'].unique()))

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 Signals",
    "📊 IV Analysis",
    "📈 Greeks & GEX",
    "🔥 Advanced"
])

viz = OptionsVisualizer()

with tab1:
    st.subheader("Trading Signals")
    
    try:
        # Create strategy
        if strategy_type in ADVANCED_STRATEGIES:
            strategy = get_advanced_strategy(strategy_type, params)
        else:
            strategy = get_strategy(strategy_type, params)
        
        st.success(f"✅ {strategy.name}")
        
        # Generate signals
        data_copy = data.copy()
        data_copy['timestamp'] = pd.Timestamp.now(tz='UTC')
        
        spot_data = pd.DataFrame({
            'timestamp': [pd.Timestamp.now(tz='UTC')],
            'price': [spot_price]
        })
        
        with st.spinner("Generating signals..."):
            signals = strategy.generate_signals(data_copy, spot_data)
        
        if signals:
            st.success(f"✅ {len(signals)} signals")
            
            buy_signals = [s for s in signals if s.signal_type.name == 'BUY']
            sell_signals = [s for s in signals if s.signal_type.name == 'SELL']
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 🟢 BUY")
                if buy_signals:
                    buy_df = pd.DataFrame([{
                        'Instrument': s.instrument,
                        'Strike': f"${s.strike:,.0f}",
                        'IV': f"{s.iv:.1f}%",
                        'Reason': s.reason
                    } for s in buy_signals])
                    st.dataframe(buy_df, hide_index=True, use_container_width=True)
                else:
                    st.info("No buy signals")
            
            with col2:
                st.markdown("### 🔴 SELL")
                if sell_signals:
                    sell_df = pd.DataFrame([{
                        'Instrument': s.instrument,
                        'Strike': f"${s.strike:,.0f}",
                        'IV': f"{s.iv:.1f}%",
                        'Reason': s.reason
                    } for s in sell_signals])
                    st.dataframe(sell_df, hide_index=True, use_container_width=True)
                else:
                    st.info("No sell signals")
            
            # Timeline
            fig = viz.plot_signal_timeline(signals, spot_data)
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.warning("⚠️ No signals. Try adjusting parameters.")
    
    except Exception as e:
        st.error(f"Error: {e}")

with tab2:
    st.subheader("IV Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 3D Surface")
        fig = viz.plot_iv_surface_3d(data, spot_price)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### Heatmap")
        fig = viz.plot_iv_heatmap(data, spot_price)
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("### Skew Term Structure")
    fig = viz.plot_skew_term_structure(data, spot_price)
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("Greeks & GEX")
    
    expiry = st.selectbox("Expiry", sorted(data['expiry'].unique()))
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Greeks")
        fig = viz.plot_greeks_dashboard(data, expiry)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### GEX")
        fig = viz.plot_gex_profile(data, spot_price, expiry)
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.subheader("Advanced Charts")
    
    expiry_adv = st.selectbox("Expiry", sorted(data['expiry'].unique()), key='adv')
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = plot_iv_smile(data, expiry_adv, spot_price)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = plot_open_interest(data, expiry_adv)
        st.plotly_chart(fig, use_container_width=True)

# Footer
st.markdown("---")
st.markdown(
    f"<div style='text-align: center; color: #666;'>"
    f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Powered by Kaiko"
    f"</div>",
    unsafe_allow_html=True
)