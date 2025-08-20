# DataFeed Engine 命令行使用指南

DataFeed Engine 现在支持命令行操作，可以直接通过命令行管理数据获取和查看统计信息。

## 🚀 快速开始

### 查看数据库统计信息
```bash
python datafeed_engine/engine.py --action stats
```

### 获取指定交易对数据
```bash
# 获取AAPL股票数据（3天）
python datafeed_engine/engine.py --action fetch --symbol AAPL --exchange yahoo --timeframe 1d --days 3

# 获取BTC/USDT加密货币数据（7天）
python datafeed_engine/engine.py --action fetch --symbol BTC/USDT --exchange okx --timeframe 1h --days 7

# 获取A股数据
python datafeed_engine/engine.py --action fetch --symbol 000001.SZ --exchange tushare --timeframe 1d --days 30
```

### 获取所有配置的数据
```bash
python datafeed_engine/engine.py --action fetch
```

### 启动定时任务
```bash
python datafeed_engine/engine.py --action start
```

### 清理数据
```bash
# 清理所有数据
python datafeed_engine/engine.py --action clear

# 清理指定交易对数据
python datafeed_engine/engine.py --action clear --symbol BTC/USDT --exchange okx --timeframe 1h
```

## 📋 命令参数说明

### 必需参数
- `--action`: 执行的操作
  - `stats`: 显示数据库统计信息
  - `fetch`: 获取数据
  - `clear`: 清理数据  
  - `start`: 启动定时任务

### 可选参数
- `--config`: 配置文件路径（默认：datafeed_engine/config.ini）
- `--db`: 数据库文件路径（默认：market_data.db）
- `--symbol`: 交易对符号（如：BTC/USDT、AAPL、000001.SZ）
- `--exchange`: 交易所（okx、binance、yahoo、tushare）
- `--timeframe`: 时间周期（1m、5m、15m、30m、1h、2h、1d）
- `--days`: 获取多少天的数据（默认：7天）

## 💡 使用示例

### 1. 首次使用 - 查看状态
```bash
python datafeed_engine/engine.py --action stats
```
输出示例：
```
📊 DataFeed Engine 数据库统计
==================================================
数据库路径: E:\python\bt\backtrader\market_data.db
数据库大小: 24.00 KB
总记录数: 0
💡 数据库为空，使用 --action fetch 开始获取数据
```

### 2. 获取历史数据
```bash
# 获取7天的比特币小时线数据
python datafeed_engine/engine.py --action fetch --symbol BTC/USDT --exchange okx --timeframe 1h --days 7
```

### 3. 查看获取结果
```bash
python datafeed_engine/engine.py --action stats
```
输出示例：
```
📊 DataFeed Engine 数据库统计
==================================================
数据库路径: E:\python\bt\backtrader\market_data.db
数据库大小: 256.50 KB
总记录数: 1,680

📈 按交易所分布:
  okx: 1,680 条记录

⏱️ 按时间周期分布:
  1h: 1,680 条记录

🔥 热门交易对 (前10):
  BTC/USDT: 1,680 条记录
```

### 4. 启动自动化定时任务
```bash
python datafeed_engine/engine.py --action start
```

## ⚠️ 注意事项

1. **API限制**：各数据源都有API调用频率限制
   - Yahoo Finance: 可能遇到"Too Many Requests"
   - OKX/Binance: 需要稳定的网络连接和正确的API密钥
   - Tushare: 需要有效的token

2. **网络问题**：
   - 如遇到连接问题，检查代理设置（config.ini中的proxy配置）
   - 确保防火墙允许Python访问网络

3. **配置文件**：
   - 确保config.ini文件包含正确的API密钥
   - 敏感信息受.gitignore保护，不会被提交到git

4. **数据库**：
   - SQLite数据库文件默认创建在当前工作目录
   - 可通过--db参数指定其他位置

## 🔧 故障排除

### 导入错误
如果遇到导入错误，确保从正确的目录运行：
```bash
# ✅ 正确：从backtrader根目录运行
cd /path/to/backtrader
python datafeed_engine/engine.py --action stats

# ❌ 错误：直接在datafeed_engine目录运行
cd datafeed_engine
python engine.py --action stats  # 会出现导入错误
```

### 配置文件找不到
指定完整的配置文件路径：
```bash
python datafeed_engine/engine.py --action stats --config /path/to/your/config.ini
```

### 网络连接问题
检查config.ini中的代理设置：
```ini
[OKX]
proxy = 127.0.0.1:3067

[PROXY]
http_proxy = 127.0.0.1:3067
https_proxy = 127.0.0.1:3067
```
