import React, { useEffect, useRef, useState } from 'react';
import { rows, integral, reference } from './data.js';
import './prototype.css';

const colors = ['#6155d9', '#d25693', '#38a477'];
const names = ['La', 'Sc', 'H'];
const fmt = (v, n = 3) => Number.isFinite(v) ? (Math.abs(v) < 0.5 * 10 ** -n ? 0 : v).toFixed(n) : '—';
const title = kind => kind === 'dos' ? '声子 DOS 解析详情' : 'α²F 谱函数解析详情';

function Plot({ kind, vertical = false, overlay = false, source = false, visible = [true, true, true] }) {
  const ref = useRef(null);
  const [width, setWidth] = useState(480);
  useEffect(() => {
    const observer = new ResizeObserver(entries => setWidth(entries[0].contentRect.width));
    observer.observe(ref.current.parentElement);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const canvas = ref.current, ctx = canvas.getContext('2d');
    const w = width, h = width < 420 ? 280 : 330, left = 48, right = w - 22, top = 35, bottom = h - 48;
    canvas.width = w * 2; canvas.height = h * 2; ctx.scale(2, 2);
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, w, h);
    const dos = kind === 'dos', maxA = dos ? 1.25 : 1.5;
    const x = (f, a) => left + (right - left) * (vertical ? a / maxA : f / 70);
    const y = (f, a) => bottom - (bottom - top) * (vertical ? f / 70 : a / maxA);
    ctx.font = '11px sans-serif'; ctx.lineWidth = 1;
    for (let i = 0; i <= 7; i++) {
      const f = i * 10; ctx.strokeStyle = '#edf0f6'; ctx.beginPath();
      if (vertical) { ctx.moveTo(left, y(f, 0)); ctx.lineTo(right, y(f, 0)); }
      else { ctx.moveTo(x(f, 0), top); ctx.lineTo(x(f, 0), bottom); }
      ctx.stroke(); ctx.fillStyle = '#65718b';
      ctx.fillText(String(f), vertical ? 20 : x(f, 0) - 6, vertical ? y(f, 0) + 4 : bottom + 20);
    }
    for (let i = 0; i <= 3; i++) {
      const a = maxA * i / 3; ctx.fillStyle = '#65718b';
      ctx.fillText(a.toFixed(2), vertical ? x(0, a) - 12 : 10, vertical ? bottom + 20 : y(0, a) + 4);
    }
    ctx.strokeStyle = '#9ba6bb'; ctx.beginPath(); ctx.moveTo(left, top); ctx.lineTo(left, bottom); ctx.lineTo(right, bottom); ctx.stroke();
    const ampLabel = dos ? 'DOS / 相对幅值' : 'α²F / 无量纲';
    ctx.fillStyle = '#38445e'; ctx.font = '12px sans-serif';
    ctx.fillText(vertical ? '频率 / THz' : ampLabel, left, 17);
    ctx.textAlign = 'center'; ctx.fillText(vertical ? ampLabel : '频率 / THz', (left + right) / 2, h - 7); ctx.textAlign = 'left';
    const draw = (field, color, dashed = false) => {
      ctx.strokeStyle = color; ctx.lineWidth = dashed ? 2.4 : 2.8; ctx.setLineDash(dashed ? [7, 5] : []); ctx.beginPath(); let started = false;
      for (const r of rows) {
        const a = r[field]; if (a == null) { started = false; continue; }
        if (started) ctx.lineTo(x(r.f, a), y(r.f, a)); else ctx.moveTo(x(r.f, a), y(r.f, a)); started = true;
      }
      ctx.stroke(); ctx.setLineDash([]);
    };
    if (dos) names.forEach((_, i) => { if (visible[i]) { draw(source || overlay ? `d${i}` : `e${i}`, colors[i]); if (overlay) draw(`e${i}`, '#202d48', true); } });
    else { draw(source || overlay ? 'original' : 'a', source || overlay ? '#b2a243' : '#6155d9'); if (overlay) draw('a', '#6155d9', true); }
  }, [kind, vertical, overlay, source, visible.join(','), width]);
  return <canvas ref={ref} role="img" aria-label={`${vertical ? '纵轴' : '横轴'}为频率的${kind === 'dos' ? 'DOS' : 'α²F'}${overlay ? '叠加对照' : '谱图'}，合成演示数据`} />;
}

