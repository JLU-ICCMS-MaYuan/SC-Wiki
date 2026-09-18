// 真实页面与 Chromium 输入事件；所有 API 被隔离夹具接管，绝不写真实论文。
import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({ headless: true, ...(process.env.CHROMIUM_PATH ? {executablePath:process.env.CHROMIUM_PATH} : {}), args: ['--no-sandbox'] })
const fields = ['pressure_value_gpa','pressure_raw','pressure_unit_raw','pressure_min_gpa','pressure_max_gpa']
try {
  for (const role of ['admin','superadmin']) {
    const user = {id:7,username:'fixture-reviewer',email:'fixture@example.invalid',role,is_admin:true,is_superadmin:role==='superadmin',is_approved:true,is_email_verified:true,account_status:'active'}
    const context = await browser.newContext({ viewport:{width:1440,height:1000} })
    await context.addInitScript(user => {
      localStorage.setItem('auth_token','fixture-only')
      localStorage.setItem('auth_user',JSON.stringify(user))
      localStorage.setItem('sc-wiki.language','zh')
    }, user)
    let version = 1, draft, saves = [], forbidden = [], unexpected = []
    let states = [{id:11,state_key:'tin',superconductor:{chemical_formula:'Sn'},material:'Sn',state_kind:'experimental',material_dimensionality:'three_dimensional',crystal_system:'tetragonal',element_count:1,pressure_value_gpa:0.000101,pressure_raw:'0.000101',pressure_unit_raw:'GPa',pressure_min_gpa:0.0001,pressure_max_gpa:0.0002,property_modules:[],structures:[],structure_families:[]}]
    let detail = {id:990103,title:'隔离压强编辑验收',year:2026,authors:[],journal:'Test',paper_type:'experimental',superconductor_kind:'conventional',review_status:'pending',material_families:[{id:8,name:'单质超导体',status:'confirmed'}],key_properties:[]}
    const record = () => ({key:'pressure',item_key:'pressure',state_key:'tin',field:'material_states[0].pressure_value_gpa',label:'压力',current_value:states[0].pressure_value_gpa,status:'uncertain',reason:'旧压强的核对结果',evidences:[],provenance:{kind:'derived',verified:true},stale:version>1&&!draft,...(draft?{proposal_draft:draft}:{})})
    await context.route('**/api/**', async route => {
      const req = route.request(), path = new URL(req.url()).pathname
      const json = body => route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)})
      if (path === '/api/auth/me') return json({user})
      if (path === '/api/admin/papers/990103') {
        if (req.method() === 'PUT') detail = {...detail,...req.postDataJSON()}
        return json({...detail,material_states:states})
      }
      if (path.endsWith('/review-artifact')) return json({data:{}})
      if (path === '/api/classification-catalogs') return json({material_families:[{id:8,name:'单质超导体'}],structure_families:[],material_dimensionalities:[{value:'three_dimensional',name:'三维'},{value:'unknown',name:'未知'}]})
      if (path === '/api/rag/space-groups') return json({space_groups:[]})
      if (path === '/api/rag/llm/current') return json({})
      if (path === '/api/rag/evidence/preflight') return json({version:`v${version}`,needs_check:!draft,records:states[0].pressure_value_gpa==null?[]:[record()]})
      if (path === '/api/rag/papers/990103/scientific-draft') {
        const body = req.postDataJSON()
        saves.push(body); states = body.material_states; version++; draft=undefined
        return json({ok:true,data:{revision_bumped:false}})
      }
      if (path === '/api/rag/evidence/proposals') {
        const body = req.postDataJSON()
        assert.equal(body.expected_version,`v${version}`)
        draft=body
        return json({draft})
      }
      if (path.endsWith('/jobs') || path.endsWith('/review')) forbidden.push(path)
      else if (!['/api/site-settings','/api/site-config','/api/news','/api/chart-groups'].includes(path)) unexpected.push(path)
      return json({items:[],total:0})
    })
    const page = await context.newPage()
    const errors = []
    page.on('pageerror',error=>errors.push(error.message))
    await page.goto(`${process.env.FRONTEND_URL || 'http://127.0.0.1:5173'}/admin/papers/990103/edit`)
    const input = page.getByLabel('压强 (GPa)',{exact:true})
    await input.waitFor()
    const label = page.getByRole('button',{name:'压强 (GPa)',exact:true})
    await label.waitFor()
    assert.equal(await input.inputValue(),'0.000101')
    await input.click()
    assert.equal(await page.getByRole('dialog').count(),0)
    await input.press('ControlOrMeta+A')
    await input.pressSequentially('0.0025')
    assert.equal(await input.inputValue(),'0.0025')
    await label.click()
    const reason = page.getByLabel('人工核对理由')
    await reason.fill('按实验记录更正，保留论文原始压强')
    await page.getByRole('button',{name:'返回编辑当前值',exact:true}).click()
    await page.waitForFunction(() => document.activeElement?.closest('[data-issue-field]')?.getAttribute('data-issue-field') === 'material_states[0].pressure_value_gpa')
    await label.click()
    assert.equal(await reason.inputValue(),'按实验记录更正，保留论文原始压强')
    await page.getByRole('button',{name:'完成',exact:true}).click()
    await page.getByRole('dialog').waitFor({state:'detached'})
    assert.equal(saves[0].material_states[0].pressure_value_gpa,0.0025)
    assert.equal(saves[0].material_states[0].pressure_raw,'0.000101')
    assert.equal(draft.expected_version,'v2'); assert.equal(draft.accepted,true); assert.deepEqual(draft.values,{})
    await input.fill('1e-')
    await page.getByRole('button',{name:'保存修改',exact:true}).click()
    assert.equal(saves.length,1)
    // Clipboard 写入并按键粘贴，覆盖浏览器原生 paste/input。
    await context.grantPermissions(['clipboard-read','clipboard-write'])
    await page.evaluate(() => navigator.clipboard.writeText('0'))
    await input.click(); await input.press('ControlOrMeta+A'); await input.press('ControlOrMeta+V')
    assert.equal(await input.inputValue(),'0')
    await Promise.all([page.waitForResponse(response=>response.url().endsWith('/preflight')),page.getByRole('button',{name:'保存修改',exact:true}).click()])
    assert.equal(saves.at(-1).material_states[0].pressure_value_gpa,0)
    await input.click(); await input.press('ControlOrMeta+A'); await input.press('Backspace')
    assert.equal(await input.inputValue(),'')
    await page.getByRole('button',{name:'保存修改',exact:true}).click()
    await label.waitFor({state:'detached'})
    for (const field of fields) assert.equal(saves.at(-1).material_states[0][field],null)
    await page.reload(); await input.waitFor()
    assert.equal(await input.inputValue(),'')
    await page.getByText('原始压强、单位与范围',{exact:true}).click()
    for (const name of ['原始压强','原始压强单位','压强下限 (GPa)','压强上限 (GPa)']) assert.equal(await page.getByLabel(name,{exact:true}).inputValue(),'')
    assert.deepEqual(forbidden,[]); assert.deepEqual(errors,[])
    console.log(JSON.stringify({role,saves:saves.length,forbidden,unexpected:[...new Set(unexpected)],result:'passed'}))
    await context.close()
  }
} finally { await browser.close() }
