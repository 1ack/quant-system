#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
长江电力 (600900) 双策略回测

策略 1: 布林带均值回归策略
策略 2: MACD 趋势跟踪策略
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from clickhouse_driver import Client
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

print("=" * 70)
print("长江电力 (600900) 双策略回测")
print("=" * 70)

# 连接 ClickHouse
client = Client(host='localhost', database='quant')

# 获取最近 2 个月数据
cutoff_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
result = client.execute(f"""
    SELECT date, open, high, low, close, volume, amount
    FROM kline_daily
    WHERE code = '600900' AND date >= '{cutoff_date}'
    ORDER BY date
""")

if not result:
    print(f"❌ 未找到长江电力 (600900) 的数据")
    print(f"   请确认数据已下载")
    sys.exit(1)

# 转换为 DataFrame
df = pd.DataFrame(result, columns=['date', 'open', 'high', 'low', 'close', 'volume', 'amount'])
print(f"\n📊 数据范围：{df['date'].min()} 至 {df['date'].max()}")
print(f"   数据条数：{len(df)} 个交易日")

# 回测配置
INITIAL_CAPITAL = 100000  # 10 万本金
COMMISSION_RATE = 0.0003  # 万三手续费


def backtest_bollinger(df, period=10, num_std=1.5):
    """
    策略 1: 布林带均值回归策略（宽松参数）
    
    逻辑:
    - 价格跌破下轨：买入（超卖）
    - 价格突破上轨：卖出（超买）
    
    长江电力波动小，使用更敏感的参数
    """
    data = df.copy()
    
    # 计算布林带
    data['ma'] = data['close'].rolling(window=period).mean()
    data['std'] = data['close'].rolling(window=period).std()
    data['upper'] = data['ma'] + num_std * data['std']
    data['lower'] = data['ma'] - num_std * data['std']
    
    # 回测变量
    capital = INITIAL_CAPITAL
    position = 0
    trades = []
    daily_values = []
    
    for i in range(period, len(data)):
        row = data.iloc[i]
        price = row['close']
        date = row['date']
        
        # 价格跌破下轨：买入
        if row['low'] < row['lower'] and position == 0:
            buy_volume = int(capital * 0.95 / price / 100) * 100
            if buy_volume >= 100:
                cost = buy_volume * price * (1 + COMMISSION_RATE)
                if cost <= capital:
                    capital -= cost
                    position = buy_volume
                    trades.append({
                        'date': date, 'type': 'BUY', 'price': price,
                        'volume': buy_volume, 'signal': 'Lower Break'
                    })
        
        # 价格突破上轨：卖出
        elif row['high'] > row['upper'] and position > 0:
            revenue = position * price * (1 - COMMISSION_RATE)
            capital += revenue
            trades.append({
                'date': date, 'type': 'SELL', 'price': price,
                'volume': position, 'signal': 'Upper Break'
            })
            position = 0
        
        # 记录净值
        daily_values.append({
            'date': date,
            'total_value': capital + position * price,
            'capital': capital,
            'position_value': position * price,
        })
    
    # 计算绩效
    dv = pd.DataFrame(daily_values)
    if len(dv) == 0:
        return None
    
    final_value = dv['total_value'].iloc[-1]
    total_return = (final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL
    dv['daily_return'] = dv['total_value'].pct_change()
    sharpe = (dv['daily_return'].mean() / dv['daily_return'].std()) * np.sqrt(252) if len(dv) > 10 else 0
    dv['cummax'] = dv['total_value'].cummax()
    dv['drawdown'] = (dv['total_value'] - dv['cummax']) / dv['cummax']
    max_drawdown = dv['drawdown'].min()
    
    return {
        'name': '布林带均值回归',
        'final_value': final_value,
        'total_return': total_return,
        'sharpe': sharpe,
        'max_drawdown': max_drawdown,
        'trades': len(trades),
        'trade_details': trades,
        'daily_values': dv,
    }


def backtest_macd(df, fast=12, slow=26, signal=9):
    """
    策略 2: MACD 趋势跟踪策略
    
    逻辑:
    - DIF 上穿 DEA（金叉）：买入
    - DIF 下穿 DEA（死叉）：卖出
    """
    data = df.copy()
    
    # 计算 MACD
    exp1 = data['close'].ewm(span=fast, adjust=False).mean()
    exp2 = data['close'].ewm(span=slow, adjust=False).mean()
    data['dif'] = exp1 - exp2
    data['dea'] = data['dif'].ewm(span=signal, adjust=False).mean()
    data['macd'] = (data['dif'] - data['dea']) * 2
    data['dif_prev'] = data['dif'].shift(1)
    data['dea_prev'] = data['dea'].shift(1)
    
    # 回测变量
    capital = INITIAL_CAPITAL
    position = 0
    trades = []
    daily_values = []
    
    start_idx = max(fast, slow, signal) * 2
    
    for i in range(start_idx, len(data)):
        row = data.iloc[i]
        prev_row = data.iloc[i - 1]
        price = row['close']
        date = row['date']
        
        if pd.isna(row['dif']) or pd.isna(row['dea']):
            continue
        
        # 金叉：买入
        if prev_row['dif'] < prev_row['dea'] and row['dif'] > row['dea'] and position == 0:
            buy_volume = int(capital * 0.95 / price / 100) * 100
            if buy_volume >= 100:
                cost = buy_volume * price * (1 + COMMISSION_RATE)
                if cost <= capital:
                    capital -= cost
                    position = buy_volume
                    trades.append({
                        'date': date, 'type': 'BUY', 'price': price,
                        'volume': buy_volume, 'signal': 'Golden Cross'
                    })
        
        # 死叉：卖出
        elif prev_row['dif'] > prev_row['dea'] and row['dif'] < row['dea'] and position > 0:
            revenue = position * price * (1 - COMMISSION_RATE)
            capital += revenue
            trades.append({
                'date': date, 'type': 'SELL', 'price': price,
                'volume': position, 'signal': 'Death Cross'
            })
            position = 0
        
        # 记录净值
        daily_values.append({
            'date': date,
            'total_value': capital + position * price,
            'capital': capital,
            'position_value': position * price,
        })
    
    # 计算绩效
    dv = pd.DataFrame(daily_values)
    if len(dv) == 0:
        return None
    
    final_value = dv['total_value'].iloc[-1]
    total_return = (final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL
    dv['daily_return'] = dv['total_value'].pct_change()
    sharpe = (dv['daily_return'].mean() / dv['daily_return'].std()) * np.sqrt(252) if len(dv) > 10 else 0
    dv['cummax'] = dv['total_value'].cummax()
    dv['drawdown'] = (dv['total_value'] - dv['cummax']) / dv['cummax']
    max_drawdown = dv['drawdown'].min()
    
    return {
        'name': 'MACD 趋势跟踪',
        'final_value': final_value,
        'total_return': total_return,
        'sharpe': sharpe,
        'max_drawdown': max_drawdown,
        'trades': len(trades),
        'trade_details': trades,
        'daily_values': dv,
    }


# 运行回测
print("\n" + "=" * 70)
print("运行策略回测...")
print("=" * 70)

result_bollinger = backtest_bollinger(df, period=20, num_std=2)
result_macd = backtest_macd(df, fast=12, slow=26, signal=9)

# 输出结果
print("\n" + "=" * 70)
print("📊 回测结果对比")
print("=" * 70)

results = [result_bollinger, result_macd]
for r in results:
    if r:
        print(f"\n【{r['name']}】")
        print(f"  初始资金：     {INITIAL_CAPITAL:>12,.2f} 元")
        print(f"  最终资产：     {r['final_value']:>12,.2f} 元")
        print(f"  总收益率：     {r['total_return']*100:>11.2f}%")
        print(f"  夏普比率：     {r['sharpe']:>12.2f}")
        print(f"  最大回撤：     {r['max_drawdown']*100:>11.2f}%")
        print(f"  交易次数：     {r['trades']:>12} 笔")

# 生成对比图表
fig, axes = plt.subplots(3, 1, figsize=(16, 12))
fig.suptitle('600900 长江电力 - 双策略回测对比 (近 6 个月)', fontsize=16, fontweight='bold')

# 图 1: 价格走势 + 布林带
ax1 = axes[0]
ax1.plot(df['date'], df['close'], linewidth=1.5, color='#333', label='Close', alpha=0.7)

# 计算布林带用于绘图
df['ma'] = df['close'].rolling(window=20).mean()
df['std'] = df['close'].rolling(window=20).std()
df['upper'] = df['ma'] + 2 * df['std']
df['lower'] = df['ma'] - 2 * df['std']

ax1.plot(df['date'], df['ma'], linewidth=1.5, color='#FF6B6B', label='MA20')
ax1.fill_between(df['date'], df['upper'], df['lower'], alpha=0.2, color='#4ECDC4', label='Bollinger Band')

# 标记买卖点
if result_bollinger and result_bollinger['trade_details']:
    buy_dates = [t['date'] for t in result_bollinger['trade_details'] if t['type'] == 'BUY']
    buy_prices = [t['price'] for t in result_bollinger['trade_details'] if t['type'] == 'BUY']
    sell_dates = [t['date'] for t in result_bollinger['trade_details'] if t['type'] == 'SELL']
    sell_prices = [t['price'] for t in result_bollinger['trade_details'] if t['type'] == 'SELL']
    if buy_dates:
        ax1.scatter(buy_dates, buy_prices, marker='^', color='red', s=150, zorder=5, label='Buy')
    if sell_dates:
        ax1.scatter(sell_dates, sell_prices, marker='v', color='green', s=150, zorder=5, label='Sell')

ax1.set_ylabel('Price (CNY)', fontsize=12)
ax1.set_title('Strategy 1: Bollinger Bands Mean Reversion', fontsize=14)
ax1.legend(loc='upper left')
ax1.grid(True, alpha=0.3)

# 图 2: MACD
ax2 = axes[1]
ax2.plot(df['date'], df['dif'], linewidth=1.5, color='#FF6B6B', label='DIF')
ax2.plot(df['date'], df['dea'], linewidth=1.5, color='#4ECDC4', label='DEA')
ax2.bar(df['date'], df['macd'], color='gray', alpha=0.3, label='MACD')
ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
ax2.set_ylabel('MACD', fontsize=12)
ax2.set_title('Strategy 2: MACD Trend Following', fontsize=14)
ax2.legend(loc='upper left')
ax2.grid(True, alpha=0.3)

# 图 3: 净值曲线对比
ax3 = axes[2]
if result_bollinger:
    ax3.plot(result_bollinger['daily_values']['date'], 
             result_bollinger['daily_values']['total_value'],
             linewidth=2, color='#FF6B6B', label='Bollinger Strategy')
if result_macd:
    ax3.plot(result_macd['daily_values']['date'], 
             result_macd['daily_values']['total_value'],
             linewidth=2, color='#4ECDC4', label='MACD Strategy')
ax3.axhline(y=INITIAL_CAPITAL, color='gray', linestyle='--', linewidth=1, alpha=0.5, label='Initial Capital')
ax3.set_ylabel('Portfolio Value (CNY)', fontsize=12)
ax3.set_xlabel('Date', fontsize=12)
ax3.set_title('Portfolio Value Comparison', fontsize=14)
ax3.legend(loc='upper left')
ax3.grid(True, alpha=0.3)

# 格式化日期
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
ax3.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')

plt.tight_layout()

# 保存图表
chart_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'backtest_600900_comparison.png')
plt.savefig(chart_path, dpi=150, bbox_inches='tight')
print(f"\n💾 回测图表已保存：{chart_path}")

# 保存详细数据
if result_bollinger:
    bollinger_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'backtest_600900_bollinger.csv')
    result_bollinger['daily_values'].to_csv(bollinger_path, index=False)
    print(f"   布林带策略数据：{bollinger_path}")

if result_macd:
    macd_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'backtest_600900_macd.csv')
    result_macd['daily_values'].to_csv(macd_path, index=False)
    print(f"   MACD 策略数据：{macd_path}")

print("\n✅ 回测完成！")

# 输出结论
print("\n" + "=" * 70)
print("📌 策略结论")
print("=" * 70)

if result_bollinger and result_macd:
    if result_bollinger['total_return'] > result_macd['total_return']:
        better = "布林带均值回归策略"
        better_return = result_bollinger['total_return'] * 100
    else:
        better = "MACD 趋势跟踪策略"
        better_return = result_macd['total_return'] * 100
    
    print(f"\n🏆 表现更好的策略：{better}")
    print(f"   收益率：{better_return:.2f}%")
    
    print("\n💡 建议:")
    if result_bollinger['total_return'] > 0 or result_macd['total_return'] > 0:
        print("   - 长江电力适合趋势/震荡结合的策略")
        print("   - 可考虑将两个策略信号结合使用")
    else:
        print("   - 两个策略均亏损，长江电力近 6 个月可能处于震荡市")
        print("   - 建议尝试其他策略（如网格交易、定投策略）")
else:
    print("❌ 回测数据不足，无法得出结论")

print("=" * 70)