function Entry() {
  return <><header><div><p className="eyebrow">SC-Wiki / 材料状态</p><h1>谱数据查看入口</h1><p>从材料状态进入独立详情，原表单继续保留。</p></div><span className="badge">交互 Demo</span></header>
    <div className="notice">本 Demo 使用合成谱展示交互与积分，不是 La–Sc–H 的真实提取结果。</div>
    <section><h2>材料状态 · LaSc₂H₂₄</h2><p className="muted">P6/mmm · 300 GPa · 页面布局示例</p>
      <label className="draft-label">材料备注（用于验证新标签页保留输入）<input placeholder="在这里输入临时备注，再打开详情" /></label>
      {[['超导性质', 'alpha', 'Eliashberg 谱函数 α²F(ω)', '查看 α²F'], ['动力学性质', 'dos', '声子态密度 DOS', '查看声子 DOS']].map(([module, kind, name, button]) => <div className="module" key={kind}><h3>{module}</h3><div className="entry-card"><div><strong>{name}</strong><p>一组谱 · {kind === 'dos' ? 'La / Sc / H 分波' : '独立幅值标定'} · 演示频段 0.5–70 THz</p></div><a className="button primary" href={`?page=${kind}`} target="_blank" rel="noopener noreferrer">{button}</a></div></div>)}
    </section></>;
}

function Comparison({ scenario }) {
  const available = scenario !== 'uncalibrated';
  const reason = scenario === 'stale' ? '材料条件已变化，参考失效' : scenario === 'missing' ? '论文未报告参考值' : scenario === 'uncalibrated' ? '幅值刻度待核对，暂不积分' : '';
  return <section><div className="section-heading"><div><h2>03 · 积分结果与参考值对比</h2><p>在同一频段内积分；偏差衡量与参考值的差异。</p></div><span className="badge">合成数据计算示例</span></div>
    <div className="metrics"><div><span>提取频率范围</span><strong>0.50–70.00 <small>THz</small></strong></div><div><span>实际积分范围</span><strong>{available ? '0.50–70.00' : '暂不可计算'} <small>{available ? 'THz' : ''}</small></strong></div><div><span>未覆盖低频</span><strong>0–0.50 <small>THz</small></strong></div></div>
    <div className="table-wrap compare"><table><thead><tr>{['参数', '提取谱积分值', '参考值', '偏差 Δ', '绝对差 |Δ|', '相对偏差'].map(x => <th key={x}>{x}</th>)}</tr></thead><tbody>{[['λ（无量纲）', 'lambda', 3], ['ωlog（K）', 'wlog', 1]].map(([label, key, precision]) => {
      const value = integral[key], base = scenario === 'zero' ? 0 : reference[key], comparable = !reason, delta = value - base;
      return <tr key={key}><th>{label}</th><td className="accent">{available ? fmt(value, precision) : '—'}</td><td>{comparable ? fmt(base, precision) : '—'}</td><td>{comparable ? `${delta >= 0 ? '+' : ''}${fmt(delta, precision)}` : '—'}</td><td>{comparable ? fmt(Math.abs(delta), precision) : '—'}</td><td>{comparable && base !== 0 ? `${delta >= 0 ? '+' : ''}${fmt(100 * delta / base, 2)}%` : '—'}</td></tr>;
    })}</tbody></table></div>
    <p className={reason || scenario === 'zero' ? 'notice slim' : 'muted footnote'}>{reason || (scenario === 'zero' ? '参考值为零：保留差值，相对偏差无定义。' : '参考值由合成原谱在同一频段积分得到，用于演示论文参考栏；未借用材料的真实报告值。')}</p>
    <p className="footnote">Δ = 提取谱积分值 − 参考值；相对偏差 = Δ / |参考值| × 100%。频段外未补零，有限频段积分不等于完整谱积分。</p>
  </section>;
}

