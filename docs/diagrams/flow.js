// 程序流程图渲染器：主干纵向、支线左右横置，节点为 HTML，连线为单层 SVG。
// 页面只声明 JSON 数据，不连接任何业务接口，也不写入真实数据。
(() => {
  'use strict';

  const source = document.querySelector('#flow-data');
  if (!source) return;
  const data = JSON.parse(source.textContent);

  // 功能模块编号的唯一来源：顶部陈列与节点徽标都从这里取编号。
  const MODULES = [
    { no: '01', name: '上传与解析', href: '01-upload-parse.html' },
    { no: '02', name: '审核与维护', href: '02-review-audit.html' },
    { no: '03', name: '检索与发现', href: '03-search.html' },
    { no: '04', name: '引用知识图谱', href: '04-knowledge-graph.html' },
    { no: '05', name: '检索增强问答', href: '05-rag-qa.html' },
    { no: '06', name: '研究社区', href: '06-community.html' },
    { no: '07', name: 'Tc 估算', href: '07-tc-predict.html' }
  ];

  function moduleOf(node) {
    if (node.module) return MODULES.find(item => item.no === String(node.module)) || null;
    for (const link of node.links || []) {
      const target = String(link.href || '').split('#')[0];
      const found = MODULES.find(item => item.href === target);
      if (found) return found;
    }
    return null;
  }

  const NODE_H = 94;
  const GEO = {
    width: 1140,
    top: 56,
    rowGap: 128,
    mainGap: 54,
    branchGap: 36,
    nodeHeight: NODE_H,
    outerPad: 32,
    innerGap: 128,
    laneStep: 12,
    main: { x: 380, w: 380 },
    left: { x: 32, w: 248 },
    right: { x: 820, w: 248 }
  };
  if (!(data.branches || []).length) {
    GEO.width = 640;
    GEO.main = { x: 110, w: 420 };
  } else {
    GEO.left.x = GEO.outerPad;
    GEO.main.x = GEO.left.x + GEO.left.w + GEO.innerGap;
    GEO.right.x = GEO.main.x + GEO.main.w + GEO.innerGap;
    GEO.width = GEO.right.x + GEO.right.w + GEO.outerPad;
  }
  const NS = 'http://www.w3.org/2000/svg';
  const canvas = document.querySelector('.canvas');
  const wrap = document.querySelector('.canvas-wrap');
  const viewport = document.querySelector('.viewport');

  const nodes = new Map();
  data.main.forEach((node, index) => {
    const mod = moduleOf(node);
    nodes.set(node.id, {
      ...node,
      col: 'main',
      index,
      module: mod,
      step: node.step || (mod ? `功能 ${mod.no}` : `主干 ${String(index + 1).padStart(2, '0')}`),
      x: GEO.main.x,
      y: GEO.top,
      w: GEO.main.w
    });
  });

  const rawBranches = data.branches || [];
  const branchMap = new Map(rawBranches.map(branch => [branch.id, branch]));
  const children = new Map();
  for (const branch of rawBranches) {
    if (!nodes.has(branch.attachTo) && !branchMap.has(branch.attachTo)) continue;
    const list = children.get(branch.attachTo) || [];
    list.push(branch);
    children.set(branch.attachTo, list);
  }

  function descendantsOf(mainId) {
    const ordered = [];
    const queue = [...(children.get(mainId) || [])];
    const seen = new Set();
    while (queue.length) {
      const branch = queue.shift();
      if (seen.has(branch.id)) continue;
      seen.add(branch.id);
      ordered.push(branch);
      queue.push(...(children.get(branch.id) || []));
    }
    return ordered;
  }

  let cursorY = GEO.top;
  for (const main of data.main) {
    const node = nodes.get(main.id);
    node.y = cursorY;
    const group = descendantsOf(main.id);
    const sideCursor = { left: cursorY, right: cursorY };

    // 每个主干节点自己形成一个局部支线簇；下一主干让出整个簇的高度。
    for (const branch of group) {
      const anchor = nodes.get(branch.attachTo);
      if (!anchor) continue;
      const side = branch.side === 'left' ? 'left' : 'right';
      const desired = anchor.col === 'main'
        ? cursorY
        : anchor.y + NODE_H + GEO.branchGap;
      const y = Math.max(desired, sideCursor[side]);
      nodes.set(branch.id, {
        ...branch,
        col: side,
        kind: branch.kind || 'wait',
        module: moduleOf(branch),
        step: branch.step || (moduleOf(branch) ? `功能 ${moduleOf(branch).no}` : `支线 · ${anchor.title}`),
        x: GEO[side].x,
        y,
        w: GEO[side].w,
        anchor: branch.attachTo,
        root: main.id
      });
      sideCursor[side] = y + NODE_H + GEO.branchGap;
    }

    let bottom = cursorY + NODE_H;
    for (const branch of group) {
      const placed = nodes.get(branch.id);
      if (placed) bottom = Math.max(bottom, placed.y + NODE_H);
    }
    node.clusterBottom = bottom;
    cursorY = Math.max(cursorY + NODE_H + GEO.rowGap, bottom + GEO.mainGap);
  }

  const height = Math.max(...Array.from(nodes.values(), node => node.y + NODE_H)) + 80;
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
  const specs = [];

  const mainIndex = new Map(data.main.map((node, index) => [node.id, index]));
  const flowEdges = data.edges || data.main.slice(1).map((node, index) => ({
    from: data.main[index].id, to: node.id, label: node.label
  }));
  for (const edge of flowEdges) {
    if (nodes.has(edge.from) && nodes.has(edge.to)) {
      specs.push({ from: edge.from, to: edge.to, label: edge.label, branch: false });
    }
  }
  for (const branch of rawBranches) {
    if (nodes.has(branch.attachTo) && nodes.has(branch.id)) {
      specs.push({
        from: branch.attachTo,
        to: branch.id,
        label: branch.label,
        branch: true
      });
    }
    if (branch.returnTo && nodes.has(branch.returnTo) && nodes.has(branch.id)) {
      specs.push({
        from: branch.id,
        to: branch.returnTo,
        label: branch.returnLabel,
        branch: true,
        ret: true
      });
    }
  }

  function inwardSide(node) {
    return node.col === 'left' ? 'right' : 'left';
  }

  function sidesFor(spec, from, to) {
    const cross = (from.col === 'left' && to.col === 'right')
      || (from.col === 'right' && to.col === 'left');
    if (cross) return { fromSide: from.col, toSide: to.col, band: null, cross: true };
    if (from.col === 'main' && to.col !== 'main') {
      return { fromSide: to.col, toSide: inwardSide(to), band: to.col };
    }
    if (from.col !== 'main' && to.col === 'main') {
      return { fromSide: inwardSide(from), toSide: from.col, band: from.col };
    }
    if (from.col === 'main' && to.col === 'main') {
      return { fromSide: 'left', toSide: 'left', band: 'left' };
    }
    if (from.col === to.col) {
      return { fromSide: inwardSide(from), toSide: inwardSide(to), band: from.col };
    }
    return { fromSide: 'left', toSide: 'left', band: 'left' };
  }

  const portRequests = new Map();
  for (const spec of specs) {
    const from = nodes.get(spec.from);
    const to = nodes.get(spec.to);
    spec.straight = from.col === 'main' && to.col === 'main'
      && mainIndex.get(to.id) === mainIndex.get(from.id) + 1;
    if (spec.straight) continue;
    Object.assign(spec, sidesFor(spec, from, to));
    const addPort = (node, side, other, role) => {
      const key = `${node.id}:${side}`;
      const list = portRequests.get(key) || [];
      list.push({ spec, role, side, node, otherY: other.y + NODE_H / 2 });
      portRequests.set(key, list);
    };
    addPort(from, spec.fromSide, to, 'from');
    addPort(to, spec.toSide, from, 'to');
  }

  // 同一侧的端口都落在同一条水平走廊上；两个端口只差 1~2px 时，连线在视觉上会并成一条。
  // 因此先记录全部端口，再按 y 排序做一次最小间距松弛，最后才写回连线端点。
  const portRecords = [];
  for (const list of portRequests.values()) {
    list.sort((a, b) => a.otherY - b.otherY
      || (a.role === b.role ? 0 : a.role === 'from' ? -1 : 1));
    const count = list.length;
    list.forEach((request, index) => {
      const node = request.node;
      const base = count === 1
        ? NODE_H / 2
        : 20 + (NODE_H - 40) * (index / (count - 1));
      // 出口与入口使用不同奇偶的轨道，主干与支线再错开 2px。
      const even = Math.round(base / 2) * 2;
      const offset = request.role === 'from'
        ? (node.col === 'main' ? 1 : 3)
        : (node.col === 'main' ? 0 : 2);
      portRecords.push({
        request,
        side: request.side,
        x: request.side === 'left' ? node.x : node.x + node.w,
        y: node.y + even + offset,
        min: node.y + 8,
        max: node.y + NODE_H - 8
      });
    });
  }

  // 端口分组的键不是“方向”，而是它所在的那条水平走廊：
  // 主干左边缘（x=主干左）与左列右边缘共享同一条走廊，必须一起松弛，否则仍会并线。
  const corridorOf = x => (x <= GEO.main.x ? 'L'
    : x >= GEO.main.x + GEO.main.w ? 'R' : 'C');
  const portGroups = new Map();
  for (const record of portRecords) {
    const key = corridorOf(record.x);
    const list = portGroups.get(key) || [];
    list.push(record);
    portGroups.set(key, list);
  }
  for (const list of portGroups.values()) {
    list.sort((a, b) => a.y - b.y);
    for (let index = 1; index < list.length; index += 1) {
      const previous = list[index - 1];
      const current = list[index];
      // 只处理“看起来并成一条”的近重合（<=3px），避免大范围位移改变车道、反而制造交叉。
      if (current.y - previous.y > 3) continue;
      current.y = Math.min(Math.max(previous.y + 5, current.min), current.max);
    }
  }

  for (const record of portRecords) {
    const point = [record.x, record.y];
    if (record.request.role === 'from') record.request.spec.start = point;
    else record.request.spec.end = point;
  }

  function rangesOverlap(a, b) {
    return a.min < b.max + 5 && b.min < a.max + 5;
  }

  const laneBands = { left: [], right: [] };
  const innerSpecs = specs.filter(spec => !spec.straight && !spec.cross
    && spec.start && spec.end && Math.abs(spec.start[1] - spec.end[1]) > 1);
  innerSpecs.sort((a, b) => (Math.abs(a.start[1] - a.end[1]) - Math.abs(b.start[1] - b.end[1]))
    || (Math.min(a.start[1], a.end[1]) - Math.min(b.start[1], b.end[1])));
  for (const spec of innerSpecs) {
    const range = {
      min: Math.min(spec.start[1], spec.end[1]),
      max: Math.max(spec.start[1], spec.end[1])
    };
    const band = laneBands[spec.band];
    let lane = band.find(item => item.ranges.every(other => !rangesOverlap(range, other)));
    if (!lane) {
      lane = { index: band.length, ranges: [] };
      band.push(lane);
    }
    lane.ranges.push(range);
    spec.laneIndex = lane.index;
  }

  // 车道必须留在两列之间的走廊里：步距按车道条数自适应，条数多时自动收紧，
  // 否则最外侧车道会挤进支线列、把连线画到卡片上。
  const laneLimits = {
    left: { inner: GEO.main.x - 16, outer: GEO.left.x + GEO.left.w + 12 },
    right: { inner: GEO.main.x + GEO.main.w + 16, outer: GEO.right.x - 12 }
  };
  const laneStepOf = {};
  for (const side of ['left', 'right']) {
    const count = laneBands[side].length;
    const span = Math.abs(laneLimits[side].inner - laneLimits[side].outer);
    laneStepOf[side] = count > 1 ? Math.min(GEO.laneStep, span / (count - 1)) : 0;
  }

  function laneX(spec) {
    const { inner } = laneLimits[spec.band];
    const offset = spec.laneIndex * laneStepOf[spec.band];
    return spec.band === 'left' ? inner - offset : inner + offset;
  }

  let crossIndex = 0;
  for (const spec of specs) {
    if (spec.straight) {
      const from = nodes.get(spec.from);
      const to = nodes.get(spec.to);
      spec.points = [
        [from.x + from.w / 2, from.y + NODE_H],
        [to.x + to.w / 2, to.y]
      ];
      spec.labelHint = {
        x: from.x + from.w / 2 + 12,
        y: (from.y + NODE_H + to.y) / 2,
        anchor: 'start'
      };
      continue;
    }
    if (spec.cross) {
      const from = nodes.get(spec.from);
      const to = nodes.get(spec.to);
      const fromRoot = nodes.get(from.root || from.id);
      const toRoot = nodes.get(to.root || to.id);
      const bottom = Math.max(
        fromRoot.clusterBottom || from.y + NODE_H,
        toRoot.clusterBottom || to.y + NODE_H
      );
      const trackY = bottom + 16 + crossIndex * GEO.laneStep;
      const leftOuter = 8 + (crossIndex % 3) * 6;
      const rightOuter = GEO.width - 8 - (crossIndex % 3) * 6;
      const fromOuter = from.col === 'left' ? leftOuter : rightOuter;
      const toOuter = to.col === 'left' ? leftOuter : rightOuter;
      spec.points = [
        spec.start,
        [fromOuter, spec.start[1]],
        [fromOuter, trackY],
        [toOuter, trackY],
        [toOuter, spec.end[1]],
        spec.end
      ];
      spec.labelHint = {
        x: (leftOuter + rightOuter) / 2,
        y: trackY - 8,
        anchor: 'middle'
      };
      crossIndex += 1;
      continue;
    }
    if (Math.abs(spec.start[1] - spec.end[1]) <= 1) {
      spec.points = [spec.start, spec.end];
    } else {
      const x = laneX(spec);
      spec.points = [
        spec.start,
        [x, spec.start[1]],
        [x, spec.end[1]],
        spec.end
      ];
    }
    const target = nodes.get(spec.to);
    spec.labelHint = {
      x: target.x + target.w / 2,
      y: target.y - 8,
      anchor: 'middle'
    };
  }

  const simplified = points => points.filter((point, index) => {
    if (!index) return true;
    const previous = points[index - 1];
    return point[0] !== previous[0] || point[1] !== previous[1];
  });

  for (const spec of specs) {
    const points = simplified(spec.points);
    const path = document.createElementNS(NS, 'path');
    path.setAttribute('d', points.map(([x, y], index) => `${index ? 'L' : 'M'}${x} ${y}`).join(' '));
    path.setAttribute('data-from', spec.from);
    path.setAttribute('data-to', spec.to);
    path.setAttribute('class', 'edge' + (spec.branch ? ' branch' : '') + (spec.ret ? ' return' : ''));
    edgeLayer.append(path);
    edges.push({
      from: spec.from,
      to: spec.to,
      path,
      points,
      label: spec.label,
      labelHint: spec.labelHint,
      branch: !!spec.branch,
      ret: !!spec.ret
    });
  }

  function nodeBoxes() {
    return Array.from(nodes.values(), node => {
      const control = controls.get(node.id);
      return {
        x: node.x - 4,
        y: node.y - 4,
        w: node.w + 8,
        h: (control ? control.offsetHeight : NODE_H) + 8
      };
    });
  }

  function intersects(a, b) {
    return a.x < b.x + b.w && b.x < a.x + a.w
      && a.y < b.y + b.h && b.y < a.y + a.h;
  }

  // 每条线的标签先挂在“线段附近”的若干首选点，再由这些小偏移扩展成包围盒候选。
  // 偏移量按到原点的距离排序：能不动就不动，实在挤不开才让位，避免标签飘离所属线条。
  const LABEL_NUDGES = (() => {
    const steps = [0, 12, 26, 44, 68, 96];
    const list = [];
    for (const dy of steps) {
      for (const dx of steps) {
        if (!dx && !dy) continue;
        list.push([dx, dy], [-dx, dy], [dx, -dy], [-dx, -dy]);
      }
    }
    list.unshift([0, 0]);
    return list.sort((a, b) => (Math.abs(a[0]) + Math.abs(a[1])) - (Math.abs(b[0]) + Math.abs(b[1])));
  })();

  function labelCandidates(edge) {
    const candidates = [];
    const seen = new Set();
    const push = candidate => {
      const key = [
        Math.round(candidate.x), Math.round(candidate.y), candidate.anchor, candidate.rotate || 0
      ].join('|');
      if (seen.has(key)) return;
      seen.add(key);
      candidates.push(candidate);
    };
    if (edge.labelHint) push(edge.labelHint);
    const segments = [];
    for (let index = 1; index < edge.points.length; index += 1) {
      const [x1, y1] = edge.points[index - 1];
      const [x2, y2] = edge.points[index];
      const length = Math.abs(x2 - x1) + Math.abs(y2 - y1);
      if (length >= 30) segments.push({ x1, y1, x2, y2, length });
    }
    segments.sort((a, b) => b.length - a.length);
    for (const segment of segments) {
      if (Math.abs(segment.y1 - segment.y2) < 1) {
        const x = (segment.x1 + segment.x2) / 2;
        push({ x, y: segment.y1 - 8, anchor: 'middle' });
        push({ x, y: segment.y1 + 15, anchor: 'middle' });
        push({ x: segment.x1 + 12, y: segment.y1 - 8, anchor: 'start' });
        push({ x: segment.x2 - 12, y: segment.y1 - 8, anchor: 'end' });
      } else {
        const mid = (segment.y1 + segment.y2) / 2;
        const top = Math.min(segment.y1, segment.y2) + 18;
        const bottom = Math.max(segment.y1, segment.y2) - 18;
        push({ x: segment.x1 + 8, y: mid, anchor: 'start' });
        push({ x: segment.x1 - 8, y: mid, anchor: 'end' });
        push({ x: segment.x1, y: mid, anchor: 'middle', rotate: -90 });
        if (bottom > top) {
          push({ x: segment.x1 + 8, y: top, anchor: 'start' });
          push({ x: segment.x1 - 8, y: bottom, anchor: 'end' });
        }
      }
    }
    return candidates;
  }

  // 旋转文本的包围盒要按 transform 实际落点换算，否则“算的地方”和“画的地方”会差半个字高。
  function rotatedBox(candidate, box) {
    const cx = box.x + box.w / 2;
    const cy = box.y + box.h / 2;
    const centerX = candidate.x + (cy - candidate.y);
    const centerY = candidate.y - (cx - candidate.x);
    return {
      x: centerX - box.h / 2,
      y: centerY - box.w / 2,
      w: box.h,
      h: box.w
    };
  }

  function layoutEdgeLabels() {
    const boxes = nodeBoxes();
    const placed = [];
    for (const edge of edges) {
      if (!edge.label) continue;
      const text = document.createElementNS(NS, 'text');
      text.setAttribute('class', 'edge-label');
      text.textContent = edge.label;
      edgeLayer.append(text);
      let best = null;
      let bestCost = Infinity;
      const candidates = labelCandidates(edge);
      for (let rank = 0; rank < candidates.length; rank += 1) {
        const candidate = candidates[rank];
        text.removeAttribute('transform');
        text.setAttribute('x', candidate.x);
        text.setAttribute('y', candidate.y);
        text.style.textAnchor = candidate.anchor;
        const raw = text.getBBox();
        // DOMRect 的 x/y/width/height 在原型上，不能直接展开；必须逐项取值，
        // 否则包围盒是 NaN，碰撞检测会静默失效、标签全部叠在同一处。
        const plain = { x: raw.x, y: raw.y, w: raw.width, h: raw.height };
        const base = candidate.rotate ? rotatedBox(candidate, plain) : plain;
        const w = base.w + 6;
        const h = base.h + 4;
        for (const [dx, dy] of LABEL_NUDGES) {
          const padded = { x: base.x + dx - 3, y: base.y + dy - 2, w, h };
          const outside = padded.x < 1 || padded.y < 1
            || padded.x + padded.w > GEO.width - 1 || padded.y + padded.h > height - 1;
          const hitNode = boxes.some(item => intersects(padded, item));
          const hitLabel = placed.some(item => intersects(padded, item));
          const cost = (outside ? 1e9 : 0) + (hitNode ? 1e6 : 0) + (hitLabel ? 2e5 : 0)
            + rank * 3 + Math.abs(dx) + Math.abs(dy);
          if (cost < bestCost) {
            bestCost = cost;
            best = {
              x: candidate.x + dx,
              y: candidate.y + dy,
              anchor: candidate.anchor,
              rotate: candidate.rotate,
              box: padded
            };
          }
        }
        // 已经零惩罚且几乎没挪动，无需再试更远的候选。
        if (bestCost < 4) break;
      }
      if (!best) continue;
      text.setAttribute('x', best.x);
      text.setAttribute('y', best.y);
      text.style.textAnchor = best.anchor;
      if (best.rotate) text.setAttribute('transform', `rotate(${best.rotate} ${best.x} ${best.y})`);
      placed.push(best.box);
      edge.labelEl = text;
    }
  }

  const controls = new Map();
  const host = document.createElement('div');
  host.setAttribute('role', 'group');
  host.setAttribute('aria-label', '流程节点');
  const pageName = decodeURIComponent(location.pathname.split('/').pop() || 'index.html');
  // 详情页已是展开终点：卡片本身不再承担导航，只保留“说明”按钮。
  // 角色以页面显式标记为准，文件名仅作兜底，避免改名后点击语义悄悄反转。
  const role = document.body.dataset.flowRole || '';
  const detailsPage = role === 'details' || (!role && /-details\.html$/.test(pageName));

  // 其余节点仅保留独立的“说明”按钮，避免把静态方块伪装成页面链接。
  function targetOf(node) {
    if (detailsPage) return null;
    return (node.links || []).find(item => item.href && !item.href.startsWith('#')) || null;
  }

  for (const node of nodes.values()) {
    const target = targetOf(node);
    const control = document.createElement(target ? 'a' : 'article');
    control.id = node.id;
    control.className = 'node' + (node.col === 'main' ? '' : ' branch')
      + (node.kind ? ' ' + node.kind : '') + (target ? ' linked' : ' static');
    control.style.left = node.x + 'px';
    control.style.top = node.y + 'px';
    control.style.width = node.w + 'px';
    control.style.minHeight = NODE_H + 'px';
    control.setAttribute('data-active', 'false');
    control.setAttribute('aria-label', `${node.step} ${node.title}`);
    if (target) {
      control.setAttribute('href', target.href);
      control.addEventListener('mouseenter', () => select(node.id, false));
      control.addEventListener('focus', () => select(node.id, false));
    }
    const step = document.createElement('span');
    step.className = 'step';
    step.textContent = node.step;
    const title = document.createElement('strong');
    title.textContent = node.title;
    const summary = document.createElement('span');
    summary.className = 'summary';
    summary.textContent = node.summary || '';
    control.append(step, title, summary);
    if (node.kind === 'check') {
      const flag = document.createElement('span');
      flag.className = 'flag';
      flag.textContent = '判断';
      control.append(flag);
    }
    if (target) {
      const go = document.createElement('span');
      go.className = 'go';
      go.textContent = '打开 ↗';
      control.append(go);
    } else {
      const more = document.createElement('button');
      more.type = 'button';
      more.className = 'node-more';
      more.textContent = '说明';
      more.setAttribute('aria-label', `查看 ${node.title} 的实现说明`);
      more.setAttribute('aria-controls', 'detail-title detail-description');
      more.addEventListener('click', () => select(node.id));
      control.append(more);
    }
    controls.set(node.id, control);
    host.append(control);
  }

  canvas.append(lane, svg, host);
  layoutEdgeLabels();

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
      control.setAttribute('data-active', String(key === id));
    }
    for (const edge of edges) {
      const active = edge.from === id || edge.to === id;
      edge.path.setAttribute('class', 'edge'
        + (edge.branch ? ' branch' : '')
        + (edge.ret ? ' return' : '')
        + (active ? ' active' : ''));
      if (edge.labelEl) edge.labelEl.classList.toggle('active', active);
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
    if (writeHash) {
      try { history.replaceState(null, '', '#' + id); }
      catch { location.hash = id; }
    }
  }

  // 顶部功能陈列由 MODULES 生成，编号与节点徽标同源，新增模块只改一处。
  function renderModuleNav() {
    const nav = document.querySelector('nav[data-module-nav]');
    if (!nav) return;
    const here = (location.pathname.split('/').pop() || 'index.html');
    nav.replaceChildren(...MODULES.map(item => {
      const link = document.createElement('a');
      link.href = item.href;
      link.textContent = `${item.no} ${item.name}`;
      const detailsHref = item.href.replace(/\.html$/, '-details.html');
      if (item.href === here || detailsHref === here) link.setAttribute('aria-current', 'page');
      return link;
    }));
  }

  function fitCanvas() {
    const scale = Math.max(.62, Math.min(1, viewport.clientWidth / GEO.width));
    canvas.style.transform = `scale(${scale})`;
    wrap.style.width = GEO.width * scale + 'px';
    wrap.style.height = height * scale + 'px';
  }

  const initial = location.hash.slice(1);
  select(nodes.has(initial) ? initial : data.main[0].id, false);
  renderModuleNav();
  window.addEventListener('hashchange', () => {
    const id = location.hash.slice(1);
    if (nodes.has(id)) select(id, false);
  });
  new ResizeObserver(fitCanvas).observe(viewport);
  fitCanvas();
})();
