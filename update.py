# -*- coding: utf-8 -*-
"""一键增量更新 Dashboard: 收盘后运行一次即可
用法: python update.py
流程: 增量拉全A日线 -> 板块/PCR/申万成分 -> 指标计算 -> 同步资料库事件文档 -> 重新生成HTML
"""
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(BASE_DIR, "scripts")
PY = sys.executable

STEPS = [
    ("增量拉取全A日线", os.path.join(SCRIPTS, "fetch_stocks.py")),
    ("更新板块/PCR/申万成分", os.path.join(SCRIPTS, "fetch_aux.py")),
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

# 事件数据同步后需重新生成 HTML（build 会把 events.json 内联进页面）
print(f"\n{'='*20} 重新生成Dashboard(含事件页) {'='*20}", flush=True)
r = subprocess.run([PY, "-u", os.path.join(SCRIPTS, "build_dashboard.py")], cwd=BASE_DIR)
if r.returncode != 0:
    print(f"[失败] 生成Dashboard 退出码 {r.returncode}", flush=True)
    sys.exit(1)
print("\n全部完成 -> output/dashboard.html", flush=True)
