# -*- coding: utf-8 -*-
"""孤岛反转事件研究回测

形态：向下跳空后30日内放量向上跳空形成孤岛反转（信号由 island_reversal_screener.py 产生）
事件日 = 向上跳空日（gap_up_date）
买入 = 事件日 + 1 个交易日，以开盘价成交（无 look-ahead）
卖出 = 买入日 + N 个交易日，以收盘价成交
费用 = 0（事件研究默认，不扭曲平均收益）

持有期对比：5 / 10 / 20 个交易日

输出：
  island_reversal_trades.csv   每行一个事件+一个持有期
  island_reversal_summary.json 三组持有期的事件级统计
  index.html                   多tab对比仪表盘
"""
import os
import sys
import json
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KLINE_DIR = os.path.join(BASE_DIR, "data", "kline")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SIGNALS_CSV = os.path.join(OUTPUT_DIR, "island_reversal_signals.csv")
TRADES_CSV = os.path.join(OUTPUT_DIR, "island_reversal_trades.csv")
SUMMARY_JSON = os.path.join(OUTPUT_DIR, "island_reversal_summary.json")
DASHBOARD_HTML = os.path.join(OUTPUT_DIR, "island_reversal_index.html")

# 渲染依赖（expert 自带）
RENDER_DIR = os.path.join(
    os.path.expanduser("~"),
    ".workbuddy", "plugins", "marketplaces", "experts", "plugins",
    "strategy-backtest-expert", "skills", "quant-backtest-lab", "reference",
)
TEMPLATE_HTML = os.path.join(RENDER_DIR, "dashboard_template.html")

HOLDING_PERIODS = [5, 10, 20]


def build_trading_calendar(kline_dir):
    ref_path = os.path.join(kline_dir, "000001.parquet")
    ref = pd.read_parquet(ref_path, columns=["date"])
    cal = sorted(ref["date"].astype(str).tolist())
    return cal, {d: i for i, d in enumerate(cal)}


def load_kline(code):
    path = os.path.join(KLINE_DIR, f"{code}.parquet")
    if not os.path.exists(path):
        return None
    df = pd.read_parquet(path)
    df["date"] = df["date"].astype(str)
    return df.sort_values("date").reset_index(drop=True)


def compute_event_returns(signals_df, cal_index, holding_days):
    """对一组信号计算指定持有期的事件级收益。

    事件日 = gap_up_date
    买入日 = 事件日 +1 交易日，开盘价
    卖出日 = 买入日 + holding_days 交易日，收盘价
    """
    trades = []
    skipped = 0
    for _, sig in signals_df.iterrows():
        code = str(sig["code"]).zfill(6)
        name = str(sig["name"])
        event_date = str(sig["gap_up_date"])

        df = load_kline(code)
        if df is None:
            skipped += 1
            continue

        # 定位事件日在交易日历中的位置
        ev_pos = cal_index.get(event_date)
        if ev_pos is None:
            skipped += 1
            continue

        buy_pos = ev_pos + 1
        sell_pos = buy_pos + holding_days

        # 用日期字符串在 df 中定位行（更稳健，避免该股停牌导致位置偏移）
        buy_date = cal[buy_pos] if buy_pos < len(cal) else None
        sell_date = cal[sell_pos] if sell_pos < len(cal) else None
        if buy_date is None or sell_date is None:
            skipped += 1
            continue

        buy_row = df[df["date"] == buy_date]
        sell_row = df[df["date"] == sell_date]
        if buy_row.empty or sell_row.empty:
            # 该股在买入日或卖出日停牌（无数据）
            skipped += 1
            continue

        buy_price = float(buy_row["open"].iloc[0])
        sell_price = float(sell_row["close"].iloc[0])
        if buy_price <= 0 or sell_price <= 0:
            skipped += 1
            continue

        pnl_pct = (sell_price / buy_price - 1.0) * 100.0

        trades.append({
            "event_date": event_date,
            "code": code,
            "symbol": code,
            "name": name,
            "symbol_name": name,
            "label": f"{name} 孤岛反转",
            "entry_date": buy_date,
            "exit_date": sell_date,
            "entry_price": round(buy_price, 3),
            "exit_price": round(sell_price, 3),
            "pnl_pct": round(pnl_pct, 2),
            "holding_bars": holding_days,
        })
    return trades, skipped


def event_stats(trades):
    """计算事件级统计指标。"""
    if not trades:
        return {}
    rets = [t["pnl_pct"] for t in trades]
    ordered = sorted(rets)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 == 1 else (ordered[mid - 1] + ordered[mid]) / 2.0
    wins = sum(1 for r in rets if r > 0)
    return {
        "total_events": len(trades),
        "cumulative_return_pct": round(sum(rets), 2),
        "avg_return_pct": round(sum(rets) / len(rets), 2),
        "median_return_pct": round(median, 2),
        "win_rate_pct": round(wins / len(rets) * 100, 1),
        "best_trade_pct": round(max(rets), 2),
        "worst_trade_pct": round(min(rets), 2),
    }


