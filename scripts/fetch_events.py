# -*- coding: utf-8 -*-
"""
从资料库文档《未来2月影响股市的重大事件时间表（含重要性等级）》拉取最新内容，
解析为 data/events.json（供 build_dashboard.py 的"事件时间表"页面使用）。

用法：
  自动化/sandbox（auth-proxy 注入身份）：python scripts/fetch_events.py
  agent/client 环境：EVENT_TOKEN=op_xxx python scripts/fetch_events.py
  --inspect：仅打印文档结构（表格行列/标题/列表）用于调试，不写文件
"""
import os
import re
import sys
import json
import subprocess

DOC_NODE_ID = os.environ.get("EVENT_DOC_ID", "562uE34SRzJp9aAolpjPNo")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SKILL_DIR = r"C:/Users/hainu/.workbuddy/plugins/cache/workbuddy-builtin/skill-library/0.5.9"
PY = sys.executable

CERT_MAP = {"✅": "已确认", "🔶": "预计（待官方确认）", "🔁": "派生（由主事件派生）"}
IMP_DESC = {
    "10": "改变全球资产定价的核心事件", "9": "强板块定价锚/中长期政策主线",
    "8": "明确主题催化、影响多个子板块", "7": "行业级催化/长假流动性/关键数据",
    "6": "区域/细分领域事件", "5": "专业窄主题", "4": "技术性/派生事件"
}
# 文档"主题性投资线索"表导出时常缺失字段，此为补全映射（主线 -> 事件 -> 板块 -> 核心个股）
SECTORS_FALLBACK = [
    {"theme": "AI算力链", "events": "英伟达财报 8/26 · 博通 9/1 · 北京AI算力大会 9/15 · 云栖大会 9/22 · 台积电 Q3（10月中）", "sectors": "光模块、PCB、液冷、电源、IDC、HBM", "stocks": "中际旭创、新易盛、天孚通信、沪电股份、胜宏科技、英维克、欧陆通"},
    {"theme": "人形机器人", "events": "世界机器人大会 8/19–23 · 人形机器人运动会 8/22–26 · 宇树科技上市 8/26", "sectors": "机器人整机、减速器、丝杠、传感器", "stocks": "宇树科技、绿的谐波、三花智控、拓普集团、鸣志电器"},
    {"theme": "半导体设备/材料", "events": "ESIS峰会 8/29 · CSEAC展 8/31 · 台积电 Q3（10月中）", "sectors": "半导体设备、材料、先进制程", "stocks": "北方华创、中微公司、盛美上海、拓荆科技、沪硅产业"},
    {"theme": "消费电子/折叠屏", "events": "苹果秋季发布会 9/8–9（首款折叠 iPhone Ultra）", "sectors": "果链、折叠屏、2nm制程", "stocks": "立讯精密、歌尔股份、蓝思科技、东山精密"},
    {"theme": "金融地产/高股息", "events": "8月LPR 8/20 · 社融数据 9/13 · 三季报（10月）", "sectors": "银行、地产、券商、高股息", "stocks": "招商银行、保利发展、中信证券、中国神华"},
    {"theme": "商业航天", "events": "朱雀三号/双曲线三号首发 8月 · 梦舟一号首飞 9/25", "sectors": "卫星制造、火箭配套、地面设备", "stocks": "中国卫星、航天电子、铖昌科技、上海瀚讯"},
    {"theme": "资金面/解禁", "events": "9月解禁 2900亿 · 10月解禁 4200亿 · 新基金发行", "sectors": "回避\"高解禁+高涨幅+无锁仓\"；AI/硬科技/红利/港股ETF增量", "stocks": "关注北向资金、宽基ETF申赎、国家队动向"}
]
# 文档表格大量使用合并单元格（如"8/26"合并英伟达财报+AGIC、速览表事件名与日期分列），
# 自动解析无法恢复的行，按文档"重点事件详解/休市与交割日历"等章节内容补全。
TIMELINE_PATCH = [
    {"date": "8/19–23", "event": "世界机器人大会（北京）", "cat": "AI/机器人峰会", "impact": "人形机器人、减速器、传感器", "certainty": "✅", "imp": 6},
    {"date": "8/26 盘后", "event": "英伟达 NVDA 财报（全球 AI 链定价锚）", "cat": "海外财报/AI", "impact": "光模块、PCB、液冷、电源、HBM", "certainty": "✅", "imp": 10},
    {"date": "8/26", "event": "上证50ETF期权交割日", "cat": "派生/交割", "impact": "权重蓝筹波动", "certainty": "✅", "imp": 4},
    {"date": "8/22–26", "event": "人形机器人运动会", "cat": "AI/机器人峰会", "impact": "人形机器人整机、零部件", "certainty": "✅", "imp": 7},
    {"date": "8/31", "event": "中国 8 月官方制造业 PMI", "cat": "宏观数据", "impact": "内需、周期", "certainty": "✅", "imp": 7},
    {"date": "8/29", "event": "DSMC 中国制造业&新能源数智峰会（上海）", "cat": "半导体", "impact": "制造业、新能源", "certainty": "✅", "imp": 5},
    {"date": "8/31", "event": "第十四届半导体设备展 CSEAC 2026（无锡）", "cat": "半导体", "impact": "半导体设备、材料", "certainty": "✅", "imp": 5},
    {"date": "9/1 盘后", "event": "博通 AVGO FY2026 Q3 财报", "cat": "海外财报", "impact": "AI组网、光通信", "certainty": "✅", "imp": 9},
    {"date": "9/18", "event": "中金所交割日", "cat": "派生/交割", "impact": "股指期货交割", "certainty": "✅", "imp": 4},
    {"date": "9/15–16", "event": "美联储 9 月 FOMC 季度会议（含 SEP 点阵图）", "cat": "宏观", "impact": "全球资产定价", "certainty": "✅", "imp": 10},
    {"date": "9/23", "event": "上证50ETF期权交割日", "cat": "派生/交割", "impact": "权重蓝筹波动", "certainty": "✅", "imp": 4},
    {"date": "9/25", "event": "梦舟一号新一代载人飞船·长征十号甲无人首飞", "cat": "商业航天", "impact": "载人航天、商业航天", "certainty": "🔶", "imp": 7},
    {"date": "9/25–27", "event": "中秋休市", "cat": "休市/长假", "impact": "长假流动性", "certainty": "✅", "imp": 7},
    {"date": "9月（全月）", "event": "A股解禁约 2900 亿（科技股约 1100 亿）", "cat": "资金面", "impact": "高位科技股抛压", "certainty": "✅", "imp": 6},
    {"date": "10/7", "event": "中国 9 月进出口数据", "cat": "宏观数据", "impact": "出口链、航运", "certainty": "✅", "imp": 6},
    {"date": "10/16", "event": "中金所交割日", "cat": "派生/交割", "impact": "股指期货交割", "certainty": "✅", "imp": 4},
    {"date": "10/20", "event": "中国 Q3 GDP", "cat": "宏观数据", "impact": "全年增长目标兑现度、顺周期", "certainty": "✅", "imp": 8},
    {"date": "10/21（预计）", "event": "特斯拉 TSLA Q3 财报", "cat": "海外财报", "impact": "新能源车、储能、人形机器人", "certainty": "🔶", "imp": 6},
]


