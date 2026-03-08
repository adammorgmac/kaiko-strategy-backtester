"""
Advanced Streamlit dashboard with enhanced visualizations.
Clean version with proper data handling and no unfinished strategies.
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
    page_title="Kaiko Options Signal Screener",
    page_icon="📊",
    layout="wide"
)

# Title
st.markdown("""
<h1 style='text-align: center; color: #1f77b4;'>
    📊 Kaiko Options Signal Screener
</h1>
<p style='text-align: center; color: #888; font-size: 0.9em;'>
    Research Prototype • Real-time Analysis • Experimental Features
</p>
""", unsafe_allow_html=True)

# Warning banner
st.warning("""
⚠️ **Research Tool**: This platform analyzes current market snapshots and generates signals. 
Historical backtesting requires multi-day snapshot collection. Not for production trading.
""")

# Load API key
load_dotenv()

@st.cache_data(ttl=300)
def fetch_data(asset, num_expiries):
    """Fetch options data with caching."""
    api_key = os.getenv('KAIKO_API_KEY')
    if not api_key:
        raise ValueError("KAIKO_API_KEY not found in environment")
    
    fetcher = HistoricalDataFetcher(api_key)
    data = fetcher.fetch_current_snapshot(asset, num_expiries=num_expiries)
    spot = fetcher.client.get_spot_price(asset, 'usd')
    
    # Add snapshot timestamp if not present
    if not data.empty and 'snapshot_timestamp' not in data.columns:
        data['snapshot_timestamp'] = pd.Timestamp.now(tz='UTC')
    
    # Add spot price to data
    if not data.empty:
        data['spot_price'] = spot
    
    return data, spot

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    asset = st.selectbox("Asset", ['btc', 'eth'], index=0)
    num_expiries = st.slider("Expiries", 1, 10, 5)
    
    st.markdown("---")
    st.subheader("📊 Strategy Selection")
    
    # Filter out unfinished strategies
    enabled_advanced = {
        k: v for k, v in ADVANCED_STRATEGIES.items() 
        if k != 'calendar'  # Not yet implemented
    }
    all_strategies = {**AVAILABLE_STRATEGIES, **enabled_advanced}
    strategy_names = list(all_strategies.keys())
    
    strategy_type = st.selectbox(
        "Strategy Type",
        strategy_names,
        format_func=lambda x: x.replace('_', ' ').title(),
        help="Select trading strategy. Calendar spreads coming soon."
    )
    
    st.markdown("---")
    st.subheader("🎯 Parameters")
    
    params = {}
    
    if strategy_type == 'simple_vol':
        params['high_iv_threshold'] = st.slider(
            "High IV Threshold (%)", 
            50, 100, 75,
            help="Sell when IV exceeds this threshold"
        )
        params['low_iv_threshold'] = st.slider(
            "Low IV Threshold (%)", 
            0, 50, 25,
            help="Buy when IV falls below this threshold"
        )
    
    elif strategy_type == 'skew':
        params['skew_threshold'] = st.slider(
            "Skew Threshold (%)", 
            1.0, 20.0, 5.0, 0.5,
            help="Trade when put/call IV difference exceeds this"
        )
        params['atm_range'] = st.slider(
            "ATM Range", 
            0.01, 0.15, 0.05, 0.01,
            help="Consider strikes within this % of spot"
        )
    
    elif strategy_type == 'gamma_scalp':
        params['min_gamma'] = st.number_input(
            "Min Gamma", 
            0.0001, 0.01, 0.0001, 
            format="%.4f",
            help="Minimum gamma for scalping opportunities"
        )
        params['atm_range'] = st.slider(
            "ATM Range", 
            0.01, 0.10, 0.03, 0.01
        )
    
    elif strategy_type == 'straddle_screen':
        params['max_iv'] = st.slider(
            "Max IV", 
            50, 100, 70,
            help="Maximum IV for entry"
        )
        params['min_gamma'] = st.number_input(
            "Min Gamma", 
            0.0001, 0.01, 0.0001, 
            format="%.4f"
        )
        params['min_oi'] = st.number_input(
            "Min Open Interest", 
            1.0, 100.0, 10.0
        )
    
    st.markdown("---")
    
    if st.button("🔄 Refresh Data", type="primary"):
        st.cache_data.clear()
        st.rerun()

# Fetch data
with st.spinner(f"Fetching {asset.upper()} options data..."):
    try:
        data, spot_price = fetch_data(asset, num_expiries)
        
        if data.empty:
            st.error("❌ No data retrieved. Check API key and connection.")
            st.stop()
            
    except Exception as e:
        st.error(f"❌ Error fetching data: {e}")
        st.stop()

# Metrics row
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("💰 Spot Price", f"${spot_price:,.0f}")

with col2:
    st.metric("📊 Instruments", f"{len(data):,}")

with col3:
    avg_iv = data['mark_iv'].mean()
    st.metric("📈 Avg IV", f"{avg_iv:.1f}%")

with col4:
    total_oi = data['open_interest'].sum()
    st.metric("🔢 Total OI", f"{total_oi:,.0f}")

with col5:
    st.metric("📅 Expiries", len(data['expiry'].unique()))

# Main tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 Trading Signals",
    "📊 IV Analysis",
    "📈 Greeks & GEX",
    "🔥 Advanced Charts"
])

# Initialize visualizer
viz = OptionsVisualizer()

# TAB 1: Trading Signals
with tab1:
    st.subheader("Trading Signal Generation")
    
    try:
        # Create strategy instance
        if strategy_type in enabled_advanced:
            strategy = get_advanced_strategy(strategy_type, params)
        else:
            strategy = get_strategy(strategy_type, params)
        
        st.success(f"✅ Strategy: **{strategy.name}**")
        
        with st.expander("📋 Strategy Parameters", expanded=False):
            st.json(strategy.params)
        
        # Prepare data for signal generation
        data_copy = data.copy()
        
        # Ensure snapshot_timestamp exists
        if 'snapshot_timestamp' not in data_copy.columns:
            data_copy['snapshot_timestamp'] = pd.Timestamp.now(tz='UTC')
        
        # Create spot data DataFrame
        spot_data = pd.DataFrame({
            'timestamp': [pd.Timestamp.now(tz='UTC')],
            'price': [spot_price]
        })
        
        # Generate signals
        with st.spinner("Generating trading signals..."):
            signals = strategy.generate_signals(data_copy, spot_data)
        
        if signals:
            st.success(f"✅ Generated **{len(signals)}** trading signals")
            
            # Separate buy and sell signals
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
                    st.info("No buy signals generated")
            
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
                    st.info("No sell signals generated")
            
            # Signal visualization
            st.markdown("### 📊 Signal Distribution")
            fig_timeline = viz.plot_signal_timeline(signals, spot_data)
            st.plotly_chart(fig_timeline, use_container_width=True)
            
            # Download signals
            signals_df = pd.DataFrame([{
                'timestamp': s.timestamp,
                'action': s.signal_type.name,
                'instrument': s.instrument,
                'strike': s.strike,
                'option_type': s.option_type,
                'iv': s.iv,
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
            st.warning("⚠️ No signals generated. Try adjusting strategy parameters in the sidebar.")
            st.info("💡 Tip: Lower thresholds or widen ATM ranges to generate more signals.")
    
    except ValueError as e:
        st.error(f"❌ Signal generation error: {e}")
        st.info("This usually means snapshot_timestamp is missing. Try refreshing data.")
    except Exception as e:
        st.error(f"❌ Unexpected error: {e}")
        st.exception(e)

# TAB 2: IV Analysis
with tab2:
    st.subheader("Implied Volatility Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 3D IV Surface")
        with st.spinner("Generating 3D surface..."):
            fig_3d = viz.plot_iv_surface_3d(data, spot_price)
            st.plotly_chart(fig_3d, use_container_width=True)
    
    with col2:
        st.markdown("### IV Heatmap")
        with st.spinner("Generating heatmap..."):
            fig_heatmap = viz.plot_iv_heatmap(data, spot_price)
            st.plotly_chart(fig_heatmap, use_container_width=True)
    
    st.markdown("### Skew Term Structure")
    with st.spinner("Analyzing skew..."):
        fig_skew = viz.plot_skew_term_structure(data, spot_price)
        st.plotly_chart(fig_skew, use_container_width=True)
    
    # IV Statistics table
    st.markdown("### IV Statistics by Expiry")
    iv_stats = data.groupby('expiry')['mark_iv'].agg(['mean', 'std', 'min', 'max']).reset_index()
    iv_stats.columns = ['Expiry', 'Mean IV', 'Std Dev', 'Min IV', 'Max IV']
    iv_stats['Mean IV'] = iv_stats['Mean IV'].apply(lambda x: f"{x:.1f}%")
    iv_stats['Std Dev'] = iv_stats['Std Dev'].apply(lambda x: f"{x:.1f}%")
    iv_stats['Min IV'] = iv_stats['Min IV'].apply(lambda x: f"{x:.1f}%")
    iv_stats['Max IV'] = iv_stats['Max IV'].apply(lambda x: f"{x:.1f}%")
    st.dataframe(iv_stats, hide_index=True, use_container_width=True)

# TAB 3: Greeks & GEX
with tab3:
    st.subheader("Greeks Analysis & Gamma Exposure")
    
    # Expiry selector
    expiry = st.selectbox(
        "Select Expiry for Detailed Analysis",
        sorted(data['expiry'].unique()),
        format_func=lambda x: str(x)[:10]
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Greeks Dashboard")
        with st.spinner("Calculating Greeks..."):
            fig_greeks = viz.plot_greeks_dashboard(data, expiry)
            st.plotly_chart(fig_greeks, use_container_width=True)
    
    with col2:
        st.markdown("### Gamma Exposure Profile")
        with st.spinner("Calculating GEX..."):
            fig_gex = viz.plot_gex_profile(data, spot_price, expiry)
            st.plotly_chart(fig_gex, use_container_width=True)
    
    # Greeks summary table
    st.markdown("### Greeks Summary")
    expiry_data = data[data['expiry'] == expiry]
    greeks_summary = expiry_data.groupby('option_type')[['delta', 'gamma', 'vega', 'theta']].agg(['mean', 'std'])
    st.dataframe(greeks_summary, use_container_width=True)

# TAB 4: Advanced Charts
with tab4:
    st.subheader("Detailed Market Analysis")
    
    expiry_adv = st.selectbox(
        "Select Expiry",
        sorted(data['expiry'].unique()),
        format_func=lambda x: str(x)[:10],
        key='advanced_expiry'
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### IV Smile")
        fig_smile = plot_iv_smile(data, expiry_adv, spot_price)
        st.plotly_chart(fig_smile, use_container_width=True)
    
    with col2:
        st.markdown("### Open Interest Distribution")
        fig_oi = plot_open_interest(data, expiry_adv)
        st.plotly_chart(fig_oi, use_container_width=True)
    
    # Raw data table
    st.markdown("### Raw Market Data")
    
    col1, col2 = st.columns(2)
    with col1:
        option_type_filter = st.multiselect(
            "Filter by Type",
            options=['call', 'put'],
            default=['call', 'put']
        )
    with col2:
        show_greeks = st.checkbox("Show Greeks", value=True)
    
    filtered_data = data[
        (data['expiry'] == expiry_adv) &
        (data['option_type'].isin(option_type_filter))
    ].copy()
    
    if show_greeks:
        display_cols = ['instrument', 'strike_price', 'option_type', 'mark_iv', 
                       'delta', 'gamma', 'vega', 'theta', 'open_interest']
    else:
        display_cols = ['instrument', 'strike_price', 'option_type', 'mark_iv', 'open_interest']
    
    display_cols = [col for col in display_cols if col in filtered_data.columns]
    
    st.dataframe(
        filtered_data[display_cols].sort_values('strike_price'),
        hide_index=True,
        use_container_width=True
    )
    
    # Download data
    csv_data = filtered_data.to_csv(index=False)
    st.download_button(
        label="📥 Download Market Data CSV",
        data=csv_data,
        file_name=f"market_data_{asset}_{expiry_adv}_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

# Footer
st.markdown("---")
st.markdown(
    f"<div style='text-align: center; color: #666; font-size: 0.9em;'>"
    f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC | "
    f"Powered by Kaiko API | "
    f"<a href='https://github.com/adammorgmac/kaiko-strategy-backtester' target='_blank'>GitHub</a>"
    f"</div>",
    unsafe_allow_html=True
)