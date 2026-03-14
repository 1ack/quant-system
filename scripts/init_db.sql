-- =====================================================
-- MySQL 数据库初始化脚本
-- 量化回测系统 - 关系型数据存储
-- =====================================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS quant DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE quant;

-- -----------------------------------------------------
-- 股票信息表
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_info (
    code VARCHAR(10) PRIMARY KEY COMMENT '股票代码',
    name VARCHAR(50) NOT NULL COMMENT '股票名称',
    market ENUM('SH', 'SZ') NOT NULL COMMENT '市场',
    industry VARCHAR(50) COMMENT '行业',
    list_date DATE COMMENT '上市日期',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_market (market),
    INDEX idx_industry (industry)
) ENGINE=InnoDB COMMENT='股票基本信息表';

-- -----------------------------------------------------
-- 策略表
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE COMMENT '策略名称',
    description TEXT COMMENT '策略描述',
    author VARCHAR(50) COMMENT '作者',
    version VARCHAR(20) COMMENT '版本号',
    params JSON COMMENT '策略参数',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_active (is_active)
) ENGINE=InnoDB COMMENT='策略定义表';

-- -----------------------------------------------------
-- 回测结果表
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_result (
    id INT AUTO_INCREMENT PRIMARY KEY,
    strategy_id INT NOT NULL COMMENT '策略 ID',
    strategy_name VARCHAR(100) NOT NULL COMMENT '策略名称',
    start_date DATE NOT NULL COMMENT '回测开始日期',
    end_date DATE NOT NULL COMMENT '回测结束日期',
    initial_capital DECIMAL(15,2) NOT NULL COMMENT '初始资金',
    final_capital DECIMAL(15,2) NOT NULL COMMENT '最终资金',
    total_return DECIMAL(10,6) COMMENT '总收益率',
    annual_return DECIMAL(10,6) COMMENT '年化收益',
    sharpe_ratio DECIMAL(10,4) COMMENT '夏普比率',
    max_drawdown DECIMAL(10,6) COMMENT '最大回撤',
    win_rate DECIMAL(10,6) COMMENT '胜率',
    total_trades INT COMMENT '总交易次数',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategy(id),
    INDEX idx_strategy (strategy_id),
    INDEX idx_date_range (start_date, end_date)
) ENGINE=InnoDB COMMENT='回测结果表';

-- -----------------------------------------------------
-- 交易记录表
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS trade_record (
    id INT AUTO_INCREMENT PRIMARY KEY,
    backtest_id INT COMMENT '回测结果 ID',
    strategy_id INT NOT NULL COMMENT '策略 ID',
    code VARCHAR(10) NOT NULL COMMENT '股票代码',
    trade_date DATE NOT NULL COMMENT '交易日期',
    direction ENUM('buy', 'sell') NOT NULL COMMENT '买卖方向',
    price DECIMAL(10,4) NOT NULL COMMENT '成交价',
    volume INT NOT NULL COMMENT '成交数量',
    amount DECIMAL(15,2) NOT NULL COMMENT '成交金额',
    commission DECIMAL(15,2) DEFAULT 0 COMMENT '手续费',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (backtest_id) REFERENCES backtest_result(id),
    FOREIGN KEY (strategy_id) REFERENCES strategy(id),
    INDEX idx_code_date (code, trade_date),
    INDEX idx_strategy (strategy_id)
) ENGINE=InnoDB COMMENT='交易记录表';

-- -----------------------------------------------------
-- 数据更新日志表
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS data_update_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    update_type ENUM('full', 'incremental') NOT NULL COMMENT '更新类型',
    stock_count INT COMMENT '更新股票数量',
    kline_count BIGINT COMMENT '更新 K 线数量',
    start_time DATETIME NOT NULL COMMENT '开始时间',
    end_time DATETIME COMMENT '结束时间',
    status ENUM('running', 'success', 'failed') DEFAULT 'running',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_time (start_time)
) ENGINE=InnoDB COMMENT='数据更新日志表';

-- -----------------------------------------------------
-- 插入示例策略
-- -----------------------------------------------------
INSERT INTO strategy (name, description, author, version, params) VALUES
('MA_Cross', '双均线交叉策略：金叉买入，死叉卖出', 'Quant System', '1.0.0', 
 '{"short_window": 5, "long_window": 20}')
ON DUPLICATE KEY UPDATE description=VALUES(description);

-- -----------------------------------------------------
-- 创建视图：回测结果汇总
-- -----------------------------------------------------
CREATE OR REPLACE VIEW v_backtest_summary AS
SELECT 
    br.id,
    br.strategy_name,
    br.start_date,
    br.end_date,
    br.initial_capital,
    br.final_capital,
    br.total_return,
    br.annual_return,
    br.sharpe_ratio,
    br.max_drawdown,
    br.win_rate,
    br.total_trades,
    br.created_at,
    DATEDIFF(br.end_date, br.start_date) AS duration_days
FROM backtest_result br
ORDER BY br.created_at DESC;

-- =====================================================
-- 初始化完成
-- =====================================================
