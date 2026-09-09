#!/bin/bash
# 看门狗：运行 update.py，检测挂起(日志无进展)与总超时，自动杀掉进程树，避免无人值守时永久卡死。
set -u
BASE="E:/EProjects/workspace/market_dashboard"
PY="$BASE/../../../../Users/hainu/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
# 修正：C:/Users 在 git bash 下
PY="C:/Users/hainu/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
LOG="$BASE/update_run_2026-09-08.log"
HANG_TIMEOUT=900      # 连续无日志进展 15 分钟 -> 判定挂起
MAX_TOTAL=7200        # 总时长上限 2 小时 -> 强制终止
POLL=30

cd "$BASE" || exit 9
: > "$LOG"

echo "[WATCHDOG] launch update.py at $(date)" | tee -a "$LOG"
"$PY" -u update.py >> "$LOG" 2>&1 &
PID=$!
echo "[WATCHDOG] update.py PID=$PID" | tee -a "$LOG"

start=$(date +%s)
last_size=$(stat -c%s "$LOG" 2>/dev/null || echo 0)
last_change=$start

while kill -0 "$PID" 2>/dev/null; do
  now=$(date +%s)
  size=$(stat -c%s "$LOG" 2>/dev/null || echo 0)
  if [ "$size" -ne "$last_size" ]; then
    last_size=$size
    last_change=$now
  fi
  elapsed=$((now - start))
  quiet=$((now - last_change))
  if [ "$quiet" -ge "$HANG_TIMEOUT" ]; then
    echo "[WATCHDOG] HANG detected: no log progress for ${quiet}s (>= ${HANG_TIMEOUT}s). Killing PID=$PID tree." | tee -a "$LOG"
    cmd.exe /c "taskkill /F /PID $PID /T" >/dev/null 2>&1
    sleep 3
    echo "WATCHDOG_RESULT=HANG_KILL" | tee -a "$LOG"
    exit 2
  fi
  if [ "$elapsed" -ge "$MAX_TOTAL" ]; then
    echo "[WATCHDOG] MAX_TOTAL ${MAX_TOTAL}s exceeded. Killing PID=$PID tree." | tee -a "$LOG"
    cmd.exe /c "taskkill /F /PID $PID /T" >/dev/null 2>&1
    sleep 3
    echo "WATCHDOG_RESULT=MAXTIME_KILL" | tee -a "$LOG"
    exit 3
  fi
  sleep "$POLL"
done

wait "$PID"
rc=$?
now=$(date +%s)
echo "[WATCHDOG] update.py exited rc=$rc elapsed=$((now-start))s" | tee -a "$LOG"
echo "WATCHDOG_RESULT=DONE rc=$rc" | tee -a "$LOG"
exit $rc
