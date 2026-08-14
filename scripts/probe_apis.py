# -*- coding: utf-8 -*-
"""接口探测: 验证 akshare 关键接口可用性（小样本）
1. 单只股票历史日线
2. 申万二级行业列表 + 成分
3. 东财板块列表(概念/行业) + 板块历史
4. 期权PCR(新浪)
"""
import akshare as ak
import pandas as pd

pd.set_option("display.width", 200)

print("=" * 60)
print("[1] 单只股票日线 stock_zh_a_hist")
try:
    df = ak.stock_zh_a_hist(symbol="600519", period="daily",
                            start_date="20250801", end_date="20250810", adjust="qfq")
    print(f"OK rows={len(df)} cols={list(df.columns)}")
    print(df.tail(2).to_string())
except Exception as e:
    print(f"FAIL: {e}")

print("=" * 60)
print("[2] 申万二级行业 index_realtime_sw")
sw2 = None
try:
    sw2 = ak.index_realtime_sw(symbol="二级行业")
    print(f"OK rows={len(sw2)} cols={list(sw2.columns)}")
    print(sw2.head(3).to_string())
except Exception as e:
    print(f"FAIL: {e}")

if sw2 is not None and len(sw2) > 0:
    code_col = [c for c in sw2.columns if "代码" in c][0]
    test_code = str(sw2.iloc[0][code_col])
    print(f"[2b] 申万行业成分 index_component_sw symbol={test_code}")
    try:
        comp = ak.index_component_sw(symbol=test_code)
        print(f"OK rows={len(comp)} cols={list(comp.columns)}")
        print(comp.head(3).to_string())
    except Exception as e:
        print(f"FAIL: {e}")

print("=" * 60)
print("[3] 东财板块列表")
try:
    ind = ak.stock_board_industry_name_em()
    print(f"行业板块 rows={len(ind)} 样例: {ind['板块名称'].head(5).tolist()}")
except Exception as e:
    print(f"行业 FAIL: {e}")
try:
    con = ak.stock_board_concept_name_em()
    print(f"概念板块 rows={len(con)} 样例: {con['板块名称'].head(5).tolist()}")
    # 搜索目标板块
    targets = ["半导体材料", "半导体设备", "算力租赁", "端侧", "光通信", "云"]
    for t in targets:
        hits = con[con["板块名称"].str.contains(t, na=False)]["板块名称"].tolist()
        print(f"  概念含'{t}': {hits[:8]}")
except Exception as e:
    print(f"概念 FAIL: {e}")

print("=" * 60)
print("[3b] 板块历史 stock_board_concept_hist_em")
try:
    df = ak.stock_board_concept_hist_em(symbol="半导体材料", period="日k",
                                        start_date="20260801", end_date="20260811", adjust="")
    print(f"OK rows={len(df)} cols={list(df.columns)}")
    print(df.tail(2).to_string())
except Exception as e:
    print(f"FAIL: {e}")

print("=" * 60)
print("[4] 期权PCR option_pcr_analysis_sina")
for sym in ["300ETF", "500ETF", "科创50ETF", "科创板50ETF"]:
    try:
        df = ak.option_pcr_analysis_sina(symbol=sym)
        print(f"{sym}: OK rows={len(df)} cols={list(df.columns)}")
        print(df.tail(2).to_string())
    except Exception as e:
        print(f"{sym}: FAIL: {e}")

print("=" * 60)
print("探测完成")
