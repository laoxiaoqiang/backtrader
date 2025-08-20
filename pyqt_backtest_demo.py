#!/usr/bin/env python3
"""
PyQt图表回测演示 - 蜡烛图风格显示
使用新的数据加载模块和PyQt后端
"""

import sys
import os
import backtrader as bt
from datetime import datetime
import matplotlib
# 设置matplotlib后端为Qt5Agg (PyQt5)
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt

# 添加数据加载模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from data_loader import load_crypto, load_stock, quick_load, get_data_info


class SmaCrossStrategy(bt.Strategy):
    """简单移动平均交叉策略"""
    
    params = (
        ('sma1_period', 10),
        ('sma2_period', 30),
        ('printlog', True),
    )
    
    def __init__(self):
        # 移动平均线
        self.sma1 = bt.ind.SMA(period=self.params.sma1_period)
        self.sma2 = bt.ind.SMA(period=self.params.sma2_period)
        
        # 交叉信号
        self.crossover = bt.ind.CrossOver(self.sma1, self.sma2)
        
        # 交易计数
        self.trade_count = 0
        self.order = None
    
    def next(self):
        if self.order:
            return
        
        if not self.position:
            if self.crossover > 0:  # 金叉买入
                cash = self.broker.cash
                price = self.data.close[0]
                size = (cash * 0.95) / price
                self.order = self.buy(size=size)
                self.trade_count += 1
                if self.params.printlog:
                    self.log(f'🟢 买入信号 - 价格: ${price:,.2f}')
        else:
            if self.crossover < 0:  # 死叉卖出
                self.order = self.close()
                if self.params.printlog:
                    self.log(f'🔴 卖出信号 - 价格: ${self.data.close[0]:,.2f}')
    
    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}: {txt}')
    
    def notify_order(self, order):
        if order.status == order.Completed:
            if order.isbuy():
                self.log(f'✅ 买入完成 - 价格: ${order.executed.price:.2f}, 数量: {order.executed.size:.6f}')
            else:
                self.log(f'✅ 卖出完成 - 价格: ${order.executed.price:.2f}, 数量: {order.executed.size:.6f}')
        self.order = None
    
    def notify_trade(self, trade):
        if trade.isclosed:
            self.log(f'💰 交易完成 - 盈亏: ${trade.pnlcomm:.2f}')


class RSIStrategy(bt.Strategy):
    """RSI策略"""
    
    params = (
        ('rsi_period', 14),
        ('rsi_upper', 70),
        ('rsi_lower', 30),
    )
    
    def __init__(self):
        self.rsi = bt.ind.RSI(period=self.params.rsi_period)
        self.order = None
    
    def next(self):
        if self.order:
            return
            
        if not self.position:
            if self.rsi < self.params.rsi_lower:  # 超卖买入
                cash = self.broker.cash
                price = self.data.close[0]
                size = (cash * 0.95) / price
                self.order = self.buy(size=size)
        else:
            if self.rsi > self.params.rsi_upper:  # 超买卖出
                self.order = self.close()
    
    def notify_order(self, order):
        if order.status == order.Completed:
            self.order = None


