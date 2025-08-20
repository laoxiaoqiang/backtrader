import ccxt
import yfinance as yf
import tushare as ts
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Union
import logging
import time
import configparser
import os

class BaseDataFetcher:
    """数据获取基类"""
    
    def __init__(self, config_path: str = "config.ini"):
        """
        初始化数据获取器
        
        Args:
            config_path: 配置文件路径
        """
        self.config = configparser.ConfigParser()
        self.config_path = config_path
        self.logger = self._setup_logger()
        
        # 加载配置
        if os.path.exists(config_path):
            self.config.read(config_path)
        else:
            self.logger.warning(f"配置文件 {config_path} 不存在")
    
    def _setup_logger(self):
        """设置日志记录器"""
        logger = logging.getLogger(self.__class__.__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def fetch_data(self, symbol: str, timeframe: str, start_time: Optional[datetime] = None, 
                  end_time: Optional[datetime] = None, limit: int = 1000) -> pd.DataFrame:
        """
        获取数据的抽象方法
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期
            start_time: 开始时间
            end_time: 结束时间  
            limit: 限制数量
            
        Returns:
            OHLCV数据DataFrame
        """
        raise NotImplementedError("子类必须实现此方法")


class OKXDataFetcher(BaseDataFetcher):
    """OKX数据获取器"""
    
    def __init__(self, config_path: str = "config.ini"):
        super().__init__(config_path)
        self.exchange = None
        self._init_exchange()
    
    def _init_exchange(self):
        """初始化OKX交易所连接"""
        try:
            # 从配置文件获取API密钥
            api_key = self.config.get('OKX', 'api_key', fallback='')
            api_secret = self.config.get('OKX', 'api_secret', fallback='')
            api_passphrase = self.config.get('OKX', 'api_passphrase', fallback='')
            sandbox = self.config.getboolean('OKX', 'sandbox', fallback=False)
            proxy = self.config.get('OKX', 'proxy', fallback='')
            
            exchange_config = {
                'apiKey': api_key,
                'secret': api_secret,
                'password': api_passphrase,
                'sandbox': sandbox,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot'
                }
            }
            
            # 如果有代理配置则添加
            if proxy:
                exchange_config['proxies'] = {
                    'http': f'http://{proxy}',
                    'https': f'http://{proxy}'
                }
            
            self.exchange = ccxt.okx(exchange_config)
            self.logger.info("OKX交易所连接初始化成功")
            
        except Exception as e:
            self.logger.error(f"初始化OKX交易所失败: {e}")
            self.exchange = None
    
    def fetch_data(self, symbol: str, timeframe: str, start_time: Optional[datetime] = None, 
                  end_time: Optional[datetime] = None, limit: int = 1000) -> pd.DataFrame:
        """
        获取OKX的OHLCV数据
        
        Args:
            symbol: 交易对符号 (如 'BTC/USDT')
            timeframe: 时间周期 ('1m', '5m', '15m', '30m', '1h', '2h', '1d')
            start_time: 开始时间
            end_time: 结束时间
            limit: 每次请求的限制数量
            
        Returns:
            包含OHLCV数据的DataFrame
        """
        if not self.exchange:
            self.logger.error("OKX交易所未初始化")
            return pd.DataFrame()
        
        try:
            # 设置默认时间范围
            if not end_time:
                end_time = datetime.now()
            if not start_time:
                start_time = end_time - timedelta(days=7)  # 默认7天
            
            # 转换为毫秒时间戳
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(end_time.timestamp() * 1000)
            
            # 计算时间帧对应的毫秒数
            timeframe_ms = self._get_timeframe_ms(timeframe)
            
            all_data = []
            current_ms = start_ms
            
            # 分批获取数据直到结束时间
            while current_ms < end_ms:
                try:
                    # 获取一批数据
                    ohlcv = self.exchange.fetch_ohlcv(
                        symbol=symbol,
                        timeframe=timeframe,
                        since=current_ms,
                        limit=min(limit, 100)  # OKX限制每次最多100条
                    )
                    
                    if not ohlcv:
                        self.logger.info(f"没有更多数据可获取，当前时间: {datetime.fromtimestamp(current_ms/1000)}")
                        break
                    
                    # 过滤掉超出结束时间的数据
                    filtered_data = [candle for candle in ohlcv if candle[0] <= end_ms]
                    
                    if not filtered_data:
                        break
                    
                    all_data.extend(filtered_data)
                    
                    # 更新当前时间戳到最后一根K线的下一个周期
                    last_timestamp = filtered_data[-1][0]
                    current_ms = last_timestamp + timeframe_ms
                    
                    # 如果获取的数据少于限制数量，说明已经到达最新数据
                    if len(ohlcv) < min(limit, 100):
                        break
                    
                    # API限制，稍作延迟
                    time.sleep(0.1)
                    
                except ccxt.BaseError as e:
                    self.logger.error(f"获取OKX数据失败: {e}")
                    break
            
            if not all_data:
                self.logger.warning(f"未获取到{symbol}的数据")
                return pd.DataFrame()
            
            # 转换为DataFrame
            df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # 去重并按时间戳排序
            df = df.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
            
            # 转换时间戳
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # 转换数据类型
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            self.logger.info(f"成功获取OKX {symbol} {timeframe} 数据: {len(df)} 条记录")
            return df
            
        except Exception as e:
            self.logger.error(f"获取OKX数据时发生错误: {e}")
            return pd.DataFrame()
    
    def _get_timeframe_ms(self, timeframe: str) -> int:
        """将时间周期转换为毫秒数"""
        timeframe_map = {
            '1m': 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '30m': 30 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '2h': 2 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000
        }
        return timeframe_map.get(timeframe, 60 * 1000)  # 默认1分钟


