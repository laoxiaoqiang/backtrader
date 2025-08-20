import sqlite3
import pandas as pd
from typing import Optional
import os

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "market_data.db"):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 创建市场数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, exchange, timeframe, timestamp)
                )
            """)
            
            # 创建索引以提高查询性能
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_exchange_timeframe 
                ON market_data(symbol, exchange, timeframe)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON market_data(timestamp)
            """)
            
            conn.commit()
    
    def save_data(self, data: pd.DataFrame, symbol: str, exchange: str, timeframe: str) -> int:
        """
        保存数据到数据库
        
        Args:
            data: OHLCV数据DataFrame，索引为timestamp
            symbol: 交易对符号
            exchange: 交易所
            timeframe: 时间周期
            
        Returns:
            插入的记录数
        """
        if data.empty:
            return 0
            
        # 准备数据
        data_to_insert = []
        for timestamp, row in data.iterrows():
            data_to_insert.append({
                'symbol': symbol,
                'exchange': exchange,
                'timeframe': timeframe,
                'timestamp': int(timestamp.timestamp() * 1000) if hasattr(timestamp, 'timestamp') else int(timestamp),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume'])
            })
        
        # 批量插入数据
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            insert_count = 0
            for record in data_to_insert:
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO market_data 
                        (symbol, exchange, timeframe, timestamp, open, high, low, close, volume)
                        VALUES (:symbol, :exchange, :timeframe, :timestamp, :open, :high, :low, :close, :volume)
                    """, record)
                    if cursor.rowcount > 0:
                        insert_count += 1
                except sqlite3.Error as e:
                    print(f"插入数据失败: {e}")
                    continue
            
            conn.commit()
            return insert_count
    
    def get_data(self, symbol: str, exchange: str, timeframe: str, 
                 start_time: Optional[int] = None, end_time: Optional[int] = None,
                 limit: Optional[int] = None) -> pd.DataFrame:
        """
        从数据库获取数据
        
        Args:
            symbol: 交易对符号
            exchange: 交易所
            timeframe: 时间周期
            start_time: 开始时间戳(毫秒)
            end_time: 结束时间戳(毫秒)
            limit: 限制记录数
            
        Returns:
            OHLCV数据DataFrame
        """
        with sqlite3.connect(self.db_path) as conn:
            # 构建查询语句
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM market_data
                WHERE symbol = ? AND exchange = ? AND timeframe = ?
            """
            params = [symbol, exchange, timeframe]
            
            if start_time is not None:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time is not None:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            query += " ORDER BY timestamp"
            
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)
            
            df = pd.read_sql_query(query, conn, params=params)
            
            if not df.empty:
                # 转换时间戳为datetime索引
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
            
            return df
    
    def get_latest_timestamp(self, symbol: str, exchange: str, timeframe: str) -> Optional[int]:
        """
        获取最新的时间戳
        
        Args:
            symbol: 交易对符号
            exchange: 交易所
            timeframe: 时间周期
            
        Returns:
            最新时间戳(毫秒)，如果没有数据返回None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(timestamp) FROM market_data
                WHERE symbol = ? AND exchange = ? AND timeframe = ?
            """, (symbol, exchange, timeframe))
            
            result = cursor.fetchone()
            return result[0] if result[0] is not None else None
    
    def get_data_count(self, symbol: str = None, exchange: str = None, 
                      timeframe: str = None) -> int:
        """
        获取数据条数
        
        Args:
            symbol: 交易对符号(可选)
            exchange: 交易所(可选)
            timeframe: 时间周期(可选)
            
        Returns:
            数据条数
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = "SELECT COUNT(*) FROM market_data"
            params = []
            conditions = []
            
            if symbol:
                conditions.append("symbol = ?")
                params.append(symbol)
            
            if exchange:
                conditions.append("exchange = ?")
                params.append(exchange)
            
            if timeframe:
                conditions.append("timeframe = ?")
                params.append(timeframe)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else 0
    
    def get_symbols(self, exchange: str = None) -> list:
        """
        获取所有交易对符号
        
        Args:
            exchange: 交易所(可选)
            
        Returns:
            交易对符号列表
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if exchange:
                cursor.execute("""
                    SELECT DISTINCT symbol FROM market_data WHERE exchange = ?
                    ORDER BY symbol
                """, (exchange,))
            else:
                cursor.execute("""
                    SELECT DISTINCT symbol FROM market_data ORDER BY symbol
                """)
            
            return [row[0] for row in cursor.fetchall()]
    
    def get_database_info(self) -> dict:
        """
        获取数据库信息
        
        Returns:
            数据库信息字典
        """
        info = {
            'database_path': os.path.abspath(self.db_path),
            'database_size': os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
            'total_records': self.get_data_count()
        }
        
        # 按交易所和时间周期统计
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 按交易所统计
            cursor.execute("""
                SELECT exchange, COUNT(*) as count
                FROM market_data
                GROUP BY exchange
                ORDER BY count DESC
            """)
            info['records_by_exchange'] = dict(cursor.fetchall())
            
            # 按时间周期统计
            cursor.execute("""
                SELECT timeframe, COUNT(*) as count
                FROM market_data
                GROUP BY timeframe
                ORDER BY count DESC
            """)
            info['records_by_timeframe'] = dict(cursor.fetchall())
            
            # 按交易对统计
            cursor.execute("""
                SELECT symbol, COUNT(*) as count
                FROM market_data
                GROUP BY symbol
                ORDER BY count DESC
                LIMIT 10
            """)
            info['top_symbols'] = dict(cursor.fetchall())
        
        return info
    
    def clear_data(self, symbol: str = None, exchange: str = None, 
                  timeframe: str = None) -> int:
        """
        清理数据
        
        Args:
            symbol: 交易对符号(可选)
            exchange: 交易所(可选) 
            timeframe: 时间周期(可选)
            
        Returns:
            删除的记录数
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = "DELETE FROM market_data"
            params = []
            conditions = []
            
            if symbol:
                conditions.append("symbol = ?")
                params.append(symbol)
            
            if exchange:
                conditions.append("exchange = ?")
                params.append(exchange)
            
            if timeframe:
                conditions.append("timeframe = ?")
                params.append(timeframe)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            cursor.execute(query, params)
            deleted_count = cursor.rowcount
            conn.commit()
            
            return deleted_count
