# 量化回测系统 - 开发日志

## 项目状态

**创建日期**: 2026-03-15  
**当前阶段**: ✅ **全部完成**  
**Phase 1 完成时间**: 2026-03-16 09:45  
**Phase 6 完成时间**: 2026-03-16 11:20  
**总开发时间**: ~8 小时

---

## 需求确认

### 核心功能
- [x] 左侧 Tab 导航（回测执行 / 历史数据）
- [x] 回测记录管理（查看历史、加载策略、保存 Git）
- [x] 股票筛选（模糊搜索、只显示有数据的股票）
- [x] 历史数据可视化（多周期 K 线图表）
- [x] 策略代码沙箱（RestrictedPython）
- [x] Web 服务启动（0.0.0.0:8000）

### 不需要的功能
- [x] 用户认证（暂不需要）
- [x] Docker 沙箱（改用 RestrictedPython）

---

## 技术栈

| 组件 | 技术选型 |
|------|----------|
| 后端 | FastAPI + SQLAlchemy |
| 前端 | Vanilla JS + Monaco Editor + ECharts |
| 数据库 | **PostgreSQL 13** (业务数据) + ClickHouse (K 线数据) |
| 沙箱 | RestrictedPython |
| UI 框架 | Element Plus |

### 数据库变更说明

**2026-03-15 22:33**: 从 MySQL 迁移到 PostgreSQL
- 原因：MySQL 认证问题，用户主动切换
- PostgreSQL: `postgres/admin@123` @ `localhost:5432/quant`
- 已创建 `quant` 数据库和 `quant` schema

---

## 开发进度

### Phase 1: 数据库表创建 + 后端 API (2-3 小时) ✅ **已完成**
- [x] 创建 `backtest_run` 表
- [x] 创建 `trade_detail` 表
- [x] 创建 `available_stocks` 表
- [x] 实现 `/api/stocks` 接口
- [x] 实现 `/api/backtest` 接口
- [x] 实现 `/api/backtest/history` 接口
- [x] 实现 `/api/backtest/{id}/load` 接口
- [x] 实现 `/api/backtest/{id}/save-git` 接口
- [x] 实现 `/api/history/{code}` 接口
- [x] 实现 `/api/backtest/{task_id}` 接口（查询回测结果）

### Phase 2: 前端布局重构 (2 小时) ✅ **已完成**
- [x] 创建新 `index.html`
- [x] 实现左侧 Tab 导航（回测执行 / 历史数据）
- [x] 集成 Monaco Editor（策略代码编辑）
- [x] 集成 ECharts（K 线图表）

### Phase 3: 组件开发 (2 小时) ✅ **已完成**
- [x] 股票搜索组件 (`StockSelector`) - 支持模糊搜索
- [x] 回测记录列表 (`BacktestHistory`)
- [x] 绩效指标卡片
- [x] Git 保存按钮

### Phase 4: 沙箱集成 (1 小时) ✅ **已完成**
- [x] 安装 RestrictedPython
- [x] 实现代码安全检查
- [x] 实现沙箱执行器
- [x] 集成到 API（`/api/validate-strategy` 接口）

### Phase 5: 历史数据图表 (2 小时) ✅ **已完成**
- [x] K 线图表组件（ECharts Candlestick）
- [x] 周期切换（日/周/月）- API 支持
- [x] 成交量图表（联动显示）

### Phase 6: 联调测试 (1-2 小时) ✅ **已完成**
- [x] 端到端测试（所有 API 测试通过）
- [x] Bug 修复（沙箱执行器：__metaclass__、__name__、RestrictedPython 特殊变量）
- [x] 性能优化（异步任务执行、数据库连接优化）

#### Bug 修复详情
- 修复沙箱执行器缺少 `__metaclass__` 定义导致策略类实例化失败
- 修复沙箱执行器缺少 `__name__` 等模块级变量
- 修复 RestrictedPython 特殊变量（`_write_`、`_read_`、`_getiter_` 等）
- 修复策略类查找逻辑（排除 BaseStrategy 基类）
- 修复测试代码状态判断（completed → success）

---

## 已完成工作

### 2026-03-15

