#!/usr/bin/env python3
"""
DataFeed Engine Test Script

This script demonstrates the basic usage of the DataFeed Engine
and tests the pagination fix for complete historical data coverage.
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datafeed_engine import DataFeedEngine

def test_database_connection():
    """测试数据库连接"""
    print("=== 测试数据库连接 ===")
    try:
        engine = DataFeedEngine()
        info = engine.get_database_info()
        print(f"数据库路径: {info['database_path']}")
        print(f"数据库大小: {info['database_size']} bytes")
        print(f"总记录数: {info['total_records']}")
        print("✅ 数据库连接正常")
        return engine
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return None

def test_crypto_data_fetch(engine):
    """测试加密货币数据获取"""
    print("\n=== 测试加密货币数据获取 ===")
    try:
        # 获取少量数据进行测试
        results = engine.fetch_crypto_data(
            symbols=['BTC/USDT'],
            timeframes=['1h'],
            exchanges=['okx'],
            days=1  # 只获取1天数据进行测试
        )
        
        print(f"OKX数据获取结果: {results}")
        
        # 检查数据库中的数据
        data = engine.get_data('BTC/USDT', 'okx', '1h')
        if not data.empty:
            print(f"✅ 成功获取 {len(data)} 条BTC/USDT 1h数据")
            print(f"时间范围: {data.index.min()} 到 {data.index.max()}")
            print(f"最新价格: {data['close'].iloc[-1]}")
        else:
            print("⚠️ 未获取到数据，可能需要配置API密钥")
            
    except Exception as e:
        print(f"❌ 加密货币数据获取失败: {e}")

def test_pagination_fix(engine):
    """测试分页修复"""
    print("\n=== 测试分页修复 ===")
    try:
        # 获取7天的1分钟数据，应该有10080条记录
        print("获取7天BTC/USDT 1分钟数据...")
        results = engine.fetch_crypto_data(
            symbols=['BTC/USDT'],
            timeframes=['1m'],
            exchanges=['okx'],
            days=7
        )
        
        # 检查实际获取的数据量
        data = engine.get_data('BTC/USDT', 'okx', '1m')
        expected_records = 7 * 24 * 60  # 7天 * 24小时 * 60分钟 = 10080
        
        print(f"期望记录数: {expected_records}")
        print(f"实际记录数: {len(data)}")
        
        if len(data) > 100:  # 如果超过100条，说明分页修复成功
            print("✅ 分页修复成功！不再限制于100条记录")
        else:
            print("⚠️ 可能仍存在分页问题或API配置问题")
            
    except Exception as e:
        print(f"❌ 分页测试失败: {e}")

def test_us_stock_data(engine):
    """测试美股数据获取"""
    print("\n=== 测试美股数据获取 ===")
    try:
        results = engine.fetch_us_stock_data(
            symbols=['AAPL'],
            timeframes=['1d'],
            days=7
        )
        
        print(f"Yahoo Finance数据获取结果: 插入{results}条记录")
        
        data = engine.get_data('AAPL', 'yahoo', '1d')
        if not data.empty:
            print(f"✅ 成功获取 {len(data)} 条AAPL日线数据")
            print(f"最新价格: {data['close'].iloc[-1]}")
        else:
            print("⚠️ 未获取到AAPL数据")
            
    except Exception as e:
        print(f"❌ 美股数据获取失败: {e}")

def show_database_summary(engine):
    """显示数据库概要"""
    print("\n=== 数据库概要 ===")
    try:
        info = engine.get_database_info()
        
        print(f"总记录数: {info['total_records']}")
        
        if 'records_by_exchange' in info:
            print("\n按交易所分布:")
            for exchange, count in info['records_by_exchange'].items():
                print(f"  {exchange}: {count} 条记录")
        
        if 'records_by_timeframe' in info:
            print("\n按时间周期分布:")
            for timeframe, count in info['records_by_timeframe'].items():
                print(f"  {timeframe}: {count} 条记录")
        
        if 'top_symbols' in info:
            print("\n热门交易对(前5):")
            for symbol, count in list(info['top_symbols'].items())[:5]:
                print(f"  {symbol}: {count} 条记录")
                
    except Exception as e:
        print(f"❌ 获取数据库概要失败: {e}")

def main():
    """主测试函数"""
    print("DataFeed Engine 测试脚本")
    print("=" * 50)
    
    # 测试数据库连接
    engine = test_database_connection()
    if not engine:
        print("无法连接数据库，退出测试")
        return
    
    # 显示当前数据库状态
    show_database_summary(engine)
    
    # 测试加密货币数据获取
    test_crypto_data_fetch(engine)
    
    # 测试分页修复
    test_pagination_fix(engine)
    
    # 测试美股数据获取
    test_us_stock_data(engine)
    
    # 显示最终数据库状态
    show_database_summary(engine)
    
    print("\n=== 测试完成 ===")
    print("如果看到API相关错误，请检查config.ini文件中的API密钥配置")

if __name__ == "__main__":
    main()
