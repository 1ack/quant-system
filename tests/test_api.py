#!/usr/bin/env python3
"""
测试量化回测系统 API
"""
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

# 策略代码示例（双均线策略）
STRATEGY_CODE = '''
from strategy.base import BaseStrategy, Signal, SignalType
import pandas as pd

class TestStrategy(BaseStrategy):
    """简单双均线策略"""
    
    def init(self, data: pd.DataFrame):
        """初始化"""
        self.ma5 = None
        self.ma10 = None
    
    def generate_signals(self, df: pd.DataFrame) -> list:
        """生成交易信号"""
        signals = []
        
        # 计算均线
        close = df["close"]
        ma5 = close.rolling(5).mean()
        ma10 = close.rolling(10).mean()
        
        if len(df) < 2:
            return signals
        
        code = df["code"].iloc[-1]
        date = df["date"].iloc[-1]
        price = close.iloc[-1]
        
        # 金叉买入
        if ma5.iloc[-1] > ma10.iloc[-1] and ma5.iloc[-2] <= ma10.iloc[-2]:
            signals.append(Signal(
                code=code,
                date=date,
                signal_type=SignalType.BUY,
                price=price,
            ))
        
        # 死叉卖出
        elif ma5.iloc[-1] < ma10.iloc[-1] and ma5.iloc[-2] >= ma10.iloc[-2]:
            signals.append(Signal(
                code=code,
                date=date,
                signal_type=SignalType.SELL,
                price=price,
            ))
        
        return signals
'''

def test_stocks_api():
    """测试股票列表 API"""
    print("\n=== 测试 GET /api/stocks ===")
    
    # 测试基本查询
    resp = requests.get(f"{BASE_URL}/api/stocks?limit=5")
    assert resp.status_code == 200
    stocks = resp.json()
    print(f"✓ 获取股票列表：{len(stocks)} 只")
    assert len(stocks) > 0
    assert "code" in stocks[0]
    assert "name" in stocks[0]
    
    # 测试搜索
    resp = requests.get(f"{BASE_URL}/api/stocks?q=600&limit=3")
    assert resp.status_code == 200
    stocks = resp.json()
    print(f"✓ 搜索股票 (q=600)：{len(stocks)} 只")
    assert all("600" in s["code"] for s in stocks)
    
    print("✅ 股票 API 测试通过\n")


def test_history_api():
    """测试历史数据 API"""
    print("=== 测试 GET /api/history/{code} ===")
    
    # 测试获取长江电力历史数据
    resp = requests.get(f"{BASE_URL}/api/history/600900?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    
    # API 返回格式：{code, period, candles}
    assert "code" in data
    assert "candles" in data
    assert data["code"] == "600900"
    
    klines = data["candles"]
    print(f"✓ 获取 600900 历史数据：{len(klines)} 条")
    assert len(klines) > 0
    assert "open" in klines[0]
    assert "close" in klines[0]
    
    print("✅ 历史数据 API 测试通过\n")


def test_backtest_api():
    """测试回测 API"""
    print("=== 测试 POST /api/backtest ===")
    
    # 准备回测请求（使用有充足数据的日期范围）
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2026, 3, 13)
    
    backtest_request = {
        "strategy_code": STRATEGY_CODE,
        "strategy_name": "TestMAStrategy",
        "strategy_params": {},
        "codes": ["600538"],  # 国发股份（有 1443 条数据）
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "initial_capital": 1000000.0,
        "commission_rate": 0.0003,
        "slippage_rate": 0.001,
    }
    
    # 创建回测任务
    resp = requests.post(f"{BASE_URL}/api/backtest", json=backtest_request)
    assert resp.status_code == 200
    result = resp.json()
    task_id = result["task_id"]
    print(f"✓ 创建回测任务：{task_id}")
    assert result["status"] == "running"
    
    # 等待回测完成（最多等待 30 秒）
    import time
    for i in range(30):
        time.sleep(1)
        resp = requests.get(f"{BASE_URL}/api/backtest/{task_id}")
        assert resp.status_code == 200
        result = resp.json()
        status = result["status"]
        
        if status == "success":
            print(f"✓ 回测完成 (耗时 {i+1}秒)")
            assert "result" in result
            assert "metrics" in result["result"]
            metrics = result["result"]["metrics"]
            total_return = metrics.get('total_return')
            sharpe = metrics.get('sharpe_ratio')
            max_dd = metrics.get('max_drawdown')
            trades = metrics.get('total_trades', 0)
            print(f"  - 总收益率：{total_return*100:.2f}%" if total_return is not None else "  - 总收益率：N/A")
            print(f"  - 夏普比率：{sharpe:.2f}" if sharpe is not None else "  - 夏普比率：N/A")
            print(f"  - 最大回撤：{max_dd*100:.2f}%" if max_dd is not None else "  - 最大回撤：N/A")
            print(f"  - 交易次数：{trades}")
            break
        elif status == "failed":
            print(f"✗ 回测失败：{result.get('error', 'Unknown error')}")
            assert False, "回测失败"
        else:
            print(f"  等待中... ({status}, {i+1}s)")
    else:
        assert False, "回测超时"
    
    print("✅ 回测 API 测试通过\n")


def test_backtest_history_api():
    """测试回测历史 API"""
    print("=== 测试 GET /api/backtest/history ===")
    
    resp = requests.get(f"{BASE_URL}/api/backtest/history?limit=10")
    assert resp.status_code == 200
    history = resp.json()
    print(f"✓ 获取回测历史：{len(history)} 条")
    
    if len(history) > 0:
        assert "task_id" in history[0]
        assert "strategy_name" in history[0]
        assert "status" in history[0]
    
    print("✅ 回测历史 API 测试通过\n")


def test_load_strategy_api():
    """测试加载策略 API"""
    print("=== 测试 GET /api/backtest/{id}/load ===")
    
    # 获取最新的回测任务
    resp = requests.get(f"{BASE_URL}/api/backtest/history?limit=1")
    assert resp.status_code == 200
    history = resp.json()
    
    if len(history) > 0:
        task_id = history[0]["task_id"]
        resp = requests.get(f"{BASE_URL}/api/backtest/{task_id}/load")
        assert resp.status_code == 200
        result = resp.json()
        print(f"✓ 加载策略：{result['strategy_name']}")
        assert "strategy_code" in result
        assert "stock_codes" in result
    else:
        print("⊘ 跳过（无回测记录）")
    
    print("✅ 加载策略 API 测试通过\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("量化回测系统 API 测试")
    print("="*60)
    
    try:
        test_stocks_api()
        test_history_api()
        test_backtest_api()
        test_backtest_history_api()
        test_load_strategy_api()
        
        print("="*60)
        print("✅ 所有 API 测试通过！")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ 测试失败：{e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ 测试异常：{e}")
        import traceback
        traceback.print_exc()
        exit(1)
