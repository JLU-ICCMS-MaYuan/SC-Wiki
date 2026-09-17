// 使用实际编辑页复现关闭后的滚动；所有接口隔离，不访问真实论文数据。
import assert from 'node:assert/strict'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright')
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox']})
const failures=[]
try {
  for(const role of ['admin','superadmin']) {
    const context=await browser.newContext({viewport:{width:1440,height:900}})
    const user={id:7,username:'fixture',role,is_admin:true,is_superadmin:role==='superadmin',is_approved:true,is_email_verified:true,account_status:'active'}
    await context.addInitScript(user=>{
      localStorage.setItem('auth_token','fixture-only');localStorage.setItem('auth_user',JSON.stringify(user));localStorage.setItem('sc-wiki.language','zh')
    },user)
    let draft, version=1, requests=[], pageLoads=0
    let states=Array.from({length:5},(_,i)=>({state_key:`state-${i}`,material_name:`样品 ${i+1}`,material:'Sn',state_kind:'experimental',material_dimensionality:'three_dimensional',crystal_system:'tetragonal',element_count:1,pressure_value_gpa:1,property_modules:[],structures:[],structure_families:[]}))
    const detail={id:990103,title:'隔离核对关闭验收',year:2026,authors:[],journal:'Test',paper_type:'experimental',superconductor_kind:'conventional',review_status:'pending',material_families:[{id:8,name:'单质超导体',status:'confirmed'}],key_properties:[]}
    const record=()=>({key:'pressure',item_key:'pressure',state_key:'state-4',field:'material_states[4].pressure_value_gpa',label:'末尾压强',current_value:1,status:'uncertain',reason:'需确认',evidences:[],...(draft?{proposal_draft:draft}:{})})
    await context.route('**/api/**',async route=>{
      const req=route.request(),path=new URL(req.url()).pathname
      requests.push({path,method:req.method()})
      const json=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)})
      if(path==='/api/auth/me')return json({user})
      if(path==='/api/admin/papers/990103')return json({...detail,material_states:states})
      if(path.endsWith('/review-artifact'))return json({data:{}})
      if(path==='/api/classification-catalogs')return json({material_families:[{id:8,name:'单质超导体'}],structure_families:[],material_dimensionalities:[]})
      if(path==='/api/rag/space-groups')return json({space_groups:[]})
      if(path==='/api/rag/llm/current')return json({})
      if(path.endsWith('/preflight'))return json({version:`v${version}`,needs_check:true,records:[record()]})
      if(path.endsWith('/scientific-draft')){states=req.postDataJSON().material_states;return json({ok:true,data:{unchanged:true}})}
      if(path.endsWith('/proposals')) {
        draft=req.postDataJSON();assert.equal(draft.expected_version,`v${version}`);return json({draft})
      }
      assert(!path.endsWith('/jobs')&&!path.endsWith('/review'))
      return json({items:[],total:0})
    })
    const page=await context.newPage(),errors=[]
    page.on('pageerror',e=>errors.push(e.message))
    page.on('framenavigated',frame=>{if(frame===page.mainFrame())pageLoads++})
    await page.goto(`${process.env.FRONTEND_URL||'http://127.0.0.1:5173'}/admin/papers/990103/edit`)
    await page.getByRole('button',{name:'全部展开',exact:true}).click()
    const input=page.locator('[data-state-key="state-4"]').getByLabel('压强 (GPa)',{exact:true})
    await input.waitFor()
    await page.waitForTimeout(500)
    await input.evaluate(el=>el.scrollIntoView({block:'center'}))
    await page.waitForTimeout(500)
    const label=page.getByRole('button',{name:'压强 (GPa)',exact:true})
    const initialLoads=pageLoads
    const position=()=>input.evaluate(el=>({top:el.getBoundingClientRect().top,scroll:window.scrollY}))
    const stable=async(before,action)=>{
      // 等待关闭动画、旧实现的 300ms 焦点定时器及后续布局帧。
      await page.waitForTimeout(450)
      const after=await position()
      if(Math.abs(before.top-after.top)>3)failures.push({role,action,before,after})
      assert.equal(pageLoads,initialLoads,'不应刷新或重新导航')
    }
    // 手动关闭入口：遮罩、Escape、关闭按钮、返回修改。
    for(const action of ['backdrop','escape','close','back']) {
      const before=await position()
      await label.click()
      if(action==='backdrop')await page.locator('.MuiDrawer-root > .MuiBackdrop-root').click({position:{x:10,y:450}})
      if(action==='escape')await page.keyboard.press('Escape')
      if(action==='close')await page.getByLabel('关闭来源详情').click()
      if(action==='back')await page.getByRole('button',{name:'返回修改记录',exact:true}).click()
      await page.getByRole('dialog').waitFor({state:'detached'})
      await stable(before,action)
    }
    const before=await position()
    await label.click()
    await page.getByLabel('人工核对理由').fill('按原始实验记录确认')
    await input.evaluate(el=>{
      window.drawerPositions=[];window.trackDrawerPosition=true
      const sample=()=>{if(!window.trackDrawerPosition)return;window.drawerPositions.push(el.getBoundingClientRect().top);requestAnimationFrame(sample)}
      requestAnimationFrame(sample)
    })
    await page.getByRole('button',{name:'完成',exact:true}).click()
    await page.waitForFunction(()=>!!document.querySelector('button[data-evidence-key="pressure"]'))
    await page.waitForTimeout(450)
    const remained=await page.getByRole('dialog').count()
    if(remained){failures.push({role,action:'complete-stayed-open'});await page.getByLabel('关闭来源详情').click()}
    await stable(before,'complete')
    const positions=await page.evaluate(()=>{window.trackDrawerPosition=false;return window.drawerPositions})
    if(positions.some(top=>Math.abs(top-before.top)>3))failures.push({role,action:'complete-visible-jump',min:Math.min(...positions),max:Math.max(...positions)})
    assert.equal(draft.accepted,true)
    assert.deepEqual(errors,[])
    console.log(JSON.stringify({role,pageLoads,position:await position(),requests:requests.length,failures:failures.filter(f=>f.role===role)}))
    await context.close()
  }
  assert.deepEqual(failures,[])
} finally {await browser.close()}
