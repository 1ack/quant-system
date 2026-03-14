"""
量化回测系统 - Web API 服务

FastAPI 后端，提供策略管理、回测执行、结果查询接口
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import json
import traceback
from loguru import logger

from backtest.engine import BacktestEngine, BacktestConfig, BacktestResult
from strategy.base import BaseStrategy, Signal, SignalType
from data.storage import DataStorage

# 初始化 FastAPI
app = FastAPI(
    title="量化回测系统",
    description="A 股量化回测平台 - 策略编辑、回测执行、绩效分析",
    version="1.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
static_dir = project_root / "web" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 回测任务存储（内存，生产环境应使用 Redis/数据库）
backtest_tasks: Dict[str, Dict[str, Any]] = {}


# ==================== 数据模型 ====================

class StrategyRequest(BaseModel):
    """策略提交请求"""
    name: str
    code: str  # Python 代码
    description: Optional[str] = ""
    params: Optional[Dict[str, Any]] = {}


class BacktestRequest(BaseModel):
    """回测请求"""
    strategy_code: str
    strategy_name: str = "CustomStrategy"
    strategy_params: Optional[Dict[str, Any]] = {}
    codes: List[str]  # 股票代码列表
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    initial_capital: float = 1000000.0
    commission_rate: float = 0.0003
    slippage_rate: float = 0.001


class BacktestResponse(BaseModel):
    """回测响应"""
    task_id: str
    status: str  # pending, running, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ==================== 动态策略加载 ====================

def create_strategy_class(code: str, name: str, params: Dict[str, Any]):
    """
    从代码字符串动态创建策略类
    
    安全提示：生产环境需要使用沙箱隔离
    """
    namespace = {
        "BaseStrategy": BaseStrategy,
        "Signal": Signal,
        "SignalType": SignalType,
        "pd": __import__("pandas"),
        "List": List,
    }
    
    try:
        exec(code, namespace)
        
        # 查找策略类（继承自 BaseStrategy 的第一个类）
        strategy_class = None
        for obj in namespace.values():
            if (isinstance(obj, type) and 
                issubclass(obj, BaseStrategy) and 
                obj != BaseStrategy):
                strategy_class = obj
                break
        
        if not strategy_class:
            raise ValueError("未找到策略类，请确保定义了继承自 BaseStrategy 的类")
        
        # 设置策略名称
        strategy_class.name = name
        
        return strategy_class(params)
        
    except Exception as e:
        raise ValueError(f"策略代码编译失败：{str(e)}")


# ==================== API 接口 ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    """返回前端页面"""
    index_file = project_root / "web" / "static" / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse(content="<h1>量化回测系统</h1><p>访问 /docs 查看 API 文档</p>")


@app.get("/api/strategies", response_model=List[Dict[str, Any]])
async def list_strategies():
    """获取策略列表"""
    # 从数据库或文件系统加载已保存的策略
    return [
        {"name": "MA_Cross", "description": "双均线交叉策略"},
        {"name": "Custom", "description": "自定义策略"},
    ]


@app.post("/api/backtest", response_model=BacktestResponse)
async def create_backtest(request: BacktestRequest, background_tasks: BackgroundTasks):
    """
    创建回测任务
    
    异步执行回测，返回 task_id 用于查询结果
    """
    task_id = str(uuid.uuid4())
    
    # 保存任务
    backtest_tasks[task_id] = {
        "status": "pending",
        "request": request.dict(),
        "result": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
    }
    
    # 后台执行回测
    background_tasks.add_task(run_backtest, task_id, request)
    
    return BacktestResponse(
        task_id=task_id,
        status="pending",
    )


@app.get("/api/backtest/{task_id}", response_model=BacktestResponse)
async def get_backtest_result(task_id: str):
    """查询回测任务状态和结果"""
    if task_id not in backtest_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = backtest_tasks[task_id]
    
    return BacktestResponse(
        task_id=task_id,
        status=task["status"],
        result=task["result"],
        error=task["error"],
    )


@app.get("/api/stocks")
async def list_stocks(q: Optional[str] = None, limit: int = 100):
    """获取股票列表（支持搜索）"""
    storage = DataStorage()
    # 这里简化处理，实际应从数据库查询
    stocks = [
        {"code": "000001", "name": "平安银行"},
        {"code": "000002", "name": "万科 A"},
        {"code": "600000", "name": "浦发银行"},
        {"code": "600036", "name": "招商银行"},
        {"code": "601318", "name": "中国平安"},
        {"code": "600519", "name": "贵州茅台"},
    ]
    
    if q:
        stocks = [s for s in stocks if q in s["code"] or q in s["name"]]
    
    return stocks[:limit]


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ==================== 后台任务 ====================

def run_backtest(task_id: str, request: BacktestRequest):
    """执行回测任务"""
    try:
        # 更新状态
        backtest_tasks[task_id]["status"] = "running"
        
        logger.info(f"开始回测任务：{task_id}")
        
        # 创建策略实例
        strategy = create_strategy_class(
            request.strategy_code,
            request.strategy_name,
            request.strategy_params,
        )
        
        # 配置回测
        config = BacktestConfig(
            start_date=datetime.strptime(request.start_date, "%Y-%m-%d"),
            end_date=datetime.strptime(request.end_date, "%Y-%m-%d"),
            initial_capital=request.initial_capital,
            commission_rate=request.commission_rate,
            slippage_rate=request.slippage_rate,
        )
        
        # 执行回测
        engine = BacktestEngine(config)
        result = engine.run(strategy, request.codes)
        
        # 格式化结果
        result_data = format_backtest_result(result)
        
        # 保存结果
        backtest_tasks[task_id]["status"] = "completed"
        backtest_tasks[task_id]["result"] = result_data
        
        logger.info(f"回测任务完成：{task_id}")
        
    except Exception as e:
        logger.error(f"回测任务失败：{task_id} - {str(e)}")
        backtest_tasks[task_id]["status"] = "failed"
        backtest_tasks[task_id]["error"] = f"{str(e)}\n\n{traceback.format_exc()}"


def format_backtest_result(result: BacktestResult) -> Dict[str, Any]:
    """格式化回测结果为 JSON"""
    import pandas as pd
    
    # 绩效指标
    metrics = {
        "strategy_name": result.strategy_name,
        "start_date": result.start_date.strftime("%Y-%m-%d"),
        "end_date": result.end_date.strftime("%Y-%m-%d"),
        "initial_capital": result.initial_capital,
        "final_capital": result.final_capital,
        "total_return": result.total_return,
        "annual_return": result.annual_return,
        "sharpe_ratio": result.sharpe_ratio,
        "max_drawdown": result.max_drawdown,
        "win_rate": result.win_rate,
        "total_trades": result.total_trades,
    }
    
    # 每日净值数据（用于绘制曲线）
    daily_data = []
    if result.daily_values is not None:
        for _, row in result.daily_values.iterrows():
            daily_data.append({
                "date": row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], 'strftime') else str(row["date"]),
                "value": float(row["total_value"]),
                "cash": float(row["cash"]),
                "position_value": float(row["position_value"]),
            })
    
    # 交易记录
    trades = []
    for trade in result.trades:
        trades.append({
            "code": trade.code,
            "date": trade.date.strftime("%Y-%m-%d") if hasattr(trade.date, 'strftime') else str(trade.date),
            "direction": trade.direction,
            "price": float(trade.price),
            "volume": trade.volume,
            "amount": float(trade.amount),
            "commission": float(trade.commission),
        })
    
    return {
        "metrics": metrics,
        "daily_data": daily_data,
        "trades": trades,
    }


# ==================== 启动 ====================

if __name__ == "__main__":
    import uvicorn
    
    # 配置日志
    logger.add(
        project_root / "logs" / "web.log",
        rotation="10 MB",
        retention="7 days",
        level="INFO",
    )
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
