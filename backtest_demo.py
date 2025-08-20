#!/usr/bin/env python3
"""
BackTrader 回测程序演示
从DataFeed引擎数据库导入数据进行回测
"""

import sys
import os
import pandas as pd
import backtrader as bt
from datetime import datetime, timedelta

# 添加datafeed_engine到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from datafeed_engine import DataFeedEngine


class SmaCross(bt.SignalStrategy):
    """SMA交叉策略"""
    
    params = (
        ('sma1_period', 10),
        ('sma2_period', 30),
    )
    
    def __init__(self):
        # 创建移动平均线指标
        sma1 = bt.ind.SMA(period=self.params.sma1_period)
        sma2 = bt.ind.SMA(period=self.params.sma2_period)
        
        # 创建交叉信号
        crossover = bt.ind.CrossOver(sma1, sma2)
        
        # 添加信号
        self.signal_add(bt.SIGNAL_LONG, crossover)


class DatabaseDataFeed(bt.feeds.PandasData):
    """
    自定义数据源，从数据库读取数据
    """
    
    # 定义数据列映射
    params = (
        ('datetime', None),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('openinterest', None),
    )


def load_data_from_database(symbol='BTC/USDT', exchange='okx', timeframe='1h', 
                          start_date=None, end_date=None, config_path='datafeed_engine/config.ini'):
    """
    从DataFeed引擎数据库加载数据
    
    Args:
        symbol: 交易对符号
        exchange: 交易所
        timeframe: 时间周期
        start_date: 开始日期
        end_date: 结束日期
        config_path: 配置文件路径
        
    Returns:
        pandas.DataFrame: OHLCV数据
    """
    print(f"📊 从数据库加载数据: {exchange} {symbol} {timeframe}")
    
    try:
        # 初始化DataFeed引擎
        engine = DataFeedEngine(config_path=config_path)
        
        # 从数据库获取数据
        data = engine.get_data(
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
            start_time=start_date,
            end_time=end_date
        )
        
        if data.empty:
            print(f"❌ 没有找到数据: {exchange} {symbol} {timeframe}")
            return None
        
        print(f"✅ 成功加载 {len(data)} 条数据")
        print(f"时间范围: {data.index.min()} 到 {data.index.max()}")
        print(f"价格范围: ${data['close'].min():.2f} - ${data['close'].max():.2f}")
        
        return data
        
    except Exception as e:
        print(f"❌ 加载数据失败: {e}")
        return None


def run_backtest(symbol='BTC/USDT', exchange='okx', timeframe='1h', 
                start_date=None, end_date=None, initial_cash=10000.0,
                commission=0.001, config_path='datafeed_engine/config.ini'):
    """
    运行回测
    
    Args:
        symbol: 交易对符号
        exchange: 交易所
        timeframe: 时间周期
        start_date: 开始日期
        end_date: 结束日期
        initial_cash: 初始资金
        commission: 手续费率
        config_path: 配置文件路径
    """
    print("=" * 60)
    print("🚀 BackTrader 回测程序")
    print("=" * 60)
    
    # 1. 从数据库加载数据
    data = load_data_from_database(
        symbol=symbol,
        exchange=exchange,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        config_path=config_path
    )
    
    if data is None:
        print("❌ 无法加载数据，退出回测")
        return
    
    # 2. 创建Cerebro引擎
    cerebro = bt.Cerebro()
    
    # 3. 添加策略
    cerebro.addstrategy(SmaCross)
    
    # 4. 添加数据源
    datafeed = DatabaseDataFeed(dataname=data)
    cerebro.adddata(datafeed, name=f"{symbol}")
    
    # 5. 设置初始资金
    cerebro.broker.setcash(initial_cash)
    
    # 6. 设置手续费
    cerebro.broker.setcommission(commission=commission)
    
    # 7. 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    
    # 8. 添加观察器
    cerebro.addobserver(bt.observers.BuySell)
    cerebro.addobserver(bt.observers.Value)
    
    print(f"\n📈 回测配置:")
    print(f"交易对: {symbol}")
    print(f"交易所: {exchange}")
    print(f"时间周期: {timeframe}")
    print(f"数据条数: {len(data)}")
    print(f"初始资金: ${initial_cash:,.2f}")
    print(f"手续费率: {commission:.3%}")
    
    # 9. 运行回测
    print(f"\n🔄 开始回测...")
    start_value = cerebro.broker.getvalue()
    
    results = cerebro.run()
    
    # 10. 输出回测结果
    end_value = cerebro.broker.getvalue()
    
    print("\n" + "=" * 60)
    print("📊 回测结果")
    print("=" * 60)
    
    print(f"初始资金: ${start_value:,.2f}")
    print(f"期末资金: ${end_value:,.2f}")
    print(f"总收益: ${end_value - start_value:,.2f}")
    print(f"收益率: {(end_value - start_value) / start_value:.2%}")
    
    # 分析器结果
    strategy = results[0]
    
    # 夏普比率
    if hasattr(strategy.analyzers.sharpe, 'get_analysis'):
        sharpe_ratio = strategy.analyzers.sharpe.get_analysis().get('sharperatio', 0)
        print(f"夏普比率: {sharpe_ratio:.3f}" if sharpe_ratio else "夏普比率: N/A")
    
    # 最大回撤
    if hasattr(strategy.analyzers.drawdown, 'get_analysis'):
        drawdown = strategy.analyzers.drawdown.get_analysis()
        max_drawdown = drawdown.get('max', {}).get('drawdown', 0)
        print(f"最大回撤: {max_drawdown:.2%}")
    
    # 交易分析
    if hasattr(strategy.analyzers.trades, 'get_analysis'):
        trades = strategy.analyzers.trades.get_analysis()
        total_trades = trades.get('total', {}).get('total', 0)
        won_trades = trades.get('won', {}).get('total', 0)
        lost_trades = trades.get('lost', {}).get('total', 0)
        
        print(f"总交易次数: {total_trades}")
        print(f"盈利交易: {won_trades}")
        print(f"亏损交易: {lost_trades}")
        if total_trades > 0:
            win_rate = won_trades / total_trades
            print(f"胜率: {win_rate:.2%}")
    
    return cerebro, results


