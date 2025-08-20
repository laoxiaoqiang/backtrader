#!/usr/bin/env python3
"""
增强版BackTrader回测演示
包含多种策略和详细分析
"""

import sys
import os
import pandas as pd
import backtrader as bt
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# 添加datafeed_engine到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from datafeed_engine import DataFeedEngine


class SmaCrossStrategy(bt.Strategy):
    """SMA交叉策略 - 带详细日志的版本"""
    
    params = (
        ('sma1_period', 10),
        ('sma2_period', 30),
        ('printlog', True),
    )
    
    def __init__(self):
        # 创建移动平均线指标
        self.sma1 = bt.ind.SMA(period=self.params.sma1_period)
        self.sma2 = bt.ind.SMA(period=self.params.sma2_period)
        
        # 创建交叉信号
        self.crossover = bt.ind.CrossOver(self.sma1, self.sma2)
        
        # 交易计数器
        self.trade_count = 0
    
    def next(self):
        """每个数据点调用"""
        if not self.position:  # 没有持仓
            if self.crossover > 0:  # 金叉 - 买入信号
                size = int(self.broker.cash / self.data.close[0])
                self.buy(size=size)
                self.trade_count += 1
                if self.params.printlog:
                    self.log(f'买入信号 - 价格: {self.data.close[0]:.2f}, 数量: {size}')
        
        else:  # 有持仓
            if self.crossover < 0:  # 死叉 - 卖出信号
                self.close()
                if self.params.printlog:
                    self.log(f'卖出信号 - 价格: {self.data.close[0]:.2f}')
    
    def log(self, txt, dt=None):
        """日志输出"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}: {txt}')
    
    def notify_order(self, order):
        """订单通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入完成 - 价格: {order.executed.price:.2f}, '
                        f'成本: {order.executed.value:.2f}, '
                        f'手续费: {order.executed.comm:.2f}')
            else:
                self.log(f'卖出完成 - 价格: {order.executed.price:.2f}, '
                        f'成本: {order.executed.value:.2f}, '
                        f'手续费: {order.executed.comm:.2f}')
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'订单失败: {order.status}')
    
    def notify_trade(self, trade):
        """交易通知"""
        if not trade.isclosed:
            return
        
        self.log(f'交易完成 - 毛利: {trade.pnl:.2f}, 净利: {trade.pnlcomm:.2f}')


class RsiStrategy(bt.Strategy):
    """RSI超买超卖策略"""
    
    params = (
        ('rsi_period', 14),
        ('rsi_upper', 70),
        ('rsi_lower', 30),
        ('printlog', False),
    )
    
    def __init__(self):
        self.rsi = bt.ind.RSI(period=self.params.rsi_period)
        self.trade_count = 0
    
    def next(self):
        if not self.position:
            if self.rsi < self.params.rsi_lower:  # 超卖 - 买入
                size = int(self.broker.cash / self.data.close[0])
                self.buy(size=size)
                self.trade_count += 1
        else:
            if self.rsi > self.params.rsi_upper:  # 超买 - 卖出
                self.close()


def load_data_from_database(symbol='BTC/USDT', exchange='okx', timeframe='1h', 
                          days=30, config_path='datafeed_engine/config.ini'):
    """从数据库加载数据"""
    print(f"📊 从数据库加载数据: {exchange} {symbol} {timeframe} (最近{days}天)")
    
    try:
        engine = DataFeedEngine(config_path=config_path)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        data = engine.get_data(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            start_time=start_date,
            end_time=end_date
        )
        
        if data.empty:
            print(f"❌ 没有找到数据")
            return None
        
        print(f"✅ 成功加载 {len(data)} 条数据")
        print(f"时间范围: {data.index.min()} 到 {data.index.max()}")
        print(f"价格范围: ${data['close'].min():.2f} - ${data['close'].max():.2f}")
        
        return data
        
    except Exception as e:
        print(f"❌ 加载数据失败: {e}")
        return None


