// 程序流程图渲染器：根图 / 功能步骤 / 支线 三种层级视图。
// 每次只画当前节点的直接子结构，其余层级通过点击进入；节点是 HTML，连线是单层 SVG。
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

  const pageName = decodeURIComponent(location.pathname.split('/').pop() || 'index.html');
  const role = document.body.dataset.flowRole || 'root';
  const feature = MODULES.find(item => item.href === pageName
    || item.href.replace(/\.html$/, '-details.html') === pageName) || null;
  const detailsHref = pageName.replace(/\.html$/, '-details.html');

  const mains = data.main || [];
  const branches = data.branches || [];
  const byId = new Map([...mains, ...branches].map(node => [node.id, node]));
  const childrenOf = id => branches.filter(branch => branch.attachTo === id);
  const hasChildren = id => childrenOf(id).length > 0;

  function moduleOf(node) {
    if (node.module) return MODULES.find(item => item.no === String(node.module)) || null;
    for (const link of node.links || []) {
      const target = String(link.href || '').split('#')[0];
      const matched = MODULES.find(item => item.href === target);
      if (matched) return matched;
    }
    return null;
  }

  function stepLabel(node, fallbackIndex) {
    if (node.step) return node.step;
    const mod = moduleOf(node);
    if (mod) return `功能 ${mod.no}`;
    // 没有编号也没有步骤号的节点（例如只指向外部资料的旁支）不能显示成“步骤 00”。
    return fallbackIndex >= 0
      ? `步骤 ${String(fallbackIndex + 1).padStart(2, '0')}`
      : '外部资料';
  }

  const NODE_H = 94;
  const NS = 'http://www.w3.org/2000/svg';
  const canvas = document.querySelector('.canvas');
  const wrap = document.querySelector('.canvas-wrap');
  const viewport = document.querySelector('.viewport');

  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('class', 'connections');
  svg.setAttribute('aria-hidden', 'true');
  svg.innerHTML = `<defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0 0 L10 5 L0 10 z" fill="#8b9eac"></path>
    </marker>
    <marker id="arrow-active" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0 0 L10 5 L0 10 z" fill="#275d9f"></path>
    </marker>
  </defs><g id="edges"></g>`;
  const edgeLayer = svg.querySelector('#edges');

  const controls = new Map();
  const stepOf = new Map();
  const edges = [];
  let scene = null;
  let currentPath = [];

  // ---------- 三种层级的坐标计算 ----------

  function baseScene(width) {
    return { width, height: 0, nodes: [], edges: [], pills: [], caption: '' };
  }

  function layoutRoot() {
    const pad = 32;
    const leftW = 248;
    const mainW = 380;
    const rightW = 248;
    const columnGap = 128;
    const rowGap = 150;
    const mainX = pad + leftW + columnGap;
    const width = mainX + mainW + columnGap + rightW + pad;
    const current = baseScene(width);
    const positions = new Map();

    let cursor = 56;
    for (const node of mains) {
      positions.set(node.id, { x: mainX, y: cursor, col: 'main' });
      cursor += rowGap;
    }
    const sides = { left: 56, right: 56 };
    for (const branch of branches) {
      const anchor = positions.get(branch.attachTo);
      if (!anchor) continue;
      const side = branch.side === 'left' ? 'left' : 'right';
      const y = Math.max(anchor.y, sides[side]);
      positions.set(branch.id, {
        x: side === 'left' ? pad : mainX + mainW + columnGap,
        y,
        col: side
      });
      sides[side] = y + NODE_H + 44;
    }

    for (const [id, position] of positions) {
      const node = byId.get(id);
      current.nodes.push({
        node,
        x: position.x,
        y: position.y,
        w: position.col === 'main' ? mainW : leftW,
        step: stepLabel(node, mains.findIndex(item => item.id === id)),
        target: node.links && node.links.length ? node.links[0].href : null
      });
    }

    // 支线走线槽：同一父节点的首条支线占最外侧槽位，后续支线依次贴近主干，
    // 这样横向引入线只与外侧竖线平行，不会彼此穿插。
    const groups = new Map();
    const sideUsed = { left: 0, right: 0 };
    const deliveryRows = { left: [], right: [] };
    for (const branch of branches) {
      const from = positions.get(branch.attachTo);
      const to = positions.get(branch.id);
      if (!from || !to) continue;
      const key = `${branch.attachTo}|${to.col}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(branch);
    }
    const slotOf = new Map();
    for (const list of groups.values()) {
      const side = positions.get(list[0].id).col === 'right' ? 'right' : 'left';
      const base = sideUsed[side];
      list.forEach((branch, order) => {
        slotOf.set(branch.id, base + (list.length - 1 - order));
        deliveryRows[side].push(positions.get(branch.id).y + NODE_H / 2);
      });
      sideUsed[side] = base + list.length;
    }

    const chain = data.edges && data.edges.length
      ? data.edges
      : mains.slice(1).map((node, index) => ({ from: mains[index].id, to: node.id, label: node.label }));
    const cx = mainX + mainW / 2;
    const hugUsed = { left: 0, right: 0 };
    const mainIndex = new Map(mains.map((node, index) => [node.id, index]));
    for (const edge of chain) {
      const from = positions.get(edge.from);
      const to = positions.get(edge.to);
      if (!from || !to || from.col !== 'main' || to.col !== 'main') continue;
      if (mainIndex.get(edge.to) === mainIndex.get(edge.from) + 1) {
        current.edges.push({
          from: edge.from,
          to: edge.to,
          label: edge.label,
          points: [[cx, from.y + NODE_H], [cx, to.y]]
        });
        continue;
      }
      // 跨行连线（跳步或回退）绝不压中轴：贴主干外侧走一条独立专线。
      const down = to.y > from.y;
      const side = down ? 'left' : 'right';
      const slot = hugUsed[side];
      hugUsed[side] += 1;
      const hugX = down ? mainX - 12 - slot * 8 : mainX + mainW + 12 + slot * 8;
      const startY = down ? from.y + NODE_H - 22 : from.y + 22;
      const endY = to.y + NODE_H / 2;
      const startX = down ? from.x : from.x + mainW;
      const endX = down ? to.x : to.x + mainW;
      current.edges.push({
        from: edge.from,
        to: edge.to,
        label: edge.label,
        points: [[startX, startY], [hugX, startY], [hugX, endY], [endX, endY]]
      });
    }
    // 每条支线一个独立出口位 + 独立侧向车道，出口位移开所有支线落点行，杜绝共线。
    const branchSeen = new Map();
    for (const branch of branches) {
      const from = positions.get(branch.attachTo);
      const to = positions.get(branch.id);
      if (!from || !to) continue;
      const side = to.col === 'right' ? 'right' : 'left';
      const order = branchSeen.get(branch.attachTo) || 0;
      branchSeen.set(branch.attachTo, order + 1);
      const startX = side === 'right' ? from.x + mainW : from.x;
      const endX = side === 'right' ? to.x : to.x + leftW;
      const endY = to.y + NODE_H / 2;
      const rows = deliveryRows[side];
      let tapY = from.y + 22 + order * 18;
      for (let step = 0; step < 5 && rows.some(row => Math.abs(row - tapY) < 6); step += 1) tapY += 6;
      const slot = slotOf.get(branch.id) || 0;
      const lane = side === 'right' ? mainX + mainW + 26 + slot * 14 : mainX - 26 - slot * 14;
      current.edges.push({
        from: branch.attachTo,
        to: branch.id,
        label: branch.label,
        points: Math.abs(tapY - endY) < 1
          ? [[startX, tapY], [endX, tapY]]
          : [[startX, tapY], [lane, tapY], [lane, endY], [endX, endY]]
      });
    }

    current.height = Math.max(cursor, sides.left, sides.right) + 48;
    return current;
  }

  function layoutSteps() {
    const width = 780;
    const x = 180;
    const nodeW = 420;
    const gap = 76;
    const current = baseScene(width);
    let y = 56;

    mains.forEach((node, index) => {
      const kids = childrenOf(node.id);
      current.nodes.push({
        node,
        x,
        y,
        w: nodeW,
        step: node.step || `步骤 ${String(index + 1).padStart(2, '0')}`,
        target: kids.length ? `${detailsHref}#${node.id}` : null,
        badge: kids.length ? `展开 ${kids.length} 条支线 ▸` : null
      });
      y += NODE_H + gap;
    });

    const chain = data.edges && data.edges.length
      ? data.edges
      : mains.slice(1).map((node, index) => ({ from: mains[index].id, to: node.id, label: node.label }));
    const cx = x + nodeW / 2;
    const jumps = [];
    for (const edge of chain) {
      const fromIndex = mains.findIndex(item => item.id === edge.from);
      const toIndex = mains.findIndex(item => item.id === edge.to);
      if (fromIndex < 0 || toIndex < 0) continue;
      if (toIndex === fromIndex + 1) {
        current.edges.push({
          from: edge.from,
          to: edge.to,
          label: edge.label,
          points: [
            [cx, 56 + fromIndex * (NODE_H + gap) + NODE_H],
            [cx, 56 + toIndex * (NODE_H + gap)]
          ]
        });
      } else {
        jumps.push({ edge, fromIndex, toIndex });
      }
    }

    // 跨步（跳步或回退）连线走右侧车道：中轴线只留给相邻两步。
    // 车道按跨度由短到长依次外移，长跨度必然包住短跨度，嵌套后互不穿插。
    const lanes = [];
    jumps.sort((a, b) => (Math.abs(a.toIndex - a.fromIndex) - Math.abs(b.toIndex - b.fromIndex))
      || (Math.min(a.fromIndex, a.toIndex) - Math.min(b.fromIndex, b.toIndex)));
    // 出口位自上而下按车道由外到内分配：外侧线先出，后出的线才不会横切已落下的竖线。
    const groupIndex = new Map();
    const groupSize = new Map();
    for (const jump of jumps) groupSize.set(jump.edge.from, (groupSize.get(jump.edge.from) || 0) + 1);
    const headUsed = new Map();
    for (const jump of jumps) {
      const min = Math.min(jump.fromIndex, jump.toIndex);
      const max = Math.max(jump.fromIndex, jump.toIndex);
      let lane = lanes.find(item => item.ranges.every(range => max + 6 < range.min || min - 6 > range.max));
      if (!lane) {
        lane = { index: lanes.length, ranges: [] };
        lanes.push(lane);
      }
      lane.ranges.push({ min, max });
      const laneX = x + nodeW + 26 + lane.index * 18;
      const slot = groupIndex.get(jump.edge.from) || 0;
      groupIndex.set(jump.edge.from, slot + 1);
      const tapSlot = Math.min(3, (groupSize.get(jump.edge.from) || 1) - 1 - slot);
      const headCount = headUsed.get(jump.edge.to) || 0;
      headUsed.set(jump.edge.to, headCount + 1);
      const headSlot = Math.min(3, headCount);
      // 出口位落在卡片右缘上半段、入口位落在下半段，同一节点既是出口又是入口时也不会共线。
      const fromY = 56 + jump.fromIndex * (NODE_H + gap) + 22 + tapSlot * 10;
      const toY = 56 + jump.toIndex * (NODE_H + gap) + 62 + headSlot * 10;
      current.edges.push({
        from: jump.edge.from,
        to: jump.edge.to,
        label: jump.edge.label,
        points: [
          [x + nodeW, fromY],
          [laneX, fromY],
          [laneX, toY],
          [x + nodeW, toY]
        ]
      });
    }

    current.width = Math.max(width, x + nodeW + 26 + Math.max(0, lanes.length - 1) * 18 + 40);
    current.height = y + 24;
    return current;
  }

  function layoutBranch(path) {
    const parentId = path[path.length - 1];
    const parent = byId.get(parentId);
    const kids = childrenOf(parentId);
    const width = 1180;
    const entryW = Math.max(120, 44 + Math.max(0, kids.length - 1) * 20);
    const entryX = 120;
    const entryY = 48;
    const childX = 440;
    const childW = 430;
    const rowGap = 54;
    const top = 152;
    const current = baseScene(width);
    current.caption = parent && parent.kind === 'check'
      ? `判定依据：${parent.summary || parent.title}`
      : '';

    current.pills.push({ kind: 'entry', text: '入口', x: entryX, y: entryY, w: entryW, h: 36 });

    kids.forEach((kid, index) => {
      const grand = childrenOf(kid.id);
      const y = top + index * (NODE_H + rowGap);
      current.nodes.push({
        node: kid,
        x: childX,
        y,
        w: childW,
        step: kid.step || '支线',
        target: grand.length ? `#${[...path, kid.id].join('/')}` : null,
        badge: grand.length ? `展开 ${grand.length} 条子支线 ▸` : null
      });
      if (kid.returnTo) {
        const target = byId.get(kid.returnTo);
        current.pills.push({
          kind: 'exit',
          text: `出口 · 回到 ${target ? target.title : kid.returnTo}`,
          x: childX + childW + 48,
          y: y + NODE_H / 2 - 16,
          w: 250,
          h: 32
        });
      }
    });

    // 每个子节点一条独立车道：越靠上的子节点车道越贴近子节点列，横向引入线彼此不穿越。
    kids.forEach((kid, index) => {
      const laneX = entryX + 22 + (kids.length - 1 - index) * 20;
      const childY = top + index * (NODE_H + rowGap) + NODE_H / 2;
      current.edges.push({
        from: 'entry',
        to: kid.id,
        label: kid.label,
        points: [[laneX, entryY + 36], [laneX, childY], [childX, childY]]
      });
      if (kid.returnTo) {
        current.edges.push({
          from: kid.id,
          to: `exit:${kid.id}`,
          dashed: true,
          points: [
            [childX + childW, childY],
            [childX + childW + 48, childY]
          ]
        });
      }
    });

    current.height = Math.max(top + kids.length * (NODE_H + rowGap) + 24, 320);
    return current;
  }

  function layoutSingle(nodeId) {
    const node = byId.get(nodeId);
    const current = baseScene(760);
    current.caption = '该节点没有可展开的下一层，说明见右侧。';
    current.nodes.push({
      node,
      x: 170,
      y: 90,
      w: 420,
      step: node.step || '节点',
      target: null
    });
    current.height = 300;
    return current;
  }

  // ---------- 交叉断口：竖线跨横线处抬一个小桥，区分“相交”与“相连” ----------

  function segmentList(points) {
    const list = [];
    for (let index = 1; index < points.length; index += 1) {
      const [x1, y1] = points[index - 1];
      const [x2, y2] = points[index];
      list.push({ at: index - 1, x1, y1, x2, y2, horizontal: Math.abs(y1 - y2) < 1 });
    }
    return list;
  }

  function collectHops(sceneEdges) {
    const segments = sceneEdges.map(edge => segmentList(edge.points));
    const hops = segments.map(() => new Map());
    for (let i = 0; i < segments.length; i += 1) {
      for (let j = i + 1; j < segments.length; j += 1) {
        for (const first of segments[i]) {
          for (const second of segments[j]) {
            if (first.horizontal === second.horizontal) continue;
            const horizontal = first.horizontal ? first : second;
            const vertical = first.horizontal ? second : first;
            // 断口只能画在竖线所属的那条边上，横线保持连续，才不会被误读成“相连”。
            const ownerIndex = first.horizontal ? j : i;
            // 横线上留 4px 余量（避免在拐点处起桥），竖线上留 12px 余量（避免在端点附近起桥）。
            const lowX = Math.min(horizontal.x1, horizontal.x2) + 4;
            const highX = Math.max(horizontal.x1, horizontal.x2) - 4;
            const lowY = Math.min(vertical.y1, vertical.y2) + 12;
            const highY = Math.max(vertical.y1, vertical.y2) - 12;
            if (vertical.x1 <= lowX || vertical.x1 >= highX) continue;
            if (horizontal.y1 <= lowY || horizontal.y1 >= highY) continue;
            const bucket = hops[ownerIndex].get(vertical.at) || [];
            if (!bucket.includes(horizontal.y1)) bucket.push(horizontal.y1);
            hops[ownerIndex].set(vertical.at, bucket);
          }
        }
      }
    }
    return hops;
  }

  function pathData(points, hopMap) {
    let d = `M${points[0][0]} ${points[0][1]}`;
    const gap = 5;
    let drawn = 0;
    for (let index = 1; index < points.length; index += 1) {
      const [x1, y1] = points[index - 1];
      const [x2, y2] = points[index];
      const stops = ((hopMap && hopMap.get(index - 1)) || []).slice().sort((a, b) => a - b);
      const horizontal = Math.abs(y1 - y2) < 1;
      const low = horizontal ? Math.min(x1, x2) : Math.min(y1, y2);
      const high = horizontal ? Math.max(x1, x2) : Math.max(y1, y2);
      // 断口必须整段落在线上，贴端点的交叉不再断，避免把线剪出毛刺。
      const usable = stops.filter(stop => stop - gap - 1 > low && stop + gap + 1 < high);
      if (horizontal) {
        const dir = x2 > x1 ? 1 : -1;
        for (const stop of usable) {
          // 先画到断口一侧，再用 M 起笔续画另一侧：中间这段不落笔，才不会被看成相连。
          d += ` L${stop - gap * dir} ${y1} M${stop + gap * dir} ${y1}`;
          drawn += 1;
        }
      } else {
        const dir = y2 > y1 ? 1 : -1;
        for (const stop of usable) {
          d += ` L${x1} ${stop - gap * dir} M${x1} ${stop + gap * dir}`;
          drawn += 1;
        }
      }
      d += ` L${x2} ${y2}`;
    }
    return { d, hops: drawn };
  }

  // ---------- 标签：候选点 + 偏移搜索，避开卡片、出口提示与其他标签 ----------

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
    const list = [];
    const seen = new Set();
    const push = candidate => {
      const key = [Math.round(candidate.x), Math.round(candidate.y), candidate.anchor].join('|');
      if (seen.has(key)) return;
      seen.add(key);
      list.push(candidate);
    };
    const segments = [];
    for (let index = 1; index < edge.points.length; index += 1) {
      const [x1, y1] = edge.points[index - 1];
      const [x2, y2] = edge.points[index];
      const length = Math.abs(x2 - x1) + Math.abs(y2 - y1);
      if (length >= 30) {
        segments.push({ x1, y1, x2, y2, length, last: index === edge.points.length - 1 });
      }
    }
    // 贴近目标的那一段优先，标签才不会飘到长车道中部、失去归属。
    segments.sort((a, b) => (Number(b.last) - Number(a.last)) || (b.length - a.length));
    for (const segment of segments) {
      if (Math.abs(segment.y1 - segment.y2) < 1) {
        const mid = (segment.x1 + segment.x2) / 2;
        push({ x: mid, y: segment.y1 - 8, anchor: 'middle' });
        push({ x: mid, y: segment.y1 + 15, anchor: 'middle' });
        push({ x: segment.x1 + 10, y: segment.y1 - 8, anchor: 'start' });
      } else {
        const mid = (segment.y1 + segment.y2) / 2;
        push({ x: segment.x1 + 8, y: mid, anchor: 'start' });
        push({ x: segment.x1 - 8, y: mid, anchor: 'end' });
      }
    }
    return list;
  }

  function intersects(a, b) {
    return a.x < b.x + b.w && b.x < a.x + a.w
      && a.y < b.y + b.h && b.y < a.y + a.h;
  }

  function layoutEdgeLabels(boxes) {
    const placed = [];
    // 标签也不能压在别的连线上：把所有线段收成细长框，供打分时避让。
    const lineBoxes = [];
    for (const edge of edges) {
      for (let index = 1; index < edge.points.length; index += 1) {
        const [x1, y1] = edge.points[index - 1];
        const [x2, y2] = edge.points[index];
        lineBoxes.push({
          edge,
          x: Math.min(x1, x2) - 2,
          y: Math.min(y1, y2) - 2,
          w: Math.abs(x2 - x1) + 4,
          h: Math.abs(y2 - y1) + 4
        });
      }
    }
    for (const edge of edges) {
      if (!edge.label) continue;
      const text = document.createElementNS(NS, 'text');
      text.setAttribute('class', 'edge-label');
      text.setAttribute('data-edge', String(edges.indexOf(edge)));
      text.textContent = edge.label;
      edgeLayer.append(text);
      let best = null;
      let bestCost = Infinity;
      const candidates = labelCandidates(edge);
      for (let rank = 0; rank < candidates.length; rank += 1) {
        const candidate = candidates[rank];
        text.setAttribute('x', candidate.x);
        text.setAttribute('y', candidate.y);
        text.style.textAnchor = candidate.anchor;
        const raw = text.getBBox();
        const base = { x: raw.x, y: raw.y, w: raw.width, h: raw.height };
        for (const [dx, dy] of LABEL_NUDGES) {
          const padded = { x: base.x + dx - 3, y: base.y + dy - 2, w: base.w + 6, h: base.h + 4 };
          const outside = padded.x < 1 || padded.y < 1
            || padded.x + padded.w > scene.width - 1 || padded.y + padded.h > scene.height - 1;
          const hitNode = boxes.some(item => intersects(padded, item));
          const hitLabel = placed.some(item => intersects(padded, item));
          const hitLine = lineBoxes.some(item => item.edge !== edge && intersects(padded, item));
          const cost = (outside ? 1e9 : 0) + (hitNode ? 1e6 : 0) + (hitLine ? 8e4 : 0)
            + (hitLabel ? 2e5 : 0)
            + rank * 3 + Math.abs(dx) + Math.abs(dy);
          if (cost < bestCost) {
            bestCost = cost;
            best = { x: candidate.x + dx, y: candidate.y + dy, anchor: candidate.anchor, box: padded };
          }
        }
        if (bestCost < 4) break;
      }
      if (!best) continue;
      text.setAttribute('x', best.x);
      text.setAttribute('y', best.y);
      text.style.textAnchor = best.anchor;
      placed.push(best.box);
      edge.labelEl = text;
    }
  }

  // ---------- 渲染 ----------

  function buildNode(item) {
    const node = item.node;
    const control = document.createElement(item.target ? 'a' : 'article');
    control.id = node.id;
    control.className = 'node'
      + (node.kind ? ' ' + node.kind : '')
      + (item.target ? ' linked' : ' static');
    control.style.left = item.x + 'px';
    control.style.top = item.y + 'px';
    control.style.width = item.w + 'px';
    control.style.minHeight = NODE_H + 'px';
    control.setAttribute('data-active', 'false');
    control.setAttribute('aria-label', `${item.step} ${node.title}`);
    if (item.target) {
      control.setAttribute('href', item.target);
      control.addEventListener('mouseenter', () => select(node.id, false));
      control.addEventListener('focus', () => select(node.id, false));
    }
    const step = document.createElement('span');
    step.className = 'step';
    step.textContent = item.step;
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
    if (item.target) {
      if (item.badge) {
        // 下沉入口写在步骤行，避免与标题抢位置，也让“可展开”一眼可见。
        const badge = document.createElement('span');
        badge.className = 'step-badge';
        badge.textContent = item.badge;
        step.append(' · ', badge);
      } else {
        const go = document.createElement('span');
        go.className = 'go';
        go.textContent = '打开 ↗';
        control.append(go);
      }
    } else {
      const more = document.createElement('button');
      more.type = 'button';
      more.className = 'node-more';
      more.textContent = node.kind === 'check' ? '判定要素' : '说明';
      more.setAttribute('aria-label', `查看 ${node.title} 的实现说明`);
      more.setAttribute('aria-controls', 'detail-title detail-description');
      more.addEventListener('click', () => select(node.id));
      control.append(more);
    }
    return control;
  }

  function renderScene(next) {
    scene = next;
    controls.clear();
    edges.length = 0;
    edgeLayer.replaceChildren();
    canvas.replaceChildren();
    stepOf.clear();
    canvas.style.width = scene.width + 'px';
    canvas.style.height = scene.height + 'px';

    const host = document.createElement('div');
    host.setAttribute('role', 'group');
    host.setAttribute('aria-label', '流程节点');

    for (const item of scene.nodes) {
      const control = buildNode(item);
      controls.set(item.node.id, control);
      stepOf.set(item.node.id, item.step);
      host.append(control);
    }
    for (const pill of scene.pills) {
      const element = document.createElement('span');
      element.className = pill.kind === 'entry' ? 'entry-pill' : 'exit-pill';
      element.style.left = pill.x + 'px';
      element.style.top = pill.y + 'px';
      element.style.width = pill.w + 'px';
      element.style.height = pill.h + 'px';
      element.textContent = pill.text;
      host.append(element);
    }

    const hopMap = collectHops(scene.edges);
    scene.edges.forEach((edge, index) => {
      const path = document.createElementNS(NS, 'path');
      const drawn = pathData(edge.points, hopMap[index]);
      path.setAttribute('d', drawn.d);
      path.setAttribute('data-hops', String(drawn.hops));
      path.setAttribute('data-from', edge.from);
      path.setAttribute('data-to', edge.to);
      path.setAttribute('class', 'edge' + (edge.dashed ? ' return' : ''));
      edgeLayer.append(path);
      edges.push({
        from: edge.from,
        to: edge.to,
        path,
        points: edge.points,
        label: edge.label,
        dashed: !!edge.dashed
      });
    });

    canvas.append(svg, host);

    const boxes = [];
    for (const item of scene.nodes) {
      const control = controls.get(item.node.id);
      boxes.push({
        x: item.x - 4,
        y: item.y - 4,
        w: item.w + 8,
        h: (control ? control.offsetHeight : NODE_H) + 8
      });
    }
    for (const pill of scene.pills) {
      boxes.push({ x: pill.x - 3, y: pill.y - 3, w: pill.w + 6, h: pill.h + 6 });
    }
    layoutEdgeLabels(boxes);
    fitCanvas();
  }

  function fitCanvas() {
    if (!scene) return;
    const scale = Math.max(.6, Math.min(1, viewport.clientWidth / scene.width));
    canvas.style.transform = `scale(${scale})`;
    wrap.style.width = scene.width * scale + 'px';
    wrap.style.height = scene.height * scale + 'px';
  }

  // ---------- 说明面板 ----------

  function select(id) {
    const node = byId.get(id);
    if (!node) return;
    for (const [key, control] of controls) {
      control.setAttribute('data-active', String(key === id));
    }
    for (const edge of edges) {
      const active = edge.from === id || edge.to === id;
      edge.path.setAttribute('class', 'edge'
        + (edge.dashed ? ' return' : '')
        + (active ? ' active' : ''));
      if (edge.labelEl) edge.labelEl.classList.toggle('active', active);
    }
    document.querySelector('#detail-step').textContent = stepOf.get(id) || stepLabel(node, 0);
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
    renderPanelLinks(node);
    document.querySelector('.details').scrollTop = 0;
  }

  function renderPanelLinks(node) {
    const box = document.querySelector('#detail-branches');
    box.replaceChildren();
    const kids = childrenOf(node.id);
    if (kids.length) {
      const drill = document.createElement('a');
      if (role === 'branch') {
        drill.href = `#${[...currentPath, node.id].join('/')}`;
        drill.textContent = `展开下一层：${node.title} 的 ${kids.length} 条子支线 →`;
      } else {
        drill.href = `${detailsHref}#${node.id}`;
        drill.textContent = `展开下一层：${node.title} 的 ${kids.length} 条支线 →`;
      }
      box.append(drill);
    }
    for (const link of node.links || []) {
      if (!link.href || link.href.startsWith('#')) continue;
      const anchor = document.createElement('a');
      anchor.href = link.href;
      anchor.textContent = link.label;
      box.append(anchor);
    }
    if (role === 'branch' && currentPath.length > 1) {
      const up = document.createElement('a');
      up.href = `#${currentPath.slice(0, -1).join('/')}`;
      up.textContent = '↑ 返回上一层';
      box.append(up);
    }
    box.hidden = box.childElementCount === 0;
    box.parentElement.hidden = box.hidden;
  }

  // ---------- 面包屑：只保留一行位置 ----------

  function renderBreadcrumb(path) {
    const nav = document.querySelector('.breadcrumb');
    if (!nav) return;
    const parts = [{ label: '全站主流程', href: role === 'root' ? null : 'index.html' }];
    if (role !== 'root' && feature) {
      parts.push({
        label: feature.name,
        href: role === 'steps' ? null : feature.href
      });
    }
    path.forEach((id, index) => {
      const node = byId.get(id);
      if (!node) return;
      const isLast = index === path.length - 1;
      parts.push({
        label: node.title,
        href: isLast ? null : `#${path.slice(0, index + 1).join('/')}`
      });
    });
    nav.replaceChildren(...parts.flatMap((part, index) => {
      const nodes = [];
      if (index) nodes.push(document.createTextNode(' / '));
      if (part.href) {
        const link = document.createElement('a');
        link.href = part.href;
        link.textContent = part.label;
        nodes.push(link);
      } else {
        const current = document.createElement('span');
        current.setAttribute('aria-current', 'page');
        current.textContent = part.label;
        nodes.push(current);
      }
      return nodes;
    }));
  }

  function renderModuleNav() {
    const nav = document.querySelector('nav[data-module-nav]');
    if (!nav) return;
    nav.replaceChildren(...MODULES.map(item => {
      const link = document.createElement('a');
      link.href = item.href;
      link.textContent = `${item.no} ${item.name}`;
      if (item.href === pageName) link.setAttribute('aria-current', 'page');
      return link;
    }));
  }

  // ---------- 层级解析与入口 ----------

  // 目标可能是叶子：沿 attachTo 上溯到最近一个有子结构的祖先，叶子本身留给面板选中。
  function ancestorsOf(id) {
    const chain = [];
    const seen = new Set();
    let node = byId.get(id);
    while (node && !seen.has(node.id)) {
      seen.add(node.id);
      chain.unshift(node.id);
      node = node.attachTo ? byId.get(node.attachTo) : null;
    }
    return chain;
  }

  function levelFor(id) {
    const chain = ancestorsOf(id);
    let deepest = -1;
    chain.forEach((cid, index) => {
      if (hasChildren(cid)) deepest = index;
    });
    return { path: deepest >= 0 ? chain.slice(0, deepest + 1) : [], selected: id };
  }

  function render() {
    renderModuleNav();
    const caption = document.querySelector('#level-caption');

    if (role === 'root' || role === 'steps') {
      currentPath = [];
      renderBreadcrumb([]);
      if (caption) caption.hidden = true;
      renderScene(role === 'root' ? layoutRoot() : layoutSteps());
      // 从其他页面带 #节点 进来：根图全部节点都在场，步骤页只画主干，
      // 因此支线锚点要上溯到它所属的主干步骤再选中，不能选一个没有卡片的节点。
      const wanted = location.hash.replace(/^#/, '');
      const mainIds = new Set(mains.map(node => node.id));
      let pick = null;
      if (role === 'root') pick = byId.has(wanted) ? wanted : null;
      else if (mainIds.has(wanted)) pick = wanted;
      else if (wanted) {
        let cursor = byId.get(wanted);
        for (let guard = 0; cursor && guard < 12; guard += 1) {
          if (mainIds.has(cursor.id)) { pick = cursor.id; break; }
          cursor = byId.get(cursor.attachTo);
        }
      }
      select(pick || (mains[0] ? mains[0].id : null));
      return;
    }

    const raw = location.hash.replace(/^#/, '');
    const wanted = raw.split('/').filter(Boolean).pop() || '';
    let usePath = [];
    let selected = null;
    if (wanted && byId.has(wanted)) {
      const info = levelFor(wanted);
      usePath = info.path;
      selected = wanted;
    }
    if (!usePath.length) {
      if (selected) {
        currentPath = [];
        renderBreadcrumb([selected]);
        if (caption) {
          caption.hidden = false;
          caption.textContent = '这一层只显示被请求的节点本身：它没有可展开的支线。';
        }
        renderScene(layoutSingle(selected));
        select(selected);
        return;
      }
      const firstParent = mains.find(node => hasChildren(node.id));
      usePath = firstParent ? [firstParent.id] : [];
    }
    const parentId = usePath[usePath.length - 1];
    if (!parentId) {
      renderScene(baseScene(760));
      return;
    }
    if (!selected) {
      const kids = childrenOf(parentId);
      selected = kids[0] ? kids[0].id : parentId;
    }
    currentPath = usePath;
    renderBreadcrumb(usePath);
    if (caption) {
      const parent = byId.get(parentId);
      caption.hidden = false;
      caption.textContent = `当前层：${parent.title}，${childrenOf(parentId).length} 条支线；只展示这一层，继续下沉请点带箭头的支线。`;
    }
    renderScene(layoutBranch(usePath));
    select(byId.has(selected) ? selected : parentId);
  }

  render();
  window.addEventListener('hashchange', render);
  new ResizeObserver(() => fitCanvas()).observe(viewport);
})();