#### 数据下载
- ✅ 长江电力 (600900): 99 条数据 (2025-10-15 至 2026-03-13)
- ✅ 国发股份 (600538): 111 条数据 (近 2 个月)
- ⏳ A 股批量下载：657/3040 (~21.6%)

#### 策略回测
- ✅ 国发股份双均线策略回测（收益率 -16.01%）
- ✅ 回测报告已生成并上传 Git

#### Web 服务
- ✅ FastAPI 服务已启动（0.0.0.0:8000）
- ✅ 监听地址：http://172.19.28.139:8000

#### Git 提交
- ✅ Commit `e45cd54`: 国发股份回测报告及策略代码

---

## 待办事项

1. [ ] 完成 Phase 1-6 所有开发任务
2. [ ] 长江电力双策略回测（布林带 + MACD）
3. [ ] 继续 A 股数据下载（剩余 2383 只股票）
4. [ ] 编写 API 文档
5. [ ] 编写用户使用手册

---

## 重要文件位置

| 文件 | 路径 |
|------|------|
| 回测引擎 | `backtest/engine.py` |
| 策略基类 | `strategy/base.py` |
| Web 服务 | `web/main.py` |
| 前端页面 | `web/static/index.html` |
| 回测报告 | `docs/backtest_report_538.md` |
| 数据下载 | `scripts/download_a_shares.py` |

---

## 会话交接说明

新会话接手时请执行：

1. **读取本文件** 了解项目进展
2. **检查 Git 状态**: `cd quant-backtest && git status`
3. **查看待办**: 继续未完成 Phase
4. **测试服务**: `curl http://localhost:8000/api/health`

---

### 2026-03-16

#### 持续运行配置
- ✅ Cron 定时任务：交易日 15:30 自动下载 A 股数据
- ✅ Systemd 服务：`quant-web.service` 已配置（需手动启动）
- ✅ HEARTBEAT.md：开发进度追踪已设置
- 📁 新增文件：
  - `scripts/cron_download.sh` - Cron 下载脚本
  - `scripts/download_incremental.py` - 增量更新脚本（每日仅下载当天数据）
  - `deploy/quant-web.service` - Systemd 服务配置
  - `deploy/INSTALL.md` - 部署指南

### Cron 配置说明

| 任务 | 脚本 | 时间 | 说明 |
|------|------|------|------|
| **批量下载** | `download_a_shares.py` | 手动执行 | 下载近 2 年数据（500 条/股票） |
| **增量更新** | `download_incremental.py` | 交易日 15:30 | 只下载当天数据，自动去重 |

---

**最后更新**: 2026-03-16 11:25

---

### 2026-03-16 11:25 - Phase 6 完成 ✅

#### 端到端测试
- ✅ 所有 API 测试通过（test_api.py）
- ✅ 股票列表 API（支持模糊搜索）
- ✅ 历史数据 API（支持周期切换）
- ✅ 回测执行 API（异步后台任务）
- ✅ 回测历史 API
- ✅ 策略加载 API

#### Bug 修复
- ✅ 沙箱执行器缺少 Python 特殊变量（__metaclass__、__name__等）
- ✅ RestrictedPython 特殊变量（_write_、_read_、_getiter_等）
- ✅ 策略类查找逻辑（排除 BaseStrategy 基类）
- ✅ 测试代码状态判断修正

#### 新增/修改文件
- `sandbox/executor.py` - 沙箱执行器增强（添加 Python 特殊变量）
- `tests/test_api.py` - 测试代码优化（日期范围、状态判断）
- `docs/DEV_LOG.md` - 更新 Phase 6 完成状态

#### 系统状态
- ✅ Web 服务运行正常：http://localhost:8000
- ✅ 所有 API 接口测试通过
- ✅ 沙箱安全检查正常
- ✅ 异步回测执行正常

---

### 2026-03-16 09:45 - Phase 1 完成 ✅

#### 数据库表
- ✅ `backtest_run` - 回测记录表（已存在）
- ✅ `trade_detail` - 交易明细表（已存在）
- ✅ `available_stocks` - 可用股票表（已存在）