def run_strategy_comparison():
    """运行策略比较"""
    print("=" * 80)
    print("🚀 BackTrader 策略比较回测")
    print("=" * 80)
    
    # 加载数据
    data = load_data_from_database(symbol='BTC/USDT', exchange='okx', timeframe='1h', days=7)
    if data is None:
        return
    
    strategies = [
        ('SMA交叉策略', SmaCrossStrategy),
        ('RSI策略', RsiStrategy),
    ]
    
    results = {}
    
    for strategy_name, strategy_class in strategies:
        print(f"\n📈 测试策略: {strategy_name}")
        print("-" * 40)
        
        # 创建Cerebro
        cerebro = bt.Cerebro()
        cerebro.addstrategy(strategy_class)
        
        # 添加数据
        datafeed = bt.feeds.PandasData(dataname=data)
        cerebro.adddata(datafeed)
        
        # 设置初始资金和手续费
        cerebro.broker.setcash(10000.0)
        cerebro.broker.setcommission(commission=0.001)
        
        # 添加分析器
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        
        # 运行回测
        start_value = cerebro.broker.getvalue()
        strategy_results = cerebro.run()
        end_value = cerebro.broker.getvalue()
        
        # 收集结果
        strategy_instance = strategy_results[0]
        
        result = {
            'start_value': start_value,
            'end_value': end_value,
            'return_pct': (end_value - start_value) / start_value * 100,
            'cerebro': cerebro,
            'strategy': strategy_instance
        }
        
        # 获取分析器结果
        try:
            sharpe = strategy_instance.analyzers.sharpe.get_analysis().get('sharperatio', 0)
            drawdown = strategy_instance.analyzers.drawdown.get_analysis()
            trades = strategy_instance.analyzers.trades.get_analysis()
            
            result['sharpe_ratio'] = sharpe if sharpe else 0
            result['max_drawdown'] = drawdown.get('max', {}).get('drawdown', 0)
            result['total_trades'] = trades.get('total', {}).get('total', 0)
            result['won_trades'] = trades.get('won', {}).get('total', 0)
            result['win_rate'] = result['won_trades'] / result['total_trades'] * 100 if result['total_trades'] > 0 else 0
            
        except:
            result.update({
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'total_trades': 0,
                'won_trades': 0,
                'win_rate': 0
            })
        
        results[strategy_name] = result
        
        # 输出结果
        print(f"初始资金: ${result['start_value']:,.2f}")
        print(f"期末资金: ${result['end_value']:,.2f}")
        print(f"收益率: {result['return_pct']:.2f}%")
        print(f"夏普比率: {result['sharpe_ratio']:.3f}")
        print(f"最大回撤: {result['max_drawdown']:.2f}%")
        print(f"交易次数: {result['total_trades']}")
        print(f"胜率: {result['win_rate']:.2f}%")
    
    # 策略比较
    print("\n" + "=" * 80)
    print("📊 策略比较结果")
    print("=" * 80)
    
    comparison_df = pd.DataFrame({
        name: {
            '收益率(%)': f"{result['return_pct']:.2f}",
            '夏普比率': f"{result['sharpe_ratio']:.3f}",
            '最大回撤(%)': f"{result['max_drawdown']:.2f}",
            '交易次数': result['total_trades'],
            '胜率(%)': f"{result['win_rate']:.2f}"
        }
        for name, result in results.items()
    })
    
    print(comparison_df.T)
    
    # 绘制对比图
    try:
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('策略比较分析', fontsize=16)
        
        strategy_names = list(results.keys())
        returns = [results[name]['return_pct'] for name in strategy_names]
        sharpe_ratios = [results[name]['sharpe_ratio'] for name in strategy_names]
        max_drawdowns = [abs(results[name]['max_drawdown']) for name in strategy_names]
        trade_counts = [results[name]['total_trades'] for name in strategy_names]
        
        # 收益率对比
        axes[0,0].bar(strategy_names, returns, color=['blue', 'green'])
        axes[0,0].set_title('收益率对比 (%)')
        axes[0,0].set_ylabel('收益率 (%)')
        
        # 夏普比率对比
        axes[0,1].bar(strategy_names, sharpe_ratios, color=['orange', 'red'])
        axes[0,1].set_title('夏普比率对比')
        axes[0,1].set_ylabel('夏普比率')
        
        # 最大回撤对比
        axes[1,0].bar(strategy_names, max_drawdowns, color=['purple', 'brown'])
        axes[1,0].set_title('最大回撤对比 (%)')
        axes[1,0].set_ylabel('最大回撤 (%)')
        
        # 交易次数对比
        axes[1,1].bar(strategy_names, trade_counts, color=['pink', 'gray'])
        axes[1,1].set_title('交易次数对比')
        axes[1,1].set_ylabel('交易次数')
        
        plt.tight_layout()
        plt.show()
        
    except Exception as e:
        print(f"⚠️ 无法显示对比图表: {e}")
    
    return results


def main():
    """主函数"""
    try:
        results = run_strategy_comparison()
        print(f"\n✅ 策略比较完成！")
        
        # 找出最佳策略
        if results:
            best_strategy = max(results.keys(), key=lambda x: results[x]['return_pct'])
            print(f"🏆 最佳策略: {best_strategy}")
            print(f"   收益率: {results[best_strategy]['return_pct']:.2f}%")
        
    except Exception as e:
        print(f"❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
