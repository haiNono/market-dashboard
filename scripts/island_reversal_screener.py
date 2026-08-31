# -*- coding: utf-8 -*-
"""孤岛反转选股脚本

形态定义（严格无重叠缺口 + 放量确认）：
  1. 向下跳空日 D1：当日最高价 < 前一交易日最低价（D1.high < prev.low），向下缺口区间 (D1.high, prev.low) 不为空
  2. 向上跳空日 D2：D1 < D2 <= D1 + 30 个交易日，且当日最低价 > 前一交易日最高价（D2.low > prev.high），向上缺口区间 (prev.high, D2.low) 不为空
  3. 孤岛不回补：D1 到 D2-1 之间（含）所有交易日的最高价都 < D1.prev.low（向下缺口从未被回补，孤岛完全位于缺口下方）
  4. 放量确认：D2 当日成交量 >= 过去 5 个交易日平均成交量的 2 倍

停牌处理：用全市场交易日历对齐，若某股两个相邻记录在交易日历上不相邻（中间停牌），
          则后一天的缺口判定无效，避免停牌复牌后的价格跳跃被误判为缺口。

数据源：data/kline/*.parquet（akshare stock_zh_a_daily，前复权 qfq）

用法：
  python island_reversal_screener.py                 # 默认扫描最近 90 个交易日
  python island_reversal_screener.py --days 250      # 扫描最近 250 个交易日
  python island_reversal_screener.py --days 0        # 0 = 扫描全部历史
  python island_reversal_screener.py --vol-ma 10 --vol-ratio 2.0   # 自定义量能参数
"""
import os
import sys
import time
import argparse
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KLINE_DIR = os.path.join(BASE_DIR, "data", "kline")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "island_reversal_signals.csv")


def build_trading_calendar(kline_dir):
    """用 000001 平安银行（永不退市的权重基准）的 date 序列作为全市场交易日历。"""
    ref_path = os.path.join(kline_dir, "000001.parquet")
    if not os.path.exists(ref_path):
        # 退化方案：扫第一个 parquet
        files = sorted(f for f in os.listdir(kline_dir) if f.endswith(".parquet"))
        if not files:
            raise RuntimeError(f"kline 目录为空: {kline_dir}")
        ref_path = os.path.join(kline_dir, files[0])
    ref = pd.read_parquet(ref_path, columns=["date"])
    cal = ref["date"].astype(str).tolist()
    cal_sorted = sorted(cal)
    cal_index = {d: i for i, d in enumerate(cal_sorted)}
    return cal_sorted, cal_index


