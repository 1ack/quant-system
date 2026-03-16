"""
量化回测系统 - API 路由模块

包含所有后端 API 接口实现：
- GET /api/stocks - 获取可用股票列表（支持模糊搜索）
- POST /api/backtest - 执行回测
- GET /api/backtest/history - 获取回测历史
- GET /api/backtest/{id}/load - 加载策略代码
- POST /api/backtest/{id}/save-git - 保存到 Git
- GET /api/history/{code} - 获取股票历史数据
"""
import sys
import os
from pathlib import Path
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import json
import uuid
import subprocess
import traceback

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# 项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings
from backtest.engine import BacktestEngine, BacktestConfig, BacktestResult
from backtest.performance import PerformanceAnalyzer
from strategy.base import BaseStrategy, Signal, SignalType
from data.storage import DataStorage
from data.models import KLine

# 创建 API 路由
router = APIRouter(prefix="/api", tags=["API"])

# ==================== 数据库连接 ====================

def get_db_engine():
    """获取 PostgreSQL 数据库引擎"""
    url = f"postgresql+psycopg2://postgres:admin%40123@localhost:5432/quant"
    return create_engine(url, echo=False)


def get_db_session() -> Session:
    """获取数据库会话"""
    engine = get_db_engine()
    Session = sessionmaker(bind=engine)
    return Session()


# ==================== 数据模型 ====================

class StockInfo(BaseModel):
    """股票信息"""
    code: str
    name: str
    market: str
    data_start: Optional[str] = None
    data_end: Optional[str] = None
    kline_count: int = 0


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


class BacktestHistoryItem(BaseModel):
    """回测历史项"""
    id: int
    task_id: str
    strategy_name: str
    stock_codes: List[str]
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: Optional[float] = None
    total_return: Optional[float] = None
    status: str
    created_at: str


class BacktestResponse(BaseModel):
    """回测响应"""
    task_id: str
    status: str  # pending, running, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class KLineData(BaseModel):
    """K 线数据"""
    code: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float


class GitSaveRequest(BaseModel):
    """Git 保存请求"""
    commit_message: Optional[str] = None


# ==================== 内存任务存储 ====================

backtest_tasks: Dict[str, Dict[str, Any]] = {}


# ==================== API 接口 ====================

@router.get("/stocks", response_model=List[StockInfo])
async def list_stocks(q: Optional[str] = Query(None, description="搜索关键词（代码或名称）"), limit: int = Query(100, ge=1, le=1000)):
    """
    获取可用股票列表
    
    - **q**: 可选的搜索关键词，支持模糊匹配代码或名称
    - **limit**: 返回数量限制（默认 100，最大 1000）
    """
    db = get_db_session()
    try:
        query = "SELECT code, name, market, data_start, data_end, kline_count FROM available_stocks"
        params = {}
        
        if q:
            query += " WHERE code ILIKE :q OR name ILIKE :q"
            params["q"] = f"%{q}%"
        
        query += " ORDER BY code LIMIT :limit"
        
        result = db.execute(text(query), {**params, "limit": limit})
        rows = result.fetchall()
        
        stocks = []
        for row in rows:
            stocks.append(StockInfo(
                code=row[0],
                name=row[1],
                market=row[2],
                data_start=row[3].isoformat() if row[3] else None,
                data_end=row[4].isoformat() if row[4] else None,
                kline_count=row[5] or 0,
            ))
        
        return stocks
    finally:
        db.close()


