"""
Store and retrieve historical options snapshots for backtesting.
SQLite database with safe upsert logic and proper timestamp handling.
"""
import pandas as pd
import sqlite3
import os
from datetime import datetime
from typing import Optional, List


class HistoricalStorage:
    """SQLite database for storing daily options snapshots."""
    
    def __init__(self, db_path: str = "data/historical_options.db"):
        """Initialize database connection."""
        self.db_path = db_path
        
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset TEXT NOT NULL,
                snapshot_date DATE NOT NULL,
                spot_price REAL,
                num_instruments INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(asset, snapshot_date)
            )
        """)
        
        # Options data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS options_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                instrument TEXT NOT NULL,
                strike_price REAL,
                option_type TEXT,
                expiry TEXT,
                mark_iv REAL,
                bid_iv REAL,
                ask_iv REAL,
                delta REAL,
                gamma REAL,
                vega REAL,
                theta REAL,
                rho REAL,
                open_interest REAL,
                FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshot_date 
            ON snapshots(asset, snapshot_date)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_options_snapshot 
            ON options_data(snapshot_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_options_instrument
            ON options_data(instrument)
        """)
        
        conn.commit()
        conn.close()
    
    def save_snapshot(self, asset: str, data: pd.DataFrame, spot_price: float):
        """
        Save a daily snapshot of options data using safe upsert logic.
        
        Args:
            asset: Asset code (e.g., 'btc', 'eth')
            data: Options data DataFrame
            spot_price: Current spot price
        """
        snapshot_date = datetime.now().date()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if snapshot already exists
            cursor.execute("""
                SELECT id FROM snapshots
                WHERE asset = ? AND snapshot_date = ?
            """, (asset, str(snapshot_date)))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing snapshot
                snapshot_id = existing[0]
                
                cursor.execute("""
                    UPDATE snapshots
                    SET spot_price = ?, num_instruments = ?
                    WHERE id = ?
                """, (float(spot_price), len(data), snapshot_id))
                
                # Delete old options data for this snapshot
                cursor.execute("""
                    DELETE FROM options_data
                    WHERE snapshot_id = ?
                """, (snapshot_id,))
                
                print(f"  Updating existing snapshot {snapshot_id}")
            else:
                # Insert new snapshot
                cursor.execute("""
                    INSERT INTO snapshots 
                    (asset, snapshot_date, spot_price, num_instruments)
                    VALUES (?, ?, ?, ?)
                """, (asset, str(snapshot_date), float(spot_price), len(data)))
                
                # Get the new snapshot ID
                cursor.execute("""
                    SELECT id FROM snapshots
                    WHERE asset = ? AND snapshot_date = ?
                """, (asset, str(snapshot_date)))
                
                result = cursor.fetchone()
                if not result:
                    conn.rollback()
                    print(f"✗ Failed to create snapshot for {asset}")
                    return
                
                snapshot_id = result[0]
                print(f"  Created new snapshot {snapshot_id}")
            
            # Prepare data for insertion
            data = data.copy()
            
            # Convert timestamps to strings
            if 'expiry' in data.columns:
                data['expiry'] = data['expiry'].astype(str)
            
            # Insert options data
            inserted = 0
            for _, row in data.iterrows():
                try:
                    cursor.execute("""
                        INSERT INTO options_data
                        (snapshot_id, instrument, strike_price, option_type, expiry,
                         mark_iv, bid_iv, ask_iv, delta, gamma, vega, theta, rho, open_interest)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        snapshot_id,
                        str(row.get('instrument', '')),
                        self._to_float(row.get('strike_price')),
                        str(row.get('option_type', '')),
                        str(row.get('expiry', '')),
                        self._to_float(row.get('mark_iv')),
                        self._to_float(row.get('bid_iv')),
                        self._to_float(row.get('ask_iv')),
                        self._to_float(row.get('delta')),
                        self._to_float(row.get('gamma')),
                        self._to_float(row.get('vega')),
                        self._to_float(row.get('theta')),
                        self._to_float(row.get('rho')),
                        self._to_float(row.get('open_interest'))
                    ))
                    inserted += 1
                except Exception as e:
                    print(f"  Warning: Failed to insert {row.get('instrument')}: {e}")
                    continue
            
            conn.commit()
            print(f"✓ Saved snapshot: {asset} on {snapshot_date} ({inserted}/{len(data)} instruments)")
            
        except Exception as e:
            conn.rollback()
            print(f"✗ Error saving snapshot: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            conn.close()
    
    def _to_float(self, value) -> Optional[float]:
        """Safely convert value to float, returning None if invalid."""
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def get_snapshot(self, asset: str, date: str) -> Optional[pd.DataFrame]:
        """
        Retrieve a specific snapshot by date.
        
        Args:
            asset: Asset code
            date: Date string (YYYY-MM-DD)
        
        Returns:
            DataFrame with options data, or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Get snapshot metadata
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, spot_price FROM snapshots
                WHERE asset = ? AND snapshot_date = ?
            """, (asset, date))
            
            result = cursor.fetchone()
            
            if not result:
                return None
            
            snapshot_id, spot_price = result
            
            # Get options data
            query = """
                SELECT 
                    instrument, strike_price, option_type, expiry,
                    mark_iv, bid_iv, ask_iv,
                    delta, gamma, vega, theta, rho,
                    open_interest
                FROM options_data
                WHERE snapshot_id = ?
            """
            
            df = pd.read_sql_query(query, conn, params=(snapshot_id,))
            
            if not df.empty:
                # Add snapshot metadata
                df['spot_price'] = spot_price
                df['snapshot_date'] = date
                df['snapshot_timestamp'] = pd.Timestamp(date, tz='UTC')
                df['timestamp'] = df['snapshot_timestamp']  # Alias for compatibility
                
                # Parse expiry as UTC-aware datetime
                df['expiry'] = pd.to_datetime(df['expiry'], utc=True, errors='coerce')
            
            return df
            
        finally:
            conn.close()
    
    def get_date_range(self, asset: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Get all snapshots in a date range.
        
        Args:
            asset: Asset code
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Combined DataFrame with all snapshots in range
        """
        conn = sqlite3.connect(self.db_path)
        
        try:
            query = """
                SELECT 
                    s.snapshot_date,
                    s.spot_price,
                    o.instrument, o.strike_price, o.option_type, o.expiry,
                    o.mark_iv, o.bid_iv, o.ask_iv,
                    o.delta, o.gamma, o.vega, o.theta, o.rho,
                    o.open_interest
                FROM snapshots s
                JOIN options_data o ON s.id = o.snapshot_id
                WHERE s.asset = ?
                AND s.snapshot_date BETWEEN ? AND ?
                ORDER BY s.snapshot_date, o.instrument
            """
            
            df = pd.read_sql_query(
                query, 
                conn, 
                params=(asset, start_date, end_date)
            )
            
            if not df.empty:
                # Add timestamp columns
                df['snapshot_timestamp'] = pd.to_datetime(df['snapshot_date'], utc=True)
                df['timestamp'] = df['snapshot_timestamp']  # Alias
                
                # Parse expiry as UTC-aware datetime
                df['expiry'] = pd.to_datetime(df['expiry'], utc=True, errors='coerce')
            
            return df
            
        finally:
            conn.close()
    
    def list_snapshots(self, asset: str = None) -> pd.DataFrame:
        """List all available snapshots."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            if asset:
                query = """
                    SELECT asset, snapshot_date, spot_price, num_instruments, created_at
                    FROM snapshots
                    WHERE asset = ?
                    ORDER BY snapshot_date DESC
                """
                df = pd.read_sql_query(query, conn, params=(asset,))
            else:
                query = """
                    SELECT asset, snapshot_date, spot_price, num_instruments, created_at
                    FROM snapshots
                    ORDER BY snapshot_date DESC, asset
                """
                df = pd.read_sql_query(query, conn)
            
            return df
            
        finally:
            conn.close()
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Count snapshots
            cursor.execute("SELECT COUNT(*) FROM snapshots")
            num_snapshots = cursor.fetchone()[0]
            
            # Count total data points
            cursor.execute("SELECT COUNT(*) FROM options_data")
            num_datapoints = cursor.fetchone()[0]
            
            # Get date range
            cursor.execute("""
                SELECT MIN(snapshot_date), MAX(snapshot_date)
                FROM snapshots
            """)
            date_range = cursor.fetchone()
            
            # Get assets
            cursor.execute("SELECT DISTINCT asset FROM snapshots ORDER BY asset")
            assets = [row[0] for row in cursor.fetchall()]
            
            return {
                'num_snapshots': num_snapshots,
                'num_datapoints': num_datapoints,
                'date_range': date_range if date_range else (None, None),
                'assets': assets
            }
            
        finally:
            conn.close()
    
    def delete_snapshot(self, asset: str, date: str) -> bool:
        """Delete a specific snapshot."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get snapshot ID
            cursor.execute("""
                SELECT id FROM snapshots
                WHERE asset = ? AND snapshot_date = ?
            """, (asset, date))
            
            result = cursor.fetchone()
            if not result:
                return False
            
            snapshot_id = result[0]
            
            # Delete options data (cascade should handle this, but be explicit)
            cursor.execute("DELETE FROM options_data WHERE snapshot_id = ?", (snapshot_id,))
            
            # Delete snapshot
            cursor.execute("DELETE FROM snapshots WHERE id = ?", (snapshot_id,))
            
            conn.commit()
            print(f"✓ Deleted snapshot: {asset} on {date}")
            return True
            
        except Exception as e:
            conn.rollback()
            print(f"✗ Error deleting snapshot: {e}")
            return False
        
        finally:
            conn.close()


class BacktestRunner:
    """
    Run signal generation on historical snapshot data.
    
    Note: This runner generates signals only. It does NOT simulate trades
    or calculate P&L unless real mark-to-mark execution logic is added.
    """
    
    def __init__(self, storage: HistoricalStorage):
        self.storage = storage
    
    def run_backtest(
        self,
        strategy,
        asset: str,
        start_date: str,
        end_date: str
    ) -> dict:
        """
        Run signal generation on historical snapshots.
        
        This generates trading signals on each historical snapshot.
        It does NOT simulate trade execution or calculate P&L.
        
        Args:
            strategy: Strategy instance
            asset: Asset to analyze
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Dictionary with signals and statistics
        """
        from .strategies import SignalType  # Import here to avoid circular dependency
        
        print(f"\n{'='*70}")
        print(f"HISTORICAL SIGNAL GENERATION: {strategy.name}")
        print(f"{'='*70}")
        print(f"Asset: {asset.upper()}")
        print(f"Period: {start_date} to {end_date}")
        print(f"\nNote: This generates signals only, not P&L.\n")
        
        # Get historical data
        historical_data = self.storage.get_date_range(asset, start_date, end_date)
        
        if historical_data.empty:
            return {
                'error': 'No historical data found for this period',
                'asset': asset,
                'start_date': start_date,
                'end_date': end_date
            }
        
        print(f"✓ Loaded {len(historical_data)} historical data points")
        print(f"  Unique dates: {historical_data['snapshot_date'].nunique()}\n")
        
        # Group by date and run strategy on each day
        all_signals = []
        
        for date in sorted(historical_data['snapshot_date'].unique()):
            day_data = historical_data[historical_data['snapshot_date'] == date].copy()
            
            # Get spot price for this day
            spot_price = day_data['spot_price'].iloc[0]
            
            # Create spot data DataFrame with UTC-aware timestamp
            spot_data = pd.DataFrame({
                'timestamp': [pd.Timestamp(date, tz='UTC')],
                'price': [spot_price]
            })
            
            # Ensure market data has proper timestamp
            day_data['timestamp'] = pd.Timestamp(date, tz='UTC')
            day_data['snapshot_timestamp'] = pd.Timestamp(date, tz='UTC')
            
            # Generate signals
            try:
                signals = strategy.generate_signals(day_data, spot_data)
                
                if signals:
                    print(f"  {date}: {len(signals)} signals @ ${spot_price:,.0f}")
                    all_signals.extend(signals)
                else:
                    print(f"  {date}: No signals @ ${spot_price:,.0f}")
                    
            except Exception as e:
                print(f"  {date}: Error - {e}")
                continue
        
        # Summarize results
        print(f"\n{'='*70}")
        print("SIGNAL GENERATION RESULTS")
        print(f"{'='*70}")
        print(f"Total Signals: {len(all_signals)}")
        
        if all_signals:
            buy_signals = [s for s in all_signals if s.signal_type == SignalType.BUY]
            sell_signals = [s for s in all_signals if s.signal_type == SignalType.SELL]
            
            print(f"BUY Signals: {len(buy_signals)}")
            print(f"SELL Signals: {len(sell_signals)}")
            
            # Create signals DataFrame
            signal_df = pd.DataFrame([{
                'timestamp': s.timestamp,
                'action': s.signal_type.name,
                'instrument': s.instrument,
                'strike': s.strike,
                'option_type': s.option_type,
                'iv': s.iv,
                'spot_price': s.spot_price,
                'reason': s.reason
            } for s in all_signals])
            
            print(f"\nSignal Distribution:")
            print(signal_df.groupby(['action', 'option_type']).size())
        else:
            signal_df = pd.DataFrame()
            print("\nNo signals generated in this period.")
        
        print(f"{'='*70}\n")
        
        return {
            'signals': all_signals,
            'signal_df': signal_df,
            'num_signals': len(all_signals),
            'date_range': (start_date, end_date),
            'num_days': historical_data['snapshot_date'].nunique(),
            'asset': asset
        }


# CLI tool
if __name__ == "__main__":
    import sys
    
    storage = HistoricalStorage()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'stats':
            stats = storage.get_stats()
            print("\nDatabase Statistics:")
            print(f"  Snapshots: {stats['num_snapshots']}")
            print(f"  Data points: {stats['num_datapoints']:,}")
            print(f"  Date range: {stats['date_range']}")
            print(f"  Assets: {', '.join(stats['assets'])}\n")
        
        elif command == 'list':
            snapshots = storage.list_snapshots()
            print("\nAvailable Snapshots:")
            if not snapshots.empty:
                print(snapshots.to_string(index=False))
            else:
                print("  (none)")
        
        else:
            print(f"Unknown command: {command}")
            print("Usage: python historical_storage.py [stats|list]")
    else:
        print("Historical Storage Module")
        print(f"Database: {storage.db_path}")
        print("\nUsage:")
        print("  python historical_storage.py stats  - Show database statistics")
        print("  python historical_storage.py list   - List all snapshots")