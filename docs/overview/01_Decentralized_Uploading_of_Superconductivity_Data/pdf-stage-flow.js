// 独立详情页共用只读绘图器；节点、判断和连线由各页面的 JSON 声明。
(() => {
  'use strict';
  const data = JSON.parse(document.querySelector('#flow-data').textContent);
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.querySelector('#flow-chart');
  const positions = {left:{x:24,w:250},main:{x:354,w:360},right:{x:804,w:270}};
  const nodes = new Map(data.nodes.map(node => [node.id, {...node, ...positions[node.column || 'main'], y:36+node.row*140, h:node.kind==='check'?104:84}]));
  const height = 160 + Math.max(...data.nodes.map(node => node.row))*140;
  svg.setAttribute('viewBox', `0 0 1100 ${height}`);
  function element(tag, attributes, text) {
    const node = document.createElementNS(ns, tag);
    for (const [key,value] of Object.entries(attributes || {})) node.setAttribute(key,value);
    if (text !== undefined) node.textContent=text;
    return node;
  }
  svg.append(element('rect',{x:338,y:18,width:392,height:height-35,rx:18,class:'lane'}));
  const defs = element('defs');
  for (const [id,color] of [['arrow','#8b9eac'],['active-arrow','#275d9f']]) {
    const marker=element('marker',{id,markerWidth:8,markerHeight:8,refX:7,refY:4,orient:'auto'});
    marker.append(element('path',{d:'M0 0 L8 4 L0 8',fill:color}));defs.append(marker);
  }
  svg.append(defs);
  const edgeLayer=element('g',{'aria-hidden':'true'}), nodeLayer=element('g');
  svg.append(edgeLayer,nodeLayer);
  function port(node,side) {
    return side==='top'?[node.x+node.w/2,node.y]:side==='bottom'?[node.x+node.w/2,node.y+node.h]:side==='left'?[node.x,node.y+node.h/2]:[node.x+node.w,node.y+node.h/2];
  }
  const paths=[];
  for (const edge of data.edges) {
    const from=nodes.get(edge.from),to=nodes.get(edge.to);
    const direction=Math.sign(to.x-from.x);
    const start=port(from,edge.fromSide||(direction>0?'right':direction<0?'left':'bottom'));
    const end=port(to,edge.toSide||(direction>0?'left':direction<0?'right':'top'));
    const middle=(start[0]+end[0])/2;
    const points=[start,...(edge.via|| (direction && start[1]!==end[1]?[[middle,start[1]],[middle,end[1]]]:[])),end];
    const path=element('path',{d:points.map(([x,y],i)=>`${i?'L':'M'}${x} ${y}`).join(' '),class:'edge','data-from':edge.from,'data-to':edge.to});
    edgeLayer.append(path);paths.push({edge,path});
    if (edge.label) {
      const [x,y]=edge.labelAt||[direction?middle:start[0]+39,(start[1]+end[1])/2-8];
      edgeLayer.append(element('text',{x,y,class:'edge-label'},edge.label));
    }
  }
  const controls=new Map();
  function select(id,writeHash=true) {
    const node=nodes.get(id);if(!node)return;
    for (const [key,control] of controls) {
      if (nodes.get(key).href) {
        if (key===id) control.setAttribute('aria-current','step');
        else control.removeAttribute('aria-current');
      } else control.setAttribute('aria-pressed',String(key===id));
    }
    for (const {edge,path} of paths) path.setAttribute('class','edge'+(edge.from===id||edge.to===id?' active':''));
    for (const [key,value] of Object.entries({title:node.title,owner:node.owner,description:node.description,code:node.code||'同一流程内的状态或控制分支'})) document.querySelector('#detail-'+key).textContent=value;
    document.querySelector('#detail-notes').replaceChildren(...(node.notes||[]).map(text=>{const item=document.createElement('li');item.textContent=text;return item}));
    const open=document.querySelector('#detail-open');
    if (open) {
      open.hidden=!node.href;
      if(node.href) { open.href=node.href;open.target='_blank';open.rel='noopener noreferrer'; }
      else open.removeAttribute('href');
    }
    if(writeHash) history.replaceState(null,'','#'+id);
  }
  for (const node of nodes.values()) {
    const control=element(node.href?'a':'g',{class:'node '+(node.kind||''),role:node.href?'link':'button',tabindex:0,'aria-label':node.title+(node.href?'：在新标签页查看详细程序流程':'：查看程序说明'),'data-node':node.id,
      ...(node.href?{href:node.href,target:'_blank',rel:'noopener noreferrer'}:{'aria-controls':'detail-title detail-description','aria-pressed':'false'})});
    const shape=node.kind==='check'
      ? element('polygon',{points:`${node.x+node.w/2},${node.y} ${node.x+node.w},${node.y+node.h/2} ${node.x+node.w/2},${node.y+node.h} ${node.x},${node.y+node.h/2}`,class:'shape'})
      : element('rect',{x:node.x,y:node.y,width:node.w,height:node.h,rx:node.kind==='result'||node.kind==='stop'?25:10,class:'shape'});
    control.append(shape,element('text',{x:node.x+node.w/2,y:node.y+node.h/2-6,class:'node-title'},node.title),element('text',{x:node.x+node.w/2,y:node.y+node.h/2+17,class:'node-summary'},node.summary));
    if(node.href) control.append(element('text',{x:node.x+node.w-12,y:node.y+15,class:'node-open'},'新标签页 ↗'));
    control.addEventListener('click',()=>select(node.id));
    if(!node.href) control.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();select(node.id)}});
    controls.set(node.id,control);nodeLayer.append(control);
  }
  function fromHash(){const id=location.hash.slice(1);select(nodes.has(id)?id:data.start,nodes.has(id)||!location.hash)}
  fromHash();window.addEventListener('hashchange',fromHash);
})();