@router.post("/backtest", response_model=BacktestResponse)
async def create_backtest(request: BacktestRequest, background_tasks: BackgroundTasks):
    """
    创建回测任务
    
    异步执行回测，返回 task_id 用于查询结果
    
    - **strategy_code**: Python 策略代码
    - **strategy_name**: 策略名称
    - **strategy_params**: 策略参数
    - **codes**: 股票代码列表
    - **start_date**: 开始日期 (YYYY-MM-DD)
    - **end_date**: 结束日期 (YYYY-MM-DD)
    - **initial_capital**: 初始资金
    - **commission_rate**: 手续费率
    - **slippage_rate**: 滑点率
    """
    task_id = str(uuid.uuid4())
    
    # 保存任务到数据库
    db = get_db_session()
    try:
        # 插入回测记录
        db.execute(
            text("""
            INSERT INTO backtest_run 
            (task_id, strategy_name, strategy_code, stock_codes, start_date, end_date, 
             initial_capital, commission_rate, status, created_at, updated_at)
            VALUES 
            (:task_id, :strategy_name, :strategy_code, :stock_codes, :start_date, :end_date,
             :initial_capital, :commission_rate, :status, NOW(), NOW())
            """),
            {
                "task_id": task_id,
                "strategy_name": request.strategy_name,
                "strategy_code": request.strategy_code,
                "stock_codes": json.dumps(request.codes),
                "start_date": request.start_date,
                "end_date": request.end_date,
                "initial_capital": request.initial_capital,
                "commission_rate": request.commission_rate,
                "status": "running",
            },
        )
        db.commit()
        
        # 获取回测 ID
        result = db.execute(
            text("SELECT id FROM backtest_run WHERE task_id = :task_id"),
            {"task_id": task_id}
        )
        backtest_id = result.fetchone()[0]
        
    finally:
        db.close()
    
    # 保存到内存任务
    backtest_tasks[task_id] = {
        "backtest_id": backtest_id,
        "status": "running",
        "request": request.dict(),
        "result": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
    }
    
    # 后台执行回测
    background_tasks.add_task(run_backtest, task_id, request)
    
    return BacktestResponse(
        task_id=task_id,
        status="running",
    )


@router.get("/backtest/history", response_model=List[BacktestHistoryItem])
async def get_backtest_history(limit: int = Query(50, ge=1, le=500)):
    """
    获取回测历史记录
    
    - **limit**: 返回数量限制（默认 50，最大 500）
    """
    db = get_db_session()
    try:
        result = db.execute(
            text("""
            SELECT id, task_id, strategy_name, stock_codes, start_date, end_date,
                   initial_capital, final_capital, total_return, status, created_at
            FROM backtest_run
            ORDER BY created_at DESC
            LIMIT :limit
            """),
            {"limit": limit}
        )
        rows = result.fetchall()
        
        history = []
        for row in rows:
            stock_codes = row[3] if isinstance(row[3], list) else json.loads(row[3]) if row[3] else []
            history.append(BacktestHistoryItem(
                id=row[0],
                task_id=row[1],
                strategy_name=row[2],
                stock_codes=stock_codes,
                start_date=row[4].isoformat() if row[4] else None,
                end_date=row[5].isoformat() if row[5] else None,
                initial_capital=float(row[6]) if row[6] else 0,
                final_capital=float(row[7]) if row[7] else None,
                total_return=float(row[8]) if row[8] else None,
                status=row[9],
                created_at=row[10].isoformat() if row[10] else None,
            ))
        
        return history
    finally:
        db.close()


@router.get("/backtest/{task_id}/load")
async def load_backtest_strategy(task_id: str):
    """
    加载回测策略代码
    
    根据 task_id 获取保存的策略代码
    """
    db = get_db_session()
    try:
        result = db.execute(
            text("""
            SELECT strategy_name, strategy_code, stock_codes, start_date, end_date,
                   initial_capital, commission_rate, status, error_message
            FROM backtest_run
            WHERE task_id = :task_id
            """),
            {"task_id": task_id}
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="回测任务不存在")
        
        stock_codes = row[2] if isinstance(row[2], list) else json.loads(row[2]) if row[2] else []
        
        return {
            "task_id": task_id,
            "strategy_name": row[0],
            "strategy_code": row[1],
            "stock_codes": stock_codes,
            "start_date": row[3].isoformat() if row[3] else None,
            "end_date": row[4].isoformat() if row[4] else None,
            "initial_capital": float(row[5]) if row[5] else 0,
            "commission_rate": float(row[6]) if row[6] else 0.0003,
            "status": row[7],
            "error_message": row[8],
        }
    finally:
        db.close()