class BinanceDataFetcher(BaseDataFetcher):
    """币安数据获取器"""
    
    def __init__(self, config_path: str = "config.ini"):
        super().__init__(config_path)
        self.exchange = None
        self._init_exchange()
    
    def _init_exchange(self):
        """初始化币安交易所连接"""
        try:
            # 从配置文件获取API密钥
            api_key = self.config.get('BINANCE', 'api_key', fallback='')
            api_secret = self.config.get('BINANCE', 'api_secret', fallback='')
            proxy = self.config.get('PROXY', 'http_proxy', fallback='')
            
            exchange_config = {
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot'
                }
            }
            
            # 如果有代理配置则添加
            if proxy:
                exchange_config['proxies'] = {
                    'http': f'http://{proxy}',
                    'https': f'http://{proxy}'
                }
            
            self.exchange = ccxt.binance(exchange_config)
            self.logger.info("币安交易所连接初始化成功")
            
        except Exception as e:
            self.logger.error(f"初始化币安交易所失败: {e}")
            self.exchange = None
    
    def fetch_data(self, symbol: str, timeframe: str, start_time: Optional[datetime] = None, 
                  end_time: Optional[datetime] = None, limit: int = 1000) -> pd.DataFrame:
        """
        获取币安的OHLCV数据
        
        Args:
            symbol: 交易对符号 (如 'BTC/USDT')
            timeframe: 时间周期 ('1m', '5m', '15m', '30m', '1h', '2h', '1d')
            start_time: 开始时间
            end_time: 结束时间
            limit: 每次请求的限制数量
            
        Returns:
            包含OHLCV数据的DataFrame
        """
        if not self.exchange:
            self.logger.error("币安交易所未初始化")
            return pd.DataFrame()
        
        try:
            # 设置默认时间范围
            if not end_time:
                end_time = datetime.now()
            if not start_time:
                start_time = end_time - timedelta(days=7)  # 默认7天
            
            # 转换为毫秒时间戳
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(end_time.timestamp() * 1000)
            
            # 计算时间帧对应的毫秒数
            timeframe_ms = self._get_timeframe_ms(timeframe)
            
            all_data = []
            current_ms = start_ms
            
            # 分批获取数据直到结束时间
            while current_ms < end_ms:
                try:
                    # 获取一批数据
                    ohlcv = self.exchange.fetch_ohlcv(
                        symbol=symbol,
                        timeframe=timeframe,
                        since=current_ms,
                        limit=min(limit, 1000)  # 币安限制每次最多1000条
                    )
                    
                    if not ohlcv:
                        self.logger.info(f"没有更多数据可获取，当前时间: {datetime.fromtimestamp(current_ms/1000)}")
                        break
                    
                    # 过滤掉超出结束时间的数据
                    filtered_data = [candle for candle in ohlcv if candle[0] <= end_ms]
                    
                    if not filtered_data:
                        break
                    
                    all_data.extend(filtered_data)
                    
                    # 更新当前时间戳到最后一根K线的下一个周期
                    last_timestamp = filtered_data[-1][0]
                    current_ms = last_timestamp + timeframe_ms
                    
                    # 如果获取的数据少于限制数量，说明已经到达最新数据
                    if len(ohlcv) < min(limit, 1000):
                        break
                    
                    # API限制，稍作延迟
                    time.sleep(0.1)
                    
                except ccxt.BaseError as e:
                    self.logger.error(f"获取币安数据失败: {e}")
                    break
            
            if not all_data:
                self.logger.warning(f"未获取到{symbol}的数据")
                return pd.DataFrame()
            
            # 转换为DataFrame
            df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # 去重并按时间戳排序
            df = df.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
            
            # 转换时间戳
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # 转换数据类型
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            self.logger.info(f"成功获取币安 {symbol} {timeframe} 数据: {len(df)} 条记录")
            return df
            
        except Exception as e:
            self.logger.error(f"获取币安数据时发生错误: {e}")
            return pd.DataFrame()
    
    def _get_timeframe_ms(self, timeframe: str) -> int:
        """将时间周期转换为毫秒数"""
        timeframe_map = {
            '1m': 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '30m': 30 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '2h': 2 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000
        }
        return timeframe_map.get(timeframe, 60 * 1000)  # 默认1分钟


