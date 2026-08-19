# -*- coding: utf-8 -*-
"""生成单文件可交互 Dashboard: dashboard.html (数据+ECharts内联, 离线可用)"""
import os
import json
import base64

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "output")

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A股市场情绪监控 Dashboard</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:"Microsoft YaHei","PingFang SC",sans-serif; background:#f5f6f8; color:#2b3245; }
  .wrap { max-width:1480px; margin:0 auto; padding:20px 16px 40px; }
  header { background:linear-gradient(135deg,#1e3a5f,#2b5b8f); color:#fff; border-radius:10px;
           padding:20px 26px; margin-bottom:18px; }
  header h1 { font-size:22px; font-weight:600; }
  header .meta { margin-top:8px; font-size:13px; opacity:.85; line-height:1.7; }
  .card { background:#fff; border-radius:10px; padding:18px 20px; margin-bottom:18px;
          box-shadow:0 1px 3px rgba(30,45,80,.08); }
  .card h2 { font-size:16px; font-weight:600; color:#1e3a5f; margin-bottom:4px;
             border-left:4px solid #2b5b8f; padding-left:10px; }
  .card .desc { font-size:12px; color:#8a94a6; margin:6px 0 10px 14px; }
  .chart { width:100%; height:380px; }
  .chart-tall { width:100%; height:460px; }
  .dual { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
  @media (max-width:900px){ .dual{ grid-template-columns:1fr; } }
  table { width:100%; border-collapse:collapse; font-size:12.5px; margin-top:8px; }
  th { background:#f0f3f7; color:#4a5568; padding:7px 8px; text-align:right; font-weight:600; }
  th.sortable { cursor:pointer; user-select:none; }
  th.sortable:hover { background:#dde5ef; color:#1e3a5f; }
  th:first-child, td:first-child { text-align:left; }
  td { padding:6px 8px; border-bottom:1px solid #eef1f5; text-align:right; }
  tr:hover td { background:#f8fafc; }
  .up { color:#e54545; font-weight:600; }
  .down { color:#18a058; font-weight:600; }
  .tag { display:inline-block; font-size:11px; background:#eef3fa; color:#2b5b8f;
         border-radius:3px; padding:1px 6px; margin-left:6px; }
  footer { font-size:12px; color:#8a94a6; line-height:1.9; background:#fff;
           border-radius:10px; padding:14px 20px; }
  .src { color:#2b5b8f; }
  /* 图表用法问号气泡 */
  .qmark { display:inline-flex; align-items:center; justify-content:center;
           width:15px; height:15px; border-radius:50%; background:#9aa6ba; color:#fff;
           font-size:11px; font-weight:700; line-height:1; cursor:help; margin-left:8px;
           position:relative; vertical-align:middle; }
  .qmark:hover { background:#2b5b8f; }
  .qtip { visibility:hidden; opacity:0; position:absolute; top:148%; left:50%;
          transform:translateX(-50%); width:300px; background:#1f2a3a; color:#e9edf3;
          text-align:left; padding:9px 11px; border-radius:7px; font-size:11.5px;
          line-height:1.65; font-weight:400; white-space:normal; z-index:999;
          box-shadow:0 6px 18px rgba(0,0,0,.25); transition:opacity .15s; }
  .qtip::after { content:''; position:absolute; bottom:100%; left:50%;
                 transform:translateX(-50%); border:6px solid transparent;
                 border-bottom-color:#1f2a3a; }
  .qmark:hover .qtip { visibility:visible; opacity:1; }
  /* 行业模块子图卡片(承接问号小标题) */
  .subcard { background:#fbfcfe; border:1px solid #eef1f5; border-radius:8px; padding:10px 12px; }
  .subtitle { font-size:13.5px; font-weight:600; color:#33405a; margin-bottom:6px; }
  /* 侧边目录导航 */
  html { scroll-behavior:smooth; }
  .layout { display:flex; align-items:flex-start; gap:18px; }
  .main { flex:1; min-width:0; }
  .card { scroll-margin-top:14px; }
  .sidenav { position:sticky; top:18px; width:190px; flex-shrink:0;
             background:#fff; border-radius:10px; padding:12px 10px;
             box-shadow:0 1px 3px rgba(30,45,80,.08); }
  .sidenav .nav-title { font-size:11px; color:#9aa6ba; letter-spacing:2px;
                        font-weight:600; padding:2px 10px 8px; }
  .sidenav a { display:block; padding:7px 10px; margin-bottom:1px; border-radius:6px;
               color:#4a5568; font-size:13px; text-decoration:none;
               border-left:3px solid transparent; transition:all .15s; }
  .sidenav a:hover { background:#f0f3f8; color:#1e3a5f; }
  .sidenav a.active { background:#eaf1f9; color:#1e3a5f; font-weight:600; border-left-color:#2b5b8f; }
  .sidenav a .no { display:inline-block; width:20px; color:#9aa6ba; font-size:12px; }
  .sidenav a.active .no { color:#2b5b8f; }
  .sidenav a.backtop { margin-top:8px; border-top:1px solid #eef1f5; padding-top:9px; color:#8a94a6; }
  @media (max-width:1150px){ .sidenav { display:none; } }
  /* 页面切换 tab */
  .tabs { display:flex; gap:8px; margin-top:12px; flex-wrap:wrap; }
  .tab { padding:7px 18px; border:1px solid rgba(255,255,255,.35); background:rgba(255,255,255,.12);
         color:#fff; border-radius:20px; font-size:13px; cursor:pointer; transition:all .15s; }
  .tab:hover { background:rgba(255,255,255,.24); }
  .tab.active { background:#fff; color:#1e3a5f; font-weight:600; }
  /* 事件页：过滤与重要性色块 */
  .filter-bar { display:flex; gap:8px; margin:6px 0 4px 14px; flex-wrap:wrap; }
  .fbtn { padding:5px 14px; border:1px solid #dde3ec; background:#fff; color:#4a5568;
          border-radius:14px; font-size:12px; cursor:pointer; transition:all .15s; }
  .fbtn:hover { border-color:#2b5b8f; color:#1e3a5f; }
  .fbtn.active { background:#2b5b8f; border-color:#2b5b8f; color:#fff; font-weight:600; }
  .lg { display:inline-block; width:18px; height:18px; border-radius:50%; color:#fff;
        font-size:10px; font-weight:700; text-align:center; line-height:18px; margin:0 2px; }
  .lg10{ background:#b71c1c; } .lg9{ background:#e54545; } .lg8{ background:#e8703a; }
  .lg7{ background:#f2a93b; } .lg6{ background:#d4a017; } .lg5{ background:#3aa6a6; } .lg4{ background:#7a8599; }
  /* 事件时间线 */
  .ev-timeline { position:relative; margin:10px 0 0 14px; padding-left:22px; }
  .ev-timeline::before { content:''; position:absolute; left:6px; top:8px; bottom:8px; width:2px;
                         background:#e3e8f0; }
  .ev-item { position:relative; display:flex; gap:10px; padding-bottom:14px; }
  .ev-item::before { content:''; position:absolute; left:-22px; top:9px; width:10px; height:10px;
                     border-radius:50%; background:#c3ccd8; border:2px solid #fff;
                     box-shadow:0 0 0 2px #c3ccd8; }
  .ev-item.top::before { background:#e54545; box-shadow:0 0 0 2px #e54545; }
  .ev-date { font-size:12.5px; font-weight:700; color:#2b5b8f; width:88px; flex-shrink:0; padding-top:3px; }
  .ev-body { flex:1; min-width:0; background:#fbfcfe; border:1px solid #eef1f5; border-radius:8px;
             padding:8px 12px; }
  .ev-top { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
  .ev-imp { color:#fff; font-size:11px; font-weight:700; min-width:20px; height:20px; padding:0 5px;
            border-radius:10px; display:inline-flex; align-items:center; justify-content:center; }
  .ev-name { font-size:13.5px; font-weight:600; color:#2b3245; }
  .ev-cat { font-size:11px; color:#6b7689; background:#f0f3f8; padding:1px 7px; border-radius:9px; }
  .ev-cert { font-size:12px; }
  .ev-impact { font-size:12px; color:#8a94a6; margin-top:4px; }
  /* 重点事件解读 */
  .deep-item { background:#fbfcfe; border:1px solid #eef1f5; border-left:3px solid #2b5b8f;
               border-radius:8px; padding:10px 14px; margin:0 0 12px 14px; }
  .deep-head { font-size:13.5px; font-weight:600; color:#1e3a5f; margin-bottom:6px; }
  .deep-imp { display:inline-block; background:#e54545; color:#fff; font-size:11px; font-weight:700;
              padding:1px 8px; border-radius:9px; margin-right:8px; vertical-align:1px; }
  .deep-item ul { margin:0; padding-left:20px; }
  .deep-item li { font-size:12.5px; color:#4a5568; line-height:1.75; margin-bottom:2px; }
  /* 板块映射与核心个股 */
  .sec-item { background:#fbfcfe; border:1px solid #eef1f5; border-radius:8px; padding:10px 14px;
              margin:0 0 12px 14px; }
  .sec-theme { font-size:14px; font-weight:700; color:#1e3a5f; margin-bottom:6px;
               border-left:3px solid #f2a93b; padding-left:8px; }
  .sec-row { font-size:12.5px; color:#4a5568; line-height:1.7; }
  .sec-row b { color:#2b5b8f; }
  .ev-note { font-size:11.5px; color:#9aa6ba; margin:4px 0 0 14px; }
  /* 风险提示 */
  .risk-list { margin:4px 0 0 34px; }
  .risk-list li { font-size:12.5px; color:#4a5568; line-height:1.8; margin-bottom:4px; }
</style>
</head>
<body id="top">
<div class="wrap">
  <div class="layout">
    <aside class="sidenav">
      <div id="navMarket">
        <div class="nav-title">目录导航</div>
        <a href="#sec1"><span class="no">①</span>中长期宽度</a>
        <a href="#sec2"><span class="no">②</span>短期宽度</a>
        <a href="#sec3"><span class="no">③</span>行业轮动</a>
        <a href="#sec4"><span class="no">④</span>关注板块</a>
        <a href="#sec5"><span class="no">⑤</span>期权PCR</a>
        <a href="#top" class="backtop"><span class="no">↑</span>回到顶部</a>
      </div>
      <div id="navEvents" style="display:none">
        <div class="nav-title">事件时间表</div>
        <a href="#ev0"><span class="no">📅</span>事件时间线</a>
        <a href="#ev1"><span class="no">📖</span>重点解读</a>
        <a href="#ev2"><span class="no">🗺️</span>板块映射</a>
        <a href="#ev3"><span class="no">⚠️</span>风险提示</a>
        <a href="#top" class="backtop"><span class="no">↑</span>回到顶部</a>
      </div>
    </aside>
    <div class="main">
  <header>
    <h1>A股市场情绪监控 Dashboard</h1>
    <div class="meta" id="metaLine"></div>
    <div class="tabs">
      <button class="tab active" data-tab="market">📊 市场看板</button>
      <button class="tab" data-tab="events">📅 事件时间表</button>
    </div>
  </header>

  <div id="pageMarket" class="page">

  <div class="card" id="sec1">
    <h2>中长期市场宽度 &amp; 全市场平均股价<span class="qmark">?<span class="qtip">左轴三条线 = 站上20/50/120日均线的股票占比(%)。三线呈"20&gt;50&gt;120"阶梯且都&gt;60%为理想多头；若20高但120低(如当前)则是"短期反弹、长期套牢重"结构。右轴为全市场平均股价(前复权)。三线全&gt;80%弹过热警示、全&lt;20%弹超卖提示。</span></span></h2>
    <div class="desc">左轴：站上20/50/120日均线的股票占比（%）｜右轴：全市场平均股价（元，前复权口径）｜<b id="rangeL"></b><br>告警规则：三条宽度线最新值全部&gt;80%显示过热警示（红），全部&lt;20%显示超卖提示（绿）</div>
    <div id="chartBreadthLong" class="chart-tall"></div>
  </div>

  <div class="card" id="sec2">
    <h2>短期市场宽度（5日 / 10日）<span class="qmark">?<span class="qtip">站上5日/10日均线的股票占比(%)，短期情绪温度计。两线齐升=反弹初期情绪修复；齐跌=短期转弱。与"中长期宽度"配合：短中期共振走强=趋势确立。两线全&gt;80%或全&lt;20%时图中央弹告警。</span></span></h2>
    <div class="desc">站上5日与10日均线的股票占比（%）｜两条宽度线最新值全部&gt;80%或全部&lt;20%时显示告警文字</div>
    <div id="chartBreadthShort" class="chart"></div>
  </div>

  <div class="card" id="sec3">
    <h2>申万二级行业宽度周变化 <span class="tag" id="indTag"></span><span class="qmark">?<span class="qtip">按申万二级行业统计"站上5/10日均线"股票占比及其周变化。下方左图=本周改善最多的10行业，右图=恶化最多的10行业，用于发现资金行业流向。下方完整127行业表格可按任意列点击排序。</span></span></h2>
    <div class="desc">按"5日宽度周变化 + 10日宽度周变化"综合排序，左：改善最多 Top10 ｜ 右：恶化最多 Bottom10<br>着色规则：红=改善(正值) 绿=恶化(负值)，深色=5日 浅色=10日｜Top10 中偶见绿柱 = 该行业该项周变化为负、但另一项大幅改善使综合分靠前</div>
    <div class="dual">
      <div class="subcard">
        <div class="subtitle">改善最多 Top10<span class="qmark">?<span class="qtip">本周改善最多(5日+10日宽度周变化综合靠前)的10个申万二级行业。红柱=该项周变化为正(改善)、绿柱=为负(恶化)；深色=5日、浅色=10日。偶见绿柱=该项短期回落但另一项大幅改善使综合靠前。</span></span></div>
        <div id="chartIndTop" class="chart"></div>
      </div>
      <div class="subcard">
        <div class="subtitle">恶化最多 Bottom10<span class="qmark">?<span class="qtip">本周恶化最多的10个行业。绿柱=该项为负(恶化)、红柱=为正；深色=5日、浅色=10日。用于规避资金流出行业。结合下方表格绝对值可区分"极弱回补"与"强趋势回落"。</span></span></div>
        <div id="chartIndBottom" class="chart"></div>
      </div>
    </div>
    <div id="indTableWrap"></div>
  </div>

  <div class="card" id="sec4">
    <h2>关注板块对比（近半个月，首日=100）<span class="qmark">?<span class="qtip">你关注的10个板块近半个月归一化净值(首日=100)，直接比相对强弱——线越靠上=同期越强。点击某条线或图例可"聚焦"该板块(其余变淡)，再点或点空白恢复。用于对比半导体/算力/券商等强弱轮动。</span></span></h2>
    <div class="desc">归一化净值走势，便于横向对比相对强弱｜<b id="rangeS"></b><br>交互：点击某条图线或图例可聚焦该板块（其余变淡），再次点击或点击空白处恢复</div>
    <div id="chartSectors" class="chart-tall"></div>
  </div>

  <div class="card" id="sec5">
    <h2>ETF期权 Put/Call Ratio（成交量口径）<span class="qmark">?<span class="qtip">认沽成交量÷认购成交量。&gt;1 认沽更活跃(情绪偏空/可能见底)，&lt;1 偏多。逆向指标：极端高(如&gt;1.2)常对应阶段底、极端低(&lt;0.6)常对应过热。三条线对应沪深300/中证500/科创50ETF期权，可点击聚焦；PCR=1为参考线。</span></span></h2>
    <div class="desc">沪深300ETF / 中证500ETF / 科创50ETF 期权认沽认购成交量比，数据来源：上交所每日统计｜<b id="rangeP"></b><br>交互：点击图线或图例聚焦该品种（其余变淡），再次点击或点击空白处恢复；PCR=1 为参考线不参与聚焦</div>
    <div id="chartPcr" class="chart"></div>
  </div>

  <footer>
    <b>数据口径说明</b>：<br>
    · 市场宽度 = 当日收盘价高于 N 日均线的前复权收盘价股票数 ÷ 当日有效股票数（上市满 N 个交易日），统计范围：沪深京 A 股，剔除 ST/*ST/退市股及 B 股。<span class="src">来源：新浪财经日线，前复权。</span><br>
    · 平均股价为全市场有效股票收盘价简单算术平均（前复权口径，用于趋势观察）。<br>
    · 行业宽度按申万二级行业分类（124个），周变化 = 最近交易日比例 − 5个交易日前比例。<span class="src">来源：申万宏源官网成分。</span><br>
    · 板块：半导体材料/设备为申万三级成分等权自建指数；其余为同花顺概念/行业指数（端侧→消费电子，云服务器→云计算，光通信→共封装光学CPO）。<br>
    · 期权 PCR = 认沽成交量 ÷ 认购成交量。<span class="src">来源：上海证券交易所官网每日统计。</span><br>
    · 数据区间：2025-01-01 起（板块模块为近半个月），更新于 <span id="updatedAt"></span>。本页面仅供市场观察，不构成投资建议。
  </footer>
  </div>

  <div id="pageEvents" class="page" style="display:none">
    <div class="card" id="ev0">
      <h2>未来2月重大事件时间线（2026-08-16 ~ 10-16）<span class="qmark">?<span class="qtip">按时间顺序排列影响股市的 52 个事件。左侧数字徽章=重要性等级(1-10，越大越重要)，颜色分级：深红=10、红=9、橙红=8、橙=7、金黄=6、青蓝=5、灰=4。可按"全部 / ≥7重要 / ≥9核心"过滤。确定性：✅已确认 🔶预计 🔁派生。</span></span></h2>
      <div class="desc">重要性颜色：<span class="lg lg10">10</span><span class="lg lg9">9</span><span class="lg lg8">8</span><span class="lg lg7">7</span><span class="lg lg6">6</span><span class="lg lg5">5</span><span class="lg lg4">4</span> ｜ 确定性：✅已确认　🔶预计　🔁派生</div>
      <div class="filter-bar">
        <button class="fbtn active" data-min="0">全部事件</button>
        <button class="fbtn" data-min="7">≥7 重要</button>
        <button class="fbtn" data-min="9">≥9 核心</button>
      </div>
      <div class="ev-timeline" id="evTimeline"></div>
    </div>
    <div class="card" id="ev1">
      <h2>重点事件解读<span class="qmark">?<span class="qtip">10 个重点事件的详细解读：每条含催化逻辑、影响路径与跟踪要点，重要性标注在标题前。用于理解事件"为什么重要"及事件落地前后的板块交易逻辑（防"买预期卖事实"）。</span></span></h2>
      <div class="desc">来自文档"重点事件详解"：催化逻辑 · 影响路径 · 跟踪要点</div>
      <div id="evDeep"></div>
    </div>
    <div class="card" id="ev2">
      <h2>事件 → 板块映射与核心个股<span class="qmark">?<span class="qtip">把时间线事件映射到 7 条投资主线：每条含催化事件、受益板块与代表性核心个股。核心个股仅为板块代表性标的、非推荐买入，用于定位行情发起点与跟踪对象。</span></span></h2>
      <div class="desc">主线 → 催化事件 → 受益板块 → 核心个股（代表性标的，仅供研究参考）</div>
      <div id="evSectors"></div>
    </div>
    <div class="card" id="ev3">
      <h2>风险提示与用法建议<span class="qmark">?<span class="qtip">使用事件日历的 7 条风控要点：确定性分级、"买预期卖事实"、数据驱动锚点、解禁≠减持、三季报+解禁叠加、长假效应等。交易决策前先过一遍本条。</span></span></h2>
      <div class="desc">事件日历的使用边界与风控要点（非投资建议）</div>
      <div id="evRisks"></div>
    </div>
  </div>

    </div>
  </div>
</div>

<script>__ECHARTS__</script>
<script>
const DATA = __DATA__;

const C_UP = '#e54545', C_DOWN = '#18a058';
const PALETTE = ['#2b5b8f','#e54545','#f2a93b','#18a058','#8f4fc4','#e06fa8','#3aa6a6','#7a8599','#c46a1f','#5b8fd9'];

function lineSeries(name, data, color, yAxisIndex) {
  return { name:name, type:'line', data:data, yAxisIndex:yAxisIndex||0, showSymbol:false,
           smooth:0.2, lineStyle:{ width:1.6, color:color }, itemStyle:{ color:color } };
}
function baseTooltip() {
  return { trigger:'axis', axisPointer:{ type:'cross' },
           backgroundColor:'rgba(255,255,255,.96)', borderColor:'#dde3ec',
           textStyle:{ color:'#2b3245', fontSize:12 } };
}
function zoomX() {
  return [ { type:'inside', xAxisIndex:0 }, { type:'slider', xAxisIndex:0, height:18, bottom:6 } ];
}
function catX(dates) {
  return { type:'category', data:dates, boundaryGap:false,
           axisLabel:{ showMinLabel:true, showMaxLabel:true } };
}
// 宽度全同向告警: 全部<20 或 全部>80 时在图上叠加醒目文字
function breadthAlert(vals) {
  const allLow = vals.every(v=>v<20);
  const allHigh = vals.every(v=>v>80);
  if (!allLow && !allHigh) return [];
  const color = allHigh ? '#e54545' : '#18a058';
  const text = allHigh ? '全部宽度 > 80%：市场过热警示' : '全部宽度 < 20%：市场超卖提示';
  return [ {
    type:'group', right:16, top:12,
    children:[
      { type:'rect', shape:{ width:220, height:24, r:4 },
        style:{ fill: allHigh ? 'rgba(229,69,69,.08)' : 'rgba(24,160,88,.08)',
                stroke:color, lineWidth:1 } },
      { type:'text', left:110, top:12,
        style:{ text:text, fontSize:12, fontWeight:'bold', fill:color,
                textAlign:'center', textVerticalAlign:'middle' } }
    ]
  } ];
}
function lastOf(arr) { return arr[arr.length-1]; }

// ---- 1. 中长期宽度 + 平均股价 ----
(function(){
  const b = DATA.breadth;
  echarts.init(document.getElementById('chartBreadthLong')).setOption({
    tooltip: baseTooltip(),
    legend: { data:['20日宽度','50日宽度','120日宽度','平均股价'], top:0 },
    grid: { left:56, right:64, top:36, bottom:64 },
    xAxis: catX(b.dates),
    yAxis: [
      { type:'value', name:'宽度(%)', min:0, max:100, axisLabel:{ formatter:'{value}%' } },
      { type:'value', name:'平均股价(元)', scale:true, splitLine:{ show:false } }
    ],
    dataZoom: zoomX(),
    graphic: breadthAlert([lastOf(b.b20), lastOf(b.b50), lastOf(b.b120)]),
    series: [
      lineSeries('20日宽度', b.b20, PALETTE[0]),
      lineSeries('50日宽度', b.b50, PALETTE[1]),
      lineSeries('120日宽度', b.b120, PALETTE[2]),
      lineSeries('平均股价', b.avg_price, '#2b3245', 1)
    ]
  });
})();

// ---- 2. 短期宽度 ----
(function(){
  const b = DATA.breadth;
  echarts.init(document.getElementById('chartBreadthShort')).setOption({
    tooltip: baseTooltip(),
    legend: { data:['5日宽度','10日宽度'], top:0 },
    grid: { left:56, right:24, top:36, bottom:64 },
    xAxis: catX(b.dates),
    yAxis: [ { type:'value', name:'宽度(%)', min:0, max:100, axisLabel:{ formatter:'{value}%' } } ],
    dataZoom: zoomX(),
    graphic: breadthAlert([lastOf(b.b5), lastOf(b.b10)]),
    series: [
      lineSeries('5日宽度', b.b5, PALETTE[1]),
      lineSeries('10日宽度', b.b10, PALETTE[0])
    ]
  });
})();

// ---- 3. 行业宽度 Top10 / Bottom10 ----
function indBarOption(title, rows, legendColors) {
  const names = rows.map(r=>r.industry).reverse();
  const chg5 = rows.map(r=>r.chg5).reverse();
  const chg10 = rows.map(r=>r.chg10).reverse();
  return {
    tooltip: baseTooltip(),
    legend: { data:['5日宽度周变化','10日宽度周变化'], top:0, textStyle:{ fontSize:11 } },
    grid: { left:110, right:40, top:34, bottom:24 },
    xAxis: { type:'value', axisLabel:{ formatter:'{value}pp' } },
    yAxis: { type:'category', data:names, axisLabel:{ fontSize:11.5 } },
    series: [
      { name:'5日宽度周变化', type:'bar', barWidth:8, itemStyle:{ color:legendColors.main },
        data:chg5.map(v=>({ value:v,
          itemStyle:{ color: v>=0 ? C_UP : C_DOWN } })) },
      { name:'10日宽度周变化', type:'bar', barWidth:8, itemStyle:{ color:legendColors.light },
        data:chg10.map(v=>({ value:v,
          itemStyle:{ color: v>=0 ? '#f08c8c' : '#6fc79a' } })) }
    ]
  };
}
(function(){
  const ind = DATA.industry;
  const top10 = ind.slice(0,10);
  const bot10 = ind.slice(-10).reverse();
  echarts.init(document.getElementById('chartIndTop'))
    .setOption(indBarOption('改善最多 Top10', top10, { main:C_UP, light:'#f08c8c' }));
  echarts.init(document.getElementById('chartIndBottom'))
    .setOption(indBarOption('恶化最多 Bottom10', bot10, { main:C_DOWN, light:'#6fc79a' }));

  // 表格(全部行业, 可点击表头排序)
  const cmp = DATA.meta.industry_compare;
  document.getElementById('indTag').textContent = cmp.latest + ' vs ' + cmp.week_ago;
  document.getElementById('indTableWrap').innerHTML =
    '<table id="indTable"><thead><tr>' +
    '<th data-key="industry" class="sortable">行业</th>' +
    '<th data-key="n_stocks" class="sortable">成分数</th>' +
    '<th data-key="pct5" class="sortable">5日宽度%</th>' +
    '<th data-key="pct10" class="sortable">10日宽度%</th>' +
    '<th data-key="chg5" class="sortable">5日周变化pp</th>' +
    '<th data-key="chg10" class="sortable">10日周变化pp</th>' +
    '</tr></thead><tbody id="indTbody"></tbody></table>';

  let sortKey = 'score', sortDir = -1;
  const tbody = document.getElementById('indTbody');
  function renderIndRows() {
    const sorted = ind.slice().sort((a,b)=>{
      const va = a[sortKey], vb = b[sortKey];
      if (va==null && vb==null) return 0;
      if (va==null) return 1;
      if (vb==null) return -1;
      if (typeof va === 'string') return sortDir * va.localeCompare(vb, 'zh');
      return sortDir * (va - vb);
    });
    let html = '';
    sorted.forEach(r=>{
      const c5 = r.chg5==null ? '-' : (r.chg5>=0?'+':'') + r.chg5;
      const c10 = r.chg10==null ? '-' : (r.chg10>=0?'+':'') + r.chg10;
      const cls5 = r.chg5==null ? '' : (r.chg5>=0?'up':'down');
      const cls10 = r.chg10==null ? '' : (r.chg10>=0?'up':'down');
      html += '<tr><td>'+r.industry+'</td><td>'+r.n_stocks+'</td><td>'+r.pct5+'</td><td>'+r.pct10+
              '</td><td class="'+cls5+'">'+c5+'</td><td class="'+cls10+'">'+c10+'</td></tr>';
    });
    tbody.innerHTML = html;
    document.querySelectorAll('#indTable th.sortable').forEach(th=>{
      const base = th.dataset.label || th.textContent.replace(/[ ▲▼]/g,'');
      th.dataset.label = base;
      th.textContent = base + (th.dataset.key===sortKey ? (sortDir<0?' ▼':' ▲') : '');
    });
  }
  document.querySelectorAll('#indTable th.sortable').forEach(th=>{
    th.addEventListener('click', ()=>{
      const k = th.dataset.key;
      if (sortKey === k) { sortDir = -sortDir; } else { sortKey = k; sortDir = -1; }
      renderIndRows();
    });
  });
  renderIndRows();
})();

// ---- 4. 板块对比 (点击聚焦) ----
(function(){
  const s = DATA.sectors;
  const names = Object.keys(s);
  let dates = [];
  names.forEach(n=>{ if (s[n].dates.length > dates.length) dates = s[n].dates; });
  const series = names.map((n,i)=>{
    const m = {};
    s[n].dates.forEach((d,j)=>{ m[d]=s[n].values[j]; });
    return lineSeries(n, dates.map(d=>m[d]!==undefined?m[d]:null), PALETTE[i%PALETTE.length]);
  });
  const chart = echarts.init(document.getElementById('chartSectors'));
  chart.setOption({
    tooltip: baseTooltip(),
    legend: { data:names, top:0, type:'scroll' },
    grid: { left:52, right:24, top:44, bottom:64 },
    xAxis: catX(dates),
    yAxis: [ { type:'value', name:'净值(首日=100)', scale:true } ],
    dataZoom: zoomX(),
    series: series
  });

  // 聚焦逻辑: 点击某条线/图例 -> 其余线和图例变淡; 再点或点空白恢复
  let focusName = null;
  function fadeColor(hex) {
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    return 'rgba(' + r + ',' + g + ',' + b + ',0.15)';
  }
  function applyFocus() {
    chart.setOption({
      legend: { data: names.map(n=>({ name:n,
        textStyle:{ color: (!focusName || n===focusName) ? '#2b3245' : '#c8ccd4' } })) },
      series: names.map((n,i)=>{
        const on = !focusName || n === focusName;
        const c = on ? PALETTE[i%PALETTE.length] : fadeColor(PALETTE[i%PALETTE.length]);
        return { name:n, lineStyle:{ color:c, width: on ? 2 : 1 }, itemStyle:{ color:c } };
      })
    });
  }
  function toggleFocus(name) {
    focusName = (focusName === name) ? null : name;
    applyFocus();
  }
  chart.on('click', p=>{ if (p.seriesName) toggleFocus(p.seriesName); });
  chart.on('legendselectchanged', p=>{
    chart.dispatchAction({ type:'legendAllSelect' });
    toggleFocus(p.name);
  });
  chart.getZr().on('click', e=>{
    if (!e.target && focusName) { focusName = null; applyFocus(); }
  });
})();

// ---- 5. 期权PCR (点击聚焦) ----
(function(){
  const p = DATA.pcr;
  const names = Object.keys(p);
  let dates = [];
  names.forEach(n=>{ if (p[n].dates.length > dates.length) dates = p[n].dates; });
  const series = names.map((n,i)=>{
    const m = {};
    p[n].dates.forEach((d,j)=>{ m[d]=p[n].values[j]; });
    return lineSeries(n, dates.map(d=>m[d]!==undefined?m[d]:null), PALETTE[i%PALETTE.length]);
  });
  series.push({ name:'PCR=1', type:'line', data:dates.map(()=>1), showSymbol:false,
                lineStyle:{ type:'dashed', width:1, color:'#a0a8b8' }, itemStyle:{ color:'#a0a8b8' } });
  const chart = echarts.init(document.getElementById('chartPcr'));
  chart.setOption({
    tooltip: baseTooltip(),
    legend: { data:names.concat(['PCR=1']), top:0 },
    grid: { left:52, right:24, top:36, bottom:64 },
    xAxis: catX(dates),
    yAxis: [ { type:'value', name:'Put/Call', scale:true } ],
    dataZoom: zoomX(),
    series: series
  });

  // 聚焦逻辑(PCR=1参考线不参与聚焦, 聚焦时同步变淡)
  let focusName = null;
  function fadeColor(hex) {
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    return 'rgba(' + r + ',' + g + ',' + b + ',0.15)';
  }
  function applyFocus() {
    const refColor = focusName ? '#dde1e8' : '#a0a8b8';
    chart.setOption({
      legend: { data: names.map(n=>({ name:n,
          textStyle:{ color: (!focusName || n===focusName) ? '#2b3245' : '#c8ccd4' } }))
          .concat([{ name:'PCR=1', textStyle:{ color: focusName ? '#c8ccd4' : '#2b3245' } }]) },
      series: names.map((n,i)=>{
        const on = !focusName || n === focusName;
        const c = on ? PALETTE[i%PALETTE.length] : fadeColor(PALETTE[i%PALETTE.length]);
        return { name:n, lineStyle:{ color:c, width: on ? 2 : 1 }, itemStyle:{ color:c } };
      }).concat([{ name:'PCR=1',
        lineStyle:{ type:'dashed', width:1, color:refColor }, itemStyle:{ color:refColor } }])
    });
  }
  function toggleFocus(name) {
    focusName = (focusName === name) ? null : name;
    applyFocus();
  }
  chart.on('click', p=>{
    if (p.seriesName && names.indexOf(p.seriesName) >= 0) toggleFocus(p.seriesName);
  });
  chart.on('legendselectchanged', p=>{
    chart.dispatchAction({ type:'legendAllSelect' });
    if (names.indexOf(p.name) >= 0) toggleFocus(p.name);
  });
  chart.getZr().on('click', e=>{
    if (!e.target && focusName) { focusName = null; applyFocus(); }
  });
})();

// 元信息
(function(){
  const m = DATA.meta;
  document.getElementById('metaLine').textContent =
    '数据更新: ' + m.updated_at + ' ｜ 最新交易日: ' + m.latest_trade_date +
    ' ｜ 统计股票数: ' + m.stock_count + ' ｜ 区间: ' + m.data_start + ' 起';
  document.getElementById('updatedAt').textContent = m.updated_at;
  const bd = DATA.breadth.dates;
  document.getElementById('rangeL').textContent =
    '数据区间 ' + bd[0] + ' ~ ' + bd[bd.length-1] + '（' + bd.length + '个交易日）';
  const sk = Object.keys(DATA.sectors);
  if (sk.length) {
    let s0 = sk[0], s1 = sk[0];
    sk.forEach(n=>{
      const ds = DATA.sectors[n].dates;
      if (ds[0] < DATA.sectors[s0].dates[0]) s0 = n;
      if (ds[ds.length-1] > DATA.sectors[s1].dates[DATA.sectors[s1].dates.length-1]) s1 = n;
    });
    document.getElementById('rangeS').textContent =
      '数据区间 ' + DATA.sectors[s0].dates[0] + ' ~ ' +
      DATA.sectors[s1].dates[DATA.sectors[s1].dates.length-1];
  }
  const pk = Object.keys(DATA.pcr);
  if (pk.length) {
    const pd = DATA.pcr[pk[0]].dates;
    document.getElementById('rangeP').textContent =
      '数据区间 ' + pd[0] + ' ~ ' + pd[pd.length-1];
  }
})();

// 侧边导航 scrollspy：滚动时高亮当前可视模块（市场页/事件页各一套，隐藏页不参与）
function bindScrollspy(sel){
  const links = Array.from(document.querySelectorAll(sel));
  const ids = links.map(a=>a.getAttribute('href').slice(1));
  function onScroll(){
    const y = window.scrollY + 140;
    let current = ids[0];
    ids.forEach(id=>{
      const el = document.getElementById(id);
      if (el && el.offsetTop <= y && el.offsetParent !== null) current = id;
    });
    links.forEach(a=>a.classList.toggle('active', a.getAttribute('href')==='#'+current));
  }
  window.addEventListener('scroll', onScroll, {passive:true});
  onScroll();
}
bindScrollspy('.sidenav a[href^="#sec"]');
bindScrollspy('.sidenav a[href^="#ev"]');

// ---- 页面切换（市场看板 / 事件时间表）----
function switchPage(name){
  document.querySelectorAll('.page').forEach(p=>{ p.style.display = (p.id.toLowerCase() === 'page'+name) ? 'block' : 'none'; });
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active', t.dataset.tab === name));
  document.getElementById('navMarket').style.display = (name === 'market') ? 'block' : 'none';
  document.getElementById('navEvents').style.display = (name === 'events') ? 'block' : 'none';
  window.scrollTo(0,0);
  // 只 resize 当前可见页内的图表：对 display:none 容器 resize 会把 ECharts 画布压成 0 宽，
  // 切回时图表会空白。用 rAF 延迟到布局稳定后再 resize。
  const pageEl = document.getElementById('page' + name);
  if (typeof echarts !== 'undefined') {
    requestAnimationFrame(function(){
      pageEl.querySelectorAll('.chart,.chart-tall').forEach(function(el){
        const inst = echarts.getInstanceByDom(el);
        if (inst) inst.resize();
      });
    });
  }
}
document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click', ()=>switchPage(t.dataset.tab)));

// ---- 事件页渲染 ----
(function(){
  try {
  const ev = DATA.events_page;
  function impColor(imp){
    if (imp>=10) return '#b71c1c';
    if (imp>=9) return '#e54545';
    if (imp>=8) return '#e8703a';
    if (imp>=7) return '#f2a93b';
    if (imp>=6) return '#d4a017';
    if (imp>=5) return '#3aa6a6';
    return '#7a8599';
  }
  const cert = ev.certainty_map;
  function renderTimeline(minImp){
    const items = ev.timeline.filter(e=>e.imp>=minImp);
    document.getElementById('evTimeline').innerHTML = items.map(e=>
      '<div class="ev-item' + (e.imp>=9?' top':'') + '">' +
        '<div class="ev-date">' + e.date + '</div>' +
        '<div class="ev-body">' +
          '<div class="ev-top">' +
            '<span class="ev-imp" style="background:' + impColor(e.imp) + '" title="重要性 ' + e.imp + '/10">' + e.imp + '</span>' +
            '<span class="ev-name">' + e.event + '</span>' +
            '<span class="ev-cat">' + e.cat + '</span>' +
            '<span class="ev-cert" title="' + (cert[e.certainty]||'') + '">' + e.certainty + '</span>' +
          '</div>' +
          '<div class="ev-impact">影响：' + e.impact + '</div>' +
        '</div>' +
      '</div>').join('');
  }
  document.querySelectorAll('.fbtn').forEach(b=>b.addEventListener('click', ()=>{
    document.querySelectorAll('.fbtn').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    renderTimeline(parseInt(b.dataset.min,10));
  }));
  renderTimeline(0);

  document.getElementById('evDeep').innerHTML = ev.deep.map(d=>
    '<div class="deep-item"><div class="deep-head"><span class="deep-imp">' + d.imp + '</span>' + d.title + '</div><ul>' +
    d.points.map(p=>'<li>' + p + '</li>').join('') + '</ul></div>').join('');

  document.getElementById('evSectors').innerHTML = ev.sectors.map(s=>
    '<div class="sec-item"><div class="sec-theme">' + s.theme + '</div>' +
    '<div class="sec-row"><b>催化事件：</b>' + s.events + '</div>' +
    '<div class="sec-row"><b>受益板块：</b>' + s.sectors + '</div>' +
    '<div class="sec-row"><b>核心个股：</b>' + s.stocks + '</div></div>').join('') +
    '<div class="ev-note">核心个股仅为板块代表性标的，仅供研究参考，不构成投资建议。</div>';

  document.getElementById('evRisks').innerHTML =
    '<ol class="risk-list">' + ev.risks.map(r=>'<li>' + r + '</li>').join('') + '</ol>';
  } catch(e) { console.error('事件页渲染失败:', e); }
})();

window.addEventListener('resize', ()=>{
  document.querySelectorAll('.chart,.chart-tall').forEach(el=>{
    const inst = echarts.getInstanceByDom(el);
    if (inst) inst.resize();
  });
});
</script>
</body>
</html>
"""


def run():
    data_path = os.path.join(OUT_DIR, "dashboard_data.json")
    with open(data_path, "r", encoding="utf-8") as fp:
        data = json.load(fp)

    events_path = os.path.join(DATA_DIR, "events.json")
    with open(events_path, "r", encoding="utf-8") as fp:
        data["events_page"] = json.load(fp)

    echarts_path = os.path.join(OUT_DIR, "echarts.min.js")
    with open(echarts_path, "r", encoding="utf-8") as fp:
        echarts_js = fp.read()

    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    html = html.replace("__ECHARTS__", echarts_js)

    out_path = os.path.join(OUT_DIR, "dashboard.html")
    with open(out_path, "w", encoding="utf-8") as fp:
        fp.write(html)
    print(f"生成 {out_path}  大小 {os.path.getsize(out_path)/1024:.0f}KB")

    # GitHub Pages 部署副本: docs/index.html (Pages 仅支持根目录或 /docs)
    docs_dir = os.path.join(BASE_DIR, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    docs_path = os.path.join(docs_dir, "index.html")
    with open(docs_path, "w", encoding="utf-8") as fp:
        fp.write(html)
    print(f"生成 {docs_path}  大小 {os.path.getsize(docs_path)/1024:.0f}KB")

    # 抽出内联JS做语法自检 (最后一个script块已含DATA声明, 直接提取即可)
    start = html.rfind("<script>") + len("<script>")
    end = html.rfind("</script>")
    js_check = html[start:end]
    check_path = os.path.join(OUT_DIR, "_check.js")
    with open(check_path, "w", encoding="utf-8") as fp:
        fp.write(js_check)
    print(f"JS自检文件 {check_path}")


if __name__ == "__main__":
    run()