def build_cumulative_curve(trades):
    """按事件日(entry_date)排序的累计 pnl_pct 曲线，同日多事件聚合为一个点。"""
    if not trades:
        return []
    # 按日期聚合：同一天的所有事件 pnl_pct 求和
    daily = {}
    for t in trades:
        d = t["entry_date"]
        daily[d] = daily.get(d, 0.0) + t["pnl_pct"]
    cum = 0.0
    curve = []
    for d in sorted(daily.keys()):
        cum += daily[d]
        curve.append({"date": d, "value": round(100.0 + cum, 2)})
    return curve


def fmt_pct(v, suffix="%"):
    if v is None:
        return "--"
    return f"{v:,.2f}{suffix}"


def build_report_data(all_trades, all_stats, language="zh"):
    """手动构建多 tab 对比 report_data。"""
    import html as html_mod

    # --- 公共数据 ---
    meta = {
        "strategy_name": "孤岛反转事件研究",
        "report_kind": "event_study",
        "event_overview_mode": "both",
        "market": "china_a",
        "start": "2026-04-21",
        "end": "2026-08-28",
    }

    # 主 trades（用10日持有期作为 overview tab 的主数据，因为它居中）
    main_hp = 10
    main_trades = all_trades[main_hp]
    main_summary = all_stats[main_hp]
    main_curve = build_cumulative_curve(main_trades)

    # 累计收益对比曲线（line_chart）
    comp_series = []
    colors = {5: "#f23645", 10: "#ff9800", 20: "#2196f3"}
    for hp in HOLDING_PERIODS:
        curve = build_cumulative_curve(all_trades[hp])
        comp_series.append({
            "name": f"持有{hp}日",
            "stroke": colors[hp],
            "points": curve,
        })

    # --- KPI / metric 对比表 ---
    metric_rows = []
    metric_labels = {
        "total_events": "事件总数",
        "cumulative_return_pct": "累计收益",
        "avg_return_pct": "平均收益",
        "median_return_pct": "中位数收益",
        "win_rate_pct": "胜率",
        "best_trade_pct": "最佳单事件",
        "worst_trade_pct": "最差单事件",
    }
    for key, label in metric_labels.items():
        vals = []
        for hp in HOLDING_PERIODS:
            v = all_stats[hp].get(key)
            if key == "total_events":
                vals.append({"main": str(v) if v is not None else "--"})
            else:
                vals.append({"main": fmt_pct(v), "raw": v})
        metric_rows.append({"metric": label, "values": vals})

    # --- 事件标记（每个持有期 tab 独立） ---
    def build_markers(trades):
        markers = []
        for t in trades:
            markers.append({
                "date": t["entry_date"],
                "action": "event",
                "price": t["entry_price"],
                "symbol": t["symbol_name"],
                "label": t["label"],
                "pnl_pct": t["pnl_pct"],
                "entry_date": t["entry_date"],
                "exit_date": t["exit_date"],
            })
        return markers

    # --- trades_table 列定义 ---
    trade_columns = [
        {"key": "label", "label": "事件", "format": "text"},
        {"key": "symbol_name", "label": "股票", "format": "text"},
        {"key": "entry_date", "label": "买入日", "format": "text"},
        {"key": "exit_date", "label": "卖出日", "format": "text"},
        {"key": "entry_price", "label": "买入价", "format": "number"},
        {"key": "exit_price", "label": "卖出价", "format": "number"},
        {"key": "pnl_pct", "label": "收益率", "format": "pct"},
    ]

    # --- 组装 modules ---
    modules = []

    # Tab1: 对比
    modules.append({
        "type": "metric_table",
        "tab": "compare",
        "title": "持有期对比",
        "subtitle": "孤岛反转信号 · 5/10/20日持有期事件级统计",
        "columns": ["指标", "持有5日", "持有10日", "持有20日"],
        "rows": metric_rows,
    })
    modules.append({
        "type": "line_chart",
        "tab": "compare",
        "title": "累计事件收益曲线对比",
        "subtitle": "按信号触发日排序的累计 pnl_pct（基准=100）",
        "series": comp_series,
    })

    # Tab2/3/4: 每个持有期
    tab_names = {5: "hp5", 10: "hp10", 20: "hp20"}
    for hp in HOLDING_PERIODS:
        tab_id = tab_names[hp]
        trades = all_trades[hp]
        stats = all_stats[hp]
        curve = build_cumulative_curve(trades)
        markers = build_markers(trades)

        kpi_stats = [
            {"label": "累计收益", "value": fmt_pct(stats.get("cumulative_return_pct")), "raw": stats.get("cumulative_return_pct")},
            {"label": "事件数", "value": str(stats.get("total_events", 0))},
            {"label": "胜率", "value": fmt_pct(stats.get("win_rate_pct")), "raw": stats.get("win_rate_pct")},
            {"label": "平均收益", "value": fmt_pct(stats.get("avg_return_pct")), "raw": stats.get("avg_return_pct")},
            {"label": "中位数", "value": fmt_pct(stats.get("median_return_pct")), "raw": stats.get("median_return_pct")},
        ]

        # drawdown curve for this tab
        dd_curve = []
        peak = None
        for pt in curve:
            v = pt["value"]
            peak = v if peak is None else max(peak, v)
            dd_pct = 0.0 if not peak else (v / peak - 1.0) * 100.0
            dd_curve.append({"date": pt["date"], "drawdown_pct": dd_pct, "drawdown_abs": peak - v})

        # merge points
        points = []
        dd_map = {d["date"]: d for d in dd_curve}
        for pt in curve:
            dd = dd_map.get(pt["date"], {})
            points.append({
                "date": pt["date"],
                "equity": pt["value"],
                "drawdown_abs": abs(dd.get("drawdown_abs", 0)),
                "pnl": pt["value"] - 100.0,
            })

        modules.append({
            "type": "overview_chart",
            "tab": tab_id,
            "width": "full",
            "stats": kpi_stats,
            "points": points,
            "markers": markers,
            "series_key": "equity",
            "stroke": colors[hp],
            "area_fill": "rgba(181,126,255,0.18)",
            "bars_key": "drawdown_abs",
            "bars_fill": "rgba(181,126,255,0.32)",
            "toggles": [
                {"id": "equity", "label": "累计收益", "checked": True},
                {"id": "drawdown", "label": "回撤", "checked": False},
                {"id": "trades", "label": "事件标记", "checked": True},
            ],
            "modes": [
                {"id": "percentage", "label": "百分比", "active": True},
                {"id": "absolute", "label": "绝对值", "active": False},
            ],
            "hide_value_row": True,
            "hide_drawdown_tooltip": True,
            "return_label": "事件收益率",
        })
        modules.append({
            "type": "trades_table",
            "tab": tab_id,
            "title": f"持有{hp}日 · 事件明细",
            "subtitle": f"共 {len(trades)} 个事件",
            "rows": trades,
            "columns": trade_columns,
        })

    # Tab5: 说明
    notes_text = (
        "## 结论摘要\n"
        f"- 5日持有：累计收益 {fmt_pct(all_stats[5].get('cumulative_return_pct'))}，"
        f"平均 {fmt_pct(all_stats[5].get('avg_return_pct'))}，"
        f"胜率 {fmt_pct(all_stats[5].get('win_rate_pct'))}\n"
        f"- 10日持有：累计收益 {fmt_pct(all_stats[10].get('cumulative_return_pct'))}，"
        f"平均 {fmt_pct(all_stats[10].get('avg_return_pct'))}，"
        f"胜率 {fmt_pct(all_stats[10].get('win_rate_pct'))}\n"
        f"- 20日持有：累计收益 {fmt_pct(all_stats[20].get('cumulative_return_pct'))}，"
        f"平均 {fmt_pct(all_stats[20].get('avg_return_pct'))}，"
        f"胜率 {fmt_pct(all_stats[20].get('win_rate_pct'))}\n\n"
        "## 方法假设\n"
        "- 信号触发日 = 向上跳空日（孤岛反转确认日）\n"
        "- 买入 = 信号次日开盘价（无 look-ahead）\n"
        "- 卖出 = 买入后 N 个交易日收盘价\n"
        "- 费用 = 0（事件研究默认，不扭曲平均收益）\n"
        "- 数据源：akshare 前复权全A日线\n\n"
        "## 已知局限\n"
        "- 事件研究不报 Sharpe / 年化 / 最大回撤（无连续组合净值）\n"
        "- 未建模滑点与冲击成本，实盘大单会有偏差\n"
        "- 268条信号集中在2026年4-8月，样本期偏短，统计显著性有限\n"
        "- 北交所信号占12%，流动性差，实盘需二次筛选\n"
    )
    modules.append({
        "type": "text",
        "tab": "notes",
        "title": "结论与方法说明",
        "text": notes_text,
    })

    report_data = {
        "meta": meta,
        "summary": main_summary,
        "equity_curve": main_curve,
        "pnl_curve": [{"date": p["date"], "pnl": p["value"] - 100.0} for p in main_curve],
        "drawdown_curve": [],
        "trade_history": main_trades,
        "ui": {
            "subtitle": "孤岛反转事件研究 · 多持有期对比",
            "active_tab": "compare",
            "tabs": [
                {"id": "compare", "label": "持有期对比"},
                {"id": "hp5", "label": "持有5日"},
                {"id": "hp10", "label": "持有10日"},
                {"id": "hp20", "label": "持有20日"},
                {"id": "notes", "label": "说明"},
            ],
            "language": language,
            "color_scheme": "eastern",
        },
        "modules": modules,
    }
    return report_data