class YahooDataFetcher(BaseDataFetcher):
    """Yahoo Finance数据获取器"""
    
    def __init__(self, config_path: str = "config.ini"):
        super().__init__(config_path)
    
    def fetch_data(self, symbol: str, timeframe: str, start_time: Optional[datetime] = None, 
                  end_time: Optional[datetime] = None, limit: int = 1000) -> pd.DataFrame:
        """
        获取Yahoo Finance的OHLCV数据
        
        Args:
            symbol: 股票代码 (如 'AAPL', 'TSLA')
            timeframe: 时间周期 ('1m', '5m', '15m', '30m', '1h', '1d')
            start_time: 开始时间
            end_time: 结束时间
            limit: 限制数量(Yahoo Finance不使用此参数)
            
        Returns:
            包含OHLCV数据的DataFrame
        """
        try:
            # 设置默认时间范围
            if not end_time:
                end_time = datetime.now()
            if not start_time:
                start_time = end_time - timedelta(days=30)  # 默认30天
            
            # 转换时间周期格式
            interval = self._convert_timeframe(timeframe)
            if not interval:
                self.logger.error(f"不支持的时间周期: {timeframe}")
                return pd.DataFrame()
            
            # 获取股票数据
            ticker = yf.Ticker(symbol)
            
            # 对于分钟级数据，Yahoo Finance有时间限制
            if interval in ['1m', '2m', '5m', '15m', '30m', '90m']:
                # 分钟级数据最多只能获取最近60天
                max_start_time = end_time - timedelta(days=60)
                if start_time < max_start_time:
                    start_time = max_start_time
                    self.logger.warning(f"分钟级数据时间范围调整为最近60天")
            
            data = ticker.history(
                start=start_time.strftime('%Y-%m-%d'),
                end=end_time.strftime('%Y-%m-%d'),
                interval=interval,
                auto_adjust=True,
                prepost=False
            )
            
            if data.empty:
                self.logger.warning(f"未获取到{symbol}的数据")
                return pd.DataFrame()
            
            # 重命名列以匹配标准格式
            data.columns = [col.lower() for col in data.columns]
            
            # 确保有必需的列
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in data.columns:
                    self.logger.error(f"缺少必需的列: {col}")
                    return pd.DataFrame()
            
            # 只保留需要的列
            df = data[required_columns].copy()
            
            # 处理缺失值
            df = df.dropna()
            
            # 转换数据类型
            for col in required_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            self.logger.info(f"成功获取Yahoo Finance {symbol} {timeframe} 数据: {len(df)} 条记录")
            return df
            
        except Exception as e:
            self.logger.error(f"获取Yahoo Finance数据时发生错误: {e}")
            return pd.DataFrame()
    
    def _convert_timeframe(self, timeframe: str) -> Optional[str]:
        """转换时间周期格式"""
        timeframe_map = {
            '1m': '1m',
            '5m': '5m', 
            '15m': '15m',
            '30m': '30m',
            '1h': '1h',
            '2h': '2h',
            '1d': '1d'
        }
        return timeframe_map.get(timeframe)


