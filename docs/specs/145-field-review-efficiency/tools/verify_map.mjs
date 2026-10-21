// 可视化校验：完整清单可选、修改/未修改分支可切换、窄屏无裁切；不连接业务API。
import assert from 'node:assert/strict'
import {mkdir,writeFile} from 'node:fs/promises'
import {pathToFileURL} from 'node:url'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright')
const preview=process.argv[2],out=process.argv[3]
assert(preview&&out,'需要预览HTML绝对路径及验证输出目录')
await mkdir(out,{recursive:true})
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH})
const report=[],errors=[]
try{
 const page=await browser.newPage();page.on('pageerror',e=>errors.push(e.message))
 await page.goto(pathToFileURL(preview).href)
 const iframe=await page.$('iframe'),frame=iframe?await iframe.contentFrame():page
 assert.equal(await frame.evaluate(()=>document.characterSet),'UTF-8')
 assert.equal(await frame.locator('.heading').textContent(),'每个字段，究竟核对了什么？')
 assert((await frame.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--foreground'))).trim())
 await frame.waitForSelector('[data-field] option',{state:'attached'})
 for(const width of [736,360]){
  await page.setViewportSize({width,height:1100});await page.waitForTimeout(250)
  const result=await frame.evaluate(()=>{
   const root=document.getElementById('field-review-audit-145'),svg=root.querySelector('svg')
   return {contentWidth:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth,
    units:JSON.parse(root.querySelector('[data-audit]').textContent).units.length,
    clipped:[...svg.querySelectorAll('text')].filter(t=>{const b=t.getBBox();return b.x<0||b.x+b.width>svg.viewBox.baseVal.width+1}).map(t=>t.textContent)}
  })
  assert.deepEqual(result.clipped,[]);assert(result.scrollWidth<=result.contentWidth+2)
  report.push({width,...result});await page.screenshot({path:out+'/map-'+width+'.png',fullPage:true})
 }
 const coverage=await frame.evaluate(()=>{
  const root=document.getElementById('field-review-audit-145'),g=root.querySelector('[data-group]'),f=root.querySelector('[data-field]')
  const ids=new Set();let entries=0
  for(const option of g.options){
   g.value=option.value;g.dispatchEvent(new Event('change'))
   for(const item of f.options){f.value=item.value;f.dispatchEvent(new Event('change'));ids.add(item.value);entries+=root.querySelector('[data-child]').options.length}
  }
  return {units:ids.size,entriesIncludingReadOnly:entries}
 })
 assert.equal(coverage.units,447);report.push(coverage)
 await frame.selectOption('[data-group]','计算条件')
 const id=await frame.evaluate(()=>JSON.parse(document.querySelector('[data-audit]').textContent).units.find(r=>r.condition?.stage==='sscha'&&r.condition?.parameter==='calculation_code'&&r.owner.includes('250.0')).id)
 await frame.selectOption('[data-field]',id);await frame.check('input[value="proposed"]')
 assert((await frame.locator('svg').textContent()).includes('科学值不写入'))
 const counts=await frame.locator('[data-counts]').textContent()
 assert(counts.includes('条件依据验证5'));assert(counts.includes('原文片段定位36'))
 report.push({interaction:'250 GPa SSCHA建议分支',counts})
 await frame.selectOption('[data-group]','电子性质')
 assert((await frame.locator('[data-child] option').count())>3)
 await frame.selectOption('[data-operation]','manual');await frame.check('input[value="current"]')
 assert((await frame.locator('svg').textContent()).includes('保存本项说明'))
 report.push({interaction:'N(EF)共享单元与人工说明流程',passed:true})
 assert.deepEqual(errors,[])
 await writeFile(out+'/visual-verification.json',JSON.stringify({report,errors},null,2))
 console.log(JSON.stringify({checks:report.length,errors}))
}finally{await browser.close()}
