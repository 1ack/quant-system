"""
数据获取模块 - 新浪财经 API

支持:
- A 股股票列表
- 日 K 线数据
- 实时行情
"""
import requests
import re
from datetime import datetime, timedelta
from typing import List, Optional
from loguru import logger

from .models import StockInfo, KLine
from ..config import settings


class DataIngestor:
    """数据获取器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
    
    def get_stock_list(self) -> List[StockInfo]:
        """
        获取 A 股股票列表
        
        返回所有沪深 A 股的基本信息
        """
        stocks = []
        
        # 获取沪深 A 股列表
        for market in ["sh", "sz"]:
            url = f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple"
            params = {
                "page": 1,
                "num": 80,
                "sort": "symbol",
                "asc": 1,
                "node": market,
                "symbol": "",
                "_srt": 0,
                "_srt": 0,
            }
            
            # 分页获取（每页 80 只，最多获取 100 页）
            for page in range(1, 101):
                params["page"] = page
                try:
                    resp = self.session.get(url, params=params, timeout=10)
                    resp.raise_for_status()
                    data = resp.json()
                    
                    if not data:
                        break
                    
                    for item in data:
                        code = item.get("code", "")
                        name = item.get("name", "")
                        
                        # 过滤非 A 股（指数、B 股等）
                        if not code or len(code) != 6:
                            continue
                        
                        stocks.append(StockInfo(
                            code=code,
                            name=name,
                            market=market.upper(),
                        ))
                    
                    logger.info(f"[{market.upper()}] Page {page}: 获取 {len(data)} 只股票")
                    
                except Exception as e:
                    logger.error(f"获取 {market} 股票列表失败：{e}")
                    break
        
        logger.info(f"共获取 {len(stocks)} 只 A 股股票")
        return stocks
    
    def get_kline(self, code: str, start_date: Optional[datetime] = None, 
                  end_date: Optional[datetime] = None) -> List[KLine]:
        """
        获取单只股票的日 K 线数据
        
        Args:
            code: 股票代码，如 000001
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            KLine 列表
        """
        klines = []
        
        # 新浪财经 K 线 API 参数
        # symbol: 股票代码
        # scale: 时间周期 (60=分钟，day=日，week=周，month=月)
        # dataline: 返回数据条数（最多 1022 条）
        # condition: 复权类型 (1=前复权，2=后复权，空=不复权)
        
        params = {
            "symbol": code,
            "scale": "day",
            "datalen": "1022",  # 最大条数
        }
        
        try:
            resp = self.session.get(settings.sina_kline_url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            for item in data:
                date_str = item.get("day", "")
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    continue
                
                # 日期过滤
                if start_date and date < start_date:
                    continue
                if end_date and date > end_date:
                    continue
                
                klines.append(KLine(
                    code=code,
                    date=date,
                    open=float(item.get("open", 0)),
                    high=float(item.get("high", 0)),
                    low=float(item.get("low", 0)),
                    close=float(item.get("close", 0)),
                    volume=int(item.get("volume", 0)),
                    amount=float(item.get("amount", 0)),
                ))
            
            logger.debug(f"{code}: 获取 {len(klines)} 条 K 线")
            
        except Exception as e:
            logger.error(f"{code}: 获取 K 线失败 - {e}")
        
        return klines
    
    def get_realtime_quote(self, codes: List[str]) -> dict:
        """
        获取实时行情
        
        Args:
            codes: 股票代码列表
        
        Returns:
            {code: {open, high, low, close, volume, ...}}
        """
        quotes = {}
        
        # 新浪财经实时行情 API
        symbols = ",".join([f"{c[:2].lower()}{c[2:]}" for c in codes])
        url = f"http://hq.sinajs.cn/list={symbols}"
        
        try:
            resp = self.session.get(url, timeout=10)
            resp.encoding = "gbk"  # 新浪返回 GBK 编码
            lines = resp.text.strip().split("\n")
            
            for line in lines:
                # 解析格式：var hq_str_sh000001="..."
                match = re.search(r'hq_str_(\w\w\d{6})="([^"]+)"', line)
                if not match:
                    continue
                
                code = match.group(1)[2:]  # 去掉市场前缀
                fields = match.group(2).split(",")
                
                if len(fields) < 32:
                    continue
                
                quotes[code] = {
                    "name": fields[0],
                    "open": float(fields[1]) if fields[1] else 0,
                    "high": float(fields[2]) if fields[2] else 0,
                    "low": float(fields[3]) if fields[3] else 0,
                    "close": float(fields[4]) if fields[4] else 0,  # 当前价
                    "pre_close": float(fields[2]) if fields[2] else 0,  # 昨收
                    "volume": int(float(fields[8]) if fields[8] else 0),
                    "amount": float(fields[9]) if fields[9] else 0,
                }
            
        except Exception as e:
            logger.error(f"获取实时行情失败：{e}")
        
        return quotes
    
    def ingest_full(self, codes: Optional[List[str]] = None, 
                    start_date: datetime = None) -> int:
        """
        全量录入历史数据
        
        Args:
            codes: 股票代码列表，None 表示全部
            start_date: 开始日期，默认 2010-01-01
        
        Returns:
            录入的股票数量
        """
        from .storage import DataStorage
        
        if start_date is None:
            start_date = datetime(2010, 1, 1)
        
        # 获取股票列表
        if codes is None:
            stock_list = self.get_stock_list()
            codes = [s.code for s in stock_list]
        
        storage = DataStorage()
        count = 0
        
        for i, code in enumerate(codes):
            logger.info(f"[{i+1}/{len(codes)}] 录入 {code}")
            
            klines = self.get_kline(code, start_date=start_date)
            if klines:
                storage.save_klines(klines)
                count += 1
        
        logger.info(f"全量录入完成：{count}/{len(codes)} 只股票")
        return count
    
    def ingest_incremental(self, codes: Optional[List[str]] = None) -> int:
        """
        增量更新数据（仅更新最新交易日）
        
        Returns:
            更新的股票数量
        """
        from .storage import DataStorage
        
        storage = DataStorage()
        
        # 获取股票列表
        if codes is None:
            stock_list = self.get_stock_list()
            codes = [s.code for s in stock_list]
        
        count = 0
        today = datetime.now().date()
        
        for code in codes:
            # 获取该股票最后一条数据日期
            last_date = storage.get_last_kline_date(code)
            
            # 如果已有今天数据，跳过
            if last_date and last_date.date() == today:
                continue
            
            # 获取最近数据
            klines = self.get_kline(code, start_date=last_date)
            if klines:
                storage.save_klines(klines)
                count += 1
        
        logger.info(f"增量更新完成：{count} 只股票")
        return count


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="A 股数据录入")
    parser.add_argument("--full", action="store_true", help="全量录入")
    parser.add_argument("--incremental", action="store_true", help="增量更新")
    parser.add_argument("--code", type=str, help="指定股票代码")
    parser.add_argument("--start-date", type=str, help="开始日期 (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    ingestor = DataIngestor()
    
    if args.full:
        codes = [args.code] if args.code else None
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d") if args.start_date else None
        ingestor.ingest_full(codes, start_date)
    elif args.incremental:
        codes = [args.code] if args.code else None
        ingestor.ingest_incremental(codes)
    else:
        parser.print_help()
