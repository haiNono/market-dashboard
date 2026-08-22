# -*- coding: utf-8 -*-
"""
拉取当日主题 ETF 资金流 Top10（流入/流出） -> data/etf_flow.json
数据源: 东财行情中心 clist（主力净流入 f62，当日快照）
说明: push2 接口升序参数(po=0/-1/2)在当前网络不可用，故用 po=1 降序分页拉全量(约1300只)，
      本地按主力净流入排序取流入/流出 Top10。
主题ETF判定: 全部ETF剔除宽基指数/固收/跨境/商品实物类（名称黑名单）
字段: 代码/名称/最新价/涨跌幅%/主力净流入(亿元)
失败策略: 单页重试5次，失败页跳过（已拉数据仍可用），全失败则保留上次数据不阻断
"""
import os
import re
import json
import time
import datetime
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "etf_flow.json")

HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}

# 名称黑名单：宽基指数 / 固收 / 跨境 / 商品实物
BLACK = re.compile(
    r"沪深300|上证50|上证180|上证指数|上证综指|中证100|中证500|中证800|中证1000|中证2000|中证A股|中证流通|"
    r"国证2000|科创50|科创100|创业板|双创|深证100|深100|深证成指|"
    r"A50|A500|MSCI|北证50|北证|全指|综指|大盘|中盘|小盘|微盘|核心资产|"
    r"货币|国债|政金|信用债|公司债|短融|城投|利率债|可转债|转债|金融债|银行债|存单|债券|"
    r"标普|纳指|恒生|恒指|日经|德国|法国|沙特|亚太|新兴市场|美国|道琼斯|中概|沪港深|港股通|越南|印度|"
    r"黄金ETF|白银|原油|豆粕"
)


def fetch_page(pn=1, pz=100, retry=5):
    # push2delay 为东财延迟行情端点，对频繁访问限流宽松（push2 会被短时封禁）
    url = ("https://push2delay.eastmoney.com/api/qt/clist/get?"
           f"fid=f62&po=1&pz={pz}&pn={pn}&np=1&fltt=2&invt=2&fs=b:MK0021"
           "&fields=f12,f14,f2,f3,f62")
    for i in range(retry):
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            if not r.text:
                raise ValueError("empty")
            j = r.json()
            return (j.get("data") or {}).get("diff") or []
        except Exception:
            time.sleep(6)
    return None


def clean(items):
    out = []
    for it in items or []:
        if not it.get("f14") or BLACK.search(it["f14"]):
            continue
        try:
            net = float(it.get("f62") or 0)
            if net != net:  # NaN
                net = 0.0
        except (TypeError, ValueError):
            net = 0.0
        out.append({
            "code": it["f12"],
            "name": it["f14"],
            "price": it.get("f2"),
            "pct": it.get("f3"),
            "main_net": round(net / 1e8, 2),  # 元->亿元
        })
    return out


def run():
    print("[ETF资金流] 分页拉取全量ETF(f62降序, push2delay)...", flush=True)
    all_items = []
    failed_pages = 0
    pn = 1
    while pn <= 14:  # 1301/100 = 14页
        items = fetch_page(pn)
        if items is None:
            failed_pages += 1
            print(f"[ETF资金流] 第{pn}页失败(重试5次仍不可用)", flush=True)
            if failed_pages >= 3:
                print("[ETF资金流] 连续失败过多，终止拉取", flush=True)
                break
            pn += 1
            time.sleep(3)
            continue
        if not items:
            break  # 无更多数据
        all_items.extend(items)
        pn += 1
        time.sleep(2)

    print(f"[ETF资金流] 共拉到 {len(all_items)} 只 (失败页 {failed_pages})", flush=True)
    if len(all_items) < 300:
        print("[ETF资金流] 数据量不足，跳过（保留上次数据）", flush=True)
        return 0

    c = clean(all_items)
    c_in = sorted([x for x in c if x["main_net"] > 0], key=lambda x: -x["main_net"])
    c_out = sorted([x for x in c if x["main_net"] < 0], key=lambda x: x["main_net"])

    result = {
        "date": datetime.date.today().strftime("%Y-%m-%d"),
        "inflow": c_in[:10],
        "outflow": c_out[:10],
        "meta": {
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_etf": len(all_items),
            "filtered": f"主题ETF判定=全部ETF剔除宽基/固收/跨境/商品，保留{len(c)}只",
            "source": "东财行情中心 主力净流入(f62)，当日快照",
        },
    }
    with open(DATA_PATH, "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=1)
    print(f"[ETF资金流] 完成: {result['date']} 流入{len(result['inflow'])}只 / 流出{len(result['outflow'])}只", flush=True)
    if result["inflow"]:
        print(f"[ETF资金流] 流入榜首: {result['inflow'][0]['name']} +{result['inflow'][0]['main_net']}亿", flush=True)
    if result["outflow"]:
        print(f"[ETF资金流] 流出榜首: {result['outflow'][0]['name']} {result['outflow'][0]['main_net']}亿", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