def render_dashboard(report_data, output_path, template_path):
    import html as html_mod
    template = open(template_path, encoding="utf-8").read()
    title = report_data["meta"].get("strategy_name", "Backtest Dashboard")
    report_json = json.dumps(report_data, ensure_ascii=False)
    report_json = report_json.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    rendered = (
        template.replace("__REPORT_TITLE__", html_mod.escape(title))
        .replace("__HTML_LANG__", "zh-CN")
        .replace("__REPORT_DATA__", report_json)
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)


def main():
    global cal
    if not os.path.exists(SIGNALS_CSV):
        print(f"[错误] 信号文件不存在: {SIGNALS_CSV}")
        print("请先运行: python scripts/island_reversal_screener.py --days 90")
        sys.exit(1)

    signals_df = pd.read_csv(SIGNALS_CSV)
    signals_df["code"] = signals_df["code"].astype(str).str.zfill(6)
    print(f"加载信号: {len(signals_df)} 条")
    print(f"信号时间范围: {signals_df['gap_up_date'].min()} -> {signals_df['gap_up_date'].max()}")

    cal, cal_index = build_trading_calendar(KLINE_DIR)
    print(f"交易日历: {cal[0]} -> {cal[-1]}, 共 {len(cal)} 日")

    all_trades = {}
    all_stats = {}
    for hp in HOLDING_PERIODS:
        print(f"\n--- 计算持有{hp}日 ---")
        trades, skipped = compute_event_returns(signals_df, cal_index, hp)
        stats = event_stats(trades)
        all_trades[hp] = trades
        all_stats[hp] = stats
        print(f"  事件数: {len(trades)}, 跳过(停牌/数据缺失): {skipped}")
        print(f"  累计收益: {fmt_pct(stats.get('cumulative_return_pct'))}")
        print(f"  平均收益: {fmt_pct(stats.get('avg_return_pct'))}")
        print(f"  中位数: {fmt_pct(stats.get('median_return_pct'))}")
        print(f"  胜率: {fmt_pct(stats.get('win_rate_pct'))}")
        print(f"  最佳: {fmt_pct(stats.get('best_trade_pct'))}  最差: {fmt_pct(stats.get('worst_trade_pct'))}")

    # 写 trades.csv（合并三组，用 holding_bars 区分）
    all_rows = []
    for hp in HOLDING_PERIODS:
        for t in all_trades[hp]:
            row = dict(t)
            row["holding_bars"] = hp
            all_rows.append(row)
    trades_df = pd.DataFrame(all_rows)
    trades_df = trades_df.sort_values(["holding_bars", "entry_date"]).reset_index(drop=True)
    trades_df.to_csv(TRADES_CSV, index=False, encoding="utf-8-sig")
    print(f"\ntrades.csv 已写入: {TRADES_CSV} ({len(trades_df)} 行)")

    # 写 summary.json
    summary_payload = {
        "meta": {
            "strategy_name": "孤岛反转事件研究",
            "market": "china_a",
            "start": "2026-04-21",
            "end": "2026-08-28",
        },
        "summary": all_stats[10],  # 主统计用10日
        "by_holding_period": {str(hp): all_stats[hp] for hp in HOLDING_PERIODS},
    }
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, ensure_ascii=False, indent=2)
    print(f"summary.json 已写入: {SUMMARY_JSON}")

    # 渲染仪表盘
    print(f"\n渲染仪表盘...")
    report_data = build_report_data(all_trades, all_stats, language="zh")
    render_dashboard(report_data, DASHBOARD_HTML, TEMPLATE_HTML)
    print(f"index.html 已写入: {DASHBOARD_HTML}")

    # 输出前5/后5样本
    print(f"\n=== 10日持有 · 收益最高 TOP 5 ===")
    top = trades_df[trades_df["holding_bars"] == 10].nlargest(5, "pnl_pct")
    print(top[["name", "entry_date", "exit_date", "entry_price", "exit_price", "pnl_pct"]].to_string(index=False))
    print(f"\n=== 10日持有 · 收益最低 TOP 5 ===")
    bot = trades_df[trades_df["holding_bars"] == 10].nsmallest(5, "pnl_pct")
    print(bot[["name", "entry_date", "exit_date", "entry_price", "exit_price", "pnl_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()