def screen_one(df, cal_index, island_max_days=30, vol_ma=5, vol_ratio_min=2.0):
    """对单只股票检测孤岛反转信号。

    df: 含 date/open/close/high/low/volume/code/name 的 DataFrame，按 date 升序。
    返回 list[dict]，每个 dict 为一条信号。
    """
    n = len(df)
    if n < vol_ma + 2:
        return []

    df = df.sort_values("date").reset_index(drop=True).copy()
    df["date"] = df["date"].astype(str)

    # 交易日历对齐：判断每条记录与前一条在交易日历上是否相邻
    df["cal_pos"] = df["date"].map(cal_index)
    # cal_pos 可能含 NaN（如果该股某天在基准日历里不存在，理论上不应发生）
    df["cal_pos_prev"] = df["cal_pos"].shift(1)
    df["cont"] = (df["cal_pos"] - df["cal_pos_prev"] == 1).fillna(False)

    # 前一日 OHLC
    df["prev_low"] = df["low"].shift(1)
    df["prev_high"] = df["high"].shift(1)

    # 量能均量：D2 前 vol_ma 日的平均成交量（不含 D2 当日）
    # rolling(vol_ma).mean() 在第 i 行 = mean(volume[i-vol_ma+1 : i+1])，含 i
    # shift(1) 后 = mean(volume[i-vol_ma : i])，不含 i → 正是 D2 前 vol_ma 日均量
    df["avg_vol"] = df["volume"].rolling(vol_ma).mean().shift(1)

    # 缺口判定（必须交易日历相邻，排除停牌复牌假缺口）
    gd_mask = df["cont"] & (df["high"] < df["prev_low"])      # 向下跳空
    gu_mask = df["cont"] & (df["low"] > df["prev_high"])      # 向上跳空

    gd_idx = np.where(gd_mask.values)[0]
    gu_idx = np.where(gu_mask.values)[0]

    if len(gd_idx) == 0 or len(gu_idx) == 0:
        return []

    high_arr = df["high"].values
    low_arr = df["low"].values
    prev_low_arr = df["prev_low"].values
    prev_high_arr = df["prev_high"].values
    vol_arr = df["volume"].values
    avg_vol_arr = df["avg_vol"].values
    date_arr = df["date"].values
    close_arr = df["close"].values

    code = df["code"].iloc[0]
    name = df["name"].iloc[0]

    signals = []
    for gu in gu_idx:
        # 量能确认
        avg_vol = avg_vol_arr[gu]
        if avg_vol is None or np.isnan(avg_vol) or avg_vol <= 0:
            continue
        vol_ratio = vol_arr[gu] / avg_vol
        if vol_ratio < vol_ratio_min:
            continue

        # 向前找 gap_down：从离 gu 最近的开始（保证取最近一个成立的孤岛）
        # gd 必须满足：gd < gu, gu - gd <= island_max_days
        # 反向遍历 gd_idx
        for gd in reversed(gd_idx):
            if gd >= gu:
                continue
            if gd < gu - island_max_days:
                break  # 再往前更远，超出窗口
            # 孤岛不回补：D1..D2-1 之间所有 high < D1.prev_low
            gap_down_prev_low = prev_low_arr[gd]
            if np.isnan(gap_down_prev_low):
                continue
            island_high_max = high_arr[gd:gu].max()  # [gd, gu-1]
            if island_high_max >= gap_down_prev_low:
                continue  # 孤岛期间回补了向下缺口，不成立

            # 孤岛反转成立
            gap_up_prev_high = prev_high_arr[gu]
            signals.append({
                "code": code,
                "name": name,
                "gap_down_date": date_arr[gd],
                "gap_down_prev_low": round(float(gap_down_prev_low), 3),
                "gap_down_high": round(float(high_arr[gd]), 3),
                "gap_down_pct": round(float((gap_down_prev_low - high_arr[gd]) / gap_down_prev_low * 100), 2),
                "gap_up_date": date_arr[gu],
                "gap_up_prev_high": round(float(gap_up_prev_high), 3),
                "gap_up_low": round(float(low_arr[gu]), 3),
                "gap_up_pct": round(float((low_arr[gu] - gap_up_prev_high) / gap_up_prev_high * 100), 2),
                "island_days": int(gu - gd),
                "island_max_high": round(float(island_high_max), 3),
                "volume_ratio": round(float(vol_ratio), 2),
                "gap_up_volume": int(vol_arr[gu]),
                "gap_up_close": round(float(close_arr[gu]), 3),
            })
            break  # 同一个 gap_up 只取最近一个成立的 gap_down

    return signals


