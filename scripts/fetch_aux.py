# -*- coding: utf-8 -*-
"""辅助数据拉取:
1. 关注板块指数历史(THS概念/行业指数, 近1个月)
2. 申万三级[半导体材料/半导体设备]成分股名单 -> 自建等权指数
3. 上交所期权每日统计(PCR): 510300/510500/588000, 2025-01-01至今
4. 申万二级行业成分名单(131个行业, 来源 sw_index_second_info) -> 供行业宽度计算
"""
import os
import sys
import time
import datetime as dt
import pandas as pd
import akshare as ak

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 板块映射: (展示名, 类型, 代码/名称)
# THS概念/行业指数直接拉历史; 申万三级用成分自建等权指数
SECTOR_MAP = [
    ("半导体材料", "sw3", "半导体材料"),
    ("半导体设备", "sw3", "半导体设备"),
    ("半导体芯片", "ths_ind", "半导体"),
    ("算力租赁",   "ths_con", "算力租赁"),
    ("云服务器",   "ths_con", "云计算"),
    ("端侧",       "ths_ind", "消费电子"),
    ("电力",       "ths_ind", "电力"),
    ("光通信",     "ths_con", "共封装光学(CPO)"),
    ("券商",       "ths_ind", "证券"),
    ("传媒",       "ths_ind", "文化传媒"),
]

def fetch_ths_sectors():
    """拉THS概念/行业指数近1个月日线"""
    end = dt.datetime.now().strftime("%Y%m%d")
    start = (dt.datetime.now() - dt.timedelta(days=40)).strftime("%Y%m%d")
    out = {}
    for label, kind, name in SECTOR_MAP:
        if kind not in ("ths_ind", "ths_con"):
            continue
        for attempt in range(3):
            try:
                if kind == "ths_ind":
                    df = ak.stock_board_industry_index_ths(symbol=name, start_date=start, end_date=end)
                else:
                    df = ak.stock_board_concept_index_ths(symbol=name, start_date=start, end_date=end)
                df = df[["日期", "收盘价"]].rename(columns={"日期": "date", "收盘价": "close"})
                df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                out[label] = df
                print(f"板块[{label} <- THS {name}] OK {len(df)}行", flush=True)
                break
            except Exception as e:
                print(f"板块[{label}] attempt{attempt} FAIL {repr(e)[:80]}", flush=True)
                time.sleep(2)
    return out

def fetch_sw3_components():
    """申万三级成分(半导体材料/设备) + 全部二级行业成分"""
    third = ak.sw_index_third_info()
    sw3 = {}
    for label, kind, name in SECTOR_MAP:
        if kind != "sw3":
            continue
        row = third[third["行业名称"] == name]
        if len(row) == 0:
            print(f"申万三级[{name}]未找到", flush=True)
            continue
        code = str(row["行业代码"].iloc[0]).split(".")[0]
        for attempt in range(3):
            try:
                comp = ak.index_component_sw(symbol=code)
                comp = comp[["证券代码", "证券名称"]].rename(
                    columns={"证券代码": "code", "证券名称": "name"})
                comp["code"] = comp["code"].astype(str).str.zfill(6)
                sw3[label] = comp
                print(f"申万三级[{label} <- {code}] 成分{len(comp)}只", flush=True)
                break
            except Exception as e:
                print(f"申万三级[{name}] attempt{attempt} FAIL {repr(e)[:80]}", flush=True)
                time.sleep(2)
    return sw3

