# -*- coding: utf-8 -*-
"""
从资料库文档《未来2月影响股市的重大事件时间表（含重要性等级）》拉取最新内容，
解析为 data/events.json（供 build_dashboard.py 的"事件时间表"页面使用）。

支持的文档版本：v10 起的"重建版"结构（2026-10 后），即
  一、时间线总览  —— 列表式，每条 = 「日期 标题——正文｜类别⑩｜影响板块｜确定性｜重要性」
  二、重要性速览  —— 多张 4 列小表（重要性|日期|事件|主要影响板块），按等级分块
  三、结构观察    —— H3「M/D 新增：标题」+ 类别/影响板块/确定性/重要性 + 要点段落
  关键风险清单    —— 单段落 ①②③… 编号

用法：
  自动化/sandbox（auth-proxy 注入身份）：python scripts/fetch_events.py
  agent/client 环境：EVENT_TOKEN=op_xxx python scripts/fetch_events.py
  --inspect：仅打印文档结构（表格行列/标题/列表）用于调试，不写文件
"""
import os
import re
import sys
import json
import datetime
import subprocess

# 正式版文档节点（旧节点 562uE34SRzJp9aAolpjPNo 已被作者标记"已弃用·表格损坏"并清空内容）
DOC_NODE_ID = os.environ.get("EVENT_DOC_ID", "n6hLxaUPgXmtVhQtlaLrvL")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SKILL_ROOT = r"C:/Users/hainu/.workbuddy/plugins/cache/workbuddy-builtin/skill-library"
PY = sys.executable