def run_pyqt_backtest():
    """运行带PyQt图表的回测"""
    print("=" * 80)
    print("🚀 PyQt图表回测演示")
    print("=" * 80)
    
    # 使用新的数据加载模块加载数据
    print("\n📊 使用数据加载模块加载数据...")
    
    # 方法1: 使用快速加载
    data = quick_load('btc_1h_7d')  # BTC 1小时 7天数据
    
    if data is None:
        print("❌ 数据加载失败，尝试直接加载...")
        # 方法2: 直接加载
        data = load_crypto('BTC/USDT', 'okx', '1h', 7)
    
    if data is None:
        print("❌ 无法加载数据，退出")
        return
    
    # 显示数据信息
    info = get_data_info()
    if info:
        print(f"✅ 数据加载成功!")
        print(f"   交易对: {info['symbol']}")
        print(f"   交易所: {info['exchange']}")
        print(f"   时间周期: {info['timeframe']}")
        print(f"   数据量: {info['records']} 条")
        print(f"   时间范围: {info['start_date']} 到 {info['end_date']}")
        print(f"   价格范围: ${info['price_range']['min']:,.2f} - ${info['price_range']['max']:,.2f}")
    
    # 创建Cerebro
    cerebro = bt.Cerebro()
    
    # 添加策略
    print(f"\n📈 添加策略: SMA交叉策略")
    cerebro.addstrategy(SmaCrossStrategy)
    
    # 添加数据 - 现在只需要一行代码！
    cerebro.adddata(data)
    
    # 设置初始资金和手续费
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)
    
    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    print(f"\n🎯 开始回测...")
    start_value = cerebro.broker.getvalue()
    print(f"初始资金: ${start_value:,.2f}")
    
    # 运行回测
    results = cerebro.run()
    
    end_value = cerebro.broker.getvalue()
    return_pct = (end_value - start_value) / start_value * 100
    
    print(f"\n📊 回测结果:")
    print(f"期末资金: ${end_value:,.2f}")
    print(f"总收益: ${end_value - start_value:,.2f}")
    print(f"收益率: {return_pct:.2f}%")
    
    # 获取分析器结果
    strategy = results[0]
    try:
        sharpe_analysis = strategy.analyzers.sharpe.get_analysis()
        sharpe = sharpe_analysis.get('sharperatio', 0) if sharpe_analysis else 0
        
        drawdown_analysis = strategy.analyzers.drawdown.get_analysis()
        max_drawdown = drawdown_analysis.get('max', {}).get('drawdown', 0) if drawdown_analysis else 0
        
        trades_analysis = strategy.analyzers.trades.get_analysis()
        total_trades = trades_analysis.get('total', {}).get('total', 0) if trades_analysis else 0
        won_trades = trades_analysis.get('won', {}).get('total', 0) if trades_analysis else 0
        win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0
        
        print(f"夏普比率: {sharpe:.3f}" if sharpe is not None else "夏普比率: 0.000")
        print(f"最大回撤: {max_drawdown:.2f}%" if max_drawdown is not None else "最大回撤: 0.00%")
        print(f"交易次数: {total_trades}")
        print(f"胜率: {win_rate:.2f}%")
        
    except Exception as e:
        print(f"分析器结果获取失败: {e}")
    
    # 显示PyQt图表
    print(f"\n📈 显示PyQt图表...")
    print("提示: 图表将在新窗口中打开，支持交互操作")
    print("      - 鼠标滚轮缩放")
    print("      - 拖拽平移") 
    print("      - 工具栏操作")
    
    try:
        # 设置图表样式为蜡烛图
        cerebro.plot(
            style='candlestick',  # 蜡烛图样式
            plotdist=0.1,        # 子图间距
            barup='green',       # 阳线颜色
            bardown='red',       # 阴线颜色
            volume=True,         # 显示成交量
            grid=True,           # 显示网格
            tight=True           # 紧凑布局
        )
        print("✅ 图表显示成功!")
        
    except Exception as e:
        print(f"❌ 图表显示失败: {e}")
        if "tkinter" in str(e).lower():
            print("💡 提示: 需要安装tkinter支持")
            print("   - Windows: 通常tkinter已内置，可能需要重新安装Python")
            print("   - Linux: sudo apt-get install python3-tk")
            print("   - 或尝试: pip install tk")
        else:
            print("请检查PyQt5是否正确安装")
            import traceback
            traceback.print_exc()
    
    return results


def run_multiple_strategies():
    """运行多策略对比 + 图表显示"""
    print("=" * 80)
    print("🚀 多策略对比 + PyQt图表")
    print("=" * 80)
    
    # 加载数据
    data = quick_load('btc_1h_7d')
    if data is None:
        print("❌ 数据加载失败")
        return
    
    strategies = [
        ('SMA交叉策略', SmaCrossStrategy),
        ('RSI策略', RSIStrategy),
    ]
    
    results = {}
    
    for strategy_name, strategy_class in strategies:
        print(f"\n📈 测试策略: {strategy_name}")
        
        cerebro = bt.Cerebro()
        cerebro.addstrategy(strategy_class)
        cerebro.adddata(data)
        cerebro.broker.setcash(10000.0)
        cerebro.broker.setcommission(commission=0.001)
        
        start_value = cerebro.broker.getvalue()
        strategy_results = cerebro.run()
        end_value = cerebro.broker.getvalue()
        
        return_pct = (end_value - start_value) / start_value * 100
        print(f"收益率: {return_pct:.2f}%")
        
        results[strategy_name] = {
            'return_pct': return_pct,
            'cerebro': cerebro
        }
    
    # 找出最佳策略并显示图表
    best_strategy = max(results.keys(), key=lambda x: results[x]['return_pct'])
    print(f"\n🏆 最佳策略: {best_strategy}")
    print(f"   收益率: {results[best_strategy]['return_pct']:.2f}%")
    
    print(f"\n📈 显示最佳策略图表...")
    try:
        results[best_strategy]['cerebro'].plot(
            style='candlestick',
            barup='green',
            bardown='red',
            volume=True,
            grid=True
        )
    except Exception as e:
        print(f"❌ 图表显示失败: {e}")


def main():
    """主函数"""
    print("请选择运行模式:")
    print("1. 单策略回测 + PyQt图表")
    print("2. 多策略对比 + PyQt图表")
    print("3. 数据加载器测试")
    
    try:
        choice = input("请输入选择 (1-3): ").strip()
        
        if choice == '1':
            run_pyqt_backtest()
        elif choice == '2':
            run_multiple_strategies()
        elif choice == '3':
            # 测试数据加载器
            from data_loader import data_loader
            print("\n测试数据加载器...")
            data = data_loader.quick_load('btc_1h_7d')
            if data:
                info = data_loader.get_data_info()
                print(f"✅ 测试成功: {info}")
        else:
            print("默认运行单策略回测")
            run_pyqt_backtest()
            
    except KeyboardInterrupt:
        print("\n用户取消")
    except Exception as e:
        print(f"❌ 运行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