def fetch_sw2_components():
    """申万二级全部行业成分名单 (来源: sw_index_second_info, 完整131个)"""
    sw2 = ak.sw_index_second_info()
    sw2 = sw2[["行业代码", "行业名称"]].rename(
        columns={"行业代码": "ind_code", "行业名称": "ind_name"})
    records = []
    for i, row in enumerate(sw2.itertuples(), 1):
        code = str(row.ind_code).split(".")[0]
        for attempt in range(3):
            try:
                comp = ak.index_component_sw(symbol=code)
                comp["ind_code"] = code
                comp["ind_name"] = row.ind_name
                records.append(comp[["证券代码", "ind_code", "ind_name"]])
                break
            except Exception as e:
                if attempt == 2:
                    print(f"申万二级[{row.ind_name}]成分拉取失败 {repr(e)[:60]}", flush=True)
                time.sleep(1.5)
        if i % 20 == 0:
            print(f"申万二级成分进度 {i}/{len(sw2)}", flush=True)
    allc = pd.concat(records, ignore_index=True)
    allc = allc.rename(columns={"证券代码": "code"})
    allc["code"] = allc["code"].astype(str).str.zfill(6)
    return allc

def fetch_option_pcr():
    """上交所期权每日统计: 逐交易日拉取 PCR"""
    # 生成交易日列表: 用已拉取的kline数据的日期(确保真实交易日)
    kline_dir = os.path.join(DATA_DIR, "kline")
    trade_dates = None
    if os.path.exists(kline_dir):
        files = sorted(os.listdir(kline_dir))
        if files:
            df = pd.read_parquet(os.path.join(kline_dir, files[0]))
            trade_dates = sorted(df["date"].unique())
    if trade_dates is None:
        # 回退: 上证指数交易日
        idx = ak.stock_zh_index_daily(symbol="sh000001")
        idx["date"] = pd.to_datetime(idx["date"]).dt.strftime("%Y-%m-%d")
        trade_dates = sorted(idx[idx["date"] >= "2025-01-01"]["date"].tolist())
    print(f"PCR交易日数: {len(trade_dates)}", flush=True)
    rows = []
    for i, d in enumerate(trade_dates, 1):
        dstr = d.replace("-", "")
        for attempt in range(3):
            try:
                df = ak.option_daily_stats_sse(date=dstr)
                for _, r in df.iterrows():
                    rows.append({
                        "date": d,
                        "code": str(r["合约标的代码"]),
                        "name": str(r["合约标的名称"]),
                        "call_vol": float(r["认购成交量"]),
                        "put_vol": float(r["认沽成交量"]),
                        "pcr_vol": float(r["认沽/认购"]),
                    })
                break
            except Exception as e:
                if attempt == 2:
                    print(f"PCR[{d}]失败 {repr(e)[:60]}", flush=True)
                time.sleep(1)
        if i % 50 == 0 or i == len(trade_dates):
            print(f"PCR进度 {i}/{len(trade_dates)}", flush=True)
        time.sleep(0.15)
    pcr = pd.DataFrame(rows)
    return pcr

def run():
    print("=== 1. THS板块指数 ===", flush=True)
    ths = fetch_ths_sectors()
    for label, df in ths.items():
        df.to_csv(os.path.join(DATA_DIR, f"sector_{label}.csv"), index=False, encoding="utf-8-sig")

    print("=== 2. 申万三级成分(半导体材料/设备) ===", flush=True)
    sw3 = fetch_sw3_components()
    for label, df in sw3.items():
        df.to_csv(os.path.join(DATA_DIR, f"sw3_{label}.csv"), index=False, encoding="utf-8-sig")

    print("=== 3. 申万二级全行业成分 ===", flush=True)
    sw2c = fetch_sw2_components()
    sw2c.to_csv(os.path.join(DATA_DIR, "sw2_components.csv"), index=False, encoding="utf-8-sig")
    print(f"申万二级成分总数 {len(sw2c)} 条, 行业数 {sw2c['ind_name'].nunique()}", flush=True)

    print("=== 4. 期权PCR ===", flush=True)
    pcr = fetch_option_pcr()
    pcr.to_csv(os.path.join(DATA_DIR, "option_pcr.csv"), index=False, encoding="utf-8-sig")
    print(f"PCR记录 {len(pcr)} 条", flush=True)
    print("全部辅助数据完成", flush=True)

if __name__ == "__main__":
    run()