def main():
    ap = argparse.ArgumentParser(description="孤岛反转选股：向下跳空后30日内放量向上跳空")
    ap.add_argument("--days", type=int, default=90,
                    help="只扫描最近 N 个交易日的信号（0=扫描全部历史，默认90）")
    ap.add_argument("--vol-ma", type=int, default=5, help="量能均量窗口（默认5）")
    ap.add_argument("--vol-ratio", type=float, default=2.0, help="量能倍数下限（默认2.0）")
    ap.add_argument("--island-max-days", type=int, default=30, help="向下跳空后多少日内出现向上跳空（默认30）")
    args = ap.parse_args()

    if not os.path.isdir(KLINE_DIR):
        print(f"[错误] kline 目录不存在: {KLINE_DIR}")
        sys.exit(1)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    files = sorted(f for f in os.listdir(KLINE_DIR) if f.endswith(".parquet"))
    total = len(files)
    if total == 0:
        print(f"[错误] {KLINE_DIR} 下无 parquet 文件")
        sys.exit(1)

    print(f"数据目录: {KLINE_DIR}")
    print(f"待扫描股票数: {total}")
    print(f"参数: days={args.days}, vol_ma={args.vol_ma}, vol_ratio>={args.vol_ratio}, island<={args.island_max_days}")

    cal_sorted, cal_index = build_trading_calendar(KLINE_DIR)
    print(f"交易日历基准: {cal_sorted[0]} -> {cal_sorted[-1]}, 共 {len(cal_sorted)} 个交易日")

    # 确定扫描窗口下界
    if args.days > 0:
        scan_start_date = cal_sorted[max(0, len(cal_sorted) - args.days)]
        # 多取 vol_ma + island_max_days 的前置，保证窗口边界处的量能/缺口判定有足够前置数据
        warmup = args.vol_ma + args.island_max_days + 5
        load_start_idx = max(0, len(cal_sorted) - args.days - warmup)
        load_start_date = cal_sorted[load_start_idx]
    else:
        scan_start_date = cal_sorted[0]
        load_start_date = cal_sorted[0]
    print(f"信号扫描下界: {scan_start_date}（数据加载下界 {load_start_date}，含 warmup）")

    all_signals = []
    loaded = 0
    skipped = 0
    t0 = time.time()
    for i, fn in enumerate(files, 1):
        try:
            df = pd.read_parquet(os.path.join(KLINE_DIR, fn))
        except Exception:
            skipped += 1
            continue
        if df is None or len(df) == 0:
            skipped += 1
            continue
        loaded += 1
        # 只加载 load_start_date 之后的数据（含 warmup）
        df = df[df["date"].astype(str) >= load_start_date].copy()
        if len(df) < args.vol_ma + 2:
            continue
        sigs = screen_one(df, cal_index,
                          island_max_days=args.island_max_days,
                          vol_ma=args.vol_ma,
                          vol_ratio_min=args.vol_ratio)
        if sigs:
            # 只保留 gap_up_date >= scan_start_date 的信号
            sigs = [s for s in sigs if str(s["gap_up_date"]) >= scan_start_date]
            all_signals.extend(sigs)
        if i % 1000 == 0:
            print(f"  进度 {i}/{total}，已加载 {loaded}，跳过 {skipped}，累计信号 {len(all_signals)}，耗时 {time.time()-t0:.1f}s")

    elapsed = time.time() - t0
    print(f"\n扫描完成：共 {total} 文件，成功加载 {loaded}，跳过 {skipped}，耗时 {elapsed:.1f}s")
    print(f"命中信号数: {len(all_signals)}")

    if not all_signals:
        print("[警告] 未发现满足条件的孤岛反转信号")
        # 仍写出空 CSV（带表头）
        cols = ["code", "name", "gap_down_date", "gap_down_prev_low", "gap_down_high", "gap_down_pct",
                "gap_up_date", "gap_up_prev_high", "gap_up_low", "gap_up_pct", "island_days",
                "island_max_high", "volume_ratio", "gap_up_volume", "gap_up_close"]
        pd.DataFrame(columns=cols).to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
        print(f"空清单已写入: {OUTPUT_CSV}")
        return

    out = pd.DataFrame(all_signals)
    # 按向上跳空日降序（最新在前），同日按量能倍数降序
    out = out.sort_values(["gap_up_date", "volume_ratio"], ascending=[False, False]).reset_index(drop=True)
    out.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"信号清单已写入: {OUTPUT_CSV}")
    print(f"  信号时间范围: {out['gap_up_date'].min()} -> {out['gap_up_date'].max()}")
    print(f"  涉及股票数: {out['code'].nunique()}")
    print(f"  孤岛天数中位数: {out['island_days'].median()}，均值: {out['island_days'].mean():.1f}")
    print(f"  量能倍数中位数: {out['volume_ratio'].median()}，最大: {out['volume_ratio'].max():.1f}")
    print(f"\n最新 10 条信号:")
    print(out.head(10)[["code", "name", "gap_down_date", "gap_up_date", "island_days",
                         "gap_down_pct", "gap_up_pct", "volume_ratio"]].to_string(index=False))


if __name__ == "__main__":
    main()