@router.post("/backtest/{task_id}/save-git")
async def save_backtest_to_git(task_id: str, request: GitSaveRequest = None):
    """
    保存回测结果到 Git
    
    将策略代码和回测报告提交到 Git 仓库
    """
    db = get_db_session()
    try:
        # 获取回测信息
        result = db.execute(
            text("""
            SELECT strategy_name, strategy_code, final_capital, total_return, 
                   sharpe_ratio, max_drawdown, total_trades, start_date, end_date
            FROM backtest_run
            WHERE task_id = :task_id
            """),
            {"task_id": task_id}
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="回测任务不存在")
        
        if row[4] is None:  # sharpe_ratio is None means not completed
            raise HTTPException(status_code=400, detail="回测尚未完成，无法保存")
        
        strategy_name = row[0]
        strategy_code = row[1]
        
        # 生成回测报告
        report = f"""# 回测报告 - {strategy_name}

## 基本信息
- 任务 ID: {task_id}
- 策略名称：{strategy_name}
- 回测区间：{row[7]} ~ {row[8]}

## 绩效指标
- 初始资金：{row[2]:,.2f}
- 最终资金：{row[2] * (1 + row[4]):,.2f}
- 总收益率：{row[4] * 100:.2f}%
- 夏普比率：{row[5]:.2f}
- 最大回撤：{row[6] * 100:.2f}%
- 总交易次数：{row[7]}

## 策略代码

```python
{strategy_code}
```
"""
        
        # 保存到文件
        reports_dir = project_root / "docs" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = reports_dir / f"backtest_{task_id}.md"
        strategy_file = reports_dir / f"strategy_{task_id}.py"
        
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        
        with open(strategy_file, "w", encoding="utf-8") as f:
            f.write(strategy_code)
        
        # Git 提交
        commit_message = request.commit_message or f"回测报告：{strategy_name} ({task_id[:8]})"
        
        try:
            subprocess.run(
                ["git", "add", str(report_file), str(strategy_file)],
                cwd=project_root,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=project_root,
                check=True,
                capture_output=True,
            )
            
            return {
                "success": True,
                "message": f"已保存到 Git: {commit_message}",
                "files": [str(report_file), str(strategy_file)],
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"Git 提交失败：{e.stderr.decode()}")
            raise HTTPException(status_code=500, detail=f"Git 提交失败：{e.stderr.decode()}")
        
    finally:
        db.close()


