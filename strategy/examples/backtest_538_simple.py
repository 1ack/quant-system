#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
国发股份 (600538) 简单回测策略 - 独立版本

策略：双均线交叉
- 金叉（短均线上穿长均线）：买入
- 死叉（短均线下穿长均线）：卖出
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import pandas as pd
from clickhouse_driver import Client

print("=" * 70)
print("国发股份 (600538) 策略回测 - 双均线交叉")
print("=" * 70)

# 连接 ClickHouse
client = Client(host='localhost', database='quant')

# 获取最近 2 个月数据
cutoff_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
result = client.execute(f"""
    SELECT date, open, high, low, close, volume, amount
    FROM kline_daily
    WHERE code = '600538' AND date >= '{cutoff_date}'
    ORDER BY date
""")

if not result:
    print("❌ 未找到数据")
    sys.exit(1)

# 转换为 DataFrame
df = pd.DataFrame(result, columns=['date', 'open', 'high', 'low', 'close', 'volume', 'amount'])
print(f"\n📊 数据范围：{df['date'].min()} 至 {df['date'].max()}")
print(f"   数据条数：{len(df)} 个交易日")

# 策略参数
SHORT_WINDOW = 5   # 短周期均线
LONG_WINDOW = 20   # 长周期均线
INITIAL_CAPITAL = 100000  # 初始资金 10 万
COMMISSION_RATE = 0.0003  # 万三手续费

# 计算均线
df['short_ma'] = df['close'].rolling(window=SHORT_WINDOW).mean()
df['long_ma'] = df['close'].rolling(window=LONG_WINDOW).mean()
df['ma_diff'] = df['short_ma'] - df['long_ma']
df['ma_diff_prev'] = df['ma_diff'].shift(1)

# 回测变量
capital = INITIAL_CAPITAL  # 可用资金
position = 0  # 持仓股数
avg_cost = 0  # 持仓成本
trades = []  # 交易记录
daily_values = []  # 每日净值

print(f"\n💰 初始资金：{INITIAL_CAPITAL:,.2f} 元")
print(f"📈 策略参数：{SHORT_WINDOW}日均线 / {LONG_WINDOW}日均线")
print("\n" + "-" * 70)

# 逐日回测
for i in range(1, len(df)):
    row = df.iloc[i]
    prev_row = df.iloc[i - 1]
    
    # 跳过数据不足
    if pd.isna(row['short_ma']) or pd.isna(row['long_ma']):
        daily_values.append({
            'date': row['date'],
            'capital': capital,
            'position_value': position * row['close'],
            'total_value': capital + position * row['close'],
        })
        continue
    
    date = row['date']
    price = row['close']
    
    # 检测金叉（买入信号）
    if prev_row['ma_diff'] < 0 and row['ma_diff'] > 0 and position == 0:
        # 全仓买入
        buy_volume = int(capital * 0.95 / price / 100) * 100  # 95% 仓位，100 股整数倍
        if buy_volume >= 100:
            cost = buy_volume * price * (1 + COMMISSION_RATE)
            if cost <= capital:
                capital -= cost
                position = buy_volume
                avg_cost = price
                trades.append({
                    'date': date,
                    'type': 'BUY',
                    'price': price,
                    'volume': buy_volume,
                    'commission': buy_volume * price * COMMISSION_RATE,
                })
                print(f"🟢 {date.strftime('%Y-%m-%d')} 买入 {buy_volume:6d}股 @ {price:6.2f}元 (金叉)")
    
    # 检测死叉（卖出信号）
    elif prev_row['ma_diff'] > 0 and row['ma_diff'] < 0 and position > 0:
        # 全部卖出
        revenue = position * price * (1 - COMMISSION_RATE)
        capital += revenue
        trades.append({
            'date': date,
            'type': 'SELL',
            'price': price,
            'volume': position,
            'commission': position * price * COMMISSION_RATE,
        })
        print(f"🔴 {date.strftime('%Y-%m-%d')} 卖出 {position:6d}股 @ {price:6.2f}元 (死叉)")
        position = 0
        avg_cost = 0
    
    # 记录每日净值
    daily_values.append({
        'date': date,
        'capital': capital,
        'position_value': position * row['close'],
        'total_value': capital + position * row['close'],
    })

