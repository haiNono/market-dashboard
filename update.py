# -*- coding: utf-8 -*-
"""一键增量更新 Dashboard: 收盘后运行一次即可
用法: python update.py
流程: 增量拉全A日线 -> 板块/PCR/申万成分 -> 指标计算 -> 同步资料库事件文档 -> 重新生成HTML
"""
import os
import subprocess
import sys
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(BASE_DIR, "scripts")
PY = sys.executable

STEPS = [
    ("增量拉取全A日线", os.path.join(SCRIPTS, "fetch_stocks.py")),
    ("更新板块/PCR/申万成分", os.path.join(SCRIPTS, "fetch_aux.py")),
    ("更新两融余额数据", os.path.join(SCRIPTS, "fetch_margin.py")),
    ("指标计算", os.path.join(SCRIPTS, "compute.py")),
    ("生成Dashboard", os.path.join(SCRIPTS, "build_dashboard.py")),
]

for name, script in STEPS:
    print(f"\n{'='*20} {name} {'='*20}", flush=True)
    r = subprocess.run([PY, "-u", script], cwd=BASE_DIR)
    if r.returncode != 0:
        print(f"[失败] {name} 退出码 {r.returncode}，终止后续步骤", flush=True)
        sys.exit(1)

# 事件时间表：从资料库文档同步（可选步骤，失败不阻断，沿用上次 events.json）
print(f"\n{'='*20} 同步资料库事件文档 {'='*20}", flush=True)
r = subprocess.run([PY, "-u", os.path.join(SCRIPTS, "fetch_events.py")], cwd=BASE_DIR)
if r.returncode != 0:
    print(f"[警告] 事件文档同步失败(退出码 {r.returncode})，沿用上次事件数据", flush=True)

# AI 监控数据：仅周五刷新（GPU 租赁价格周度抓取；失败不阻断，保留上次数据）
if datetime.date.today().weekday() == 4:  # 4 = Friday
    print(f"\n{'='*20} 刷新AI监控数据(周五) {'='*20}", flush=True)
    r = subprocess.run([PY, "-u", os.path.join(SCRIPTS, "fetch_ai_metrics.py")], cwd=BASE_DIR)
    if r.returncode != 0:
        print(f"[警告] AI 监控数据刷新失败(退出码 {r.returncode})，保留上次数据", flush=True)
else:
    print(f"\n{'='*20} 跳过AI监控刷新(仅周五执行) {'='*20}", flush=True)

# 事件数据同步后需重新生成 HTML（build 会把 events.json 内联进页面）
print(f"\n{'='*20} 重新生成Dashboard(含事件页) {'='*20}", flush=True)
r = subprocess.run([PY, "-u", os.path.join(SCRIPTS, "build_dashboard.py")], cwd=BASE_DIR)
if r.returncode != 0:
    print(f"[失败] 生成Dashboard 退出码 {r.returncode}", flush=True)
    sys.exit(1)
print("\n全部完成 -> output/dashboard.html", flush=True)

# 可选：提交并推送 GitHub Pages（需已配置 SSH 免密；无变更或推送失败不阻断）
print(f"\n{'='*20} 推送GitHub Pages(可选) {'='*20}", flush=True)
try:
    subprocess.run(["git", "add", "-A"], cwd=BASE_DIR, check=False)
    subprocess.run(["git", "commit", "-m", "auto: 每日数据更新", "-m", "update.py 自动提交"], cwd=BASE_DIR, check=False)
    r = subprocess.run(["git", "push"], cwd=BASE_DIR, timeout=300)
    if r.returncode == 0:
        print("[GitHub] 已推送，线上 Pages 将自动更新", flush=True)
    else:
        print(f"[GitHub] push 退出码 {r.returncode}（未推送，不影响本地更新）", flush=True)
except Exception as e:
    print(f"[GitHub] 推送跳过: {repr(e)[:120]}", flush=True)
