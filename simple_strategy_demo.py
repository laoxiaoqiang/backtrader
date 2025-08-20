#!/usr/bin/env python3
"""
简单的策略示例 - 展示如何使用新的数据加载模块
"""

import sys
import os
import backtrader as bt
import matplotlib
matplotlib.use('Qt5Agg')  # 使用PyQt5后端
import matplotlib.pyplot as plt


# 导入我们的数据加载模块
from data_loader import load_crypto, load_stock, quick_load, get_data_info


class SimpleStrategy(bt.Strategy):
    """简单策略示例"""
    
    params = (
        ('fast_period', 10),
        ('slow_period', 30),
    )
    
    def __init__(self):
        # 创建移动平均线指标
        self.fast_ma = bt.ind.SMA(period=self.params.fast_period)
        self.slow_ma = bt.ind.SMA(period=self.params.slow_period)
        
        # 创建交叉信号
        self.crossover = bt.ind.CrossOver(self.fast_ma, self.slow_ma)
        
        self.order = None
    
    def next(self):
        if self.order:
            return
        
        if not self.position:
            if self.crossover > 0:  # 快线上穿慢线 - 买入
                self.order = self.buy()
        else:
            if self.crossover < 0:  # 快线下穿慢线 - 卖出
                self.order = self.close()
    
    def notify_order(self, order):
        if order.status == order.Completed:
            if order.isbuy():
                print(f'买入: ${order.executed.price:.2f}')
            else:
                print(f'卖出: ${order.executed.price:.2f}')
        self.order = None
    
    def notify_trade(self, trade):
        if trade.isclosed:
            print(f'交易盈亏: ${trade.pnlcomm:.2f}')


def simple_backtest_example():
    """简单回测示例 - 演示数据加载模块的使用"""
    print("=" * 60)
    print("📈 简单策略回测示例")
    print("=" * 60)
    
    # 方法1: 使用快速加载 - 只需一行代码！
    print("\n🚀 方法1: 快速加载预设数据")
    data = quick_load('btc_1h_7d')  # BTC 1小时 7天
    
    if data is None:
        print("快速加载失败，尝试直接加载...")
        # 方法2: 直接加载 - 也很简单
        print("\n🚀 方法2: 直接加载数据")
        data = load_crypto('BTC/USDT', 'okx', '1h', 7)
    
    if data is None:
        print("❌ 数据加载失败")
        return
    
    # 显示数据信息
    info = get_data_info()
    if info:
        print(f"✅ 数据加载成功: {info['symbol']} ({info['records']}条)")
    
    # 创建策略和回测
    cerebro = bt.Cerebro()
    
    # 添加策略 - 使用自定义参数
    cerebro.addstrategy(SimpleStrategy, fast_period=5, slow_period=20)
    
    # 添加数据 - 现在只需要一行！
    cerebro.adddata(data)
    
    # 设置资金和手续费
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)
    
    print(f"\n开始回测...")
    start_value = cerebro.broker.getvalue()
    
    # 运行回测
    cerebro.run()
    
    end_value = cerebro.broker.getvalue()
    print(f"\n结果:")
    print(f"初始资金: ${start_value:,.2f}")
    print(f"期末资金: ${end_value:,.2f}")
    print(f"收益: ${end_value - start_value:,.2f}")
    print(f"收益率: {((end_value - start_value) / start_value) * 100:.2f}%")
    
    # 显示图表
    print(f"\n📊 显示交互式图表...")
    try:
        cerebro.plot(style='candlestick', barup='green', bardown='red', volume=True)
        print("✅ 图表显示成功!")
    except Exception as e:
        print(f"❌ 图表显示失败: {e}")
        if "tkinter" in str(e).lower():
            print("💡 提示: 需要安装tkinter支持")
            print("   - Windows: tkinter通常已内置，可能需要重新安装Python")
            print("   - Linux: sudo apt-get install python3-tk")
            print("   - 或尝试使用matplotlib的其他后端")
        print("\n回测数据和结果计算都是正常的，只是图表显示出现问题。")


def compare_different_data():
    """比较不同数据源"""
    print("=" * 60)
    print("📊 不同数据源对比")
    print("=" * 60)
    
    # 测试不同的数据加载方式
    test_cases = [
        ("BTC 1小时 7天", lambda: quick_load('btc_1h_7d')),
        ("BTC 4小时 30天", lambda: load_crypto('BTC/USDT', 'okx', '4h', 30)),
        ("ETH 1小时 7天", lambda: load_crypto('ETH/USDT', 'okx', '1h', 7)),
    ]
    
    results = {}
    
    for name, loader in test_cases:
        print(f"\n测试: {name}")
        data = loader()
        
        if data is not None:
            info = get_data_info()
            if info:
                results[name] = info
                print(f"  ✅ 成功: {info['records']}条数据")
                print(f"     价格: ${info['price_range']['min']:,.2f} - ${info['price_range']['max']:,.2f}")
        else:
            print(f"  ❌ 失败")
    
    # 显示对比结果
    if results:
        print(f"\n📊 数据对比结果:")
        for name, info in results.items():
            print(f"{name:20s}: {info['records']:4d}条, ${info['price_range']['min']:7,.0f}-${info['price_range']['max']:7,.0f}")


def main():
    """主函数"""
    print("🚀 BackTrader数据加载模块演示")
    print("\n选择运行模式:")
    print("1. 简单回测示例 (推荐)")
    print("2. 数据源对比测试")
    
    try:
        choice = input("请选择 (1-2): ").strip()
        
        if choice == '2':
            compare_different_data()
        else:
            simple_backtest_example()
            
    except KeyboardInterrupt:
        print("\n用户取消")
    except Exception as e:
        print(f"❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