# 如果还有持仓，按最后价格计算
if position > 0:
    final_price = df.iloc[-1]['close']
    position_value = position * final_price
    print(f"\n⚠️  回测结束仍有持仓：{position}股 @ {final_price:.2f}元 = {position_value:,.2f}元")

# 计算最终结果
final_value = capital + position * df.iloc[-1]['close']
total_return = (final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL

# 计算净值曲线
dv = pd.DataFrame(daily_values)
dv['daily_return'] = dv['total_value'].pct_change()
sharpe = (dv['daily_return'].mean() / dv['daily_return'].std()) * (252 ** 0.5) if len(dv) > 10 else 0

# 计算最大回撤
dv['cummax'] = dv['total_value'].cummax()
dv['drawdown'] = (dv['total_value'] - dv['cummax']) / dv['cummax']
max_drawdown = dv['drawdown'].min()

# 输出结果
print("\n" + "=" * 70)
print("📊 回测结果")
print("=" * 70)
print(f"初始资金：     {INITIAL_CAPITAL:>15,.2f} 元")
print(f"最终资产：     {final_value:>15,.2f} 元")
print(f"总收益率：     {total_return:>14.2f}%")
print(f"夏普比率：     {sharpe:>15.2f}")
print(f"最大回撤：     {max_drawdown:>13.2f}%")
print(f"交易次数：     {len(trades):>15} 笔")
print("=" * 70)

# 保存结果
output_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'backtest_538_result.csv')
dv.to_csv(output_path, index=False)
print(f"\n💾 详细结果已保存：{output_path}")

# 生成图表
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
fig.suptitle('600538 国发股份 - 双均线策略回测 (近 2 个月)', fontsize=16, fontweight='bold')

# 上图：价格和均线
ax1.plot(df['date'], df['close'], linewidth=1.5, color='#333', label='Close Price', alpha=0.7)
ax1.plot(df['date'], df['short_ma'], linewidth=1.5, color='#FF6B6B', label=f'{SHORT_WINDOW}-day MA')
ax1.plot(df['date'], df['long_ma'], linewidth=1.5, color='#4ECDC4', label=f'{LONG_WINDOW}-day MA')

# 标记买卖点
buy_dates = [t['date'] for t in trades if t['type'] == 'BUY']
buy_prices = [t['price'] for t in trades if t['type'] == 'BUY']
sell_dates = [t['date'] for t in trades if t['type'] == 'SELL']
sell_prices = [t['price'] for t in trades if t['type'] == 'SELL']

if buy_dates:
    ax1.scatter(buy_dates, buy_prices, marker='^', color='red', s=150, zorder=5, label='Buy')
if sell_dates:
    ax1.scatter(sell_dates, sell_prices, marker='v', color='green', s=150, zorder=5, label='Sell')

ax1.set_ylabel('Price (CNY)', fontsize=12)
ax1.set_title('Price & Moving Averages', fontsize=14)
ax1.legend(loc='upper left')
ax1.grid(True, alpha=0.3)

# 下图：净值曲线
ax2.plot(dv['date'], dv['total_value'], linewidth=2, color='#2196F3', label='Portfolio Value')
ax2.fill_between(dv['date'], dv['total_value'], INITIAL_CAPITAL, 
                 where=(dv['total_value'] >= INITIAL_CAPITAL), 
                 interpolate=True, color='green', alpha=0.3, label='Profit')
ax2.fill_between(dv['date'], dv['total_value'], INITIAL_CAPITAL, 
                 where=(dv['total_value'] < INITIAL_CAPITAL), 
                 interpolate=True, color='red', alpha=0.3, label='Loss')

ax2.axhline(y=INITIAL_CAPITAL, color='gray', linestyle='--', linewidth=1, alpha=0.5)
ax2.set_ylabel('Portfolio Value (CNY)', fontsize=12)
ax2.set_xlabel('Date', fontsize=12)
ax2.legend(loc='upper left')
ax2.grid(True, alpha=0.3)

# 格式化日期
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

plt.tight_layout()

# 保存图表
chart_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'backtest_538_chart.png')
plt.savefig(chart_path, dpi=150, bbox_inches='tight')
print(f"📈 回测图表已保存：{chart_path}")

print("\n✅ 回测完成！")
