'use strict';
// 演示只使用生成曲线与本会话数据，不请求业务 API。
const byId = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const storeKey = 'scwiki-spectra-navigation-demo-assigned';
function readAssignment() { try { return sessionStorage.getItem(storeKey) === 's300'; } catch { return false; } }
function refreshAssignment() {
  const assigned = readAssignment();
  byId('assigned-candidate').hidden = !assigned;
  byId('assignment-success').hidden = !assigned;
  byId('unassigned-row').hidden = assigned;
  byId('assigned-count').textContent = assigned ? '3' : '2';
  byId('unassigned-count').textContent = assigned ? '0' : '1';
}
function signal(x, series) {
  const g = (m, w, a) => a * Math.exp(-(((x - m) / w) ** 2));
  if (series === 0) return g(7, 4, 1.7) + g(13, 3, 1.1);
  if (series === 1) return g(10, 4, 1.5) + g(18, 4, .8);
  return g(25, 5, 1.3) + g(35, 4, 1.7) + g(48, 5, 1.2) + g(59, 3, .85);
}
function amplitude(x, series, dos) {
  return dos ? signal(x, series) : signal(x, 2) * .75 + signal(x, 1) * .45;
}
function svgElement(name, attributes, text) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', name);
  Object.entries(attributes).forEach(([key, value]) => el.setAttribute(key, String(value)));
  if (text != null) el.textContent = text;
  return el;
}
function drawPlot(target, dos, source) {
  const svg = svgElement('svg', { viewBox:'0 0 520 280', role:'img', 'aria-label':source ? '示意来源图' : '提取结果演示图', class:'figure-svg' });
  svg.append(svgElement('rect', { width:520, height:280, fill:source ? '#fdfcf9' : '#fff' }));
  svg.append(svgElement('text', {x:52,y:22,fill:'#8a91a0','font-size':10}, dos ? 'DOS（示意幅值）' : 'α²F(ω)（示意幅值）'));
  for (let i = 0; i <= 4; i++) {
    const y = 45 + i * 43;
    svg.append(svgElement('path', { d:'M52 ' + y + 'H495', stroke:'#f0f1f5' }));
    svg.append(svgElement('text', { x:29,y:y+3,fill:'#a5adbb','font-size':9 }, (2.4-i*.6).toFixed(1)));
  }
  svg.append(svgElement('path', { d:'M52 35V217H495',fill:'none',stroke:'#bbc2cf' }));
  for (let f = 0; f <= 60; f += 10) svg.append(svgElement('text', { x:47+f/65*440,y:236,fill:'#9ba3b2','font-size':9 }, f));
  svg.append(svgElement('text', { x:225,y:260,fill:'#929aab','font-size':10 }, '频率 / THz'));
  const colors = dos ? ['#957bc4','#d8a85c','#5a9293'] : ['#6757d9'];
  colors.forEach((color, series) => {
    let path = '';
    for (let i = 0; i <= 130; i++) {
      const x = i * .5, value = amplitude(x, series, dos) + (source ? Math.sin(i*1.7)*.012 : 0);
      path += (i ? 'L' : 'M') + (52+x/65*440).toFixed(1) + ',' + (217-value*68).toFixed(1) + ' ';
    }
    const group = svgElement('g', { 'data-series':series });
    group.append(svgElement('path', { d:path,stroke:color,'stroke-width':2,fill:'none' }));
    if (!source) {
      const points = svgElement('g', { class:'observed-points' });
      for (let i = 0; i <= 26; i++) {
        const f = i * 2.4;
        points.append(svgElement('circle', { cx:52+f/65*440,cy:217-amplitude(f,series,dos)*68,r:2,fill:color,'fill-opacity':.55 }));
      }
      group.append(points);
    }
    svg.append(group);
  });
  if (!dos) svg.append(svgElement('path', { d:'M52 214C150 210 170 193 220 163S330 90 390 65S450 50 495 48',fill:'none',stroke:'#b8a2da','stroke-dasharray':'4 4' }));
  target.replaceChildren(svg);
}
function initDetail() {
  const state = params.get('state'), kind = params.get('kind');
  const unassigned = state === 'unassigned', candidate = params.get('candidate') === '1', dos = kind === 'dos';
  if (state === 's150') {
    byId('return-link').href = 'index.html#state-s150';
    byId('return-link').textContent = '← 返回材料状态 02';
  }
  if ((!['s300','unassigned'].includes(state)) || !['dos','a2f'].includes(kind) || (unassigned && !dos) || (candidate && (!dos || !readAssignment()))) {
    byId('detail-content').hidden = true; byId('invalid-target').hidden = false; return;
  }
  const name = dos ? '声子态密度 DOS' : 'Eliashberg 谱函数 α²F(ω)';
  const source = unassigned || candidate ? '补充材料 · 演示候选' : '主文 · 图 3' + (dos ? 'B' : 'C');
  byId('detail-title').textContent = name;
  document.title = name + ' · ' + (unassigned ? '归属待确认' : '300 GPa') + ' · SC-Wiki Demo';
  byId('context-source').textContent = unassigned ? '补充材料 · 压力与近似待核对' : candidate ? '演示候选 · 已手动确认材料归属，近似待核对' : '谐近似 · ' + source + ' · 0–65 THz';
  byId('review-source').textContent = source;
  byId('source-caption').textContent = source + ' · ' + (dos ? '元素投影声子态密度' : 'Eliashberg 谱与累计 λ');
  byId(dos ? 'dos-tab' : 'a2f-tab').classList.add('selected');
  if (candidate) {
    byId('source-page').textContent = '补充材料 · 页码待核对';
    byId('review-method').textContent = '待核对';
    byId('type-tabs').hidden = true;
  }
  if (unassigned) {
    byId('assignment-panel').hidden = false; byId('type-tabs').hidden = true;
    byId('context-state').textContent = '归属待确认';
    byId('return-link').textContent = '← 返回材料状态列表';
    byId('source-page').textContent = '补充材料 · 页码待核对';
    byId('source-state').textContent = '归属：待确认';
    byId('review-state').textContent = '待确认';
    byId('review-method').textContent = '待确认';
    byId('review-warning').textContent = '材料归属未明确，不能放入任何状态。';
  }
  if (!dos) {
    byId('curve-choice').replaceChildren(new Option('α²F 与累计 λ','all'));
    byId('plot-legend').innerHTML = '<span><i style="background:#6757d9"></i>α²F(ω)</span><span><i style="background:#b8a2da"></i>累计 λ（示意）</span>';
    byId('metric-label-1').textContent = '示例 λ 积分'; byId('metric-value-1').innerHTML = '3.31 <em>无量纲</em>';
    byId('metric-label-2').textContent = '示例 ωlog'; byId('metric-value-2').innerHTML = '962 <em>K</em>';
    byId('metric-note-2').textContent = '演示值，不代表真实提取结果';
    byId('metric-label-3').textContent = '与报告值的示例偏差'; byId('metric-value-3').innerHTML = '−0.9 <em>% · λ</em>';
    byId('metric-note-3').textContent = '同条件参考方可比较；此处仅示意';
    byId('amplitude-title').textContent = 'α²F 幅值';
    byId('review-warning').textContent = '核对原图、低频、缺口及同条件 λ、ωlog 对照；示例偏差不是实际验收结果。';
  }
  drawPlot(byId('source-plot'),dos,true); drawPlot(byId('extracted-plot'),dos,false);
  [10,10.5,11,11.5].forEach(f => {
    const row = document.createElement('tr');
    [f.toFixed(2),amplitude(f,2,dos).toFixed(5),'演示采样'].forEach(value => { const td=document.createElement('td');td.textContent=value;row.append(td); });
    byId('point-rows').append(row);
  });
  byId('show-points').addEventListener('change',event => document.querySelectorAll('.observed-points').forEach(group => group.style.display=event.target.checked ? '' : 'none'));
  byId('curve-choice').addEventListener('change',event => document.querySelectorAll('#extracted-plot [data-series]').forEach(group => group.style.opacity=event.target.value==='all'||group.dataset.series===event.target.value ? '1' : '.12'));
  byId('assign-state').addEventListener('change',event => byId('confirm-assignment').disabled=!event.target.value);
  byId('confirm-assignment').addEventListener('click',() => {
    try { sessionStorage.setItem(storeKey,'s300');location.href='index.html#state-s300'; }
    catch { byId('review-warning').textContent='当前浏览器不支持会话存储，请使用本机 HTTP 预览确认归属演示。'; }
  });
  byId('export-csv').addEventListener('click',() => {
    const rows=['demo_only,frequency_thz,amplitude'];
    for(let i=0;i<=130;i++) rows.push('true,'+i*.5+','+amplitude(i*.5,dos?2:0,dos));
    const url=URL.createObjectURL(new Blob(['\uFEFF'+rows.join('\n')],{type:'text/csv;charset=utf-8'}));
    const anchor=document.createElement('a');anchor.href=url;anchor.download='DEMO-ONLY-spectrum.csv';anchor.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
}
if (byId('detail-content')) initDetail();
else {
  refreshAssignment();
  byId('reset-assignment').addEventListener('click',()=>{try{sessionStorage.removeItem(storeKey);}catch{}refreshAssignment();});
  window.addEventListener('pageshow',refreshAssignment);
}