def get_mode():
    try:
        r = subprocess.run([PY, os.path.join(SKILL_DIR, "runtime_context.py")],
                           capture_output=True, text=True, timeout=60)
        m = re.search(r'"mode"\s*:\s*"(\w+)"', r.stdout)
        return m.group(1) if m else "sandbox"
    except Exception:
        return "sandbox"


def fetch_doc(token):
    script = os.path.join(SKILL_DIR, "doc", "get_doc_reviews.py")
    cmd = [PY, script, "--page-id", DOC_NODE_ID]
    if token:
        cmd += ["--token-stdin"]
        p = subprocess.run(cmd, input=token + "\n", capture_output=True, text=True, timeout=180)
    else:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    out = p.stdout or ""
    if p.returncode != 0 or out.startswith('{"error"'):
        raise RuntimeError("拉取文档失败: " + (out[:300] if out else repr(p.stderr[:200])))
    # 提取 XML 主体（第一个 < 到 KS_DOC_REVIEWS 之前）
    i = out.find("<BlockQuote")
    j = out.find("KS_DOC_REVIEWS")
    if i < 0 or j < 0:
        raise RuntimeError("文档格式异常，未找到内容主体")
    return out[i:j]


def clean(t):
    t = re.sub(r'<Mark\b[^>]*>', '', t)
    t = re.sub(r'</Mark>', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def headings(xml):
    return [(int(lv), clean(h)) for lv, h in
            re.findall(r'<Heading\b[^>]*level="(\d)"[^>]*>(.*?)</Heading>', xml, re.S)]


def extract_tables(xml):
    tables = []
    for m in re.finditer(r'<Table\b[^>]*>(.*?)</Table>', xml, re.S):
        rows = []
        for rm in re.finditer(r'<TableRow\b[^>]*>(.*?)</TableRow>', m.group(1), re.S):
            rblock = rm.group(1)
            rblock = re.sub(r'<TableCell\b[^>]*\s*/>', '<TableCell>__EMPTY__</TableCell>', rblock)
            cells = []
            for cm in re.finditer(r'<TableCell\b[^>]*>(.*?)</TableCell>', rblock, re.S):
                txts = re.findall(r'<Paragraph\b[^>]*>(.*?)</Paragraph>', cm.group(1), re.S)
                cells.append(clean(''.join(txts)) or '')
            rows.append(cells)
        tables.append(rows)
    return tables


def extract_lists(xml, tag):
    return [clean(m) for m in re.findall(r'<%s\b[^>]*>(.*?)</%s>' % (tag, tag), xml, re.S)]


def parse_timeline(tables):
    """合并主表(6列)完整行 + 速览表(4列)完整行 + 补丁，按时间排序去重"""
    seen, out = set(), []

    def add(date, event, cat, impact, cert, imp):
        if not event or not date:
            return
        key = (date, event)
        if key in seen:
            return
        seen.add(key)
        impn = None
        m = re.match(r'^(\d+)', str(imp or ''))
        if m:
            impn = int(m.group(1))
        out.append({
            "date": date, "event": event,
            "cat": cat or "其他", "impact": impact or "",
            "certainty": cert if cert in CERT_MAP else (cert or "✅"),
            "imp": impn if impn else 4
        })

    if tables:
        # 主表：完整 6 列行（事件非空）
        for cells in tables[0]:
            cells = [c.strip() for c in cells if c.strip() != '__EMPTY__']
            if len(cells) >= 6 and cells[1]:
                add(cells[0], cells[1], cells[2], cells[3], cells[4], cells[5])
        # 速览表：4 列（重要性|日期|事件|影响方向），事件与日期均非空
        if len(tables) > 1:
            for cells in tables[1]:
                cells = [c.strip() for c in cells if c.strip() != '__EMPTY__']
                if (len(cells) >= 4 and re.match(r'^\d{1,2}([–\-]\d{1,2})?$', cells[0])
                        and cells[1] and cells[2]):
                    add(cells[1], cells[2], '', cells[3], '', cells[0])
    # 补丁（文档合并单元格丢失的行，来源见 TIMELINE_PATCH 注释）
    for e in TIMELINE_PATCH:
        add(e["date"], e["event"], e["cat"], e["impact"], e["certainty"], e["imp"])

    # 按时间排序
    def sort_key(e):
        d = e["date"]
        m = re.search(r'(\d{1,2})月', d) or re.match(r'(\d{1,2})/', d)
        month = int(m.group(1)) if m else 8
        day = 0
        md = re.search(r'/(\d{1,2})', d)
        if md:
            day = int(md.group(1))
        elif "月底" in d:
            day = 30
        elif "下旬" in d:
            day = 25
        elif "中旬" in d:
            day = 15
        elif "上旬" in d:
            day = 5
        return (month, day)

    out.sort(key=sort_key)
    return out


def parse_deep(xml, hs):
    """二、重点事件详解：level3 标题 + 其后 BulletedList"""
    m2 = re.search(r'<Heading[^>]*level="2"[^>]*>\s*二、重点事件详解\s*</Heading>(.*?)<Heading[^>]*level="2"', xml, re.S)
    seg = m2.group(1) if m2 else ""
    deep = []
    for hm in re.finditer(r'<Heading\b[^>]*level="3"[^>]*>(.*?)</Heading>(.*?)(?=<Heading\b|$)', seg, re.S):
        title = clean(hm.group(1))
        body = hm.group(2)
        pts = extract_lists(body, "BulletedList")
        m = re.search(r'重要性\s*([\d\-–/]+)', title)
        imp = m.group(1) if m else ""
        t2 = re.sub(r'^[\d]+\.\s*', '', re.sub(r'[｜|]\s*重要性.*$', '', title).strip())
        deep.append({"title": t2, "imp": imp, "points": pts})
    return deep


def parse_sectors(tables):
    """三、主题性投资线索表（主线|事件|板块），字段缺失时回退到内置补全映射"""
    if len(tables) >= 3:
        valid = []
        for cells in tables[2]:
            cells = [c.strip() for c in cells if c.strip() != '__EMPTY__']
            if len(cells) >= 3 and cells[0] and cells[0] != "主线" and cells[2]:
                valid.append({"theme": cells[0], "events": cells[1], "sectors": cells[2]})
        if len(valid) >= 3:
            return valid
    return SECTORS_FALLBACK


def parse_risks(xml):
    return extract_lists(xml, "NumberedList")


def parse_doc(xml):
    hs = headings(xml)
    tables = extract_tables(xml)
    timeline = parse_timeline(tables)
    deep = parse_deep(xml, hs)
    sectors = parse_sectors(tables)
    risks = parse_risks(xml)
    meta_m = re.search(r'梳理区间[:：]\s*([^\n\\]+)', xml)
    return {
        "meta": {
            "title": "未来2月影响股市的重大事件时间表（含重要性等级）",
            "period": (meta_m.group(1).strip() if meta_m else ""),
            "updated": "自动同步自资料库文档",
            "source": "资料库文档《未来2月影响股市的重大事件时间表（含重要性等级）》"
        },
        "certainty_map": CERT_MAP,
        "importance_desc": IMP_DESC,
        "timeline": timeline,
        "deep": deep,
        "sectors": sectors,
        "risks": risks
    }


def main():
    args = sys.argv[1:]
    mode = get_mode()
    token = os.environ.get("EVENT_TOKEN")
    if mode == "client" and not token and "--inspect" not in args:
        print("CLIENT_MODE_NO_TOKEN: agent 环境需设置 EVENT_TOKEN 环境变量")
        return 2
    xml = fetch_doc(token if mode == "client" else None)
    if "--inspect" in args:
        print("=== 标题结构 ===")
        for lv, h in headings(xml):
            print(("  " * (lv - 1)) + f"[H{lv}] {h[:60]}")
        print("\n=== 表格结构 ===")
        for ti, rows in enumerate(extract_tables(xml)):
            print(f"--- Table{ti + 1} ({len(rows)}行) ---")
            for cells in rows[:6]:
                print("  |", " | ".join(c[:20] for c in cells))
            print("  ...")
        print("\n=== NumberedList ===")
        for i, t in enumerate(extract_lists(xml, "NumberedList")):
            print(f"  {i + 1}. {t[:60]}")
        return 0
    data = parse_doc(xml)
    out_path = os.path.join(DATA_DIR, "events.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"OK -> {out_path}  timeline={len(data['timeline'])} deep={len(data['deep'])} sectors={len(data['sectors'])} risks={len(data['risks'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
