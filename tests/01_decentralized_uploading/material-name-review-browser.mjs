// 当前编辑页面的真实输入事件；全部 API 使用隔离夹具，不写真实论文。
import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_PATH, args:['--no-sandbox']})
try {
  for (const role of ['admin','superadmin']) {
    const user = {id:7,username:'fixture',role,is_admin:true,is_superadmin:role==='superadmin',is_approved:true,is_email_verified:true,account_status:'active'}
    const context = await browser.newContext({viewport:{width:1440,height:1000}})
    await context.addInitScript(user => {
      localStorage.setItem('auth_token','fixture-only')
      localStorage.setItem('auth_user',JSON.stringify(user))
      localStorage.setItem('sc-wiki.language','zh')
    }, user)
    let version=1, fail=true, accepted, saves=[], forbidden=[], unexpected=[]
    let states=[{state_key:'tin',material_name:'Tin',material:'Sn',superconductor:{chemical_formula:'Sn'},state_kind:'experimental',material_dimensionality:'three_dimensional',crystal_system:'tetragonal',element_count:1,property_modules:[],structures:[],structure_families:[]}]
    let detail={id:990103,title:'隔离材料名人工确认验收',year:2026,authors:[],journal:'Test',paper_type:'experimental',superconductor_kind:'conventional',review_status:'pending',material_families:[{id:8,name:'单质超导体',status:'confirmed'}],key_properties:[]}
    const records=()=>['material','material_name'].filter(field=>states[0][field]).map(field=>({
      key:field,item_key:field,state_key:'tin',field:`material_states[0].${field}`,label:field==='material'?'化学式':'材料名',current_value:states[0][field],status:'uncertain',reason:'论文未提供明确化学式',evidences:[],stale:version>1,
      editable_fields:[{path:`material_states[0].${field}`,label:field==='material'?'化学式':'材料名',value:states[0][field],schema:{type:'string'}}],
      ...(accepted?.key===field?{proposal_draft:accepted}:{})
    }))
    await context.route('**/api/**', async route=>{
      const req=route.request(), path=new URL(req.url()).pathname
      const json=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)})
      if(path==='/api/auth/me')return json({user})
      if(path==='/api/admin/papers/990103') {
        if(req.method()==='PUT')detail={...detail,...req.postDataJSON()}
        return json({...detail,material_states:states})
      }
      if(path.endsWith('/review-artifact'))return json({data:{}})
      if(path==='/api/classification-catalogs')return json({material_families:[{id:8,name:'单质超导体'}],structure_families:[],material_dimensionalities:[]})
      if(path==='/api/rag/space-groups')return json({space_groups:[]})
      if(path==='/api/rag/llm/current')return json({})
      if(path==='/api/rag/evidence/preflight')return json({version:`v${version}`,records:records(),needs_check:true})
      if(path==='/api/rag/papers/990103/scientific-draft') {
        saves.push(req.postDataJSON())
        if(fail)return json({detail:'隔离保存失败'},500)
        states=req.postDataJSON().material_states;version++;accepted=undefined
        return json({ok:true,data:{revision_bumped:false}})
      }
      if(path==='/api/rag/evidence/proposals') {
        accepted=req.postDataJSON();assert.equal(accepted.expected_version,`v${version}`)
        assert.equal(accepted.key,'material_name')
        return json({draft:accepted})
      }
      if(path.endsWith('/jobs')||path.endsWith('/review'))forbidden.push(path)
      else if(!['/api/site-settings','/api/site-config','/api/news','/api/chart-groups'].includes(path))unexpected.push(path)
      return json({items:[],total:0})
    })
    const page=await context.newPage(), errors=[]
    page.on('pageerror',e=>errors.push(e.message))
    await page.goto(`${process.env.FRONTEND_URL||'http://127.0.0.1:5173'}/admin/papers/990103/edit`)
    const name=page.getByLabel('材料名',{exact:true}), formula=page.getByLabel('化学式',{exact:true})
    await name.waitFor()
    assert((await name.boundingBox()).y<=(await formula.boundingBox()).y)
    await formula.click();assert.equal(await page.getByRole('dialog').count(),0)
    await formula.press('ControlOrMeta+A');await formula.press('Backspace')
    await page.getByRole('button',{name:'化学式',exact:true}).click()
    const reason=page.getByLabel('人工核对理由')
    await reason.fill('原文未提供化学式，因此清空')
    await page.getByRole('button',{name:'完成',exact:true}).click()
    await page.getByText(/当前编辑尚未保存成功/).waitFor()
    assert.equal(await reason.inputValue(),'原文未提供化学式，因此清空')
    fail=false
    await page.getByRole('button',{name:'完成',exact:true}).click()
    await page.getByRole('dialog').waitFor({state:'detached'})
    assert.equal(states[0].material,'');assert.equal(states[0].material_name,'Tin');assert.equal(accepted,undefined)
    await page.getByRole('button',{name:'材料名',exact:true}).click()
    await reason.fill('原文明确使用 Tin 作为材料名')
    await page.getByRole('button',{name:'完成',exact:true}).click()
    await page.getByRole('dialog').waitFor({state:'detached'})
    assert.equal(accepted.accepted,true)
    await page.reload();await name.waitFor()
    assert.equal(await name.inputValue(),'Tin');assert.equal(await formula.inputValue(),'')
    await name.fill('')
    const count=saves.length
    await page.getByRole('button',{name:'保存修改',exact:true}).click()
    assert.equal(saves.length,count)
    await context.grantPermissions(['clipboard-read','clipboard-write'])
    await page.evaluate(()=>navigator.clipboard.writeText('Named sample'))
    await name.click();await name.press('ControlOrMeta+V')
    assert.equal(await name.inputValue(),'Named sample')
    await Promise.all([page.waitForResponse(r=>r.url().endsWith('/scientific-draft')),page.getByRole('button',{name:'保存修改',exact:true}).click()])
    await page.reload();await name.waitFor()
    assert.equal(await name.inputValue(),'Named sample');assert.equal(await formula.inputValue(),'')
    assert.deepEqual(forbidden,[]);assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[])
    console.log(JSON.stringify({role,saves:saves.length,result:'passed',modelAndApprovalRequests:forbidden.length}))
    await context.close()
  }
} finally { await browser.close() }
