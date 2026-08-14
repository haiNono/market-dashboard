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
  .wrap { max-width:1280px; margin:0 auto; padding:20px 16px 40px; }
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
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>A股市场情绪监控 Dashboard</h1>
    <div class="meta" id="metaLine"></div>
  </header>

  <div class="card">
    <h2>中长期市场宽度 &amp; 全市场平均股价</h2>
    <div class="desc">左轴：站上20/50/120日均线的股票占比（%）｜右轴：全市场平均股价（元，前复权口径）｜<b id="rangeL"></b><br>告警规则：三条宽度线最新值全部&gt;80%显示过热警示（红），全部&lt;20%显示超卖提示（绿）</div>
    <div id="chartBreadthLong" class="chart-tall"></div>
  </div>

  <div class="card">
    <h2>短期市场宽度（5日 / 10日）</h2>
    <div class="desc">站上5日与10日均线的股票占比（%）｜两条宽度线最新值全部&gt;80%或全部&lt;20%时显示告警文字</div>
    <div id="chartBreadthShort" class="chart"></div>
  </div>

  <div class="card">
    <h2>申万二级行业宽度周变化 <span class="tag" id="indTag"></span></h2>
    <div class="desc">按"5日宽度周变化 + 10日宽度周变化"综合排序，左：改善最多 Top10 ｜ 右：恶化最多 Bottom10<br>着色规则：红=改善(正值) 绿=恶化(负值)，深色=5日 浅色=10日｜Top10 中偶见绿柱 = 该行业该项周变化为负、但另一项大幅改善使综合分靠前</div>
    <div class="dual">
      <div id="chartIndTop" class="chart"></div>
      <div id="chartIndBottom" class="chart"></div>
    </div>
    <div id="indTableWrap"></div>
  </div>

  <div class="card">
    <h2>关注板块对比（近半个月，首日=100）</h2>
    <div class="desc">归一化净值走势，便于横向对比相对强弱｜<b id="rangeS"></b><br>交互：点击某条图线或图例可聚焦该板块（其余变淡），再次点击或点击空白处恢复</div>
    <div id="chartSectors" class="chart-tall"></div>
  </div>

  <div class="card">
    <h2>ETF期权 Put/Call Ratio（成交量口径）</h2>
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
    type:'group', left:'center', top:50,
    children:[
      { type:'rect', shape:{ width:400, height:52, r:8 },
        style:{ fill: allHigh ? 'rgba(229,69,69,.10)' : 'rgba(24,160,88,.10)',
                stroke:color, lineWidth:1.5 } },
      { type:'text', left:200, top:26,
        style:{ text:text, fontSize:20, fontWeight:'bold', fill:color,
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
    title: { text:title, left:'center', textStyle:{ fontSize:13, color:'#4a5568' } },
    tooltip: baseTooltip(),
    legend: { data:['5日宽度周变化','10日宽度周变化'], top:22, textStyle:{ fontSize:11 } },
    grid: { left:110, right:40, top:52, bottom:24 },
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

    echarts_path = os.path.join(OUT_DIR, "echarts.min.js")
    with open(echarts_path, "r", encoding="utf-8") as fp:
        echarts_js = fp.read()

    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    html = html.replace("__ECHARTS__", echarts_js)

    out_path = os.path.join(OUT_DIR, "dashboard.html")
    with open(out_path, "w", encoding="utf-8") as fp:
        fp.write(html)
    print(f"生成 {out_path}  大小 {os.path.getsize(out_path)/1024:.0f}KB")

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