def plot_results(cerebro, title="BackTrader 回测结果"):
    """
    绘制回测结果图表
    
    Args:
        cerebro: BackTrader Cerebro实例
        title: 图表标题
    """
    try:
        print(f"\n📈 绘制回测图表...")
        cerebro.plot(
            style='candlestick',
            barup='green',
            bardown='red',
            volume=False,
            title=title
        )
        print("✅ 图表显示完成")
    except Exception as e:
        print(f"⚠️ 无法显示图表: {e}")
        print("提示: 需要安装matplotlib库: pip install matplotlib")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='BackTrader 回测程序')
    parser.add_argument('--symbol', default='BTC/USDT', help='交易对符号')
    parser.add_argument('--exchange', default='okx', help='交易所')
    parser.add_argument('--timeframe', default='1h', help='时间周期')
    parser.add_argument('--days', type=int, default=30, help='回测天数')
    parser.add_argument('--cash', type=float, default=10000.0, help='初始资金')
    parser.add_argument('--commission', type=float, default=0.001, help='手续费率')
    parser.add_argument('--plot', action='store_true', help='显示图表')
    parser.add_argument('--config', default='datafeed_engine/config.ini', help='配置文件路径')
    
    args = parser.parse_args()
    
    # 计算开始日期
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)
    
    # 运行回测
    cerebro, results = run_backtest(
        symbol=args.symbol,
        exchange=args.exchange,
        timeframe=args.timeframe,
        start_date=start_date,
        end_date=end_date,
        initial_cash=args.cash,
        commission=args.commission,
        config_path=args.config
    )
    
    # 显示图表
    if args.plot and cerebro and results:
        plot_results(cerebro, f"{args.symbol} - {args.timeframe}")
    
    print(f"\n✅ 回测完成！")


if __name__ == "__main__":
    # 示例运行
    if len(sys.argv) == 1:
        print("🔄 运行默认回测示例...")
        print("使用参数: BTC/USDT, okx, 1h, 30天")
        print("如需自定义参数，请使用 --help 查看选项")
        print("-" * 60)
        
        # 默认参数回测
        cerebro, results = run_backtest(
            symbol='BTC/USDT',
            exchange='okx',
            timeframe='1h',
            start_date=datetime.now() - timedelta(days=7),  # 最近7天
            end_date=datetime.now(),
            initial_cash=10000.0,
            commission=0.001
        )
        
        if cerebro and results:
            try:
                plot_results(cerebro, "BTC/USDT - 1小时 SMA交叉策略")
            except:
                print("⚠️ 跳过图表显示")
    else:
        main()
