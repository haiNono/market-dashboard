# -*- coding: utf-8 -*-
"""
每周五自动更新 AI 监控数据（Gavin Baker 五大指标）
目前只自动维护 GPU 租赁价格（周度）：抓取 gputracker.dev / vast.ai 的 H100 现货中位价，
追加/覆盖本周周点。其余指标（台积电营收/用电量/英伟达/OCF 等）为月度季度低频数据，
无稳定免费自动源，保持手工维护。

用法:
    python fetch_ai_metrics.py            # 抓取并更新（失败则跳过，不改数据）
    python fetch_ai_metrics.py --force    # 强制抓取（即使本周已有数据点也刷新为最新价）
退出码: 0 成功/跳过, 1 数据文件异常
"""
import os
import re
import sys
import json
import datetime
import statistics
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "ai_metrics.json")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def http_get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_gputracker_median():
    """抓取 gputracker.dev/gpu/H100 页面，提取所有 listing 价格($X.XX/hr)取中位数"""
    html = http_get("https://gputracker.dev/gpu/H100")
    prices = [float(p) for p in re.findall(r"\$([0-9]+\.[0-9]{2})", html)]
    valid = [p for p in prices if 0.3 <= p <= 30]
    if len(valid) < 30:
        return None
    return round(statistics.median(valid), 2)


def fetch_vastai_median():
    """尝试 vast.ai 公开查询端点（多个参数格式），成功返回中位价"""
    attempts = [
        'https://cloud.vast.ai/api/v0/bundles/?q={"gpu_name":"H100_SXM"}&limit=100',
        'https://cloud.vast.ai/api/v0/bundles/?q={"gpu_name":"H100_SXM","type":"on-demand"}',
    ]
    for url in attempts:
        try:
            raw = http_get(url, timeout=20)
            data = json.loads(raw)
            offers = data.get("offers") or data.get("bundles") or []
            if not isinstance(offers, list) or not offers:
                continue
            prices = []
            for o in offers:
                p = o.get("cuda_version")  # placeholder guard
                # 常见字段: dph_total (美元/小时)
                dph = o.get("dph_total")
                if isinstance(dph, (int, float)) and 0.3 <= dph <= 30:
                    prices.append(float(dph))
            if len(prices) >= 30:
                return round(statistics.median(prices), 2)
        except Exception:
            continue
    return None


def week_label(d):
    """本周标签: ISO 周一的日期字符串（用于去重：同一周只保留一个点）"""
    return (d - datetime.timedelta(days=d.weekday())).strftime("%Y-%m-%d")


def run(force=False):
    with open(DATA_PATH, encoding="utf-8") as fp:
        data = json.load(fp)
    gpu = data["metrics"].get("gpu_rental")
    if not gpu or not gpu.get("dates"):
        print("[AI] ai_metrics.json 缺少 gpu_rental，跳过", flush=True)
        return 1

    # 抓取
    price = None
    src = ""
    try:
        p = fetch_gputracker_median()
        if p:
            price, src = p, "gputracker.dev"
    except Exception as e:
        print(f"[AI] gputracker 抓取失败: {e}", flush=True)
    if price is None:
        try:
            p = fetch_vastai_median()
            if p:
                price, src = p, "vast.ai"
        except Exception as e:
            print(f"[AI] vast.ai 抓取失败: {e}", flush=True)
    if price is None:
        print("[AI] 所有数据源均不可用，跳过本次更新（保留既有数据）", flush=True)
        return 0

    today = datetime.date.today()
    wk = week_label(today)
    # 该周已有的点: 形如 2026-08-21（周五）落在 [wk, wk+6] 区间
    wk_dates = [d for d in gpu["dates"]
                if wk <= d <= (datetime.date.fromisoformat(wk) + datetime.timedelta(days=6)).isoformat()]
    if wk_dates and not force:
        print(f"[AI] 本周({wk})已有数据点 {wk_dates}，跳过（--force 可强制刷新为最新价 {price}$）", flush=True)
        return 0

    # 追加或覆盖
    label = today.strftime("%Y-%m-%d")
    if wk_dates:
        # 覆盖本周已有点
        idx = gpu["dates"].index(wk_dates[-1])
        gpu["dates"][idx] = label
        gpu["values"][idx] = price
        print(f"[AI] 覆盖本周点: {label} = ${price} ({src})", flush=True)
    else:
        gpu["dates"].append(label)
        gpu["values"].append(price)
        print(f"[AI] 追加周点: {label} = ${price} ({src})", flush=True)

    with open(DATA_PATH, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=1)
    print(f"[AI] gpu_rental 更新完成，共 {len(gpu['dates'])} 个周点", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(run(force="--force" in sys.argv))
