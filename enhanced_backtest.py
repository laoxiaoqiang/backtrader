#!/usr/bin/env python3
"""
增强版回测演示 - 更敏感的策略和更多交易信号
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


class QuickSmaCrossStrategy(bt.Strategy):
    """快速SMA交叉策略 - 更短周期产生更多信号"""
    
    params = (
        ('sma1_period', 5),   # 更短的快线
        ('sma2_period', 15),  # 更短的慢线
        ('printlog', True),
    )
    
    def __init__(self):
        self.sma1 = bt.ind.SMA(period=self.params.sma1_period)
        self.sma2 = bt.ind.SMA(period=self.params.sma2_period)
        self.crossover = bt.ind.CrossOver(self.sma1, self.sma2)
        self.trade_count = 0
    
    def next(self):
        if not self.position:
            if self.crossover > 0:  # 金叉 - 买入信号
                cash = self.broker.cash
                price = self.data.close[0]
                size = int(cash * 0.95 / price)  # 使用95%资金
                if size > 0:  # 确保有足够资金买入
                    self.buy(size=size)
                    self.trade_count += 1
                    if self.params.printlog:
                        self.log(f'🟢 买入 - 价格: ${price:,.2f}, 数量: {size}, 成本: ${size*price:,.2f}')
                else:
                    if self.params.printlog:
                        self.log(f'⚠️ 资金不足 - 价格: ${price:,.2f}, 可用资金: ${cash:,.2f}')
        else:
            if self.crossover < 0:  # 死叉 - 卖出信号
                self.close()
                if self.params.printlog:
                    self.log(f'🔴 卖出 - 价格: ${self.data.close[0]:,.2f}')
    
    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}: {txt}')
    
    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'💰 交易完成 - 盈亏: ${trade.pnlcomm:,.2f}')


class MomentumStrategy(bt.Strategy):
    """动量策略 - 基于价格变化率"""
    
    params = (
        ('momentum_period', 10),
        ('threshold', 0.02),  # 2%的阈值
        ('printlog', False),
    )
    
    def __init__(self):
        self.momentum = bt.ind.Momentum(period=self.params.momentum_period)
        self.momentum_pct = self.momentum / self.data.close(-self.params.momentum_period)
        self.trade_count = 0
    
    def next(self):
        if not self.position:
            if self.momentum_pct > self.params.threshold:  # 上涨动量强 - 买入
                cash = self.broker.cash
                price = self.data.close[0]
                size = int(cash * 0.95 / price)
                if size > 0:
                    self.buy(size=size)
                    self.trade_count += 1
        else:
            if self.momentum_pct < -self.params.threshold:  # 下跌动量强 - 卖出
                self.close()


class BollingerStrategy(bt.Strategy):
    """布林带策略 - 均值回归"""
    
    params = (
        ('period', 20),
        ('devfactor', 2.0),
        ('printlog', False),
    )
    
    def __init__(self):
        self.boll = bt.ind.BollingerBands(period=self.params.period, devfactor=self.params.devfactor)
        self.trade_count = 0
    
    def next(self):
        if not self.position:
            if self.data.close[0] < self.boll.lines.bot[0]:  # 价格跌破下轨 - 买入
                cash = self.broker.cash
                price = self.data.close[0]
                size = int(cash * 0.95 / price)
                if size > 0:
                    self.buy(size=size)
                    self.trade_count += 1
        else:
            if self.data.close[0] > self.boll.lines.top[0]:  # 价格突破上轨 - 卖出
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
        print(f"价格范围: ${data['close'].min():,.2f} - ${data['close'].max():,.2f}")
        
        return data
        
    except Exception as e:
        print(f"❌ 加载数据失败: {e}")
        return None


def run_enhanced_backtest():
    """运行增强版回测"""
    print("=" * 80)
    print("🚀 增强版BackTrader回测演示")
    print("=" * 80)
    
    # 加载更长时间的数据
    data = load_data_from_database(symbol='BTC/USDT', exchange='okx', timeframe='1h', days=30)
    if data is None:
        return
    
    strategies = [
        ('快速SMA交叉', QuickSmaCrossStrategy),
        ('动量策略', MomentumStrategy),
        ('布林带策略', BollingerStrategy),
    ]
    
    results = {}
    
    for strategy_name, strategy_class in strategies:
        print(f"\n📈 测试策略: {strategy_name}")
        print("-" * 50)
        
        # 创建Cerebro
        cerebro = bt.Cerebro()
        
        # 添加策略
        strat_params = {}
        if strategy_name == '快速SMA交叉':
            strat_params['printlog'] = True
        else:
            strat_params['printlog'] = False
        
        cerebro.addstrategy(strategy_class, **strat_params)
        
        # 添加数据
        datafeed = bt.feeds.PandasData(dataname=data)
        cerebro.adddata(datafeed)
        
        # 设置初始资金和手续费
        cerebro.broker.setcash(1000000.0)
        cerebro.broker.setcommission(commission=0.001)  # 0.1% 手续费
        
        # 添加分析器
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        
        # 运行回测
        print(f"初始资金: $1,000,000.00")
        start_value = cerebro.broker.getvalue()
        
        strategy_results = cerebro.run()
        
        end_value = cerebro.broker.getvalue()
        strategy_instance = strategy_results[0]
        
        # 计算结果
        return_pct = (end_value - start_value) / start_value * 100
        
        # 获取分析器结果
        try:
            sharpe = strategy_instance.analyzers.sharpe.get_analysis().get('sharperatio', 0)
            drawdown = strategy_instance.analyzers.drawdown.get_analysis()
            trades = strategy_instance.analyzers.trades.get_analysis()
            
            max_drawdown = drawdown.get('max', {}).get('drawdown', 0)
            total_trades = trades.get('total', {}).get('total', 0)
            won_trades = trades.get('won', {}).get('total', 0)
            win_rate = won_trades / total_trades * 100 if total_trades > 0 else 0
            
        except:
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
                '夏普比率': f"{result['sharpe_ratio']:.3f}",
                '最大回撤(%)': f"{result['max_drawdown']:.2f}",
                '交易次数': result['total_trades'],
                '胜率(%)': f"{result['win_rate']:.2f}",
                '期末资金($)': f"{result['end_value']:,.2f}"
            }
            for name, result in results.items()
        })
        
        print(comparison_df.T)
        
        # 找出最佳策略
        best_strategy = max(results.keys(), key=lambda x: results[x]['return_pct'])
        best_return = results[best_strategy]['return_pct']
        
        print(f"\n🏆 最佳策略: {best_strategy}")
        print(f"   收益率: {best_return:.2f}%")
        print(f"   期末资金: ${results[best_strategy]['end_value']:,.2f}")
    
    return results


def main():
    """主函数"""
    try:
        results = run_enhanced_backtest()
        print(f"\n✅ 回测完成！")
        
        if results and any(r['total_trades'] > 0 for r in results.values()):
            print("💡 提示: 策略产生了交易信号，说明datafeed引擎与BackTrader集成成功！")
        else:
            print("⚠️ 注意: 所有策略都没有产生交易信号，可能需要调整参数或使用更长的数据周期")
        
    except Exception as e:
        print(f"❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
