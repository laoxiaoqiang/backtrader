#!/usr/bin/env python3
"""
简单的DataFeed Engine功能测试
"""

import sys
import os
from datetime import datetime, timedelta

# 添加当前目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

def test_imports():
    """测试导入"""
    print("=== 测试导入 ===")
    try:
        from datafeed_engine import DataFeedEngine, OKXDataFetcher, YahooDataFetcher
        print("✅ 所有模块导入成功")
        return True
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_database_creation():
    """测试数据库创建"""
    print("\n=== 测试数据库创建 ===")
    try:
        from datafeed_engine import DataFeedEngine
        
        # 使用测试数据库
        config_path = os.path.join(current_dir, "config.ini")
        db_path = os.path.join(current_dir, "test_market_data.db")
        
        engine = DataFeedEngine(db_path=db_path, config_path=config_path)
        
        # 检查数据库信息
        info = engine.get_database_info()
        print(f"数据库路径: {info['database_path']}")
        print(f"数据库大小: {info['database_size']} bytes")
        print(f"总记录数: {info['total_records']}")
        print("✅ 数据库创建成功")
        return engine
    except Exception as e:
        print(f"❌ 数据库创建失败: {e}")
        return None

def test_yahoo_finance():
    """测试Yahoo Finance数据获取(无API密钥要求)"""
    print("\n=== 测试Yahoo Finance数据获取 ===")
    try:
        from datafeed_engine.fetchers import YahooDataFetcher
        
        config_path = os.path.join(current_dir, "config.ini")
        fetcher = YahooDataFetcher(config_path)
        
        # 获取Apple股票最近3天的日线数据
        end_time = datetime.now()
        start_time = end_time - timedelta(days=3)
        
        print("正在获取AAPL最近3天数据...")
        data = fetcher.fetch_data(
            symbol='AAPL',
            timeframe='1d',
            start_time=start_time,
            end_time=end_time
        )
        
        if not data.empty:
            print(f"✅ 成功获取 {len(data)} 条AAPL数据")
            print(f"时间范围: {data.index.min()} 到 {data.index.max()}")
            print(f"最新价格: ${data['close'].iloc[-1]:.2f}")
            print("前3行数据:")
            print(data.head(3))
            return True
        else:
            print("⚠️ 未获取到数据")
            return False
            
    except Exception as e:
        print(f"❌ Yahoo Finance测试失败: {e}")
        return False

def test_config_loading():
    """测试配置文件加载"""
    print("\n=== 测试配置文件加载 ===")
    try:
        from datafeed_engine.fetchers import BaseDataFetcher
        
        config_path = os.path.join(current_dir, "config.ini")
        
        if os.path.exists(config_path):
            fetcher = BaseDataFetcher(config_path)
            print("✅ 配置文件加载成功")
            
            # 测试读取配置
            okx_key = fetcher.config.get('OKX', 'api_key', fallback='未配置')
            tushare_token = fetcher.config.get('TUSHARE', 'token', fallback='未配置')
            
            print(f"OKX API Key: {okx_key[:10]}..." if len(okx_key) > 10 else f"OKX API Key: {okx_key}")
            print(f"Tushare Token: {tushare_token[:10]}..." if len(tushare_token) > 10 else f"Tushare Token: {tushare_token}")
            
            return True
        else:
            print(f"⚠️ 配置文件不存在: {config_path}")
            return False
            
    except Exception as e:
        print(f"❌ 配置文件测试失败: {e}")
        return False

def test_data_saving():
    """测试数据保存功能"""
    print("\n=== 测试数据保存功能 ===")
    try:
        # 如果之前的Yahoo Finance测试成功，尝试保存数据
        from datafeed_engine import DataFeedEngine
        from datafeed_engine.fetchers import YahooDataFetcher
        import pandas as pd
        
        config_path = os.path.join(current_dir, "config.ini")
        db_path = os.path.join(current_dir, "test_market_data.db")
        
        engine = DataFeedEngine(db_path=db_path, config_path=config_path)
        fetcher = YahooDataFetcher(config_path)
        
        # 获取少量数据
        end_time = datetime.now()
        start_time = end_time - timedelta(days=2)
        
        data = fetcher.fetch_data('AAPL', '1d', start_time, end_time)
        
        if not data.empty:
            # 保存数据
            saved_count = engine.db_manager.save_data(data, 'AAPL', 'yahoo', '1d')
            print(f"✅ 成功保存 {saved_count} 条数据")
            
            # 验证数据
            retrieved_data = engine.get_data('AAPL', 'yahoo', '1d')
            print(f"✅ 成功从数据库读取 {len(retrieved_data)} 条数据")
            return True
        else:
            print("⚠️ 没有数据可保存")
            return False
            
    except Exception as e:
        print(f"❌ 数据保存测试失败: {e}")
        return False

def cleanup():
    """清理测试文件"""
    try:
        test_db = os.path.join(current_dir, "test_market_data.db")
        if os.path.exists(test_db):
            os.remove(test_db)
            print("\n✅ 清理测试文件成功")
    except Exception as e:
        print(f"\n⚠️ 清理测试文件失败: {e}")

def main():
    """主测试函数"""
    print("DataFeed Engine 基础功能测试")
    print("=" * 50)
    
    # 测试结果统计
    tests_passed = 0
    total_tests = 5
    
    # 1. 测试导入
    if test_imports():
        tests_passed += 1
    
    # 2. 测试数据库创建
    engine = test_database_creation()
    if engine:
        tests_passed += 1
    
    # 3. 测试配置文件
    if test_config_loading():
        tests_passed += 1
    
    # 4. 测试Yahoo Finance
    if test_yahoo_finance():
        tests_passed += 1
    
    # 5. 测试数据保存
    if test_data_saving():
        tests_passed += 1
    
    # 清理
    cleanup()
    
    print("\n" + "=" * 50)
    print(f"测试完成: {tests_passed}/{total_tests} 项测试通过")
    
    if tests_passed == total_tests:
        print("🎉 所有测试通过！DataFeed Engine 基础功能正常")
    elif tests_passed >= 3:
        print("👍 大部分测试通过，核心功能正常")
    else:
        print("⚠️ 部分测试失败，请检查配置和网络连接")

if __name__ == "__main__":
    main()
