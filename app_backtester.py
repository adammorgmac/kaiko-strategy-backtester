"""
Streamlit dashboard for Kaiko Options Backtester
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

from backtester.historical_data import HistoricalDataFetcher

# Page config
st.set_page_config(
    page_title="Kaiko Options Backtester",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .signal-buy {
        background-color: #d4edda;
        padding: 0.5rem;
        border-radius: 0.25rem;
        border-left: 3px solid #28a745;
    }
    .signal-sell {
        background-color: #f8d7da;
        padding: 0.5rem;
        border-radius: 0.25rem;
        border-left: 3px solid #dc3545;
    }
</style>
""", unsafe_allow_html=True)

# Load API key
load_dotenv()

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_options_data(asset, num_expiries):
    """Fetch options data with caching"""
    api_key = os.getenv('KAIKO_API_KEY')
    fetcher = HistoricalDataFetcher(api_key)
    data = fetcher.fetch_current_snapshot(asset, num_expiries=num_expiries)
    spot = fetcher.client.get_spot_price(asset, 'usd')
    return data, spot

def plot_iv_smile(data, expiry, spot_price):
    """Create IV smile plot"""
    expiry_data = data[data['expiry'] == expiry].copy()
    expiry_data = expiry_data.sort_values('strike_price')
    
    # Separate calls and puts
    calls = expiry_data[expiry_data['option_type'] == 'call']
    puts = expiry_data[expiry_data['option_type'] == 'put']
    
    fig = go.Figure()
    
    # Add call IVs
    fig.add_trace(go.Scatter(
        x=calls['strike_price'],
        y=calls['mark_iv'],
        mode='lines+markers',
        name='Calls',
        line=dict(color='#28a745', width=2),
        marker=dict(size=8)
    ))
    
    # Add put IVs
    fig.add_trace(go.Scatter(
        x=puts['strike_price'],
        y=puts['mark_iv'],
        mode='lines+markers',
        name='Puts',
        line=dict(color='#dc3545', width=2),
        marker=dict(size=8)
    ))
    
    # Add vertical line at spot price
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

def plot_greeks_surface(data, greek='delta'):
    """Create 3D surface plot of Greeks"""
    pivot = data.pivot_table(
        values=greek,
        index='strike_price',
        columns='expiry',
        aggfunc='mean'
    )
    
    fig = go.Figure(data=[go.Surface(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale='Viridis'
    )])
    
    fig.update_layout(
        title=f"{greek.capitalize()} Surface",
        scene=dict(
            xaxis_title="Expiry",
            yaxis_title="Strike",
            zaxis_title=greek.capitalize()
        ),
        height=600
    )
    
    return fig

def plot_open_interest(data, expiry):
    """Plot open interest by strike"""
    expiry_data = data[data['expiry'] == expiry].copy()
    expiry_data = expiry_data.sort_values('strike_price')
    
    fig = go.Figure()
    
    calls = expiry_data[expiry_data['option_type'] == 'call']
    puts = expiry_data[expiry_data['option_type'] == 'put']
    
    fig.add_trace(go.Bar(
        x=calls['strike_price'],
        y=calls['open_interest'],
        name='Call OI',
        marker_color='#28a745',
        opacity=0.7
    ))
    
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

