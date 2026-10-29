// 正式上传路由；真实模型输出作为只读输入，HTTP 写入全部在独立浏览器夹具中。
import assert from 'node:assert/strict'
import {readFile, writeFile, mkdir} from 'node:fs/promises'
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const original = JSON.parse(await readFile(process.env.FILLING_DRAFT, 'utf8'))
const definitions = JSON.parse(await readFile(new URL('../fixtures/issue176/form-definitions.json', import.meta.url), 'utf8'))
const output = process.env.FILLING_BROWSER_OUTPUT || '/tmp/scwiki176-browser'
await mkdir(output,{recursive:true})
const browser = await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH})
const errors=[], results=[]
try {
  for (const width of [1900,390]) {
    const state=structuredClone(original.material_states.find(s=>s.material==='CaH6' && s.pressure_value_gpa===150))
    const module=state.property_modules.find(m=>m.module_code==='superconductive_properties')
    const points=module.records
    assert.equal(points.length,2)
    // 两个额外方法仅用于 UI 行布局和自定义编辑，不作为论文真实结果。
    for (const method of ['allen_dynes','other']) {
      const r=structuredClone(points[0])
      r.record_key='fixture-'+method
      r.method_code=method;r.method_raw=method==='other'?'Fixture custom theory':null
      r.definition_key='record.superconductive_properties.predicted_tc.'+method
      r.payload.tc_group.method_key='fixture-'+method;r.payload.tc_group.point_key=r.record_key
      r.value_number=200;r.payload.parameters.mu_star=.12;r.is_representative=false
      points.push(r)
    }
    let draft={...structuredClone(original),material_states:[state],
      paper:{...original.paper,title:'Isolated multi-method UI verification',paper_type:'theoretical',year:2026,authors:[]}}
    let version=1,saves=0,models=0
    const user={id:7,username:'isolated',role:'user',is_approved:true,is_email_verified:true,account_status:'active'}
    const context=await browser.newContext({viewport:{width,height:1100}})
    await context.addInitScript(user=>{
      localStorage.setItem('auth_token','isolated');localStorage.setItem('auth_user',JSON.stringify(user))
      localStorage.setItem('sc-wiki.language','zh')
    },user)
    await context.route('**/api/**',async route=>{
      const req=route.request(),path=new URL(req.url()).pathname
      const json=body=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)})
      if(path==='/api/auth/me')return json({user})
      if(path==='/api/rag/llm/catalog')return json({data:{items:[]}})
      if(path==='/api/rag/llm/current')return json({data:{provider:'fixture',provider_name:'fixture',model:'isolated',source:'server'}})
      if(path.endsWith('/activity'))return json({ok:true})
      if(path==='/api/form-definitions')return json(definitions)
      if(path.startsWith('/api/form-definitions/'))return json(definitions.find(d=>path.includes(d.definition_key)))
      if(path==='/api/classification-catalogs')return json({material_families:[],structure_families:[],material_dimensionalities:[]})
      if(path.endsWith('/space-groups'))return json({space_groups:[]})
      if(path.endsWith('/summary'))return json({version:'v'+version,records:[],needs_check:false})
      if(path.endsWith('/draft-state'))return json({version:'v'+version,draft})
      if(path==='/api/rag/evidence/draft' && req.method()==='PATCH'){
        for(const change of req.postDataJSON().changes){
          let node=draft
          const walk=(n,key)=>typeof key==='object'?n.find(row=>Object.entries(key).every(([k,v])=>row[k]===v)):n[key]
          for(const key of change.path.slice(0,-1))node=walk(node,key)
          node[change.path.at(-1)]=change.value
        }
        saves++;version++;return json({changed:true,version:'v'+version})
      }
      if(path.endsWith('/draft'))return json({data:draft})
      if(path.endsWith('/parsing'))return json({data:{status:'ready',stage:'ready',files:[],chunks:[],summary:{status:'ready',completed:1,total:1}}})
      if(path==='/api/upload-tasks/'+'176'.padEnd(32,'0'))return json({data:{task_id:'176'.padEnd(32,'0'),filename:'isolated.pdf',stage:'ready',stage_index:5,stage_total:5,processing_status:'succeeded'}})
      if(/jobs|preflight|submit-check/.test(path)){models++;throw new Error('编辑不应发起模型')}
      if(req.method()!=='GET')throw new Error('Unexpected mutation: '+path)
      return json({data:[],items:[],jobs:[],total:0})
    })
    const page=await context.newPage()
    page.on('pageerror',e=>errors.push(e.stack || e.message))
    await page.goto((process.env.FRONTEND_URL || 'http://127.0.0.1:5173')+'/upload/tasks/'+'176'.padEnd(32,'0'))
    const expand=page.getByRole('button',{name:'全部展开',exact:true})
    await expand.first().waitFor({timeout:10000}).catch(async error => {
      await page.screenshot({path:output+'/failure.png',fullPage:true})
      console.error(await page.locator('body').innerText(), errors)
      throw error
    })
    await expand.first().click()
    const core=page.getByTestId('predicted-tc-core')
    await core.waitFor()
    assert.equal(await core.getByLabel('预测方法',{exact:true}).count(),3)
    assert.equal(await core.getByLabel('Tc',{exact:true}).count(),4)
    assert.equal(await core.getByText('超导转变温度 Tc',{exact:true}).count(),0)
    await core.getByLabel('具体方法名称').fill('User custom method')
    await Promise.all([
      page.waitForResponse(r=>r.url().endsWith('/evidence/draft') && r.request().method()==='PATCH'),
      page.getByRole('button',{name:'立即保存',exact:true}).click(),
    ])
    await page.reload()
    await expand.first().click()
    await core.getByLabel('具体方法名称').waitFor()
    assert.equal(await core.getByLabel('具体方法名称').inputValue(),'User custom method')
    await core.scrollIntoViewIfNeeded()
    await page.screenshot({path:output+'/form-'+width+'.png',fullPage:true})
    const lines=await core.locator('[data-testid="tc-method-line"]').evaluateAll(nodes=>nodes.map(node=>({
      width:node.clientWidth,scrollWidth:node.scrollWidth,
      inputCenters:[...node.querySelectorAll('input[aria-label],input')].map(el=>el.getBoundingClientRect().y+el.getBoundingClientRect().height/2)
    })))
    assert.equal(models,0);assert.ok(saves>=1)
    results.push({width,saves,models,lines})
    await context.close()
  }
  assert.deepEqual(errors,[])
  await writeFile(output+'/result.json',JSON.stringify({results,errors},null,2))
} finally {await browser.close()}