@router.get("/backtest/{task_id}")
async def get_backtest_result(task_id: str):
    """查询回测任务状态和结果"""
    db = get_db_session()
    try:
        # 从数据库获取最新状态
        result = db.execute(
            text("""
            SELECT id, strategy_name, final_capital, total_return, annual_return,
                   sharpe_ratio, max_drawdown, win_rate, total_trades, status, error_message
            FROM backtest_run
            WHERE task_id = :task_id
            """),
            {"task_id": task_id}
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        status = row[9]
        
        response = {
            "task_id": task_id,
            "status": status,
        }
        
        if status == "success" and row[2] is not None:
            # 获取交易明细
            trades_result = db.execute(
                text("""
                SELECT code, trade_date, direction, price, volume, amount, commission
                FROM trade_detail
                WHERE backtest_id = :backtest_id
                ORDER BY trade_date, id
                """),
                {"backtest_id": row[0]}
            )
            trades = []
            for trade in trades_result.fetchall():
                trades.append({
                    "code": trade[0],
                    "date": trade[1].isoformat() if trade[1] else None,
                    "direction": trade[2],
                    "price": float(trade[3]),
                    "volume": trade[4],
                    "amount": float(trade[5]),
                    "commission": float(trade[6]) if trade[6] else 0,
                })
            
            response["result"] = {
                "metrics": {
                    "strategy_name": row[1],
                    "final_capital": float(row[2]) if row[2] else None,
                    "total_return": float(row[3]) if row[3] else None,
                    "annual_return": float(row[4]) if row[4] else None,
                    "sharpe_ratio": float(row[5]) if row[5] else None,
                    "max_drawdown": float(row[6]) if row[6] else None,
                    "win_rate": float(row[7]) if row[7] else None,
                    "total_trades": row[8],
                },
                "trades": trades,
            }
        elif status == "failed":
            response["error"] = row[10]
        
        return response
    finally:
        db.close()


@router.get("/history/{code}", response_model=List[KLineData])
async def get_stock_history(
    code: str,
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    limit: int = Query(1000, ge=1, le=10000),
):
    """
    获取股票历史 K 线数据
    
    从 ClickHouse 查询 K 线数据
    
    - **code**: 股票代码（如 600900）
    - **start_date**: 可选的开始日期
    - **end_date**: 可选的结束日期
    - **limit**: 返回数量限制（默认 1000，最大 10000）
    """
    storage = DataStorage()
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
        
        klines = storage.get_klines(code, start_date=start, end_date=end)
        
        # 应用限制
        if len(klines) > limit:
            klines = klines[-limit:]
        
        return [
            KLineData(
                code=k.code,
                date=k.date.strftime("%Y-%m-%d") if hasattr(k.date, 'strftime') else str(k.date),
                open=float(k.open),
                high=float(k.high),
                low=float(k.low),
                close=float(k.close),
                volume=int(k.volume),
                amount=float(k.amount),
            )
            for k in klines
        ]
    except Exception as e:
        logger.error(f"获取 K 线数据失败：{code} - {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取数据失败：{str(e)}")


# ==================== 后台任务 ====================

def run_backtest(task_id: str, request: BacktestRequest):
    """执行回测任务"""
    db = get_db_session()
    try:
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
        
        # 保存结果到数据库
        db.execute(
            text("""
            UPDATE backtest_run
            SET final_capital = :final_capital,
                total_return = :total_return,
                annual_return = :annual_return,
                sharpe_ratio = :sharpe_ratio,
                max_drawdown = :max_drawdown,
                win_rate = :win_rate,
                total_trades = :total_trades,
                status = :status,
                updated_at = NOW()
            WHERE task_id = :task_id
            """),
            {
                "final_capital": float(result.final_capital),
                "total_return": float(result.total_return),
                "annual_return": float(result.annual_return),
                "sharpe_ratio": float(result.sharpe_ratio),
                "max_drawdown": float(result.max_drawdown),
                "win_rate": float(result.win_rate) if result.win_rate else None,
                "total_trades": int(result.total_trades),
                "status": "success",
                "task_id": task_id,
            },
        )
        
        # 获取 backtest_id
        result_query = db.execute(
            text("SELECT id FROM backtest_run WHERE task_id = :task_id"),
            {"task_id": task_id}
        )
        backtest_id = result_query.fetchone()[0]
        
        # 保存交易明细
        for trade in result.trades:
            db.execute(
                text("""
                INSERT INTO trade_detail 
                (backtest_id, code, trade_date, direction, price, volume, amount, commission)
                VALUES 
                (:backtest_id, :code, :trade_date, :direction, :price, :volume, :amount, :commission)
                """),
                {
                    "backtest_id": backtest_id,
                    "code": trade.code,
                    "trade_date": trade.date,
                    "direction": trade.direction,
                    "price": float(trade.price),
                    "volume": int(trade.volume),
                    "amount": float(trade.amount),
                    "commission": float(trade.commission),
                },
            )
        
        db.commit()
        
        # 更新内存任务
        backtest_tasks[task_id]["status"] = "success"
        backtest_tasks[task_id]["result"] = {
            "final_capital": result.final_capital,
            "total_return": result.total_return,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
        }
        
        logger.info(f"回测任务完成：{task_id}")
        
    except Exception as e:
        logger.error(f"回测任务失败：{task_id} - {str(e)}")
        error_msg = f"{str(e)}\n\n{traceback.format_exc()}"
        
        db.execute(
            text("""
            UPDATE backtest_run
            SET status = :status,
                error_message = :error_message,
                updated_at = NOW()
            WHERE task_id = :task_id
            """),
            {
                "status": "failed",
                "error_message": error_msg,
                "task_id": task_id,
            },
        )
        db.commit()
        
        backtest_tasks[task_id]["status"] = "failed"
        backtest_tasks[task_id]["error"] = error_msg
    finally:
        db.close()


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
        "List": __import__("typing").List,
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
