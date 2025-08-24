import logging
import schedule
import time
import sys
import os
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import threading
import pandas as pd

# 支持相对导入和绝对导入
try:
    from .database import DatabaseManager
    from .fetchers import OKXDataFetcher, BinanceDataFetcher, YahooDataFetcher, TushareDataFetcher
except ImportError:
    # 当作为脚本直接运行时，使用绝对导入
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from database import DatabaseManager
    from fetchers import OKXDataFetcher, BinanceDataFetcher, YahooDataFetcher, TushareDataFetcher

class DataFeedEngine:
    """数据获取引擎"""
    
    def __init__(self, db_path: str = "market_data.db", config_path: str = "config.ini"):
        """
        初始化数据获取引擎
        
        Args:
            db_path: 数据库文件路径
            config_path: 配置文件路径
        """
        self.db_manager = DatabaseManager(db_path)
        self.config_path = config_path
        self.logger = self._setup_logger()
        
        # 初始化数据获取器
        self.fetchers = {
            'okx': OKXDataFetcher(config_path),
            'binance': BinanceDataFetcher(config_path),
            'yahoo': YahooDataFetcher(config_path),
            'tushare': TushareDataFetcher(config_path)
        }
        
        # 运行状态
        self.running = False
        self.scheduler_thread = None
        
        # 默认配置
        self.default_config = {
            'crypto_symbols': ['BTC/USDT', 'ETH/USDT'],
            'us_stocks': ['AAPL', 'TSLA', 'GOOGL'],
            'a_stocks': ['000001.SZ', '600000.SH'],
            'timeframes': ['1m', '5m', '15m', '30m', '1h', '2h', '1d'],
            'crypto_exchanges': ['okx', 'binance'],
            'update_interval_minutes': 60  # 每小时更新一次
        }
    
    def _setup_logger(self):
        """设置日志记录器"""
        logger = logging.getLogger('DataFeedEngine')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def fetch_crypto_data(self, symbols: List[str], timeframes: List[str], 
                         exchanges: List[str] = None, days: int = 7) -> Dict[str, int]:
        """
        获取加密货币数据
        
        Args:
            symbols: 交易对列表
            timeframes: 时间周期列表
            exchanges: 交易所列表
            days: 获取多少天的数据
            
        Returns:
            各交易所插入的数据统计
        """
        if exchanges is None:
            exchanges = ['okx', 'binance']
        
        results = {}
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        for exchange in exchanges:
            if exchange not in self.fetchers:
                continue
            
            fetcher = self.fetchers[exchange]
            results[exchange] = 0
            
            for symbol in symbols:
                for timeframe in timeframes:
                    try:
                        self.logger.info(f"获取 {exchange} {symbol} {timeframe} 数据...")
                        
                        # 检查是否已有数据，实现增量更新
                        latest_timestamp = self.db_manager.get_latest_timestamp(
                            symbol, exchange, timeframe
                        )
                        
                        if latest_timestamp:
                            # 从最新时间戳开始获取
                            fetch_start_time = datetime.fromtimestamp(latest_timestamp / 1000)
                            # 添加一个时间周期的偏移避免重复
                            fetch_start_time += self._get_timeframe_delta(timeframe)
                        else:
                            fetch_start_time = start_time
                        
                        # 如果开始时间已经超过结束时间，跳过
                        if fetch_start_time >= end_time:
                            self.logger.info(f"{exchange} {symbol} {timeframe} 数据已是最新")
                            continue
                        
                        # 获取数据
                        data = fetcher.fetch_data(
                            symbol=symbol,
                            timeframe=timeframe,
                            start_time=fetch_start_time,
                            end_time=end_time,
                            limit=1000
                        )
                        
                        # 保存到数据库
                        if not data.empty:
                            inserted_count = self.db_manager.save_data(
                                data, symbol, exchange, timeframe
                            )
                            results[exchange] += inserted_count
                            self.logger.info(f"插入 {inserted_count} 条 {exchange} {symbol} {timeframe} 数据")
                        
                        # 避免API限制
                        time.sleep(0.5)
                        
                    except Exception as e:
                        self.logger.error(f"获取 {exchange} {symbol} {timeframe} 数据失败: {e}")
                        continue
        
        return results
    
    def fetch_us_stock_data(self, symbols: List[str], timeframes: List[str], 
                           days: int = 30) -> int:
        """
        获取美股数据
        
        Args:
            symbols: 股票代码列表
            timeframes: 时间周期列表
            days: 获取多少天的数据
            
        Returns:
            插入的数据条数
        """
        fetcher = self.fetchers['yahoo']
        total_inserted = 0
        
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        for symbol in symbols:
            for timeframe in timeframes:
                try:
                    self.logger.info(f"获取Yahoo Finance {symbol} {timeframe} 数据...")
                    
                    # 检查是否已有数据
                    latest_timestamp = self.db_manager.get_latest_timestamp(
                        symbol, 'yahoo', timeframe
                    )
                    
                    if latest_timestamp:
                        fetch_start_time = datetime.fromtimestamp(latest_timestamp / 1000)
                        fetch_start_time += self._get_timeframe_delta(timeframe)
                    else:
                        fetch_start_time = start_time
                    
                    if fetch_start_time >= end_time:
                        self.logger.info(f"Yahoo Finance {symbol} {timeframe} 数据已是最新")
                        continue
                    
                    # 获取数据
                    data = fetcher.fetch_data(
                        symbol=symbol,
                        timeframe=timeframe,
                        start_time=fetch_start_time,
                        end_time=end_time
                    )
                    
                    # 保存到数据库
                    if not data.empty:
                        inserted_count = self.db_manager.save_data(
                            data, symbol, 'yahoo', timeframe
                        )
                        total_inserted += inserted_count
                        self.logger.info(f"插入 {inserted_count} 条Yahoo Finance {symbol} {timeframe} 数据")
                    
                    time.sleep(1)  # Yahoo Finance API限制
                    
                except Exception as e:
                    self.logger.error(f"获取Yahoo Finance {symbol} {timeframe} 数据失败: {e}")
                    continue
        
        return total_inserted
    
    def fetch_a_stock_data(self, symbols: List[str], timeframes: List[str] = ['1d'], 
                          days: int = 365) -> int:
        """
        获取A股数据（批量版本）
        
        Args:
            symbols: 股票代码列表
            timeframes: 时间周期列表(Tushare主要支持日线)
            days: 获取多少天的数据
            
        Returns:
            插入的数据条数
        """
        total_inserted = 0
        
        for symbol in symbols:
            for timeframe in timeframes:
                try:
                    # 使用单股票获取方法，避免代码重复
                    inserted_count = self.fetch_single_stock_data(
                        symbol=symbol,
                        exchange='tushare',
                        timeframe=timeframe,
                        days=days
                    )
                    total_inserted += inserted_count
                    
                    # Tushare API限制
                    time.sleep(1)
                    
                except Exception as e:
                    self.logger.error(f"获取A股数据失败 {symbol} {timeframe}: {e}")
                    continue
        
        return total_inserted
    
    def fetch_single_stock_data(self, symbol: str, exchange: str = 'tushare', 
                               timeframe: str = '1d', days: int = 365) -> int:
        """
        获取单只股票数据
        
        Args:
            symbol: 股票代码 (如 '000001.SZ')
            exchange: 交易所 ('tushare', 'yahoo')
            timeframe: 时间周期
            days: 获取多少天的数据
            
        Returns:
            插入的数据条数
        """
        if exchange not in self.fetchers:
            self.logger.error(f"不支持的交易所: {exchange}")
            return 0
            
        fetcher = self.fetchers[exchange]
        
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        try:
            # 检查是否已有数据
            latest_timestamp = self.db_manager.get_latest_timestamp(
                symbol, exchange, timeframe
            )
            
            if latest_timestamp:
                fetch_start_time = datetime.fromtimestamp(latest_timestamp / 1000)
                fetch_start_time += self._get_timeframe_delta(timeframe)
            else:
                fetch_start_time = start_time
            
            if fetch_start_time >= end_time:
                self.logger.info(f"{exchange} {symbol} {timeframe} 数据已是最新")
                return 0
            
            # 获取数据
            data = fetcher.fetch_data(
                symbol=symbol,
                timeframe=timeframe,
                start_time=fetch_start_time,
                end_time=end_time
            )
            
            # 保存到数据库
            if not data.empty:
                inserted_count = self.db_manager.save_data(
                    data, symbol, exchange, timeframe
                )
                return inserted_count
            else:
                return 0
                
        except Exception as e:
            self.logger.error(f"获取 {exchange} {symbol} {timeframe} 数据失败: {e}")
            return 0
    
    def fetch_all_data(self, config: Dict = None) -> Dict[str, int]:
        """
        获取所有配置的数据
        
        Args:
            config: 自定义配置，如果为None则使用默认配置
            
        Returns:
            数据获取统计
        """
        if config is None:
            config = self.default_config
        
        results = {'crypto': {}, 'us_stocks': 0, 'a_stocks': 0}
        
        # 获取加密货币数据
        if 'crypto_symbols' in config and 'timeframes' in config:
            crypto_results = self.fetch_crypto_data(
                symbols=config['crypto_symbols'],
                timeframes=config['timeframes'],
                exchanges=config.get('crypto_exchanges', ['okx', 'binance'])
            )
            results['crypto'] = crypto_results
        
        # 获取美股数据
        if 'us_stocks' in config:
            us_results = self.fetch_us_stock_data(
                symbols=config['us_stocks'],
                timeframes=config.get('timeframes', ['1d'])
            )
            results['us_stocks'] = us_results
        
        # 获取A股数据
        if 'a_stocks' in config:
            a_results = self.fetch_a_stock_data(
                symbols=config['a_stocks'],
                timeframes=['1d']  # Tushare主要支持日线
            )
            results['a_stocks'] = a_results
        
        return results
    
    def start_scheduler(self, config: Dict = None):
        """
        启动定时任务
        
        Args:
            config: 自定义配置
        """
        if self.running:
            self.logger.warning("调度器已在运行")
            return
        
        if config is None:
            config = self.default_config
        
        # 设置定时任务
        interval_minutes = config.get('update_interval_minutes', 60)
        schedule.every(interval_minutes).minutes.do(self._scheduled_fetch, config)
        
        self.running = True
        
        # 启动调度器线程
        self.scheduler_thread = threading.Thread(target=self._run_scheduler)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        
        self.logger.info(f"数据获取调度器已启动，更新间隔: {interval_minutes} 分钟")
    
    def stop_scheduler(self):
        """停止定时任务"""
        self.running = False
        schedule.clear()
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        self.logger.info("数据获取调度器已停止")
    
    def _run_scheduler(self):
        """运行调度器"""
        while self.running:
            schedule.run_pending()
            time.sleep(30)  # 每30秒检查一次
    
    def _scheduled_fetch(self, config: Dict):
        """定时获取数据"""
        try:
            self.logger.info("开始定时数据获取...")
            results = self.fetch_all_data(config)
            self.logger.info(f"定时数据获取完成: {results}")
        except Exception as e:
            self.logger.error(f"定时数据获取失败: {e}")
    
    def _get_timeframe_delta(self, timeframe: str) -> timedelta:
        """获取时间周期对应的时间间隔"""
        timeframe_map = {
            '1m': timedelta(minutes=1),
            '5m': timedelta(minutes=5),
            '15m': timedelta(minutes=15),
            '30m': timedelta(minutes=30),
            '1h': timedelta(hours=1),
            '2h': timedelta(hours=2),
            '1d': timedelta(days=1)
        }
        return timeframe_map.get(timeframe, timedelta(minutes=1))
    
    def get_database_info(self) -> dict:
        """获取数据库信息"""
        return self.db_manager.get_database_info()
    
    def get_data(self, symbol: str, exchange: str, timeframe: str,
                start_time: Optional[datetime] = None, end_time: Optional[datetime] = None,
                limit: Optional[int] = None) -> pd.DataFrame:
        """
        从数据库获取数据
        
        Args:
            symbol: 交易对符号
            exchange: 交易所
            timeframe: 时间周期
            start_time: 开始时间
            end_time: 结束时间
            limit: 限制记录数
            
        Returns:
            OHLCV数据DataFrame
        """
        start_ms = int(start_time.timestamp() * 1000) if start_time else None
        end_ms = int(end_time.timestamp() * 1000) if end_time else None
        
        return self.db_manager.get_data(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            start_time=start_ms,
            end_time=end_ms,
            limit=limit
        )
    
    def clear_database(self, symbol: str = None, exchange: str = None, 
                      timeframe: str = None) -> int:
        """
        清理数据库数据
        
        Args:
            symbol: 交易对符号(可选)
            exchange: 交易所(可选)
            timeframe: 时间周期(可选)
            
        Returns:
            删除的记录数
        """
        return self.db_manager.clear_data(symbol, exchange, timeframe)


