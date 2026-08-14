# -*- coding: utf-8 -*-
"""指标计算层: 读取本地kline缓存 -> 计算市场宽度/平均股价/行业宽度 -> dashboard_data.json"""
import os
import json
import glob
import datetime as dt
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
KLINE_DIR = os.path.join(DATA_DIR, "kline")
OUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUT_DIR, exist_ok=True)

DISPLAY_START = "2025-01-01"  # 展示起点
MA_WINDOWS = [5, 10, 20, 50, 120]


def load_all_kline() -> pd.DataFrame:
    """加载全部kline -> 长表 (date, code, close)"""
    files = glob.glob(os.path.join(KLINE_DIR, "*.parquet"))
    print(f"kline文件 {len(files)} 个", flush=True)
    frames = []
    for i, f in enumerate(files, 1):
        try:
            df = pd.read_parquet(f, columns=["date", "code", "close"])
            frames.append(df)
        except Exception:
            pass
        if i % 1000 == 0:
            print(f"  加载 {i}/{len(files)}", flush=True)
    all_df = pd.concat(frames, ignore_index=True)
    all_df = all_df.dropna(subset=["close"])
    return all_df


def compute_breadth(df: pd.DataFrame):
    """计算市场宽度: 每交易日 收盘价>MA_N 的股票占比; 及全市场平均股价
    次新股规则: K线数不足N的股票当日不计入该周期分母
    """
    print("透视收盘价矩阵...", flush=True)
    close = df.pivot(index="date", columns="code", values="close").sort_index()
    print(f"矩阵: {close.shape[0]} 交易日 x {close.shape[1]} 股票", flush=True)

    # 每只股票每日的有效K线计数(截至当日)
    valid_count = close.notna().cumsum()

    result = pd.DataFrame(index=close.index)
    for n in MA_WINDOWS:
        ma = close.rolling(n, min_periods=n).mean()
        above = (close > ma) & close.notna() & (valid_count >= n)
        denom = (close.notna() & (valid_count >= n)).sum(axis=1)
        result[f"b{n}"] = (above.sum(axis=1) / denom.replace(0, np.nan) * 100).round(2)
        print(f"  MA{n} 宽度完成", flush=True)

    # 平均股价: 当日有收盘价股票的均值
    result["avg_price"] = close.mean(axis=1).round(2)
    result["stock_cnt"] = close.notna().sum(axis=1)

    result = result[result.index >= DISPLAY_START]
    return result


def compute_industry_breadth(df: pd.DataFrame, sw2: pd.DataFrame):
    """申万二级行业: 最新交易日各行业站上MA5/MA10比例 + 周变化
    周变化 = 最近5个交易日前后的比例差(本周最后一个交易日 vs 上周最后一个交易日)
    """
    close = df.pivot(index="date", columns="code", values="close").sort_index()
    valid_count = close.notna().cumsum()
    ma5 = close.rolling(5, min_periods=5).mean()
    ma10 = close.rolling(10, min_periods=10).mean()
    above5 = (close > ma5) & (valid_count >= 5)
    above10 = (close > ma10) & (valid_count >= 10)
    denom5 = (close.notna() & (valid_count >= 5))
    denom10 = (close.notna() & (valid_count >= 10))

    dates = close.index.tolist()
    latest = dates[-1]
    week_ago = dates[-6] if len(dates) >= 6 else dates[0]

    # 行业 -> 成分代码映射
    ind_map = sw2.groupby("ind_name")["code"].apply(list).to_dict()
    rows = []
    for ind, codes in ind_map.items():
        cols = [c for c in codes if c in close.columns]
        if len(cols) < 3:
            continue
        def ratio(above, denom, day):
            d = denom.loc[day].reindex(cols).fillna(False)
            if d.sum() == 0:
                return np.nan
            return round(above.loc[day].reindex(cols).fillna(False).sum() / d.sum() * 100, 1)
        r5_now = ratio(above5, denom5, latest)
        r10_now = ratio(above10, denom10, latest)
        r5_prev = ratio(above5, denom5, week_ago)
        r10_prev = ratio(above10, denom10, week_ago)
        rows.append({
            "industry": ind,
            "n_stocks": len(cols),
            "pct5": r5_now, "pct10": r10_now,
            "pct5_prev": r5_prev, "pct10_prev": r10_prev,
            "chg5": round(r5_now - r5_prev, 1) if pd.notna(r5_now) and pd.notna(r5_prev) else None,
            "chg10": round(r10_now - r10_prev, 1) if pd.notna(r10_now) and pd.notna(r10_prev) else None,
        })
    ind_df = pd.DataFrame(rows)
    # 综合变化分: 5日与10日周变化均值, 用于排序
    ind_df["score"] = ind_df[["chg5", "chg10"]].mean(axis=1)
    ind_df = ind_df.sort_values("score", ascending=False)
    return ind_df, latest, week_ago