function Detail({ kind }) {
  const dos = kind === 'dos';
  const [view, setView] = useState('data'), [visible, setVisible] = useState([true, true, true]);
  const [scenario, setScenario] = useState('valid'), [load, setLoad] = useState('ready');
  const [search, setSearch] = useState(''), [selected, setSelected] = useState(null), [showSource, setShowSource] = useState(false);
  const timer = useRef(); useEffect(() => () => clearTimeout(timer.current), []);
  const retry = () => { setLoad('loading'); timer.current = setTimeout(() => setLoad('ready'), 450); };
  const filtered = rows.filter(r => !search || r.f.toFixed(2).includes(search));
  const download = () => {
    const fields = dos ? ['f', 'e0', 'e1', 'e2'] : ['f', 'original', 'a'];
    const csv = ['DEMO_ONLY_SYNTHETIC_DATA', fields.join(','), ...rows.map(r => fields.map(k => r[k] ?? '').join(','))].join('\n');
    const a = document.createElement('a'), url = URL.createObjectURL(new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })); a.href = url; a.download = `${kind}-DEMO.csv`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <>
    <div className="topline"><a href="?">材料状态 / 谱数据</a><span>设计预览 · #{dos ? '155' : '154'}</span></div>
    <header><div><p className="eyebrow">{dos ? '动力学性质' : '超导性质'} / 谱数据核验</p><h1>{title(kind)}</h1><p>先看图，再核验数值，最后检查数据点。</p></div><button onClick={download}>导出示例 CSV</button></header>
    <div className="demo-toolbar"><span className="badge">合成谱 Demo</span><span>不代表本材料真实提取或科学验收结果</span><label>演示状态 <select aria-label="演示状态" value={dos ? load : scenario} onChange={e => dos ? setLoad(e.target.value) : setScenario(e.target.value)}>{(dos ? [['ready','正常读取'],['error','读取失败'],['empty','尚无数据'], ...(load === 'loading' ? [['loading','正在读取']] : [])] : [['valid','参考有效'],['uncalibrated','幅值刻度待核对'],['stale','参考已失效'],['missing','缺少参考值'],['zero','参考值为零']]).map(([v,l]) => <option value={v} key={v}>{l}</option>)}</select></label></div>
    <section className="identity"><div><h2>01 · 材料与来源</h2><strong className="material">LaSc₂H₂₄ <span>P6/mmm · 300 GPa</span></strong><p>材料标签沿用截图 · 以下谱图为独立合成示例，非论文原图</p></div><div className="identity-side"><span className="badge neutral">{dos ? '一组 DOS · 三条分波' : '一条 α²F 谱'}</span><button className="link" onClick={() => setShowSource(!showSource)}>{showSource ? '收起提供的截图' : '查看提供的截图'}</button></div></section>
    {showSource && <section><h2>用户提供的原始截图 · 单位仍需核对</h2><p>截图中的频率沿竖轴；1、2、3 的刻度不能直接用于 α²F 幅值标定。以下图片仅为本次问题依据。</p><img className="evidence" src="/assets/source-screenshot.png" alt="用户提供的原始页面截图，包含论文图与旧谱展示" /></section>}
    {dos && load !== 'ready' ? <section className="failure" role="status"><h2>{load === 'error' ? '谱数据暂时无法读取' : load === 'empty' ? '该材料状态尚无 DOS 数据' : '正在重新读取…'}</h2><p>{load === 'error' ? 'HTTP 500 · 演示错误状态。材料与来源仍保留，重试后恢复此 Demo 的数据。' : load === 'empty' ? '保留当前材料信息，生成谱结果后可在这里查看。' : '读取本地演示数据，不调用业务接口。'}</p>{load === 'error' && <button className="primary" onClick={retry}>重新读取</button>}</section> : <>
    <section><div className="section-heading"><div><h2>02 · 原图与提取结果</h2><p>左侧查看来源，右侧核对提取结果；频率轴方向分别标明。</p></div><div className="segmented" aria-label="结果显示方式"><button aria-pressed={view === 'overlay'} onClick={() => setView('overlay')}>叠加到原图</button><button aria-pressed={view === 'data'} onClick={() => setView('data')}>单独显示数据</button></div></div>
      <div className="plots"><div className="plot-panel"><div className="plot-title"><h3>来源谱图 <span>合成演示</span></h3><small>频率：竖轴 / THz</small></div><Plot kind={kind} vertical source visible={visible}/><p className="plot-note">{dos ? 'La / Sc / H 使用同一相对幅值尺度。' : 'α²F 独立幅值坐标；本例未绘制累计 λ。'}</p></div>
      <div className="plot-panel"><div className="plot-title"><h3>{view === 'overlay' ? '原图覆盖对照' : '提取后的谱数据'}</h3><small>频率：{view === 'overlay' ? '竖轴' : '横轴'} / THz</small></div><Plot kind={kind} vertical={view === 'overlay'} overlay={view === 'overlay'} visible={visible}/><p className="plot-note">{view === 'overlay' ? '实线：演示来源谱；虚线：演示提取谱。' : dos ? '保持三条分波的共同幅值尺度，未知区间保留缺口。' : '横轴频率 / THz，纵轴 α²F / 无量纲（已知合成标定）。'}</p></div></div>
      {dos && <div className="legend">{names.map((name,i) => <label key={name} style={{color: colors[i]}}><input type="checkbox" checked={visible[i]} onChange={() => setVisible(visible.map((v,j) => i === j ? !v : v))}/>{name} 分波</label>)}<span>同一组 DOS 的组成，不是谱候选</span></div>}
    </section>
    {dos ? <section><h2>03 · 频段与数据完整性</h2><div className="metrics"><div><span>提取频率范围</span><strong>0.50–70.00 <small>THz</small></strong></div><div><span>幅值单位</span><strong>相对幅值</strong><small>原图未确认绝对单位时保留原尺度</small></div><div><span>H 分波缺口</span><strong>32.50–34.00 <small>THz</small></strong><small>其余分波完整；不以 0 代替未知</small></div></div><p className="footnote">DOS 本身不能给出 λ 和 ωlog；缺少原胞模式数与投影归一化依据时，不强制凑成 3N。</p></section> : <Comparison scenario={scenario}/>}
    <section><div className="section-heading"><div><h2>04 · 逐点数据核对</h2><p>{rows.length} 个采样点 · 固定表头，表内滚动 · 点击序号查看该点</p></div><input aria-label="查找频率" className="search" placeholder="查找频率，例如 20.50" value={search} onChange={e => setSearch(e.target.value)}/></div>
      <div className="table-wrap points" tabIndex="0" role="region" aria-label="可滚动的逐点数据表"><table><thead><tr>{(dos ? ['序号','频率 / THz','La / 相对幅值','Sc / 相对幅值','H / 相对幅值','数据状态'] : ['序号','频率 / THz','来源谱 α²F','提取谱 α²F','幅值差','数据状态']).map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{filtered.map(r => <tr key={r.id} className={selected === r.id ? 'selected' : ''}><td><button className="row-button" aria-label={`查看第 ${r.id} 个数据点`} onClick={() => setSelected(r.id)}>{r.id}</button></td><td>{fmt(r.f,2)}</td>{(dos ? ['e0','e1','e2'] : ['original','a','diff']).map(k => <td key={k}>{r[k] == null ? '未知' : fmt(r[k],5)}</td>)}<td><span className={dos && r.e2 == null ? 'missing' : 'point-status'}>{dos && r.e2 == null ? 'H 缺失' : '演示观测'}</span></td></tr>)}</tbody></table>{!filtered.length && <p className="empty">没有匹配的频率</p>}</div>
      <div className="table-footer" role="status"><span>{selected ? `已选中第 ${selected} 点 · 频率 ${fmt(rows[selected - 1].f,2)} THz · 仅核对查看，未修改数值` : '数据仅在表格内滚动，不再铺满整页'}</span><span>{filtered.length} / {rows.length} 点</span></div>
    </section></>}
    <footer>独立交互 Demo · {dos ? '#155 声子 DOS' : '#154 α²F'} · 真实数据标定与正式接入另行验收</footer>
  </>;
}

export function App() {
  const page = new URLSearchParams(location.search).get('page');
  useEffect(() => { document.title = page ? `${title(page)} · Demo` : '谱详情 Demo · SC-Wiki'; }, [page]);
  return <div className="app"><aside><a href="?" className="brand">SC<span>SC-Wiki</span></a><div className="side-label">数据工作台</div><a href="?" className={!page ? 'active' : ''}>材料状态</a><a href="?page=alpha" className={page === 'alpha' ? 'active' : ''}>α²F 详情</a><a href="?page=dos" className={page === 'dos' ? 'active' : ''}>声子 DOS 详情</a><div className="side-bottom">设计预览<br/>2026.10</div></aside><main>{page === 'alpha' || page === 'dos' ? <Detail key={page} kind={page}/> : <Entry/>}</main></div>;
}
