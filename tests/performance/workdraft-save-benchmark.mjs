// #186：只测量，保留保存器算法；不请求真实服务或模型。
import { readFile, writeFile, mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'
import { performance } from 'node:perf_hooks'
import { makeWorkdraft } from './workdraft-fixture.mjs'
const root = fileURLToPath(new URL('../../', import.meta.url))
const { buildSync } = await import(root + 'frontend/node_modules/esbuild/lib/main.js')
const file = process.env.WORKDRAFT_SAVER_SOURCE || root + 'frontend/src/lib/fieldDrafts.ts'
const source = await readFile(file, 'utf8')
if (!source.includes("import { api } from './api'")) throw new Error('保存器API导入已变化，不能悄悄跳过测量')
const temporary = await mkdtemp(join(tmpdir(), 'scwiki-workdraft-perf-'))
let gets = 0, writes = 0
globalThis.__perfApi = {
  get: async () => { gets++; return { version: 'isolated' } },
  patch: async () => { writes++; return { changed: true, version: 'isolated-next' } },
}
const measurements = []
const percentile = (values, q) => values.slice().sort((a,b) => a-b)[Math.min(values.length-1, Math.floor(values.length*q))]
try {
  const result = buildSync({ stdin: { contents: source.replace("import { api } from './api'", 'const api = globalThis.__perfApi'),
    resolveDir: root + 'frontend/src/lib', loader: 'ts' }, bundle: true, platform: 'node', format: 'esm', write: false })
  const entry = join(temporary, 'saver.mjs')
  await writeFile(entry, result.outputFiles[0].text)
  const module = await import('file://' + entry)
  for (const count of [5,40,100]) {
    const draft = makeWorkdraft(count)
    const encoded = JSON.stringify(draft)
    for (const mode of ['single_field','whole_save','autosave','helper_no_change']) {
      const elapsed = [], clone = [], compare = [], serialize = [], requestCounts = []
      for (let iteration = 0; iteration < 8; iteration++) {
        const current = JSON.parse(encoded)
        current.paper.knowledge_graph_title = mode === 'helper_no_change' ? draft.paper.knowledge_graph_title : 'Updated benchmark'
        const t0 = performance.now(); const copied = JSON.parse(JSON.stringify(current)); clone.push(performance.now()-t0)
        const t1 = performance.now(); const changes = module.fieldChanges(draft, copied); compare.push(performance.now()-t1)
        const t2 = performance.now(); const body = JSON.stringify(changes); serialize.push(performance.now()-t2)
        if (!body) throw new Error('序列化失败')
        const saver = module.createFieldDraftSaver({ target: 'upload', target_id: 'isolated-186' })
        saver.initialize(draft)
        gets = 0; writes = 0
        const start = performance.now()
        if (mode === 'single_field') await saver.saveField(current, 'paper.knowledge_graph_title')
        else await saver.save(current)
        elapsed.push(performance.now()-start); requestCounts.push({ gets, writes })
      }
      measurements.push({ states: count, points: count*6, bytes: Buffer.byteLength(encoded), fixture_sha256: createHash('sha256').update(encoded).digest('hex'),
        mode, repeats: elapsed.length, total_mean_ms: elapsed.reduce((a,b)=>a+b,0)/elapsed.length, total_p95_ms: percentile(elapsed,.95),
        clone_mean_ms: clone.reduce((a,b)=>a+b,0)/clone.length, comparison_mean_ms: compare.reduce((a,b)=>a+b,0)/compare.length,
        changes_serialization_mean_ms: serialize.reduce((a,b)=>a+b,0)/serialize.length, requestCounts })
    }
  }
  const report = { source: file, source_sha256: createHash('sha256').update(source).digest('hex'), node: process.version,
    date: new Date().toISOString(), boundaries: ['真实保存器CPU路径，API为隔离立即响应替身；不是生产网络或数据库耗时',
      'autosave测相同保存处理，不把5000ms等待计为CPU成本', 'helper_no_change不是UI无变化保存：原宿主可在dirty=false时直接返回',
      '输入延迟另用完整宿主浏览器测量，不能由这里的复制时间直接认定输入卡顿原因'], measurements }
  const output = process.env.WORKDRAFT_PERF_OUTPUT || join(temporary, 'results.json')
  await writeFile(output, JSON.stringify(report,null,2))
  console.log(JSON.stringify({ output, measurements: measurements.map(m=>({ states:m.states,mode:m.mode,bytes:m.bytes,total_mean_ms:m.total_mean_ms })) }))
} finally { await rm(temporary,{recursive:true,force:true}) }