def main():
    """命令行接口"""
    parser = argparse.ArgumentParser(description='DataFeed Engine 命令行工具')
    parser.add_argument('--action', choices=['stats', 'fetch', 'clear', 'start'], 
                        required=True, help='执行的操作')
    parser.add_argument('--config', help='配置文件路径')
    parser.add_argument('--db', default='market_data.db', help='数据库文件路径')
    parser.add_argument('--symbol', help='交易对符号 (如: BTC/USDT)')
    parser.add_argument('--exchange', help='交易所 (如: okx, binance, yahoo, tushare)')
    parser.add_argument('--timeframe', help='时间周期 (如: 1m, 5m, 1h, 1d)')
    parser.add_argument('--days', type=int, default=7, help='获取多少天的数据')
    
    args = parser.parse_args()
    
    # 如果没有指定配置文件，使用脚本所在目录的config.ini
    if not args.config:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        args.config = os.path.join(script_dir, 'config.ini')
    
    # 初始化引擎
    try:
        engine = DataFeedEngine(db_path=args.db, config_path=args.config)
    except Exception as e:
        print(f"❌ 初始化引擎失败: {e}")
        return 1
    
    if args.action == 'stats':
        # 显示数据库统计信息
        try:
            info = engine.get_database_info()
            print("=" * 50)
            print("📊 DataFeed Engine 数据库统计")
            print("=" * 50)
            print(f"数据库路径: {info['database_path']}")
            print(f"数据库大小: {info['database_size'] / 1024:.2f} KB")
            print(f"总记录数: {info['total_records']:,}")
            
            if info['total_records'] > 0:
                print("\n📈 按交易所分布:")
                for exchange, count in info.get('records_by_exchange', {}).items():
                    print(f"  {exchange}: {count:,} 条记录")
                
                print("\n⏱️ 按时间周期分布:")
                for timeframe, count in info.get('records_by_timeframe', {}).items():
                    print(f"  {timeframe}: {count:,} 条记录")
                
                print("\n🔥 热门交易对 (前10):")
                for symbol, count in list(info.get('top_symbols', {}).items())[:10]:
                    print(f"  {symbol}: {count:,} 条记录")
            else:
                print("\n💡 数据库为空，使用 --action fetch 开始获取数据")
            
        except Exception as e:
            print(f"❌ 获取统计信息失败: {e}")
            return 1
    
    elif args.action == 'fetch':
        # 获取数据
        print("🔄 开始获取数据...")
        
        try:
            if args.symbol and args.exchange:
                # 获取指定交易对的数据
                if args.exchange in ['okx', 'binance']:
                    results = engine.fetch_crypto_data(
                        symbols=[args.symbol],
                        timeframes=[args.timeframe] if args.timeframe else ['1h', '1d'],
                        exchanges=[args.exchange],
                        days=args.days
                    )
                    print(f"✅ 获取完成: {results}")
                elif args.exchange == 'yahoo':
                    results = engine.fetch_us_stock_data(
                        symbols=[args.symbol],
                        timeframes=[args.timeframe] if args.timeframe else ['1d'],
                        days=args.days
                    )
                    print(f"✅ 获取完成: 插入 {results} 条记录")
                elif args.exchange == 'tushare':
                    results = engine.fetch_a_stock_data(
                        symbols=[args.symbol],
                        timeframes=[args.timeframe] if args.timeframe else ['1d'],
                        days=args.days
                    )
                    print(f"✅ 获取完成: 插入 {results} 条记录")
            else:
                # 获取所有配置的数据
                results = engine.fetch_all_data()
                print(f"✅ 获取完成: {results}")
                
        except Exception as e:
            print(f"❌ 获取数据失败: {e}")
            return 1
    
    elif args.action == 'clear':
        # 清理数据
        try:
            deleted_count = engine.clear_database(args.symbol, args.exchange, args.timeframe)
            print(f"✅ 已删除 {deleted_count} 条记录")
        except Exception as e:
            print(f"❌ 清理数据失败: {e}")
            return 1
    
    elif args.action == 'start':
        # 启动定时任务
        print("🚀 启动DataFeed Engine定时任务...")
        try:
            engine.start_scheduler()
            print("✅ 定时任务已启动，按 Ctrl+C 停止")
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                engine.stop_scheduler()
                print("\n✅ 定时任务已停止")
        except Exception as e:
            print(f"❌ 启动定时任务失败: {e}")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