CERT_MAP = {"✅": "已确认", "🔶": "预计（待官方确认）", "🔁": "派生（由主事件派生）"}
IMP_DESC = {
    "10": "改变全球资产定价的核心事件", "9": "强板块定价锚/中长期政策主线",
    "8": "明确主题催化、影响多个子板块", "7": "行业级催化/长假流动性/关键数据",
    "6": "区域/细分领域事件", "5": "专业窄主题", "4": "技术性/派生事件"
}
# 文档口径编号 → 类别名（①宏观政策与流动性 … ⑩A股休市与交割日）
CAT_MAP = {
    "①": "宏观政策/流动性", "②": "宏观数据", "③": "IPO/资本事件", "④": "资金面",
    "⑤": "公司/个股事件", "⑥": "监管/制度", "⑦": "AI/机器人/算力", "⑧": "商业航天",
    "⑨": "产业变革/科技", "⑩": "休市/交割"
}
# 事件 → 板块映射（依据文档"结构观察/主线"表述整理；核心个股仅为板块代表性标的）
SECTORS_OUTLOOK = [
    {"theme": "AI算力链（光模块/CPO/PCB/液冷）",
     "events": "11/18 英伟达 FY2027Q3 · 12/9 博通 · 1/27 微软+Meta+苹果 · 1/29 亚马逊+Alphabet · 2/24 英伟达 FY2027Q4",
     "sectors": "光模块、CPO、PCB、液冷、AI服务器电源、IDC",
     "stocks": "中际旭创、新易盛、天孚通信、沪电股份、胜宏科技、英维克"},
    {"theme": "AI算力链的三条压力线（治理·政治·执行）",
     "events": "11/8 董事会情报调查 → 11/12 拟罢免 CEO · 11/4 中期选举后数据中心审批受阻 · 11/6 微软退出 Nscale",
     "sectors": "算力硬件、AI 服务器、国产 GPU（情绪与估值同向放大）",
     "stocks": "源杰科技、长光华芯、广合科技、工业富联、浪潮信息"},
    {"theme": "国产算力/半导体自主",
     "events": "阿里分拆平头哥赴港 · 12/7 摩尔线程解禁开门日 · 1/27 长鑫科技解禁 · 关税与出口管制博弈",
     "sectors": "国产 GPU、先进制程、半导体设备与材料",
     "stocks": "寒武纪、海光信息、摩尔线程、北方华创、中微公司"},
    {"theme": "存储/HBM 周期",
     "events": "12 月美光财报 · HBM/DRAM 合约价 · 长鑫科技 1/27 解禁（存储最大单笔）",
     "sectors": "DRAM、HBM、存储模组、封测",
     "stocks": "兆易创新、江波龙、澜起科技、长电科技"},
    {"theme": "政策主线：中央加杠杆 + 内需",
     "events": "12/8 政治局会议 → 12/10–11 中央经济工作会议 → 1 月地方两会 → 3 月全国两会（GDP 4.5–5%、赤字率约 4.0%）",
     "sectors": "化债清欠、基建、服务消费（养老/育幼/医疗/文旅）、地产托底",
     "stocks": "中国建筑、海螺水泥、中国中免、锦江酒店、保利发展"},
    {"theme": "红利/高股息（唯一走强的风格）",
     "events": "10 月银行/煤炭/石油创历史新高 · 年末排名冲刺的配置盘接棒 · 险资权益回撤反噬",
     "sectors": "银行、煤炭、石油石化、公用事业、红利低波",
     "stocks": "工商银行、建设银行、中国神华、中国石油、长江电力"},
    {"theme": "固态电池/锂电材料",
     "events": "《新型电池产业发展「十五五」规划》落地 · 11/12 广期所氢氧化锂期货与期权上市",
     "sectors": "固态电池、锂电材料、锂矿、电池设备",
     "stocks": "宁德时代、亿纬锂能、当升科技、赣锋锂业"},
    {"theme": "稀土/关税博弈（最大单一外部变量）",
     "events": "11/9 关税休战再续 2 个月 · 1/10 中美关税与稀土管控暂停协议到期 · 12/14–15 G20 迈阿密",
     "sectors": "稀土、磁材、半导体材料、出口链、家电、光伏",
     "stocks": "北方稀土、金力永磁、中科三环、金风科技"},
    {"theme": "商业航天/军工",
     "events": "梦舟一号 + 长征十号甲首飞（待官方）· 11/10–15 珠海航展后续订单",
     "sectors": "卫星制造、火箭配套、地面设备、军工电子",
     "stocks": "中国卫星、航天电子、铖昌科技、上海瀚讯"},
    {"theme": "券商/资本市场工具",
     "events": "11/2 央行+证监会稳市会议 · 股票回购增持再贷款优化 · 中长期资金入市",
     "sectors": "券商、金融 IT、参股金融",
     "stocks": "中信证券、华泰证券、东方财富、同花顺"},
]
# 使用边界与风控要点（文档口径之外的固定提醒，随页面长期展示）
RISK_USAGE = [
    "确定性分级：🔶/🔁 类（政治局会议与中央经济工作会议具体日、火箭首飞日、美国数据发布日）以官方最终公告为准，个别日期可能前后浮动 1–2 个交易日。",
    "「买预期卖事实」：本表用于提前埋伏与仓位节奏，事件落地当日往往是兑现窗口，重点看落地后 2–3 个交易日的承接量能。",
    "解禁 ≠ 减持：解禁只是可卖，需结合浮盈倍数、股东性质与减持新规判断真实抛压（如长鑫科技 1/27 网下浮盈约 9 倍）。",
    "数据驱动锚点优先：FOMC/CPI/非农/中央经济工作会议等硬事件的时间确定性高，优先围绕它们做节奏；峰会与产业会议多为情绪催化。",
    "长假效应：春节休市期间（2/5–2/13）的海外数据需在节后首个交易日一次性消化，节前最后一周流动性最紧。",
    "本页内容来自公开研报与官方日历整理，仅供研究参考，不构成投资建议。",
]


def resolve_skill_dir():
    """自动探测 skill-library 最新版本目录（避免硬编码版本号，插件升级后不再失效）。

    优先级：环境变量 LIBRARY_SKILL_DIR > skill-library 下含 doc/get_doc_reviews.py 的最高版本。
    """
    env = os.environ.get("LIBRARY_SKILL_DIR")
    if env and os.path.isfile(os.path.join(env, "doc", "get_doc_reviews.py")):
        return env
    cands = []
    if os.path.isdir(SKILL_ROOT):
        for name in os.listdir(SKILL_ROOT):
            d = os.path.join(SKILL_ROOT, name)
            if os.path.isfile(os.path.join(d, "doc", "get_doc_reviews.py")):
                cands.append(d)
    if not cands:
        raise RuntimeError(f"未找到可用的 skill-library 目录（{SKILL_ROOT}）")

    def vkey(d):
        # 目录名形如 5.11.3-wb.43806934.gxxx：取主版本号数字元组比较
        nums = re.findall(r"\d+", os.path.basename(d).split("-")[0])
        return tuple(int(x) for x in nums) if nums else (0,)

    cands.sort(key=vkey)
    return cands[-1]