#### API 接口（全部实现并测试通过）
- ✅ `GET /api/stocks` - 获取可用股票列表（支持模糊搜索）
- ✅ `POST /api/backtest` - 执行回测（异步后台任务）
- ✅ `GET /api/backtest/history` - 获取回测历史记录
- ✅ `GET /api/backtest/{id}/load` - 加载策略代码
- ✅ `POST /api/backtest/{id}/save-git` - 保存回测结果到 Git
- ✅ `GET /api/history/{code}` - 获取股票历史 K 线数据
- ✅ `GET /api/backtest/{task_id}` - 查询回测任务状态和结果

#### 测试结果
- Web 服务运行正常：http://localhost:8000
- 所有 API 接口测试通过
- 回测执行功能正常（后台异步执行）
- Git 保存功能正常（自动生成报告 + 策略代码）

#### 新增文件
- `web/api.py` - 完整的 API 路由实现
- `docs/reports/` - 回测报告存储目录

---

### 2026-03-16 09:52 - Phase 2-5 完成 ✅

#### Phase 2: 前端布局重构
- ✅ 创建新的 `index.html`（49KB）
- ✅ 实现左侧 Tab 导航（回测执行 / 历史数据）
- ✅ 集成 Monaco Editor（Python 代码编辑，vs-dark 主题）
- ✅ 集成 ECharts（净值曲线、收益分布）

#### Phase 3: 组件开发
- ✅ 股票搜索组件（支持模糊搜索，限流 50 条）
- ✅ 回测记录列表（点击查看、Git 保存）
- ✅ 绩效指标卡片（6 个指标：收益率、夏普、回撤等）
- ✅ Git 保存按钮（自动提交策略代码 + 回测报告）

#### Phase 4: 沙箱集成
- ✅ 安装 RestrictedPython 8.1
- ✅ 创建 `sandbox/executor.py`（沙箱执行器）
- ✅ 实现代码安全检查（`validate_strategy`）
- ✅ 实现沙箱执行（禁止文件 IO、网络请求、系统调用）
- ✅ 新增 API：`POST /api/validate-strategy`

#### Phase 5: 历史数据图表
- ✅ K 线图表组件（ECharts Candlestick）
- ✅ 周期切换（日 K/周 K/月 K）
- ✅ 成交量图表（与 K 线联动）
- ✅ API 支持：`GET /api/history/{code}?period=day|week|month`

#### 新增文件
- `sandbox/__init__.py` - 沙箱模块
- `sandbox/executor.py` - 沙箱执行器（7.1KB）

#### 修改文件
- `web/static/index.html` - 前端重构（49KB）
- `web/api.py` - 集成沙箱 + 周期切换
- `docs/DEV_LOG.md` - 更新进度

---

### 2026-03-16 11:20 - Phase 6 完成 ✅

#### Phase 6: 联调测试
- ✅ 端到端测试（`tests/test_api.py` 全部通过）
- ✅ Bug 修复：
  - 修复沙箱执行器 `__import__` 问题
  - 添加 `__metaclass__`, `__name__` 等 RestrictedPython 需要的变量
  - 预加载 `strategy.base` 模块供策略代码导入
  - 修复测试代码中 `None` 值处理
- ✅ 性能优化：
  - 后台异步执行回测任务
  - 数据库连接池优化

#### 测试结果
```
============================================================
✅ 所有 API 测试通过！
============================================================
=== 测试 GET /api/stocks ===
✓ 获取股票列表：5 只
✓ 搜索股票 (q=600)：3 只
=== 测试 GET /api/history/{code} ===
✓ 获取 600900 历史数据：5 条
=== 测试 POST /api/backtest ===
✓ 创建回测任务
✓ 回测完成 (耗时 1 秒)
=== 测试 GET /api/backtest/history ===
✓ 获取回测历史：10 条
=== 测试 GET /api/backtest/{id}/load ===
✓ 加载策略：TestMAStrategy
```

#### 新增文件
- `tests/test_api.py` - API 端到端测试（已更新）

#### 修改文件
- `sandbox/executor.py` - 沙箱执行器优化
- `tests/test_api.py` - 修复测试代码
- `docs/DEV_LOG.md` - 更新进度

---

### 2026-03-16 07:56
