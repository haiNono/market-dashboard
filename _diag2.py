import sys, traceback
sys.path.insert(0, "scripts")
import fetch_stocks
try:
    fetch_stocks.run()
except Exception:
    traceback.print_exc()
    sys.exit(2)