def generate_signals(data, spot_price, high_threshold, low_threshold):
    """Generate trading signals"""
    signals = []
    
    avg_iv = data['mark_iv'].mean()
    iv_std = data['mark_iv'].std()
    
    HIGH_IV = avg_iv + (high_threshold / 100) * iv_std
    LOW_IV = avg_iv - (low_threshold / 100) * iv_std
    
    # Find ATM options
    for expiry in data['expiry'].unique():
        expiry_data = data[data['expiry'] == expiry].copy()
        expiry_data['dist_from_spot'] = abs(expiry_data['strike_price'] - spot_price)
        atm_data = expiry_data.nsmallest(3, 'dist_from_spot')
        
        for _, row in atm_data.iterrows():
            iv = row['mark_iv']
            
            if iv > HIGH_IV:
                signals.append({
                    'Action': 'SELL',
                    'Instrument': row['instrument'],
                    'Type': row['option_type'].upper(),
                    'Strike': row['strike_price'],
                    'Expiry': row['expiry'],
                    'IV': f"{iv:.1f}%",
                    'Delta': f"{row['delta']:.3f}",
                    'Gamma': f"{row['gamma']:.5f}",
                    'OI': f"{row['open_interest']:.1f}",
                    'Reason': f"IV {iv:.1f}% > {HIGH_IV:.1f}%"
                })
            
            elif iv < LOW_IV:
                signals.append({
                    'Action': 'BUY',
                    'Instrument': row['instrument'],
                    'Type': row['option_type'].upper(),
                    'Strike': row['strike_price'],
                    'Expiry': row['expiry'],
                    'IV': f"{iv:.1f}%",
                    'Delta': f"{row['delta']:.3f}",
                    'Gamma': f"{row['gamma']:.5f}",
                    'OI': f"{row['open_interest']:.1f}",
                    'Reason': f"IV {iv:.1f}% < {LOW_IV:.1f}%"
                })
    
    return signals, HIGH_IV, LOW_IV