class TushareDataFetcher(BaseDataFetcher):
    """Tushare数据获取器"""
    
    def __init__(self, config_path: str = "config.ini"):
        super().__init__(config_path)
        self._init_tushare()
    
    def _init_tushare(self):
        """初始化Tushare"""
        try:
            token = self.config.get('TUSHARE', 'token', fallback='')
            if token:
                ts.set_token(token)
                self.pro = ts.pro_api()
                self.logger.info("Tushare初始化成功")
            else:
                self.logger.error("Tushare token未配置")
                self.pro = None
        except Exception as e:
            self.logger.error(f"初始化Tushare失败: {e}")
            self.pro = None
    
    def fetch_data(self, symbol: str, timeframe: str, start_time: Optional[datetime] = None, 
                  end_time: Optional[datetime] = None, limit: int = 1000) -> pd.DataFrame:
        """
        获取Tushare的OHLCV数据
        
        Args:
            symbol: 股票代码 (如 '000001.SZ', '600000.SH')
            timeframe: 时间周期 ('1d' - Tushare主要支持日线数据)
            start_time: 开始时间
            end_time: 结束时间
            limit: 限制数量
            
        Returns:
            包含OHLCV数据的DataFrame
        """
        if not self.pro:
            self.logger.error("Tushare未初始化")
            return pd.DataFrame()
        
        try:
            # 设置默认时间范围
            if not end_time:
                end_time = datetime.now()
            if not start_time:
                start_time = end_time - timedelta(days=365)  # 默认1年
            
            # Tushare主要支持日线数据
            if timeframe != '1d':
                self.logger.warning(f"Tushare主要支持日线数据，当前时间周期: {timeframe}")
            
            # 转换日期格式
            start_date = start_time.strftime('%Y%m%d')
            end_date = end_time.strftime('%Y%m%d')
            
            # 获取日线数据
            data = self.pro.daily(
                ts_code=symbol,
                start_date=start_date,
                end_date=end_date
            )
            
            if data.empty:
                self.logger.warning(f"未获取到{symbol}的数据")
                return pd.DataFrame()
            
            # 重命名列
            data = data.rename(columns={
                'trade_date': 'timestamp',
                'vol': 'volume'
            })
            
            # 转换日期格式
            data['timestamp'] = pd.to_datetime(data['timestamp'], format='%Y%m%d')
            data.set_index('timestamp', inplace=True)
            
            # 按时间排序
            data = data.sort_index()
            
            # 只保留需要的列
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            data = data[required_columns]
            
            # 转换数据类型
            for col in required_columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
            
            # 处理缺失值
            data = data.dropna()
            
            self.logger.info(f"成功获取Tushare {symbol} {timeframe} 数据: {len(data)} 条记录")
            return data
            
        except Exception as e:
            self.logger.error(f"获取Tushare数据时发生错误: {e}")
            return pd.DataFrame()