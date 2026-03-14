# Web 前端使用指南

## 功能特性

- 📝 **策略编辑器**: Monaco Editor（VS Code 同款），支持 Python 语法高亮
- ⚙️ **回测配置**: 日期范围、初始资金、手续费率、股票选择
- 📊 **绩效展示**: 总收益、年化收益、夏普比率、最大回撤、胜率
- 📈 **可视化图表**: 
  - 净值曲线（面积图）
  - 收益分布（柱状图）
- 📋 **交易记录**: 详细的买卖记录表格

## 快速启动

```bash
cd /home/admin/.openclaw/workspace/quant-backtest

# 1. 安装 Web 依赖
source venv/bin/activate
pip install -r web/requirements.txt

# 2. 启动服务
./web/run.sh

# 或直接运行
python -m web.main
```

## 访问地址

- **前端页面**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

## 使用流程

1. **编辑策略代码**（或点击"加载模板"使用双均线策略）
2. **配置回测参数**:
   - 选择日期范围
   - 设置初始资金
   - 选择要回测的股票
3. **点击"开始回测"**
4. **查看结果**:
   - 绩效指标卡片
   - 净值曲线图
   - 收益分布图
   - 交易记录明细

## 策略代码规范

策略类需继承 `BaseStrategy`，实现 `generate_signals` 方法：

```python
class MyStrategy(BaseStrategy):
    name = "MyStrategy"
    
    params = {
        "param1": 5,
        "param2": 20,
    }
    
    def generate_signals(self, data):
        """
        生成交易信号
        
        Args:
            data: pandas DataFrame，包含 columns:
                  [code, date, open, high, low, close, volume, amount]
        
        Returns:
            List[Signal]: 信号列表
        """
        signals = []
        # 你的策略逻辑
        # signals.append(Signal(code, date, SignalType.BUY, price))
        return signals
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/backtest` | POST | 创建回测任务 |
| `/api/backtest/{task_id}` | GET | 查询回测结果 |
| `/api/stocks` | GET | 获取股票列表 |
| `/api/strategies` | GET | 获取策略列表 |
| `/api/health` | GET | 健康检查 |

## 注意事项

- 首次运行前需确保数据库已初始化并录入数据
- 策略代码在服务器端执行，注意代码安全
- 生产环境建议添加用户认证和代码沙箱
