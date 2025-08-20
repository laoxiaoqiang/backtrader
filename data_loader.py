#!/usr/bin/env python3
"""
BackTrader数据加载模块
提供简单易用的数据加载接口，策略开发者无需关心数据获取细节
"""

import sys
import os
import pandas as pd
import backtrader as bt
from datetime import datetime, timedelta
from typing import Optional, Union, List

# 添加datafeed_engine到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from datafeed_engine import DataFeedEngine


class DataLoader:
    """BackTrader数据加载器 - 统一数据接口"""
    
    def __init__(self, config_path: str = 'datafeed_engine/config.ini'):
        """
        初始化数据加载器
        
        Args:
            config_path: datafeed引擎配置文件路径
        """
        self.engine = DataFeedEngine(config_path=config_path)
        self._last_loaded_data = None
        self._last_params = None
    
    def load_crypto_data(self, 
                        symbol: str = 'BTC/USDT',
                        exchange: str = 'okx',
                        timeframe: str = '1h',
                        days: int = 30,
                        start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> Optional[bt.feeds.PandasData]:
        """
        加载加密货币数据
        
        Args:
            symbol: 交易对，如 'BTC/USDT', 'ETH/USDT'
            exchange: 交易所，'okx' 或 'binance'
            timeframe: 时间周期，'1m', '5m', '15m', '1h', '4h', '1d'
            days: 最近多少天的数据（如果未指定start_date）
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            BackTrader数据源对象，可直接添加到cerebro
        """
        return self._load_data('crypto', symbol, exchange, timeframe, days, start_date, end_date)
    
    def load_stock_data(self,
                       symbol: str,
                       exchange: str = 'yahoo',
                       timeframe: str = '1d',
                       days: int = 252,
                       start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None) -> Optional[bt.feeds.PandasData]:
        """
        加载股票数据
        
        Args:
            symbol: 股票代码，如 'AAPL', 'MSFT' (美股) 或 '000001.SZ' (A股)
            exchange: 数据源，'yahoo' 或 'tushare'
            timeframe: 时间周期，通常为 '1d'
            days: 最近多少天的数据（如果未指定start_date）
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            BackTrader数据源对象
        """
        return self._load_data('stock', symbol, exchange, timeframe, days, start_date, end_date)
    
    def _load_data(self, 
                   data_type: str,
                   symbol: str, 
                   exchange: str, 
                   timeframe: str, 
                   days: int,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None) -> Optional[bt.feeds.PandasData]:
        """内部数据加载方法"""
        
        try:
            # 计算时间范围
            if end_date is None:
                end_date = datetime.now()
            if start_date is None:
                start_date = end_date - timedelta(days=days)
            
            # 打印加载信息
            print(f"📊 加载{data_type}数据: {exchange} {symbol} {timeframe}")
            print(f"   时间范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")
            
            # 从数据库获取数据
            data = self.engine.get_data(
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                start_time=start_date,
                end_time=end_date
            )
            
            if data.empty:
                print(f"❌ 没有找到数据，尝试从{exchange}获取...")
                
                # 如果数据库没有数据，尝试获取
                if data_type == 'crypto':
                    if exchange in self.engine.fetchers:
                        fetcher = self.engine.fetchers[exchange]
                        fetcher.fetch_data(symbol, timeframe, start_date, end_date)
                        # 重新从数据库获取
                        data = self.engine.get_data(symbol, exchange, timeframe, start_date, end_date)
                
                if data.empty:
                    print(f"❌ 无法获取数据: {symbol}")
                    return None
            
            # 缓存最后的加载参数
            self._last_params = {
                'symbol': symbol,
                'exchange': exchange, 
                'timeframe': timeframe,
                'start_date': start_date,
                'end_date': end_date,
                'data_type': data_type
            }
            self._last_loaded_data = data
            
            print(f"✅ 成功加载 {len(data)} 条数据")
            print(f"   价格范围: ${data['close'].min():,.2f} - ${data['close'].max():,.2f}")
            
            # 创建BackTrader数据源
            bt_data = bt.feeds.PandasData(
                dataname=data,
                name=f"{symbol}_{timeframe}"  # 设置数据名称
            )
            
            return bt_data
            
        except Exception as e:
            print(f"❌ 数据加载失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_data_info(self) -> Optional[dict]:
        """获取最后加载的数据信息"""
        if self._last_loaded_data is None or self._last_params is None:
            return None
        
        data = self._last_loaded_data
        params = self._last_params
        
        return {
            'symbol': params['symbol'],
            'exchange': params['exchange'],
            'timeframe': params['timeframe'],
            'data_type': params['data_type'],
            'records': len(data),
            'start_date': data.index.min(),
            'end_date': data.index.max(),
            'price_range': {
                'min': data['close'].min(),
                'max': data['close'].max(),
                'first': data['close'].iloc[0],
                'last': data['close'].iloc[-1]
            },
            'volume_range': {
                'min': data['volume'].min() if 'volume' in data else 0,
                'max': data['volume'].max() if 'volume' in data else 0,
                'avg': data['volume'].mean() if 'volume' in data else 0
            }
        }
    
    def quick_load(self, preset: str = 'btc_1h_7d') -> Optional[bt.feeds.PandasData]:
        """
        快速加载预设数据配置
        
        Args:
            preset: 预设配置名称
                - 'btc_1h_7d': BTC/USDT 1小时 最近7天
                - 'btc_4h_30d': BTC/USDT 4小时 最近30天  
                - 'eth_1h_7d': ETH/USDT 1小时 最近7天
                - 'aapl_1d_1y': AAPL 日线 最近1年
                
        Returns:
            BackTrader数据源对象
        """
        presets = {
            'btc_1h_7d': {'symbol': 'BTC/USDT', 'exchange': 'okx', 'timeframe': '1h', 'days': 7},
            'btc_4h_30d': {'symbol': 'BTC/USDT', 'exchange': 'okx', 'timeframe': '4h', 'days': 30},
            'btc_1d_90d': {'symbol': 'BTC/USDT', 'exchange': 'okx', 'timeframe': '1d', 'days': 90},
            'eth_1h_7d': {'symbol': 'ETH/USDT', 'exchange': 'okx', 'timeframe': '1h', 'days': 7},
            'eth_4h_30d': {'symbol': 'ETH/USDT', 'exchange': 'okx', 'timeframe': '4h', 'days': 30},
            'aapl_1d_1y': {'symbol': 'AAPL', 'exchange': 'yahoo', 'timeframe': '1d', 'days': 252},
            'msft_1d_1y': {'symbol': 'MSFT', 'exchange': 'yahoo', 'timeframe': '1d', 'days': 252},
        }
        
        if preset not in presets:
            print(f"❌ 未知的预设配置: {preset}")
            print(f"可用预设: {list(presets.keys())}")
            return None
        
        config = presets[preset]
        
        # 判断数据类型
        if config['exchange'] in ['okx', 'binance']:
            return self.load_crypto_data(**config)
        else:
            return self.load_stock_data(**config)


# 全局数据加载器实例，方便直接使用
data_loader = DataLoader()


def load_crypto(symbol: str = 'BTC/USDT', 
               exchange: str = 'okx',
               timeframe: str = '1h', 
               days: int = 30) -> Optional[bt.feeds.PandasData]:
    """
    快捷函数：加载加密货币数据
    
    使用示例:
        data = load_crypto('BTC/USDT', 'okx', '1h', 7)
        cerebro.adddata(data)
    """
    return data_loader.load_crypto_data(symbol, exchange, timeframe, days)


def load_stock(symbol: str,
               exchange: str = 'yahoo', 
               timeframe: str = '1d',
               days: int = 252) -> Optional[bt.feeds.PandasData]:
    """
    快捷函数：加载股票数据
    
    使用示例:
        data = load_stock('AAPL', 'yahoo', '1d', 252)
        cerebro.adddata(data)
    """
    return data_loader.load_stock_data(symbol, exchange, timeframe, days)


def quick_load(preset: str = 'btc_1h_7d') -> Optional[bt.feeds.PandasData]:
    """
    快捷函数：快速加载预设数据
    
    使用示例:
        data = quick_load('btc_1h_7d')
        cerebro.adddata(data)
    """
    return data_loader.quick_load(preset)


def get_data_info() -> Optional[dict]:
    """
    获取最后加载的数据信息
    
    Returns:
        包含数据详细信息的字典
    """
    return data_loader.get_data_info()


if __name__ == "__main__":
    """数据加载器测试"""
    print("=" * 60)
    print("🧪 BackTrader数据加载器测试")
    print("=" * 60)
    
    # 测试加密货币数据加载
    print("\n1. 测试加密货币数据加载")
    crypto_data = load_crypto('BTC/USDT', 'okx', '1h', 7)
    if crypto_data is not None:
        info = get_data_info()
        if info:
            print(f"   数据信息: {info['records']}条记录")
            print(f"   价格范围: ${info['price_range']['min']:,.2f} - ${info['price_range']['max']:,.2f}")
    
    # 测试快速加载
    print("\n2. 测试快速加载")
    quick_data = quick_load('btc_4h_30d')
    if quick_data is not None:
        info = get_data_info()
        if info:
            print(f"   快速加载成功: {info['symbol']} {info['timeframe']}")
    
    print("\n✅ 数据加载器测试完成")