SKILL_DIR = resolve_skill_dir()
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


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
    # 新版输出为 YAML front-matter + KS_DOC_REVIEWS 行 + XML 主体
    i = out.find("<BlockQuote")
    if i < 0:
        i = out.find("<Heading")
    j = out.find("KS_DOC_REVIEWS")
    if i < 0 or j < 0 or j <= i:
        raise RuntimeError("文档格式异常，未找到内容主体")
    return out[i:j]


def clean(t):
    t = re.sub(r'<Mark\b[^>]*>', '', t)
    t = re.sub(r'</Mark>', '', t)
    t = re.sub(r'\\?\*+', '', t)          # 表格导出残留的 \*\* 加粗标记
    t = re.sub(r'<[^>]+>', '', t)
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


def bullets(seg):
    """文档列表项：<BulletedList> 自身即一条（无嵌套 item 标签）"""
    return [m.group(1) for m in re.finditer(r'<BulletedList\b[^>]*>(.*?)</BulletedList>', seg, re.S)]


def paragraphs(seg):
    return [clean(p) for p in re.findall(r'<Paragraph\b[^>]*>(.*?)</Paragraph>', seg, re.S)]


# ---------------- 时间与日期 ----------------

DATE_RE = re.compile(
    r'^\s*(\d{1,2})\s*/\s*(\d{1,2})'
    r'(?:\s*[–\-—~至]\s*(\d{1,2})\s*/\s*(\d{1,2}))?'
    r'\s*(（[^）]{0,16}）)?'
)
MONTH_RE = re.compile(r'^\s*(\d{1,2})\s*月')


def parse_period_and_base(xml):
    """返回 (梳理区间文本, 整理日期文本, 基准年, 基准月)"""
    m = re.search(r'梳理区间[:：]\s*([^\\\n]+)', xml)
    period = clean(m.group(1)) if m else ""
    m2 = re.search(r'整理日期[:：]\s*([^\\\n]+)', xml)
    updated = clean(m2.group(1)) if m2 else ""
    y, mo = 2026, 10
    m3 = re.search(r'(20\d{2})\s*-\s*(\d{1,2})\s*-\s*(\d{1,2})', updated or period)
    if m3:
        y, mo = int(m3.group(1)), int(m3.group(2))
    return period, updated, y, mo


def make_iso(label, base_y, base_m):
    """把 "10/30（已产出）" / "12/8–12/9" / "1月–2月（全期）" 归一为可排序的 ISO 日期"""
    m = DATE_RE.match(label or "")
    if m:
        mon, day = int(m.group(1)), int(m.group(2))
    else:
        m = MONTH_RE.match(label or "")
        if not m:
            return None
        mon, day = int(m.group(1)), 1
    year = base_y if mon >= base_m else base_y + 1
    if mon < 1 or mon > 12 or day < 1 or day > 31:
        return None
    try:
        return datetime.date(year, mon, day).isoformat()
    except ValueError:
        return None


def split_date_label(label):
    """拆出 "10/30（已产出）" → ('10/30（已产出）', 剩余标题文本)"""
    m = DATE_RE.match(label or "")
    if not m:
        return None, label
    shown = f"{int(m.group(1))}/{int(m.group(2))}"
    if m.group(3):
        shown += f"–{int(m.group(3))}/{int(m.group(4))}"
    if m.group(5):
        shown += m.group(5)
    return shown, (label or "")[m.end():].strip()


def norm_cert(s):
    s = s or ""
    for k in ("🔶", "🔁", "✅"):
        if k in s:
            return k
    return "✅"


def cat_name(raw):
    raw = raw or ""
    for k, v in CAT_MAP.items():
        if k in raw:
            return v
    raw = re.sub(r'年级?别', '', raw).strip()
    return raw or "综合"


# 速览表无"类别"列，按事件关键词推断所属口径（命中即止，顺序即优先级）
CAT_KW = [
    (r'休市|交割|长假|假期|纪念日', "休市/交割"),
    (r'解禁|减持|回购|两融|北向|基金发行|ETF|成交额|增量资金|杠杆', "资金面"),
    (r'IPO|上市|招股|注册|配售|并购|重组|分拆', "IPO/资本事件"),
    (r'财报|业绩|预告|营收|指引|法说会', "公司/个股事件"),
    (r'火箭|卫星|航天|首飞|飞船|发射', "商业航天"),
    (r'机器人|算力|AI|人工智能|芯片|GPU|半导体|存储|HBM|DRAM|模型|云', "AI/算力/半导体"),
    (r'CPI|PMI|GDP|非农|PCE|PPI|社融|进出口|经济数据|就业|零售|销量|投资|工业增加值', "宏观数据"),
    (r'监管|新规|细则|制度|改革|规划|条例|审议', "监管/制度"),
    (r'美联储|FOMC|央行|政治局|国务院|关税|谈判|选举|峰会|G20|APEC|会议|降准|降息|加息|政策', "宏观政策/流动性"),
]


