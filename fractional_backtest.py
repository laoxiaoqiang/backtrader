#!/usr/bin/env python3
"""
实际可交易的BackTrader回测演示 - 支持分数交易
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


class FractionalSmaCrossStrategy(bt.Strategy):
    """支持分数交易的SMA交叉策略"""
    
    params = (
        ('sma1_period', 5),   
        ('sma2_period', 15),  
        ('printlog', True),
    )
    
    def __init__(self):
        self.sma1 = bt.ind.SMA(period=self.params.sma1_period)
        self.sma2 = bt.ind.SMA(period=self.params.sma2_period)
        self.crossover = bt.ind.CrossOver(self.sma1, self.sma2)
        self.trade_count = 0
        self.order = None
    
    def next(self):
        # 跳过待处理的订单
        if self.order:
            return
        
        if not self.position:
            if self.crossover > 0:  # 金叉 - 买入信号
                cash = self.broker.cash
                price = self.data.close[0]
                # 使用95%的资金，计算可买金额而不是数量
                value = cash * 0.95
                # BackTrader会自动处理分数交易
                self.order = self.buy(size=value/price)  # 这样可以买分数
                self.trade_count += 1
                if self.params.printlog:
                    self.log(f'🟢 买入订单 - 价格: ${price:,.2f}, 金额: ${value:,.2f}')
        else:
            if self.crossover < 0:  # 死叉 - 卖出信号
                self.order = self.close()
                if self.params.printlog:
                    self.log(f'🔴 卖出订单 - 价格: ${self.data.close[0]:,.2f}')
    
    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}: {txt}')
    
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status == order.Completed:
            if order.isbuy():
                self.log(f'✅ 买入完成 - 价格: ${order.executed.price:.2f}, '
                        f'数量: {order.executed.size:.6f}, '
                        f'总值: ${order.executed.value:.2f}, '
                        f'手续费: ${order.executed.comm:.2f}')
            else:
                self.log(f'✅ 卖出完成 - 价格: ${order.executed.price:.2f}, '
                        f'数量: {order.executed.size:.6f}, '
                        f'总值: ${order.executed.value:.2f}, '
                        f'手续费: ${order.executed.comm:.2f}')
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'❌ 订单失败: {order.status}')
        
        self.order = None
    
    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'💰 交易完成 - 毛利: ${trade.pnl:.2f}, 净利: ${trade.pnlcomm:.2f}')


class SimplePercentageStrategy(bt.Strategy):
    """简单百分比策略 - 每天定投"""
    
    params = (
        ('daily_investment', 100),  # 每天投资100美元
        ('printlog', False),
    )
    
    def __init__(self):
        self.trade_count = 0
        self.last_buy_date = None
        self.order = None
    
    def next(self):
        if self.order:
            return
        
        current_date = self.datas[0].datetime.date(0)
        
        # 每天定投一次
        if self.last_buy_date != current_date:
            if self.broker.cash >= self.params.daily_investment:
                price = self.data.close[0]
                size = self.params.daily_investment / price
                self.order = self.buy(size=size)
                self.trade_count += 1
                self.last_buy_date = current_date
                
                if self.params.printlog:
                    print(f'{current_date}: 定投 ${self.params.daily_investment} (价格: ${price:,.2f})')
    
    def notify_order(self, order):
        if order.status == order.Completed:
            self.order = None


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
        print(f"价格范围: ${data['close'].min():,.2f} - ${data['close'].max():,.2f}")
        
        return data
        
    except Exception as e:
        print(f"❌ 加载数据失败: {e}")
        return None


def run_fractional_backtest():
    """运行分数交易回测"""
    print("=" * 80)
    print("🚀 分数交易BackTrader回测演示")
    print("=" * 80)
    
    # 加载数据
    data = load_data_from_database(symbol='BTC/USDT', exchange='okx', timeframe='1h', days=7)  # 使用7天数据
    if data is None:
        return
    
    strategies = [
        ('分数SMA交叉策略', FractionalSmaCrossStrategy, {'printlog': True}),
        ('定投策略', SimplePercentageStrategy, {'daily_investment': 500, 'printlog': True}),  # 增加定投金额
    ]
    
    results = {}
    
    for strategy_name, strategy_class, strategy_params in strategies:
        print(f"\n📈 测试策略: {strategy_name}")
        print("-" * 50)
        
        # 创建Cerebro
        cerebro = bt.Cerebro()
        cerebro.addstrategy(strategy_class, **strategy_params)
        
        # 添加数据
        datafeed = bt.feeds.PandasData(dataname=data)
        cerebro.adddata(datafeed)
        
        # 设置初始资金和手续费
        cerebro.broker.setcash(10000.0)
        cerebro.broker.setcommission(commission=0.001)  # 0.1% 手续费
        
        # 添加分析器
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        
        # 运行回测
        print(f"初始资金: $10,000.00")
        start_value = cerebro.broker.getvalue()
        
        strategy_results = cerebro.run()
        
        end_value = cerebro.broker.getvalue()
        strategy_instance = strategy_results[0]
        
        # 计算结果
        return_pct = (end_value - start_value) / start_value * 100
        
        # 获取分析器结果
        try:
            sharpe_analysis = strategy_instance.analyzers.sharpe.get_analysis()
            sharpe = sharpe_analysis.get('sharperatio', 0) if sharpe_analysis else 0
            
            drawdown = strategy_instance.analyzers.drawdown.get_analysis()
            max_drawdown = drawdown.get('max', {}).get('drawdown', 0) if drawdown else 0
            
            trades = strategy_instance.analyzers.trades.get_analysis()
            total_trades = trades.get('total', {}).get('total', 0) if trades else 0
            won_trades = trades.get('won', {}).get('total', 0) if trades else 0
            win_rate = won_trades / total_trades * 100 if total_trades > 0 else 0
            
        except Exception as e:
            print(f"分析器错误: {e}")
            sharpe = 0
            max_drawdown = 0
            total_trades = 0
            won_trades = 0
            win_rate = 0
        
        # 确保数值不为None
        sharpe = sharpe if sharpe is not None else 0
        max_drawdown = max_drawdown if max_drawdown is not None else 0
        
        # 输出结果
        print(f"期末资金: ${end_value:,.2f}")
        print(f"收益率: {return_pct:.2f}%")
        print(f"夏普比率: {sharpe:.3f}")
        print(f"最大回撤: {max_drawdown:.2f}%")
        print(f"交易次数: {total_trades}")
        print(f"胜率: {win_rate:.2f}%")
        
        # 保存结果
        results[strategy_name] = {
            'return_pct': return_pct,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'end_value': end_value
        }
    
    # 策略比较
    print("\n" + "=" * 80)
    print("📊 策略比较结果")
    print("=" * 80)
    
    if results:
        comparison_df = pd.DataFrame({
            name: {
                '收益率(%)': f"{result['return_pct']:.2f}",
                '期末资金($)': f"{result['end_value']:,.2f}",
                '交易次数': result['total_trades'],
                '胜率(%)': f"{result['win_rate']:.2f}",
                '夏普比率': f"{result['sharpe_ratio']:.3f}",
                '最大回撤(%)': f"{result['max_drawdown']:.2f}"
            }
            for name, result in results.items()
        })
        
        print(comparison_df.T)
        
        # 找出最佳策略
        if any(r['total_trades'] > 0 for r in results.values()):
            best_strategy = max([k for k, v in results.items() if v['total_trades'] > 0], 
                              key=lambda x: results[x]['return_pct'])
            best_return = results[best_strategy]['return_pct']
            
            print(f"\n🏆 最佳策略: {best_strategy}")
            print(f"   收益率: {best_return:.2f}%")
            print(f"   期末资金: ${results[best_strategy]['end_value']:,.2f}")
            print(f"   交易次数: {results[best_strategy]['total_trades']}")
        else:
            print("\n⚠️ 所有策略都没有产生交易")
    
    return results


def main():
    """主函数"""
    try:
        results = run_fractional_backtest()
        print(f"\n✅ 回测完成！")
        
        if results and any(r['total_trades'] > 0 for r in results.values()):
            print("💡 成功演示: datafeed引擎数据在BackTrader中产生了实际交易！")
            print("🎯 这证明了数据引擎与BackTrader的完美集成！")
        else:
            print("ℹ️ 没有交易发生，但数据加载和策略执行正常")
        
    except Exception as e:
        print(f"❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
