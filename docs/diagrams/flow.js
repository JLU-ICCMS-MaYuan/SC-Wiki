// 程序流程图渲染器：主干纵向、支线左右横置，节点为 HTML，连线为单层 SVG。
// 页面只声明 JSON 数据，不连接任何业务接口，也不写入真实数据。
(() => {
  'use strict';

  const source = document.querySelector('#flow-data');
  if (!source) return;
  const data = JSON.parse(source.textContent);

  const GEO = {
    width: 1050,
    top: 56,
    rowGap: 148,
    nodeHeight: 94,
    main: { x: 330, w: 380 },
    left: { x: 16, w: 248 },
    right: { x: 756, w: 248 },
    branchGap: 118
  };
  if (!(data.branches || []).length) {
    GEO.width = 640;
    GEO.main = { x: 110, w: 420 };
  }
  const NS = 'http://www.w3.org/2000/svg';
  const canvas = document.querySelector('.canvas');
  const wrap = document.querySelector('.canvas-wrap');
  const viewport = document.querySelector('.viewport');

  const nodes = new Map();
  data.main.forEach((node, index) => {
    nodes.set(node.id, {
      ...node,
      col: 'main',
      index,
      step: node.step || `主干 ${String(index + 1).padStart(2, '0')}`,
      x: GEO.main.x,
      y: GEO.top + index * GEO.rowGap,
      w: GEO.main.w
    });
  });

  const slots = new Map();
  const laneBottom = new Map();
  for (const branch of data.branches || []) {
    const anchor = nodes.get(branch.attachTo);
    if (!anchor) continue;
    const side = branch.side === 'left' ? 'left' : 'right';
    const key = `${branch.attachTo}:${side}`;
    const slot = slots.get(key) || 0;
    slots.set(key, slot + 1);
    const y = Math.max(anchor.y + (anchor.col === 'main' ? slot * GEO.branchGap : GEO.rowGap),
      laneBottom.get(side) || 0);
    laneBottom.set(side, y + GEO.nodeHeight + 40);
    nodes.set(branch.id, {
      ...branch,
      col: side,
      kind: branch.kind || 'wait',
      step: branch.step || `支线 · ${anchor.title}`,
      x: GEO[side].x,
      y,
      w: GEO[side].w,
      anchor: branch.attachTo
    });
  }

  const height = Math.max(...Array.from(nodes.values(), node => node.y + GEO.nodeHeight)) + 80;
  canvas.style.width = GEO.width + 'px';
  canvas.style.height = height + 'px';

  const lane = document.createElement('div');
  lane.className = 'lane';
  lane.setAttribute('aria-hidden', 'true');
  Object.assign(lane.style, {
    left: (GEO.main.x - 22) + 'px',
    top: '20px',
    width: (GEO.main.w + 44) + 'px',
    height: (height - 40) + 'px'
  });

  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('class', 'connections');
  svg.setAttribute('viewBox', `0 0 ${GEO.width} ${height}`);
  svg.setAttribute('aria-hidden', 'true');
  svg.innerHTML = `<defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#8b9eac"/></marker>
    <marker id="arrow-active" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#275d9f"/></marker>
  </defs><g id="edges"></g>`;

  const edgeLayer = svg.querySelector('#edges');
  const edges = [];

  function addEdge(from, to, options = {}) {
    const start = options.start;
    const end = options.end;
    const points = options.points || [start, end];
    const path = document.createElementNS(NS, 'path');
    path.setAttribute('d', points.map(([x, y], i) => `${i ? 'L' : 'M'}${x} ${y}`).join(' '));
    path.setAttribute('class', 'edge' + (options.branch ? ' branch' : '') + (options.ret ? ' return' : ''));
    edgeLayer.append(path);
    if (options.label) {
      const text = document.createElementNS(NS, 'text');
      text.setAttribute('x', options.labelX ?? (start[0] + end[0]) / 2);
      text.setAttribute('y', options.labelY ?? (start[1] + end[1]) / 2 - 8);
      text.setAttribute('class', 'edge-label');
      text.textContent = options.label;
      edgeLayer.append(text);
    }
    edges.push({ from, to, path, branch: !!options.branch, ret: !!options.ret });
  }

  const mainEdges = data.edges || data.main.slice(1).map((node, index) => ({
    from: data.main[index].id, to: node.id, label: node.label
  }));
  mainEdges.forEach(edge => {
    const from = nodes.get(edge.from);
    const to = nodes.get(edge.to);
    if (!from || !to) return;
    const skipped = to.index !== from.index + 1;
    const start = skipped ? [from.x, from.y + 64] : [from.x + from.w / 2, from.y + GEO.nodeHeight];
    const end = skipped ? [to.x, to.y + 64] : [to.x + to.w / 2, to.y];
    const laneX = GEO.main.x - 28 - (edge.lane || 0) * 12;
    addEdge(from.id, to.id, {
      start, end,
      points: skipped ? [start, [laneX, start[1]], [laneX, end[1]], end] : [start, end],
      label: edge.label,
      labelX: skipped ? laneX : from.x + from.w / 2 + 55,
      labelY: skipped ? (start[1] + end[1]) / 2 : from.y + GEO.nodeHeight + 26
    });
  });

  for (const branch of data.branches || []) {
    const target = nodes.get(branch.id);
    const anchor = nodes.get(branch.attachTo);
    if (!target || !anchor) continue;
    const toRight = target.x > anchor.x;
    if (target.col === anchor.col) {
      addEdge(anchor.id, target.id, {
        branch: true,
        start: [anchor.x + anchor.w / 2, anchor.y + GEO.nodeHeight],
        end: [target.x + target.w / 2, target.y],
        label: branch.label
      });
    } else {
      const startX = toRight ? anchor.x + anchor.w : anchor.x;
      const startY = anchor.y + GEO.nodeHeight / 2;
      const endX = toRight ? target.x : target.x + target.w;
      const endY = target.y + GEO.nodeHeight / 2;
      const midX = toRight ? startX + 48 : startX - 48;
      addEdge(anchor.id, target.id, {
        branch: true,
        start: [startX, startY],
        end: [endX, endY],
        points: [[startX, startY], [midX, startY], [midX, endY], [endX, endY]],
        label: branch.label,
        labelX: target.x + target.w / 2,
        labelY: target.y - 8
      });
    }
    // 两侧回边各走画布外沿，避免连线穿过节点。
    if (branch.returnTo && nodes.has(branch.returnTo)) {
      const back = nodes.get(branch.returnTo);
      const right = target.col === 'right';
      const backX = right ? back.x + back.w : back.x;
      const outX = right ? target.x + target.w : target.x;
      const laneX = right ? GEO.width - 14 : 5;
      addEdge(branch.id, branch.returnTo, {
        branch: true,
        ret: true,
        start: [outX, target.y + GEO.nodeHeight / 2],
        end: [backX, back.y + GEO.nodeHeight / 2],
        points: [[outX, target.y + GEO.nodeHeight / 2], [laneX, target.y + GEO.nodeHeight / 2], [laneX, back.y + GEO.nodeHeight / 2], [backX, back.y + GEO.nodeHeight / 2]],
        label: branch.returnLabel,
        labelX: laneX,
        labelY: back.y + GEO.nodeHeight / 2 - 10
      });
    }
  }

  const controls = new Map();
  const host = document.createElement('div');
  host.setAttribute('role', 'group');
  host.setAttribute('aria-label', '流程节点');

  for (const node of nodes.values()) {
    const button = document.createElement('button');
    button.type = 'button';
    button.id = node.id;
    button.className = 'node' + (node.col === 'main' ? '' : ' branch') + (node.kind ? ' ' + node.kind : '');
    button.style.left = node.x + 'px';
    button.style.top = node.y + 'px';
    button.style.width = node.w + 'px';
    button.style.minHeight = GEO.nodeHeight + 'px';
    button.setAttribute('aria-pressed', 'false');
    button.setAttribute('aria-controls', 'detail-title detail-description');
    const step = document.createElement('span');
    step.className = 'step';
    step.textContent = node.step;
    const title = document.createElement('strong');
    title.textContent = node.title;
    const summary = document.createElement('span');
    summary.className = 'summary';
    summary.textContent = node.summary || '';
    button.append(step, title, summary);
    if (node.kind === 'check') {
      const flag = document.createElement('span');
      flag.className = 'flag';
      flag.textContent = '判断';
      button.append(flag);
    }
    button.addEventListener('click', () => select(node.id));
    controls.set(node.id, button);
    host.append(button);
  }

  canvas.append(lane, svg, host);

  function branchButtons(node) {
    const box = document.querySelector('#detail-branches');
    box.replaceChildren();
    const related = [];
    if (node.col === 'main') {
      for (const item of nodes.values()) {
        if (item.anchor === node.id) related.push(item);
      }
    } else if (node.anchor && nodes.has(node.anchor)) {
      related.push(nodes.get(node.anchor));
    }
    for (const item of related) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = item.col === 'main' ? `↑ 回主干：${item.title}` : `↳ ${item.title}`;
      button.addEventListener('click', () => select(item.id));
      box.append(button);
    }
    for (const item of node.links || []) {
      const link = document.createElement('a');
      link.href = item.href;
      link.textContent = item.label;
      box.append(link);
    }
    box.hidden = box.childElementCount === 0;
    box.parentElement.hidden = box.hidden;
  }

  function select(id, writeHash = true) {
    const node = nodes.get(id);
    if (!node) return;
    for (const [key, control] of controls) {
      control.setAttribute('aria-pressed', String(key === id));
    }
    for (const edge of edges) {
      const active = edge.from === id || edge.to === id;
      edge.path.setAttribute('class', 'edge'
        + (edge.branch ? ' branch' : '')
        + (edge.ret ? ' return' : '')
        + (active ? ' active' : ''));
    }
    document.querySelector('#detail-step').textContent = node.step;
    document.querySelector('#detail-title').textContent = node.title;
    document.querySelector('#detail-owner').textContent = node.owner || '未标注';
    document.querySelector('#detail-description').textContent = node.description || '';
    const notes = document.querySelector('#detail-notes');
    notes.replaceChildren(...(node.notes || []).map(text => {
      const item = document.createElement('li');
      item.textContent = text;
      return item;
    }));
    notes.closest('section').hidden = !(node.notes || []).length;
    document.querySelector('#detail-code').textContent = node.code || '同一流程内的状态或控制分支';
    branchButtons(node);
    document.querySelector('.details').scrollTop = 0;
    if (writeHash) history.replaceState(null, '', '#' + id);
  }

  function fitCanvas() {
    const scale = Math.max(.62, Math.min(1, viewport.clientWidth / GEO.width));
    canvas.style.transform = `scale(${scale})`;
    wrap.style.width = GEO.width * scale + 'px';
    wrap.style.height = height * scale + 'px';
  }

  const initial = location.hash.slice(1);
  select(nodes.has(initial) ? initial : data.main[0].id, false);
  window.addEventListener('hashchange', () => {
    const id = location.hash.slice(1);
    if (nodes.has(id)) select(id, false);
  });
  new ResizeObserver(fitCanvas).observe(viewport);
  fitCanvas();
})();
