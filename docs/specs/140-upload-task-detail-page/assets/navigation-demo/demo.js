/* 独立交互原型：所有任务和修改仅属于演示，不调用业务接口。 */
'use strict'
const STORAGE_KEY = 'scwiki-140-navigation-demo-v1'
const originals = [
  { id: 'lasc-ready', file: '2024 La-Sc-H 何新玲.pdf', state: 'ready', title: 'La–Sc–H 高压超导性质研究（演示）', chunks: '6/6', expires: '23小时14分后删除' },
  { id: 'hydride-reading', file: 'Hydride superconductivity.pdf', state: 'reading', title: 'Hydride superconductivity（演示）', chunks: '3/6', expires: '后台处理中' },
  { id: 'supplement-failed', file: 'Supplementary materials.pdf', state: 'failed', title: '补充材料解析（演示）', chunks: '0/4', expires: '23小时后删除' },
]
const stateLabels = { ready: '等待校对', reading: '分段阅读中', failed: '解析失败', cancelled: '已取消' }
let data
try { data = JSON.parse(localStorage.getItem(STORAGE_KEY)) } catch { /* 无演示草稿时使用初始数据。 */ }
if (!Array.isArray(data) || data.some(item => !originals.some(task => task.id === item.id))) data = structuredClone(originals)
const persist = () => localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]))
let toastTimer
function notify(message) {
  const toast = document.getElementById('toast')
  toast.textContent = message
  toast.hidden = false
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.hidden = true }, 3200)
}
function renderList() {
  const selected = new Set()
  const list = document.getElementById('tasks')
  function updateSelection() {
    document.getElementById('selection-count').hidden = selected.size === 0
    document.getElementById('selection-count').textContent = `已选 ${selected.size} 项`
    document.getElementById('batch-delete').hidden = selected.size === 0
    const all = document.getElementById('select-all')
    all.checked = data.length > 0 && selected.size === data.length
    all.indeterminate = selected.size > 0 && selected.size < data.length
    all.disabled = !data.length
    list.querySelectorAll('input').forEach(input => { input.checked = selected.has(input.value) })
  }
  function draw() {
    list.innerHTML = data.map(task => `<article class="task-row" data-task="${task.id}">
      <label class="task-select"><input type="checkbox" value="${task.id}" aria-label="选择 ${escapeHtml(task.file)}"></label>
      <div class="task-main"><a class="task-link" href="detail.html?task=${task.id}">${escapeHtml(task.file)}</a><div class="task-meta"><span class="status ${task.state}">${stateLabels[task.state]}</span><span>· ${task.chunks} 段</span><span class="expiry">${task.expires}</span></div></div>
      ${task.state === 'reading' ? `<button class="button task-action" data-action="cancel" data-id="${task.id}">取消</button>` : ['failed', 'cancelled'].includes(task.state) ? `<button class="button danger task-action" data-action="remove" data-id="${task.id}">清理</button>` : ''}
      <span class="row-chevron" aria-hidden="true">›</span></article>`).join('')
    document.getElementById('task-count').textContent = `${data.length} / 100`
    document.getElementById('empty-list').hidden = !!data.length
    updateSelection()
  }
  list.addEventListener('change', event => {
    if (!event.target.matches('input[type=checkbox]')) return
    event.target.checked ? selected.add(event.target.value) : selected.delete(event.target.value)
    updateSelection()
  })
  list.addEventListener('click', event => {
    const button = event.target.closest('[data-action]')
    if (!button) return
    const task = data.find(item => item.id === button.dataset.id)
    if (button.dataset.action === 'cancel') {
      if (!confirm('取消这条演示任务？')) return
      task.state = 'cancelled'; task.expires = '23小时后删除'
      notify('演示任务已取消，仍停留在上传列表')
    } else {
      data = data.filter(item => item.id !== task.id); selected.delete(task.id)
      notify('已清理演示任务')
    }
    persist(); draw()
  })
  document.getElementById('select-all').addEventListener('change', event => {
    selected.clear()
    if (event.target.checked) data.forEach(task => selected.add(task.id))
    updateSelection()
  })
  document.getElementById('batch-delete').addEventListener('click', () => {
    const removable = data.filter(task => selected.has(task.id) && task.state !== 'reading')
    if (!removable.length) { notify('运行中的任务需先取消'); return }
    if (!confirm(`删除 ${removable.length} 条演示任务？运行中的任务将保留。`)) return
    data = data.filter(task => !removable.includes(task)); selected.clear(); persist(); draw()
    notify('已删除所选演示任务')
  })
  const reset = () => { data = structuredClone(originals); selected.clear(); persist(); draw(); notify('已恢复初始演示数据') }
  document.getElementById('reset-demo').addEventListener('click', reset)
  document.getElementById('reset-empty').addEventListener('click', reset)
  draw()
}
function renderDetail() {
  const taskId = new URLSearchParams(location.search).get('task')
  const task = data.find(item => item.id === taskId)
  const root = document.getElementById('detail-content')
  if (!task) {
    root.innerHTML = '<section class="panel error-content"><h1>任务不可用</h1><p>这条演示任务不存在或已被清理。可以返回列表，恢复演示任务。</p><a class="button outline" href="index.html">返回上传记录</a></section>'
    return
  }
  document.title = `${task.file} · 解析与校对 Demo`
  const ready = task.state === 'ready'
  const stages = ['文件接收', '正文提取', '分段阅读', '全文汇总', '等待校对']
  const current = ready ? 4 : task.state === 'reading' ? 2 : 1
  root.innerHTML = `<div class="detail-heading"><div><h1>${escapeHtml(task.file)}</h1><p><span class="status ${task.state}">${stateLabels[task.state]}</span><span>${task.chunks} 段</span><span>主文 + 补充材料</span></p></div><div class="editor-actions"><span class="save-state" id="save-state">${ready ? '演示草稿已载入' : '结果尚未就绪'}</span><button class="button outline" id="save-draft" ${ready ? '' : 'disabled'}>保存草稿</button><button class="button primary" id="submit-preview" ${ready ? '' : 'disabled'}>提交审核</button></div></div>
    <section class="panel progress-panel" aria-label="解析进度"><div class="progress-top"><span>解析进度</span><span>${ready ? '解析完成，可开始校对' : task.state === 'reading' ? '已完成 3 段，继续处理其余段落' : '任务已停止'}</span></div><div class="stages">${stages.map((label, i) => `<div class="stage ${i < current ? 'complete' : i === current ? 'current' : ''}"><span>${i < current ? '✓' : i + 1}</span>${label}</div>`).join('')}</div></section>
    ${ready ? '' : `<div class="notice ${task.state === 'failed' ? 'error' : ''}">${task.state === 'reading' ? '正在后台阅读论文。可以先查看已完成的分段结果，完成后再校对。' : task.state === 'failed' ? '正文提取未完成。此处展示失败状态，返回列表后仍可清理这条任务。' : '任务已取消。已有结果保留在此处，可返回列表清理。'}</div>`}
    ${ready ? `<section class="panel editor-section"><div class="section-title"><h2>论文信息</h2><span>待校对</span></div><div class="fields"><label class="field wide">论文标题<input id="paper-title" value="${escapeHtml(task.title)}"><span class="helper">可修改标题，试用保存、刷新与返回流程。</span></label><label class="field">研究类型<input value="理论研究" disabled></label><label class="field">材料体系<input value="La–Sc–H" disabled></label><label class="field">论文年份<input value="2024" disabled></label><label class="field wide">核心发现<textarea disabled>此处展示论文解析后的摘要与主要结论。本 Demo 只展示页面组织，不代表真实科学提取结果。</textarea></label></div></section>
    <div class="section-label"><h2>材料状态</h2><span class="count">2</span></div>
    ${[300,150].map((pressure,index) => `<details class="panel state-card" ${index === 0 ? 'open' : ''}><summary><span class="state-name">LaSc₂H₂₄</span><span class="tag">${pressure} GPa</span><span class="tag">理论 · 演示</span><span class="state-desc">状态 ${index+1} · 点击展开或收起</span></summary><div class="state-body"><p class="helper">此处演示材料状态的分组与折叠；科学字段值未作真实提取。</p><details class="module"><summary>超导性质</summary><div class="module-body"><div class="scalar-row"><span>临界温度 Tc</span><span>待核对</span></div><div class="scalar-row"><span>电声耦合强度 λ</span><span>待核对</span></div><div class="spectrum-note"><span>谱函数 α²F(ω) 与累计 λ</span><span>尚未载入演示曲线</span></div></div></details><details class="module"><summary>电子性质</summary><div class="module-body"><div class="scalar-row"><span>费米能级态密度</span><span>待核对</span></div></div></details><details class="module"><summary>动力学性质</summary><div class="module-body"><div class="spectrum-note"><span>声子态密度 DOS</span><span>尚未载入演示曲线</span></div></div></details><details class="module"><summary>热力学性质</summary><div class="module-body"><div class="scalar-row"><span>热力学稳定性</span><span>待核对</span></div></div></details></div></details>`).join('')}` : `<div class="section-label"><h2>分段解析结果</h2></div><div class="chunks">${[1,2,3].map(i => `<details class="panel"><summary>第 ${i} 段 · ${task.state === 'reading' ? '已完成' : '尚无结果'}</summary><p>${task.state === 'reading' ? '已完成段落的内容会在这里展示。此处为交互样例，可返回列表查看其他任务。' : '任务停止前未生成可展示的段落内容。'}</p></details>`).join('')}</div>`}`
  if (!ready) return
  const input = document.getElementById('paper-title')
  const saveState = document.getElementById('save-state')
  const saveButton = document.getElementById('save-draft')
  let dirty = false
  function save() {
    if (!input.value.trim()) { input.focus(); notify('请填写论文标题'); return false }
    task.title = input.value; persist(); dirty = false
    saveState.textContent = '演示草稿已保存'; saveButton.disabled = true
    notify('演示草稿已保存，刷新或返回后仍可恢复')
    return true
  }
  saveButton.disabled = true
  input.addEventListener('input', () => {
    dirty = input.value !== task.title
    saveState.textContent = dirty ? '有未保存修改' : '演示草稿已载入'
    saveButton.disabled = !dirty
  })
  saveButton.addEventListener('click', save)
  document.getElementById('submit-preview').addEventListener('click', () => notify('已体验提交入口。本 Demo 不会提交真实论文。'))
  const dialog = document.getElementById('leave-dialog')
  let leaveTarget = 'index.html'
  document.querySelectorAll('a[href="index.html"]').forEach(link => link.addEventListener('click', event => {
    if (!dirty || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault(); leaveTarget = link.href; dialog.showModal()
  }))
  document.getElementById('stay').addEventListener('click', () => dialog.close())
  document.getElementById('discard').addEventListener('click', () => { dirty = false; location.href = leaveTarget })
  document.getElementById('save-leave').addEventListener('click', () => { if (save()) location.href = leaveTarget })
  window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = '' } })
}
if (document.body.dataset.page === 'list') renderList()
else renderDetail()