# Main app
def main():
    st.markdown('<h1 class="main-header">📈 Kaiko Options Backtester</h1>', unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.header("⚙️ Settings")
    
    asset = st.sidebar.selectbox(
        "Asset",
        options=['btc', 'eth'],
        index=0
    )
    
    num_expiries = st.sidebar.slider(
        "Number of Expiries",
        min_value=1,
        max_value=10,
        value=5,
        help="How many expiry dates to fetch"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Strategy Parameters")
    
    high_threshold = st.sidebar.slider(
        "High IV Threshold (Sell)",
        min_value=0,
        max_value=100,
        value=50,
        help="Sell when IV is this many % above average"
    )
    
    low_threshold = st.sidebar.slider(
        "Low IV Threshold (Buy)",
        min_value=0,
        max_value=100,
        value=50,
        help="Buy when IV is this many % below average"
    )
    
    # Fetch data button
    if st.sidebar.button("🔄 Fetch Data", type="primary"):
        st.cache_data.clear()
    
    # Fetch data
    with st.spinner(f"Fetching {asset.upper()} options data..."):
        try:
            data, spot_price = fetch_options_data(asset.lower(), num_expiries)
            
            if data.empty:
                st.error("No data retrieved. Check API key and connection.")
                return
            
        except Exception as e:
            st.error(f"Error fetching data: {e}")
            return
    
    # Main metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Spot Price", f"${spot_price:,.2f}")
    
    with col2:
        st.metric("Instruments", f"{len(data):,}")
    
    with col3:
        avg_iv = data['mark_iv'].mean()
        st.metric("Avg IV", f"{avg_iv:.1f}%")
    
    with col4:
        total_oi = data['open_interest'].sum()
        st.metric("Total OI", f"{total_oi:,.0f}")
    
    with col5:
        st.metric("Expiries", len(data['expiry'].unique()))
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 IV Analysis", "🎯 Trading Signals", "📈 Greeks", "📋 Raw Data"])
    
    with tab1:
        st.subheader("Implied Volatility Analysis")
        
        # IV Statistics
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### IV Statistics")
            iv_stats = pd.DataFrame({
                'Metric': ['Average', 'Std Dev', 'Min', 'Max'],
                'Value': [
                    f"{data['mark_iv'].mean():.1f}%",
                    f"{data['mark_iv'].std():.1f}%",
                    f"{data['mark_iv'].min():.1f}%",
                    f"{data['mark_iv'].max():.1f}%"
                ]
            })
            st.dataframe(iv_stats, hide_index=True, use_container_width=True)
        
        with col2:
            st.markdown("### IV Distribution")
            fig_hist = px.histogram(
                data,
                x='mark_iv',
                nbins=30,
                title="IV Distribution",
                color_discrete_sequence=['#1f77b4']
            )
            fig_hist.update_layout(
                xaxis_title="Implied Volatility (%)",
                yaxis_title="Count",
                showlegend=False,
                height=300
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        
        # IV Smile
        st.markdown("### IV Smile by Expiry")
        expiry_options = sorted(data['expiry'].unique())
        selected_expiry = st.selectbox("Select Expiry", expiry_options)
        
        fig_smile = plot_iv_smile(data, selected_expiry, spot_price)
        st.plotly_chart(fig_smile, use_container_width=True)
        
        # Open Interest
        st.markdown("### Open Interest by Strike")
        fig_oi = plot_open_interest(data, selected_expiry)
        st.plotly_chart(fig_oi, use_container_width=True)
    
    with tab2:
        st.subheader("Trading Signals")
        
        signals, high_iv, low_iv = generate_signals(data, spot_price, high_threshold, low_threshold)
        
        # Threshold display
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Average IV", f"{data['mark_iv'].mean():.1f}%")
        with col2:
            st.metric("Sell Threshold", f"{high_iv:.1f}%", delta="High IV")
        with col3:
            st.metric("Buy Threshold", f"{low_iv:.1f}%", delta="Low IV")
        
        if signals:
            st.success(f"✅ Generated {len(signals)} signals")
            
            # Separate buy/sell
            buy_signals = [s for s in signals if s['Action'] == 'BUY']
            sell_signals = [s for s in signals if s['Action'] == 'SELL']
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 🟢 BUY Signals")
                if buy_signals:
                    st.dataframe(pd.DataFrame(buy_signals), hide_index=True, use_container_width=True)
                else:
                    st.info("No buy signals")
            
            with col2:
                st.markdown("### 🔴 SELL Signals")
                if sell_signals:
                    st.dataframe(pd.DataFrame(sell_signals), hide_index=True, use_container_width=True)
                else:
                    st.info("No sell signals")
            
            # Download button
            signals_df = pd.DataFrame(signals)
            csv = signals_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Signals CSV",
                data=csv,
                file_name=f"signals_{asset}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.warning("⚠️ No signals generated. Try adjusting thresholds in sidebar.")
    
    with tab3:
        st.subheader("Greeks Analysis")
        
        # Greek selector
        greek = st.selectbox(
            "Select Greek",
            options=['delta', 'gamma', 'vega', 'theta']
        )
        
        # 3D surface
        st.markdown(f"### {greek.capitalize()} Surface")
        fig_surface = plot_greeks_surface(data, greek)
        st.plotly_chart(fig_surface, use_container_width=True)
        
        # Greek statistics by expiry
        st.markdown(f"### {greek.capitalize()} Statistics by Expiry")
        greek_stats = data.groupby('expiry')[greek].agg(['mean', 'std', 'min', 'max']).reset_index()
        greek_stats.columns = ['Expiry', 'Mean', 'Std Dev', 'Min', 'Max']
        st.dataframe(greek_stats, hide_index=True, use_container_width=True)
    
    with tab4:
        st.subheader("Raw Data")
        
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            expiry_filter = st.multiselect(
                "Filter by Expiry",
                options=sorted(data['expiry'].unique()),
                default=None
            )
        with col2:
            option_type_filter = st.multiselect(
                "Filter by Type",
                options=['call', 'put'],
                default=None
            )
        
        # Apply filters
        filtered_data = data.copy()
        if expiry_filter:
            filtered_data = filtered_data[filtered_data['expiry'].isin(expiry_filter)]
        if option_type_filter:
            filtered_data = filtered_data[filtered_data['option_type'].isin(option_type_filter)]
        
        st.dataframe(filtered_data, hide_index=True, use_container_width=True)
        
        # Download button
        csv = filtered_data.to_csv(index=False)
        st.download_button(
            label="📥 Download Data CSV",
            data=csv,
            file_name=f"options_data_{asset}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"<div style='text-align: center; color: #666;'>"
        f"Data updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Powered by Kaiko API"
        f"</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()