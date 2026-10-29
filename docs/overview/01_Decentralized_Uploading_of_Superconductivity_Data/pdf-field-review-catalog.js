// 本地字段规则库：只读查阅源码事实，不请求模型或读取真实草稿。
(() => {
  'use strict';
  const data=window.SC_WIKI_FIELD_REVIEW_CATALOG;
  const host=document.querySelector('#field-catalog');
  if(!data||!host)return;
  const byId=new Map(data.fields.map(field=>[field.id,field]));
  const search=host.querySelector('#catalog-search'),group=host.querySelector('#catalog-group'),mode=host.querySelector('#catalog-mode');
  const list=host.querySelector('#catalog-list');
  let current=data.fields[0].id,composing=false;
  function text(tag,value){const node=document.createElement(tag);node.textContent=value;return node}
  function option(value,label){const node=text('option',label);node.value=value;return node}
  for(const key of [...new Set(data.fields.map(f=>f.group))])group.append(option(key,key));
  for(const [key,profile] of Object.entries(data.profiles))mode.append(option(key,profile.label));
  const ns='http://www.w3.org/2000/svg';
  function svg(tag,attrs,value){const n=document.createElementNS(ns,tag);for(const[k,v]of Object.entries(attrs||{}))n.setAttribute(k,v);if(value!==undefined)n.textContent=value;return n}
  function graph(field,profile){
    const chart=svg('svg',{viewBox:'0 0 840 174',role:'img','aria-label':field.label+'的处理路径'});
    const defs=svg('defs'),marker=svg('marker',{id:'catalog-arrow',markerWidth:8,markerHeight:8,refX:7,refY:4,orient:'auto'});marker.append(svg('path',{d:'M0 0 L8 4 L0 8',fill:'#8197a7'}));defs.append(marker);chart.append(defs);
    const labels=field.flow||profile.flow;
    for(let i=0;i<5;i++){
      const x=8+i*169,y=20,w=148,h=70;
      if(i<4)chart.append(svg('path',{d:`M${x+w} ${y+35} L${x+166} ${y+35}`,stroke:'#8197a7','marker-end':'url(#catalog-arrow)'}));
      const shape=i===2?svg('polygon',{points:`${x+74},${y-8} ${x+w},${y+35} ${x+74},${y+78} ${x},${y+35}`,class:'gate'}):svg('rect',{x,y,width:w,height:h,rx:8,class:i===4?'result':'box'});
      chart.append(shape,svg('text',{x:x+74,y:y+31},labels[i][0]),svg('text',{x:x+74,y:y+49,class:'caption'},labels[i][1]));
    }
    chart.append(svg('path',{d:'M420 98 L420 127 L585 127',fill:'none',stroke:'#b0936b','marker-end':'url(#catalog-arrow)'}),svg('text',{x:414,y:151,class:'caption'},'不满足时：'+field.failureRoute));
    host.querySelector('#catalog-graph').replaceChildren(chart);
  }
  function fillList(id,values){host.querySelector('#'+id).replaceChildren(...values.map(v=>text('li',v)))}
  function show(id,update=true){
    const field=byId.get(id);if(!field)return;
    current=id;const profile=data.profiles[field.mode];
    host.querySelector('#catalog-field-title').textContent=field.label;
    host.querySelector('#catalog-field-key').textContent=field.path;
    host.querySelector('#catalog-field-badges').replaceChildren(...[field.group,profile.label,field.scope].map(v=>text('span',v)));
    host.querySelector('#catalog-read').textContent=field.read;
    fillList('catalog-checks',field.checks);
    host.querySelector('#catalog-model-description').textContent=field.model||profile.model;
    host.querySelector('#catalog-candidate').textContent=field.candidate||profile.candidate;
    host.querySelector('#catalog-required').textContent=field.required||profile.required;
    fillList('catalog-dependencies',field.dependencies);
    fillList('catalog-failures',field.failures);
    host.querySelector('#catalog-error-codes').textContent='可能关联的状态 / 错误：'+field.errorCodes.join(' · ');
    fillList('catalog-fixes',field.fixes);
    const refs=host.querySelector('#catalog-source-refs');
    refs.replaceChildren(...field.sources.map(source=>text('code',source.path+':'+source.line+' · '+source.symbol)));
    host.querySelector('#catalog-example').textContent=field.example;
    graph(field,profile);
    for(const button of list.querySelectorAll('button'))button.setAttribute('aria-pressed',String(button.dataset.fieldId===id));
    if(update)history.replaceState(null,'','#field='+encodeURIComponent(id));
  }
  function filter(){
    const query=search.value.trim().toLocaleLowerCase();
    const terms=query.split(/\s+/).filter(Boolean);
    const filtered=data.fields.filter(f=>(!group.value||f.group===group.value)&&(!mode.value||f.mode===mode.value)&&terms.every(t=>JSON.stringify(f).toLocaleLowerCase().includes(t)));
    const fragment=document.createDocumentFragment();
    for(const field of filtered){const button=document.createElement('button');button.type='button';button.dataset.fieldId=field.id;button.setAttribute('aria-pressed',String(field.id===current));button.setAttribute('aria-controls','catalog-field-title');button.append(text('strong',field.label),text('small',field.path));button.addEventListener('click',()=>show(field.id));fragment.append(button)}
    if(!filtered.length)fragment.append(text('p','没有匹配项。可搜索字段键、中文名称、报错原因或清空筛选。'));
    list.replaceChildren(fragment);
    host.querySelector('#catalog-count').textContent=`显示 ${filtered.length} / ${data.fields.length} 项字段与模板。空白或尚未实例化的字段不代表当前论文有问题。`;
  }
  search.addEventListener('compositionstart',()=>{composing=true});search.addEventListener('compositionend',()=>{composing=false;filter()});search.addEventListener('input',()=>{if(!composing)filter()});group.addEventListener('change',filter);mode.addEventListener('change',filter);
  host.querySelector('#catalog-reset').addEventListener('click',()=>{search.value='';group.value='';mode.value='';filter();search.focus()});
  function restore(){if(location.hash.startsWith('#field=')){let id;try{id=decodeURIComponent(location.hash.slice(7))}catch{return}if(byId.has(id))show(id,false)}}
  filter();show(current,false);restore();window.addEventListener('hashchange',restore);
  host.querySelector('#catalog-version').textContent=`规则快照：${data.date} · 源码 ${data.revision.slice(0,8)} · 本机已发布定义 ${data.definitions.length} 项。收录 ${data.fields.length} 项；开放扩展按模板覆盖，不冒称枚举所有未来自定义字段。`;
})();
