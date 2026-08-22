# -*- coding: utf-8 -*-
"""
拉取两融余额与融资占比数据 -> data/margin.json
序列（日频, 2025-01-01 起）：
  total  两融余额合计（沪深之和, 亿元）
  sh     上交所融资融券余额（亿元）
  sz     深交所融资融券余额（亿元）
  ratio  两融余额 / 沪深总市值（%），总市值=沪深交易所月度市价总值线性插值到日频
数据源: akshare macro_china_market_margin_sh / macro_china_market_margin_sz / macro_china_stock_market_cap
"""
import os
import json
import datetime
import akshare as ak
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "margin.json")
START = "2025-01-01"


def fetch():
    sh = ak.macro_china_market_margin_sh()
    sz = ak.macro_china_market_margin_sz()
    sh["日期"] = pd.to_datetime(sh["日期"]).dt.strftime("%Y-%m-%d")
    sz["日期"] = pd.to_datetime(sz["日期"]).dt.strftime("%Y-%m-%d")
    sh = sh[sh["日期"] >= START].set_index("日期")
    sz = sz[sz["日期"] >= START].set_index("日期")

    dates = sorted(set(sh.index) | set(sz.index))
    rows = []
    for d in dates:
        shv = sh.loc[d, "融资融券余额"] if d in sh.index else np.nan
        szv = sz.loc[d, "融资融券余额"] if d in sz.index else np.nan
        rows.append({"date": d, "sh": float(shv) / 1e8, "sz": float(szv) / 1e8})  # 元->亿元
    df = pd.DataFrame(rows).set_index("date")
    df["total"] = df["sh"].fillna(0) + df["sz"].fillna(0)
    # 个别缺失日（单边未发布）用前后填充
    df = df.ffill().bfill()

    # 沪深月度市价总值（亿元）-> 日频线性插值
    cap = ak.macro_china_stock_market_cap().sort_values("数据日期")
    cap["月"] = pd.to_datetime(cap["数据日期"].str.replace("月份", "01"), format="%Y年%m%d")
    cap = cap.dropna(subset=["市价总值-上海", "市价总值-深圳"])
    cap["cap_total"] = cap["市价总值-上海"] + cap["市价总值-深圳"]  # 亿元
    cap_dates = pd.date_range(cap["月"].iloc[0], cap["月"].iloc[-1], freq="MS")
    cap_vals = np.interp(
        [d.timestamp() for d in cap_dates],
        [d.timestamp() for d in cap["月"]],
        cap["cap_total"].values,
    )
    cap_series = pd.Series(cap_vals, index=cap_dates)

    # 日频市值：取当月值；最新月（未完整）用最后一个月度值
    def cap_for(d):
        ts = pd.Timestamp(d)
        month = cap_series.index[cap_series.index <= ts]
        if len(month) == 0:
            return cap_series.iloc[0]
        return cap_series.loc[month[-1]]

    out_dates = list(df.index)
    caps = [cap_for(d) for d in out_dates]
    total_vals = df["total"].values
    ratio = np.array(total_vals) / np.array(caps) * 100.0

    result = {
        "dates": out_dates,
        "total": [round(v, 1) for v in total_vals],
        "sh": [round(v, 1) for v in df["sh"].values],
        "sz": [round(v, 1) for v in df["sz"].values],
        "ratio": [round(v, 3) for v in ratio],
        "meta": {
            "start": START,
            "unit": "亿元",
            "cap_note": "总市值=沪深交易所月度市价总值线性插值日频（最新完整月 %s）"
                        % cap["月"].iloc[-1].strftime("%Y-%m"),
            "latest": out_dates[-1],
            "latest_total_yi": round(float(total_vals[-1]), 1),
            "latest_ratio_pct": round(float(ratio[-1]), 3),
        },
    }
    with open(DATA_PATH, "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=1)
    return result


if __name__ == "__main__":
    r = fetch()
    print(f"[两融] 数据点 {len(r['dates'])}（{r['dates'][0]} ~ {r['dates'][-1]}）")
    print(f"[两融] 最新: 合计 {r['meta']['latest_total_yi']} 亿元 | 两融/总市值 {r['meta']['latest_ratio_pct']}%")
    print(f"[两融] 上交所末日 {r['sh'][-1]} 亿元 | 深交所末日 {r['sz'][-1]} 亿元")
