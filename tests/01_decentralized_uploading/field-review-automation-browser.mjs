// 四类真实页面，全部API为隔离夹具；不写业务数据、不启动真实模型任务。
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || "playwright");
import {fileURLToPath} from "node:url";
const root=fileURLToPath(new URL("../../",import.meta.url));
const output=process.env.OUTPUT_DIR || "/tmp";
await fs.mkdir(output,{recursive:true});
import fs from "node:fs/promises";
import assert from "node:assert/strict";
const definitions=JSON.parse(await fs.readFile(root+"backend/data/form_definitions.v1.json","utf8"));
const browser=await chromium.launch({headless:true,channel:"chrome"});
const results=[];
const draft={paper:{id:174,title:"Fixture CaH6",knowledge_graph_title:"Graph title",year:2012,paper_type:"review",authors:[],methodology:["DFT"],summary:"Summary",material_families:[],review_status:"pending",uploaded_by_user_id:8},material_states:[],structure_candidates:[]};
const records=[
 {key:"title",item_key:"title",field:"paper.title",label:"标题",current_value:"Fixture CaH6",required:true,status:"supported",reason:"原文一致",evidences:[]},
 {key:"graph",item_key:"graph",field:"paper.knowledge_graph_title",label:"图谱科学标题",current_value:"Graph title",required:true,status:"unchecked",pending_review:true,review_error:"TimeoutError",reason:"文档补查技术失败，输入已保留。",evidences:[]},
 {key:"summary",item_key:"summary",field:"paper.summary",label:"总结",current_value:"Summary",required:true,status:"uncertain",reason:"两个归纳候选仍存在歧义。",evidences:[]},
 {key:"method",item_key:"method",field:"paper.methodology",label:"研究方法",current_value:["DFT"],required:true,status:"unchecked",review_in_progress:true,reason:"",evidences:[]}
];
try{
for(const mode of ["upload","revision","admin","superadmin"]){
 const user={id:7,username:"isolated",role:mode==="superadmin"?"superadmin":mode==="admin"?"admin":"user",is_admin:mode==="admin"||mode==="superadmin",is_approved:true,is_email_verified:true,account_status:"active"};
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addInitScript(user=>{localStorage.setItem("auth_token","isolated");localStorage.setItem("auth_user",JSON.stringify(user));localStorage.setItem("sc-wiki.language","zh");},user);
 const requests=[],errors=[];
 await context.route("**/api/**",async route=>{
  const req=route.request(),url=new URL(req.url()),p=url.pathname;requests.push({method:req.method(),path:p});
  const json=body=>route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(body)});
  if(p==="/api/auth/me")return json({user});
  if(p==="/api/rag/llm/catalog")return json({data:{items:[]}});
  if(p==="/api/rag/llm/current")return json({data:{model:"fixture",provider_name:"isolated"}});
  if(p==="/api/form-definitions")return json(definitions);
  if(p.startsWith("/api/form-definitions/"))return json(definitions.find(d=>decodeURIComponent(p).includes(d.definition_key))||{});
  if(p==="/api/classification-catalogs")return json({material_families:[],structure_families:[],material_dimensionalities:[]});
  if(p==="/api/admin/papers/174")return json({...draft.paper,material_states:[]});
  if(p.endsWith("/draft-state"))return json({version:"v1",draft,staged:false});
  if(p.endsWith("/revision-draft"))return json({data:draft,revision_id:"fixture-revision",draft_version:1});
  if(p.endsWith("/draft"))return json({data:draft});
  if(p.endsWith("/summary")||p.endsWith("/preflight"))return json({version:"v1",records,needs_check:false});
  if(p.endsWith("/field-detail")){const record=records.find(r=>r.item_key===url.searchParams.get("item_key"));return json({record,review_token:"fixture",approval_state:"ready",source_state:"empty"});}
  if(p.includes("/manual/"))return json({data:{changed:false,reason:"",items:[]}});
  if(p.endsWith("/parsing"))return json({data:{status:"ready",stage:"ready",files:[],chunks:[],summary:{status:"ready",completed:1,total:1},next_poll_ms:null}});
  if(p.includes("/upload-tasks/")&&!p.endsWith("/upload-tasks"))return json({data:{task_id:"fixture",filename:"isolated.pdf",processing_status:"succeeded",stage:"ready",stage_index:5,stage_total:5}});
  return json({data:[],items:[],jobs:[],space_groups:[],total:0});
 });
 const page=await context.newPage();page.on("pageerror",e=>errors.push(e.stack || e.message));
 const path=mode==="upload"?"/upload/tasks/"+("173".padEnd(32,"0")):mode==="revision"?"/papers/174/revise":"/admin/papers/174/edit";
 await page.goto((process.env.FRONTEND_URL || "http://127.0.0.1:5173")+path);
 const field=page.locator('[data-evidence-caption]').filter({hasText:/图谱/}).first();
 try { await field.waitFor({timeout:10000}); } catch(e) {
 console.log("BROWSER_DIAG",mode,page.url(),(await page.locator("body").innerText()).slice(0,1000),errors);
 await page.screenshot({path:output+"/field-review-failure.png"}); throw e;
}
 assert.equal(await field.getAttribute("data-evidence-status"),"failed");
 assert.equal(await page.locator("[data-evidence-pending-navigation]").count(),0);
 await field.click();
 await page.getByRole("tab",{name:"来源核对"}).click();
 const summary=page.locator("[data-field-ai-reason]");
 await summary.getByText("文档补查技术失败，输入已保留。",{exact:true}).waitFor();
 assert.equal(await page.getByRole("button",{name:"大模型核对",exact:true}).isEnabled(),true);
 await page.screenshot({path:output+"/field-review-"+mode+".png"});
 assert.equal(requests.filter(r=>r.path.endsWith("/jobs")).length,0);
 assert.deepEqual(errors,[]);
 results.push({mode,failed_marker:true,sidebar_reason:true,independent_navigation:false,model_jobs:0});
 await context.close();
}
await fs.writeFile(output+"/field-review-browser.json",JSON.stringify(results,null,2));
console.log(JSON.stringify(results,null,2));
}finally{await browser.close();}
