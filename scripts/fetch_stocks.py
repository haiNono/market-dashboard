# -*- coding: utf-8 -*-
"""拉取全A股日线行情 -> parquet 缓存（支持断点续传/增量更新）
数据源: 新浪财经 (akshare stock_zh_a_daily, 前复权)
说明: 东财接口在当前网络环境被限流, 改用新浪(全市场含北交所均验证可用)
起始日 2024-01-01: 为120日均线预留预热期
"""
import os
import sys
import time
import random
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import akshare as ak

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
KLINE_DIR = os.path.join(DATA_DIR, "kline")
START_DATE = "20240101"
MAX_WORKERS = 5

os.makedirs(KLINE_DIR, exist_ok=True)


def get_stock_universe() -> pd.DataFrame:
    """全A股列表(沪深京)，剔除ST/*ST/退市整理股/B股
    数据源: 交易所官网 (东财实时接口在当前网络不可用)
    """
    hs = ak.stock_info_a_code_name()  # 沪深
    hs = hs.rename(columns={"code": "code", "name": "name"})
    hs["code"] = hs["code"].astype(str).str.zfill(6)
    hs = hs[~hs["code"].str.startswith(("900", "200"))]  # 剔除B股
    bj = ak.stock_info_bj_name_code()  # 北交所
    bj = bj.rename(columns={"证券代码": "code", "证券简称": "name"})[["code", "name"]]
    bj["code"] = bj["code"].astype(str).str.zfill(6)
    df = pd.concat([hs, bj], ignore_index=True).drop_duplicates(subset=["code"])
    mask = ~df["name"].str.contains("ST|退", na=False)
    df = df[mask].reset_index(drop=True)
    return df


def to_sina_symbol(code: str) -> str:
    if code.startswith("6"):
        return "sh" + code
    if code.startswith(("0", "3")):
        return "sz" + code
    return "bj" + code  # 北交所 920/8/4 开头


def kline_path(code: str) -> str:
    return os.path.join(KLINE_DIR, f"{code}.parquet")


def fetch_one(code: str, name: str, end_date: str) -> tuple:
    """拉取单只股票日线，已存在则增量更新。返回 (code, ok, rows|err)"""
    path = kline_path(code)
    start = START_DATE
    old = None
    if os.path.exists(path):
        try:
            old = pd.read_parquet(path)
            if len(old) > 0:
                last_date = old["date"].max()
                if str(last_date) >= end_date:
                    return (code, True, 0)
                start = (pd.Timestamp(last_date) + pd.Timedelta(days=1)).strftime("%Y%m%d")
        except Exception:
            old = None
    time.sleep(random.uniform(0.03, 0.12))  # 随机延时防限流
    df = None
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_daily(symbol=to_sina_symbol(code),
                                     start_date=start, end_date=end_date, adjust="qfq")
            break
        except Exception:
            if attempt == 2:
                return (code, False, "fetch fail x3")
            time.sleep(1.0 * (attempt + 1))
    try:
        if df is None or len(df) == 0:
            return (code, old is not None, 0)
        df = df[["date", "open", "close", "high", "low", "volume", "amount"]].copy()
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df["code"] = code
        df["name"] = name
        if old is not None and len(old) > 0:
            df = pd.concat([old, df], ignore_index=True).drop_duplicates(
                subset=["date"], keep="last")
        df.to_parquet(path, index=False)
        return (code, True, len(df))
    except Exception as e:
        return (code, False, str(e))


def run():
    end_date = dt.datetime.now().strftime("%Y%m%d")
    universe = get_stock_universe()
    print(f"股票池: {len(universe)} 只 (剔除ST/退市/B股)", flush=True)
    universe.to_csv(os.path.join(DATA_DIR, "universe.csv"), index=False, encoding="utf-8-sig")

    ok, fail = 0, 0
    errors = []
    t0 = time.time()
    total = len(universe)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(fetch_one, r.code, r.name, end_date): r.code
                for r in universe.itertuples()}
        for i, fut in enumerate(as_completed(futs), 1):
            code, success, info = fut.result()
            if success:
                ok += 1
            else:
                fail += 1
                errors.append((code, info))
            if i % 200 == 0 or i == total:
                el = time.time() - t0
                eta = el / i * (total - i)
                print(f"进度 {i}/{total}  成功{ok} 失败{fail}  "
                      f"用时{el:.0f}s 预计剩余{eta:.0f}s", flush=True)
    print(f"完成: 成功{ok} 失败{fail}", flush=True)
    if errors:
        pd.DataFrame(errors, columns=["code", "err"]).to_csv(
            os.path.join(DATA_DIR, "fetch_errors.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    rc = 0
    try:
        run()
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else 0
    except Exception:
        rc = 1
    finally:
        # 强制退出：绕过 akshare/requests 经本地代理退出时的连接清理挂起
        # （表现为进程退出阶段 CPU 归零、仅剩 127.0.0.1 代理连接、卡死数十分钟）
        try:
            sys.stdout.flush(); sys.stderr.flush()
        except Exception:
            pass
        os._exit(rc)