def guess_cat(event, impact=""):
    for pat, name in CAT_KW:
        if re.search(pat, event or ""):
            return name
    return "综合"


def _nk(s):
    """归一化事件名用于去重：仅保留汉字/字母/数字"""
    return re.sub(r'[^\w\u4e00-\u9fff]', '', s or "")


def similar_event(a, b, n=10):
    """同一日期下判断两条是否为同一事件：短前缀包含即视为重复"""
    x, y = _nk(a)[:n], _nk(b)[:n]
    if not x or not y:
        return False
    return x.startswith(y[:6]) or y.startswith(x[:6])


def short_title(text, limit=64):
    t = (text or "").strip()
    for sep in ("——", "—", "：", "。", "；（"):
        i = t.find(sep)
        if 4 < i < limit:
            t = t[:i]
            break
    t = t.strip(" —-·,，。、")
    return t[:limit] + ("…" if len(t) > limit else "")


# ---------------- 各区块解析 ----------------

def parse_timeline(xml, base_y, base_m):
    """一、时间线总览（列表，全字段）+ 二、重要性速览（4 列表格，补全遗漏项）"""
    out = []
    by_date = {}

    def find_dup(date_key, event):
        for e in by_date.get(date_key, []):
            if similar_event(e["event"], event):
                return e
        return None

    def add(date_label, event, cat, impact, cert, imp, src):
        if not date_label or not event:
            return
        dkey = re.sub(r'\D', '', date_label)
        dup = find_dup(dkey, event)
        if dup is not None:
            # 列表式条目字段更全，覆盖速览表版本
            if src == "timeline" and dup["src"] == "brief":
                dup.update({"event": event, "cat": cat, "impact": impact,
                            "certainty": cert, "imp": imp, "src": src})
            return
        item = {
            "date": date_label,
            "iso": make_iso(date_label, base_y, base_m),
            "event": event,
            "cat": cat,
            "impact": impact,
            "certainty": cert,
            "imp": imp,
            "src": src,
        }
        out.append(item)
        by_date.setdefault(dkey, []).append(item)

    # 1) 列表式时间线（字段最全）
    i = xml.find('一、时间线总览')
    j = xml.find('二、重要性速览')
    seg = xml[i:j] if (i >= 0 and j > i) else xml
    for item in bullets(seg):
        text = clean(item)
        parts = [p.strip() for p in text.split('｜')]
        head, cat, impact, cert, imp = text, "综合", "", "✅", 4
        if len(parts) >= 5 and re.fullmatch(r'\d{1,2}', parts[-1] or ''):
            head = '｜'.join(parts[:-4]).strip()
            cat = cat_name(parts[-4])
            impact = parts[-3].strip()
            cert = norm_cert(parts[-2])
            imp = int(parts[-1])
        labels = [clean(x) for x in re.findall(r'<Mark\b[^>]*bold[^>]*>(.*?)</Mark>', item, re.S)]
        date_label, rest = split_date_label(head)
        if not date_label:
            continue
        title = ""
        for lb in labels[1:]:
            if len(lb) > 4 and not re.match(r'^\d{1,2}/\d{1,2}', lb):
                title = lb
                break
        if not title:
            title = short_title(rest)
        else:
            title = short_title(title)
        # 空影响板块时从正文兜底
        add(date_label, title, cat, impact or "全市场", cert, imp, "timeline")

    # 2) 速览表（按等级分块的多张 4 列表）
    for rows in extract_tables(xml):
        if not rows:
            continue
        head = [c.strip() for c in rows[0]]
        if not head or '重要性' not in head[0] or '日期' not in (head[1] if len(head) > 1 else ''):
            continue
        for cells in rows[1:]:
            cells = [c.strip() for c in cells if c.strip() and c.strip() != '__EMPTY__']
            if len(cells) < 4:
                continue
            m = re.match(r'^(\d{1,2})', cells[0])
            if not m:
                continue
            date_label, _ = split_date_label(cells[1])
            if not date_label:
                continue
            add(date_label, short_title(cells[2], 70), guess_cat(cells[2], cells[3]),
                cells[3], "✅", int(m.group(1)), "brief")

    # 排序：iso 优先，缺失者按 (月,日) 兜底
    def sk(e):
        if e["iso"]:
            return (0, e["iso"])
        m = re.match(r'^(\d{1,2})/(\d{1,2})', e["date"] or "")
        if m:
            return (1, f"{int(m.group(1)):02d}-{int(m.group(2)):02d}")
        return (2, e["date"] or "")

    out.sort(key=sk)
    return out