def build_sw3_equal_index():
    """申万三级 半导体材料/设备 成分自建等权指数(近半个月)"""
    end = dt.datetime.now().strftime("%Y-%m-%d")
    start = (dt.datetime.now() - dt.timedelta(days=40)).strftime("%Y-%m-%d")
    out = {}
    for label in ["半导体材料", "半导体设备"]:
        f = os.path.join(DATA_DIR, f"sw3_{label}.csv")
        if not os.path.exists(f):
            print(f"缺少 {f}", flush=True)
            continue
        comp = pd.read_csv(f, dtype={"code": str})
        frames = []
        for code in comp["code"]:
            p = os.path.join(KLINE_DIR, f"{code}.parquet")
            if os.path.exists(p):
                d = pd.read_parquet(p, columns=["date", "close"])
                d = d[(d["date"] >= start) & (d["date"] <= end)]
                d["code"] = code
                frames.append(d)
        if not frames:
            continue
        alld = pd.concat(frames)
        px = alld.pivot(index="date", columns="code", values="close").sort_index()
        ret = px.pct_change()
        eq = (1 + ret.mean(axis=1)).cumprod() * 100  # 等权日收益累计, 基点100
        eq.iloc[0] = 100
        out[label] = pd.DataFrame({"date": eq.index, "close": eq.values.round(2)})
        print(f"等权指数[{label}] {len(eq)}日 成分{px.shape[1]}只", flush=True)
    return out


def collect_sectors(sw3_idx: dict):
    """汇总10个板块序列(近半个月), 统一归一化到首日=100 便于对比"""
    sectors = {}
    # THS板块: 归一化
    for f in glob.glob(os.path.join(DATA_DIR, "sector_*.csv")):
        label = os.path.basename(f)[len("sector_"):-len(".csv")]
        df = pd.read_csv(f)
        df = df.sort_values("date")
        base = df["close"].iloc[0]
        sectors[label] = {
            "dates": df["date"].tolist(),
            "values": (df["close"] / base * 100).round(2).tolist(),
        }
    # 申万三级等权: 已归一化(首日=100)
    for label, df in sw3_idx.items():
        df = df.sort_values("date")
        base = df["close"].iloc[0]
        sectors[label] = {
            "dates": df["date"].tolist(),
            "values": (df["close"] / base * 100).round(2).tolist(),
        }
    return sectors


def collect_pcr():
    """期权PCR: 510300/510500/588000"""
    f = os.path.join(DATA_DIR, "option_pcr.csv")
    if not os.path.exists(f):
        return {}
    pcr = pd.read_csv(f, dtype={"code": str})
    out = {}
    name_map = {"510300": "沪深300ETF", "510500": "中证500ETF", "588000": "科创50ETF"}
    for code, label in name_map.items():
        sub = pcr[pcr["code"] == code].sort_values("date")
        sub = sub[sub["date"] >= DISPLAY_START]
        out[label] = {
            "dates": sub["date"].tolist(),
            "values": (sub["pcr_vol"] / 100).round(3).tolist(),  # 原始是百分数口径, 转为比率
        }
    return out


def run():
    df = load_all_kline()

    # 1. 市场宽度 + 平均股价
    breadth = compute_breadth(df)
    breadth.index.name = "date"

    # 2. 申万二级行业宽度
    sw2f = os.path.join(DATA_DIR, "sw2_components.csv")
    ind_df, latest, week_ago = None, None, None
    if os.path.exists(sw2f):
        sw2 = pd.read_csv(sw2f, dtype={"code": str})
        ind_df, latest, week_ago = compute_industry_breadth(df, sw2)
        print(f"行业宽度: {len(ind_df)}个行业, 最新日{latest} 对比基准{week_ago}", flush=True)

    # 3. 申万三级等权指数 + 板块汇总
    sw3_idx = build_sw3_equal_index()
    sectors = collect_sectors(sw3_idx)

    # 4. 期权PCR
    pcr = collect_pcr()

    # 组装JSON
    payload = {
        "meta": {
            "updated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "data_start": DISPLAY_START,
            "latest_trade_date": breadth.index[-1],
            "stock_count": int(breadth["stock_cnt"].iloc[-1]),
            "industry_compare": {"latest": latest, "week_ago": week_ago},
        },
        "breadth": {
            "dates": breadth.index.tolist(),
            "b5": breadth["b5"].tolist(),
            "b10": breadth["b10"].tolist(),
            "b20": breadth["b20"].tolist(),
            "b50": breadth["b50"].tolist(),
            "b120": breadth["b120"].tolist(),
            "avg_price": breadth["avg_price"].tolist(),
        },
        "industry": ind_df.to_dict("records") if ind_df is not None else [],
        "sectors": sectors,
        "pcr": pcr,
    }
    out_path = os.path.join(OUT_DIR, "dashboard_data.json")
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False)
    print(f"输出 {out_path}", flush=True)
    print(f"宽度区间: {breadth.index[0]} ~ {breadth.index[-1]}, {len(breadth)}交易日", flush=True)
    print(breadth.tail(3).to_string(), flush=True)


if __name__ == "__main__":
    run()