def split_points(text, chunk=110, max_points=6):
    """长段落 → 若干要点：优先按 ①②③ 编号，否则按句号累积切块"""
    text = (text or "").strip()
    if not text:
        return []
    idx = [(text.find(c), c) for c in CIRCLED if text.find(c) >= 0]
    if len(idx) >= 2:
        idx.sort()
        pts = []
        for k, (pos, _c) in enumerate(idx):
            end = idx[k + 1][0] if k + 1 < len(idx) else len(text)
            p = text[pos + 1:end].strip(" ；;。")
            if len(p) > 8:
                pts.append(p)
        return pts[:max_points]
    sents = re.split(r'(?<=[。；])', text)
    pts, buf = [], ""
    for s in sents:
        s = s.strip()
        if not s:
            continue
        if len(buf) + len(s) > chunk and buf:
            pts.append(buf.strip())
            buf = s
        else:
            buf += s
    if buf.strip():
        pts.append(buf.strip())
    return pts[:max_points]


def parse_deep(xml):
    """三、结构观察：H3「M/D 新增：标题」+ 元信息段 + 要点段"""
    i = xml.find('三、结构观察')
    seg = xml[i:] if i >= 0 else ""
    if not seg:
        return []
    deep = []
    for hm in re.finditer(r'<Heading\b[^>]*level="3"[^>]*>(.*?)</Heading>(.*?)(?=<Heading\b|$)', seg, re.S):
        title = clean(hm.group(1))
        if len(title) < 8:
            continue
        body_ps = paragraphs(hm.group(2))
        meta_p = next((p for p in body_ps if '重要性' in p or '类别' in p), "")
        imp = ""
        m = re.search(r'重要性[:：]\s*([\d\-–/]+)', meta_p)
        if m:
            imp = m.group(1)
        if not imp:
            m = re.match(r'^(\d{1,2}/\d{1,2})', title)
            imp = m.group(1) if m else "观察"
        if '主要影响板块' in meta_p:
            mm = re.search(r'主要影响板块[:：]\s*([^｜|]+)', meta_p)
            if mm:
                last_pt = f"影响板块：{mm.group(1).strip()}"
            else:
                last_pt = ""
        else:
            last_pt = ""
        key_ps = [p for p in body_ps if p.startswith('要点') or len(p) > 60]
        points = []
        for p in key_ps[:2]:
            points += split_points(re.sub(r'^要点[:：]\s*', '', p))
        if last_pt:
            points.append(last_pt)
        if not points:
            continue
        t = re.sub(r'^\d{1,2}/\d{1,2}\s*新增[:：]\s*', '', title)
        t = re.sub(r'^\d{1,2}/\d{1,2}\s*', '', t).strip()
        deep.append({"title": short_title(t, 70), "imp": imp, "points": points[:6]})
    # 无 H3 时退回：用该段列表项
    if not deep:
        for item in bullets(seg):
            txt = clean(item)
            deep.append({"title": short_title(txt, 60), "imp": "观察",
                         "points": split_points(txt)})
    return deep


def parse_risks(xml):
    txt = re.sub(r'<[^>]+>', ' ', xml)
    txt = re.sub(r'\s+', ' ', txt)
    risks = []
    k = txt.find('关键风险清单')
    if k >= 0:
        seg = txt[k:k + 3000]
        # 上行风险单独成条
        up = ""
        mu = re.search(r'上行风险[:：]\s*(.{10,400}?)(?:。|$)', seg)
        if mu:
            up = "上行风险：" + mu.group(1).strip()
        idx = sorted([(seg.find(c), c) for c in CIRCLED if seg.find(c) >= 0])
        for n, (pos, _c) in enumerate(idx):
            end = idx[n + 1][0] if n + 1 < len(idx) else min(len(seg), pos + 500)
            item = seg[pos + 1:end].strip(" ；;。")
            if len(item) > 10:
                risks.append(item)
        if up and not any('上行' in r for r in risks):
            risks.append(up)
    return risks + RISK_USAGE


def parse_doc(xml):
    period, doc_updated, base_y, base_m = parse_period_and_base(xml)
    timeline = parse_timeline(xml, base_y, base_m)
    deep = parse_deep(xml)
    risks = parse_risks(xml)
    return {
        "meta": {
            "title": "未来2月影响股市的重大事件时间表（含重要性等级）",
            "period": period,
            "doc_updated": doc_updated,
            "synced_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "updated": "自动同步自资料库文档",
            "source": "资料库文档《未来2月影响股市的重大事件时间表（含重要性等级）》",
            "doc_url": f"https://www.workbuddy.cn/space/d/{DOC_NODE_ID}",
            "count": len(timeline),
        },
        "certainty_map": CERT_MAP,
        "importance_desc": IMP_DESC,
        "cat_map": CAT_MAP,
        "timeline": timeline,
        "deep": deep,
        "sectors": SECTORS_OUTLOOK,
        "risks": risks,
    }


EXTRA_PATH = os.path.join(DATA_DIR, "events_extra.json")


def merge_extra(data):
    """把人工核实补充的超重大事件合并进时间线（独立文件，文档同步不会覆盖）。

    设计动机：资料库文档按月末更新，月中突发的治理级/监管级黑天鹅（如 11/12 英伟达
    黄仁勋辞职）无法进入文档，导致事件日历漏掉最高权重变量。
    """
    if not os.path.exists(EXTRA_PATH):
        data["meta"]["extra_count"] = 0
        return data
    try:
        with open(EXTRA_PATH, "r", encoding="utf-8") as f:
            extra = json.load(f)
    except Exception as e:
        print(f"[补充事件] 读取失败（跳过，不影响文档同步）：{e}")
        data["meta"]["extra_count"] = 0
        return data

    seen = {
        (str(e.get("iso") or "")[:10], re.sub(r"[^\w\u4e00-\u9fff]", "", str(e.get("event") or ""))[:14])
        for e in data["timeline"]
    }
    added = 0
    for e in extra.get("events", []):
        key = (str(e.get("iso") or "")[:10], re.sub(r"[^\w\u4e00-\u9fff]", "", str(e.get("event") or ""))[:14])
        if key in seen:
            continue
        seen.add(key)
        e.setdefault("src", "extra")
        data["timeline"].append(e)
        added += 1

    # 整体按 iso 排序（无 iso 的排最后，保持文档原序）
    data["timeline"].sort(key=lambda x: (str(x.get("iso") or "9999-99-99"), x.get("date") or ""))
    data["meta"]["extra_count"] = added
    data["meta"]["extra_updated"] = extra.get("meta", {}).get("updated_at")
    data["meta"]["extra_keep_days"] = extra.get("meta", {}).get("keep_days", 14)
    print(f"[补充事件] 合并 {added} 条人工核实事件（共 {len(data['timeline'])} 条）")
    return data


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
            print(("  " * (lv - 1)) + f"[H{lv}] {h[:70]}")
        print("\n=== 表格结构 ===")
        for ti, rows in enumerate(extract_tables(xml)):
            print(f"--- Table{ti + 1} ({len(rows)}行) ---")
            for cells in rows[:4]:
                print("  |", " | ".join(c[:22] for c in cells))
        data = merge_extra(parse_doc(xml))
        print("\n=== 解析结果自检 ===")
        print(f"timeline={len(data['timeline'])} deep={len(data['deep'])} "
              f"sectors={len(data['sectors'])} risks={len(data['risks'])}")
        print(f"period={data['meta']['period']} | doc_updated={data['meta']['doc_updated']}")
        for e in data["timeline"][:5]:
            print("  ", e["iso"], e["date"], e["imp"], e["certainty"], e["cat"], "|", e["event"][:40])
        print("   ...")
        for e in data["timeline"][-5:]:
            print("  ", e["iso"], e["date"], e["imp"], e["certainty"], e["cat"], "|", e["event"][:40])
        return 0
    data = merge_extra(parse_doc(xml))
    if not data["timeline"]:
        print("解析结果为空，保留原 events.json")
        return 1
    out_path = os.path.join(DATA_DIR, "events.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"OK -> {out_path}  timeline={len(data['timeline'])} deep={len(data['deep'])} "
          f"sectors={len(data['sectors'])} risks={len(data['risks'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
